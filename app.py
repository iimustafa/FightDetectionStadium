import os
import cv2
import time
import tempfile
import logging
import uuid
import json
import threading
import re
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from google import genai
from ProcessVideo import process_video

# Setup logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-development")

# Configure application
app.config['UPLOAD_FOLDER'] = 'temp_videos'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 300MB max upload

# Make sure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Gemini API key
GEMINI_API_KEY =""
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set. Report generation will not work.")
else:
    try:
        # Test API key by initializing a client
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini API: {str(e)}")
        logger.warning("Report generation might not work properly")

# Store processing jobs
processing_jobs = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        flash('No file part')
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['video']
    
    if file.filename == '':
        flash('No selected file')
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        flash('Invalid file type')
        return jsonify({'error': 'Invalid file type'}), 400

    # Get parameters from form
    sequence_length = int(request.form.get('sequence_length', 40))
    threshold = float(request.form.get('threshold', 0.8))
    output_frame_rate = int(request.form.get('output_frame_rate', 30))

    # Create a job ID and save the file with a unique name
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    temp_dir = tempfile.mkdtemp(dir=app.config['UPLOAD_FOLDER'])
    video_path = os.path.join(temp_dir, filename)
    file.save(video_path)
    
    # Store job information
    processing_jobs[job_id] = {
        'status': 'processing',
        'video_path': video_path,
        'sequence_length': sequence_length,
        'threshold': threshold,
        'output_frame_rate': output_frame_rate,
        'start_time': time.time(),
        'results': None,
        'output_video': None,
        'report': None
    }
    
    # Start processing in a separate thread
    threading.Thread(target=process_video_job, args=(job_id,)).start()
    
    return jsonify({'job_id': job_id})

def process_video_job(job_id):
    job = processing_jobs[job_id]
    try:
        logger.info(f"Starting video processing for job {job_id}")
        output_video, json_response = process_video(
            job['video_path'], 
            job['sequence_length'],
            job['threshold'],
            job['output_frame_rate']
        )
        
        if output_video and json_response:
            job['status'] = 'completed'
            job['results'] = json_response
            job['output_video'] = output_video
            logger.info(f"Video processing completed for job {job_id}")
            
            # Always attempt to generate a report (it will warn if no API key)
            try:
                generate_report(job_id)
            except Exception as e:
                logger.error(f"Error generating report: {str(e)}")
                job['report'] = f"Error generating report: {str(e)}"
                # Don't let report generation failure fail the whole job
                # We'll still show the error message to the user
        else:
            job['status'] = 'failed'
            job['error'] = json_response.get('error', 'Unknown error')
            logger.error(f"Video processing failed for job {job_id}: {job['error']}")
    except Exception as e:
        logger.exception(f"Error processing video for job {job_id}")
        job['status'] = 'failed'
        job['error'] = str(e)

def generate_report(job_id):
    job = processing_jobs[job_id]

    # If no API key, fall back to warning text
    if not GEMINI_API_KEY:
        job['report'] = (
            "<h2>Report Unavailable</h2>"
            "<p>Report generation requires a Gemini API key. "
            "Please configure GEMINI_API_KEY environment variable.</p>"
        )
        logger.warning(
            f"Cannot generate report for job {job_id}: GEMINI_API_KEY not set"
        )
        return

    try:
        logger.info(f"Starting report generation for job {job_id}")
        
        # Prepare the detection data in a structured format
        fight_incidents = [p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)]
        total_incidents = len(fight_incidents)
        
        # Initialize the Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Upload the video file directly as specified
        logger.info(f"Uploading video file to Gemini: {job['video_path']}")
        video_file = client.files.upload(file=job['video_path'])
        logger.info(f"Completed upload: {video_file.uri}")
        
        # Wait for processing to complete
        logger.info("Waiting for video processing to complete...")
        while video_file.state.name == "PROCESSING":
            logger.debug("Video still processing...")
            time.sleep(1)
            video_file = client.files.get(name=video_file.name)
        
        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed: {video_file.state.name}")
        
        logger.info('Video processing complete. Generating analysis...')
        
        # Create the prompt
        prompt = f"""
        You are a professional security analyst for a stadium. Your task is to analyze the video and fight detection results to create a security report.
        
        ## Detection Data
        - Video analyzed: {os.path.basename(job['video_path'])}
        - Total frames processed: {job['results'].get('total_frames', 'Unknown')}
        - Total incidents detected: {total_incidents}
        
        ## Request
        Create a security expert report with these sections:
        1. Executive Summary - Brief overview of the security situation
        2. Threat Analysis - Interpret the severity of detected incidents in the video
        3. Security Recommendations - Actions that should be taken
        4. Follow-up Procedures - Next steps for security personnel
        
        Important formatting requirements:
        - Use h3 tags with class="mt-4 mb-3" for section headers
        - Use Bootstrap dark theme compatible colors (text-light, text-white)
        - Use strong contrast for all text to ensure readability (no light gray text)
        - Format recommendations in alert boxes using <div class="alert alert-warning"> tags
        - Use bullet points with <ul> and <li> tags for lists
        - Make the report visually organized and easy to scan
        
        DO NOT include an Incident Summary section, as we already display this separately.
        DO NOT list each incident individually, as we already show them in a timeline.
        DO NOT wrap your response in markdown code blocks (```html or ```). Just output direct HTML.
        
        Your report must be formatted in professional HTML with Bootstrap styling for dark theme compatibility.
        """
        
        # Generate content with video and prompt
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=[video_file, prompt]
        )
        
        # Check if we have a valid response
        if hasattr(response, 'text') and response.text:
            # Add a header to the report
            header = f"""
            <div class="alert {'alert-danger' if total_incidents > 0 else 'alert-success'} mb-4">
                <h3 class="alert-heading">
                    <i class="fas {'fa-exclamation-triangle' if total_incidents > 0 else 'fa-check-circle'} me-2"></i>
                    Security Assessment Report
                </h3>
                <p class="text-white"><strong>Status:</strong> {'Incidents Detected - Action Required' if total_incidents > 0 else 'No Incidents - Normal Operations'}</p>
            </div>
            """
            
            # Clean the response text to remove any markdown code blocks
            cleaned_text = response.text
            # Remove ```html at the beginning if present
            cleaned_text = re.sub(r'^```html\s*', '', cleaned_text, flags=re.MULTILINE)
            # Remove ``` at the end if present
            cleaned_text = re.sub(r'```\s*$', '', cleaned_text, flags=re.MULTILINE)
            # Remove any other markdown code blocks
            cleaned_text = re.sub(r'```[a-zA-Z]*\s*|\s*```', '', cleaned_text)
            
            job['report'] = header + cleaned_text
            logger.info(f"Report successfully generated for job {job_id}")
        else:
            # Handle empty response
            logger.warning("Received empty response from Gemini API")
            raise ValueError("Empty response from Gemini API")
            
    except Exception as e:
        error_msg = f"Error in Gemini report generation: {str(e)}"
        logger.error(error_msg)
        logger.exception("Detailed exception information:")
        
        # Generate a simple fallback report based on the detection data but in HTML format
        fight_incidents = [p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)]
        total_incidents = len(fight_incidents)
        
        job['report'] = f"""
        <div class="alert alert-secondary mb-4">
            <p><strong>Note:</strong> AI-powered detailed analysis unavailable. Showing system-generated report.</p>
        </div>
        
        <h3>Executive Summary</h3>
        <p>This system-generated report provides an assessment of the analyzed video footage from the stadium security system.</p>
        
        <h3>Threat Analysis</h3>
        <p>Based on the automated detection system, the security threat level is <strong>{'ELEVATED' if total_incidents > 0 else 'NORMAL'}</strong>.</p>
        
        <div class="card mb-4">
            <div class="card-header bg-{'danger' if total_incidents > 0 else 'success'} text-white">
                <h4 class="mb-0">Security Assessment</h4>
            </div>
            <div class="card-body">
                <p>{'The system has detected potential security incidents that require attention.' if total_incidents > 0 else 'No security incidents were detected in the analyzed footage.'}</p>
                <ul>
                    <li>Total frames analyzed: {job['results'].get('total_frames', 'Unknown')}</li>
                    <li>Processing time: {job['results'].get('processing_time_seconds', 0):.2f} seconds</li>
                    <li>Detection threshold: {job['results'].get('threshold', 0.8)}</li>
                </ul>
            </div>
        </div>
        
        <h3>Security Recommendations</h3>
        <div class="alert alert-{'warning' if total_incidents > 0 else 'info'}">
            <p><strong>Recommended Actions:</strong></p>
            <ul>
                <li>{'Review the highlighted timestamps to confirm incidents' if total_incidents > 0 else 'Continue standard monitoring protocols'}</li>
                <li>{'Consider increasing security presence in affected areas' if total_incidents > 0 else 'Maintain current security staffing levels'}</li>
                <li>{'Investigate the cause of detected incidents' if total_incidents > 0 else 'No additional actions required at this time'}</li>
            </ul>
        </div>
        
        <h3>Follow-up Procedures</h3>
        <p>{'If incidents are confirmed, follow standard incident response protocols and document all findings.' if total_incidents > 0 else 'Continue regular security sweeps and monitoring.'}</p>
        """

@app.route('/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    response = {
        'status': job['status'],
        'job_id': job_id,
    }
    
    if job['status'] == 'failed':
        response['error'] = job.get('error', 'Unknown error')
    elif job['status'] == 'completed':
        response['processing_time'] = job['results'].get('processing_time_seconds', 0)
        
    return jsonify(response)

@app.route('/results/<job_id>', methods=['GET'])
def view_results(job_id):
    if job_id not in processing_jobs:
        flash('Job not found')
        return redirect(url_for('index'))
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        if job['status'] == 'failed':
            flash(f"Processing failed: {job.get('error', 'Unknown error')}")
        else:
            flash('Processing not complete yet')
        return redirect(url_for('index'))
    
    output_video_path = job['output_video']
    
    # if we stored None, fall back on our placeholder
    report_text = job.get('report') or "Report generation not available"
    return render_template(
        'results.html',
        job_id=job_id,
        video_path=output_video_path,
        results=job['results'],
        report=report_text,
    )


@app.route('/api/results/<job_id>', methods=['GET'])
def get_results_data(job_id):
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({
            'status': job['status'],
            'error': job.get('error', 'Processing not complete')
        }), 400
    
    return jsonify({
        'status': 'completed',
        'results': job['results'],
        'report': job.get('report', 'Report not available')
    })

@app.route('/api/regenerate-report/<job_id>', methods=['POST'])
def regenerate_report(job_id):
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({
            'status': 'error',
            'error': job.get('error', 'Processing not complete')
        }), 400
    
    try:
        # Use Gemini to regenerate the report
        logger.info(f"Regenerating report for job {job_id}")
        
        # Initialize the Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Upload the video file directly to Gemini
        logger.info(f"Uploading video file to Gemini: {job['video_path']}")
        
        # Check if the file exists
        if not os.path.exists(job['video_path']):
            raise FileNotFoundError(f"Video file not found at {job['video_path']}")
            
        # Check file size
        file_size = os.path.getsize(job['video_path']) / (1024*1024)  # Size in MB
        logger.info(f"Video file size: {file_size:.2f} MB")
        
        try:
            video_file = client.files.upload(file=job['video_path'])
            logger.info(f"Completed upload: {video_file.uri}")
        except Exception as e:
            logger.error(f"Error uploading video file: {str(e)}")
            # Try alternate approach without video
            return generate_text_only_report(job_id)
        
        # Wait for processing to complete
        logger.info("Waiting for video processing to complete...")
        try:
            processing_start = time.time()
            while video_file.state.name == "PROCESSING":
                # Log status every 10 seconds
                if (time.time() - processing_start) % 10 < 0.5:
                    logger.info(f"Video still processing... (Elapsed: {time.time() - processing_start:.1f}s)")
                
                # Check for timeout (2 minutes)
                if time.time() - processing_start > 120:
                    logger.warning("Video processing timeout reached")
                    return generate_text_only_report(job_id)
                    
                time.sleep(1)
                video_file = client.files.get(name=video_file.name)
            
            if video_file.state.name == "FAILED":
                logger.error(f"Video processing failed: {video_file.state.name}")
                return generate_text_only_report(job_id)
                
        except Exception as e:
            logger.error(f"Error during video processing: {str(e)}")
            return generate_text_only_report(job_id)
        
        logger.info('Video processing complete. Generating analysis...')
        
        # Create the prompt
        prompt = f"""
        You are a professional security analyst for a stadium. Your task is to analyze the video and fight detection results to create a security report.
        
        ## Detection Data
        - Video analyzed: {os.path.basename(job['video_path'])}
        - Total frames processed: {job['results'].get('total_frames', 'Unknown')}
        - Total incidents detected: {len([p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)])}
        
        ## Request
        Create a security expert report with these sections:
        1. Executive Summary - Brief overview of the security situation
        2. Threat Analysis - Interpret the severity of detected incidents in the video
        3. Security Recommendations - Actions that should be taken
        4. Follow-up Procedures - Next steps for security personnel
        
        Important formatting requirements:
        - Use h3 tags with class="mt-4 mb-3" for section headers
        - Use Bootstrap dark theme compatible colors (text-light, text-white)
        - Use strong contrast for all text to ensure readability (no light gray text)
        - Format recommendations in alert boxes using <div class="alert alert-warning"> tags
        - Use bullet points with <ul> and <li> tags for lists
        - Make the report visually organized and easy to scan
        
        DO NOT include an Incident Summary section, as we already display this separately.
        DO NOT list each incident individually, as we already show them in a timeline.
        DO NOT wrap your response in markdown code blocks (```html or ```). Just output direct HTML.
        
        Your report must be formatted in professional HTML with Bootstrap styling for dark theme compatibility.
        """
        
        # Generate content with video and prompt
        try:
            response = client.models.generate_content(
                model="gemini-1.5-pro",
                contents=[video_file, prompt],
            )
            
            # Check if we have a valid response
            if hasattr(response, 'text') and response.text:
                process_report_response(job, response)
                return jsonify({
                    'status': 'success',
                    'report': job['report']
                })
            else:
                # Try alternate method to get text
                try:
                    response_text = str(response.candidates[0].content.parts[0].text)
                    # Add header and clean the response
                    process_report_text(job, response_text)
                    return jsonify({
                        'status': 'success',
                        'report': job['report']
                    })
                except:
                    logger.warning("Couldn't extract text from response")
                    return generate_text_only_report(job_id)
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return generate_text_only_report(job_id)
        
    except Exception as e:
        error_msg = f"Error regenerating report: {str(e)}"
        logger.error(error_msg)
        logger.exception("Detailed exception information:")
        return jsonify({
            'status': 'error',
            'error': error_msg
        }), 500

def generate_text_only_report(job_id):
    """Fallback to generate a text-only report without video"""
    job = processing_jobs[job_id]
    logger.info(f"Generating text-only report for job {job_id}")
    
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Create the prompt for text-only analysis
        fight_incidents = [p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)]
        total_incidents = len(fight_incidents)
        
        # Format incidents for the context
        incidents_text = ""
        for i, incident in enumerate(fight_incidents):
            incidents_text += f"""
            Incident #{i+1}:
            - Time: {incident['start_time']} to {incident['end_time']}
            - Frames: {incident['chunk_start_frame']} to {incident['chunk_end_frame']}
            - Probability: {incident['fight_probability']:.2f}
            
            """
        
        # Create the prompt with context
        prompt = f"""
        You are a professional security analyst for a stadium. Create a detailed security report based on these detection results:
        
        ## Video Information
        - Filename: {os.path.basename(job['video_path'])}
        - Total frames: {job['results'].get('total_frames', 'Unknown')}
        - Processing time: {job['results'].get('processing_time_seconds', 0):.2f} seconds
        - Detection threshold: {job['results'].get('threshold', 0.8)}
        - Total incidents detected: {total_incidents}
        
        ## Detected Incidents
        {incidents_text if total_incidents > 0 else "No incidents were detected in this video."}
        
        ## Instructions
        Create a security expert report with these sections:
        1. Executive Summary - Brief overview of the security situation
        2. Threat Analysis - Interpret the severity of detected incidents
        3. Security Recommendations - Actions that should be taken
        4. Follow-up Procedures - Next steps for security personnel
        5. detecet people in the video, who starts the fight, and what did they throw and other details
        
        Important formatting requirements:
        - Use h3 tags with class="mt-4 mb-3" for section headers
        - Use Bootstrap dark theme compatible colors (text-light, text-white)
        - Use strong contrast for all text to ensure readability (no light gray text)
        - Format recommendations in alert boxes using <div class="alert alert-warning"> tags
        - Use bullet points with <ul> and <li> tags for lists
        - Make the report visually organized and easy to scan
        
        DO NOT include an Incident Summary section, as we already display this separately.
        DO NOT list each incident individually, as we already show them in a timeline.
        DO NOT wrap your response in markdown code blocks (```html or ```). Just output direct HTML.
        
        Your report must be formatted in professional HTML with Bootstrap styling for dark theme compatibility.
        """
        
        # Generate content with text-only prompt
        response = client.models.generate_content(
            model="gemini-1.5-pro",
            contents=prompt,
        )
        
        # Process the response
        if hasattr(response, 'text') and response.text:
            process_report_response(job, response)
            return jsonify({
                'status': 'success',
                'report': job['report']
            })
        else:
            # Fallback to a basic report
            fallback_report(job)
            return jsonify({
                'status': 'success',
                'report': job['report']
            })
            
    except Exception as e:
        logger.error(f"Error in text-only report: {str(e)}")
        fallback_report(job)
        return jsonify({
            'status': 'success',
            'report': job['report']
        })

def process_report_response(job, response):
    """Process a Gemini response and update the job report"""
    # Clean the response text
    cleaned_text = response.text.strip()
    # Remove ```html at the beginning if present
    cleaned_text = re.sub(r'^```html\s*', '', cleaned_text, flags=re.MULTILINE)
    # Remove ``` at the end if present
    cleaned_text = re.sub(r'```\s*$', '', cleaned_text, flags=re.MULTILINE)
    # Remove any other markdown code blocks
    cleaned_text = re.sub(r'```[a-zA-Z]*\s*|\s*```', '', cleaned_text)
    
    # Add header
    total_incidents = len([p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)])
    header = f"""
    <div class="alert {'alert-danger' if total_incidents > 0 else 'alert-success'} mb-4">
        <h3 class="alert-heading">
            <i class="fas {'fa-exclamation-triangle' if total_incidents > 0 else 'fa-check-circle'} me-2"></i>
            Security Assessment Report
        </h3>
        <p class="text-white"><strong>Status:</strong> {'Incidents Detected - Action Required' if total_incidents > 0 else 'No Incidents - Normal Operations'}</p>
    </div>
    """
    
    # Update the job with the new report
    job['report'] = header + cleaned_text
    logger.info(f"Report successfully generated for job {job['video_path']}")

def process_report_text(job, text):
    """Process raw text and update the job report"""
    cleaned_text = text.strip()
    # Remove any markdown formatting
    cleaned_text = re.sub(r'^```html\s*', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'```\s*$', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'```[a-zA-Z]*\s*|\s*```', '', cleaned_text)
    
    # Add header
    total_incidents = len([p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)])
    header = f"""
    <div class="alert {'alert-danger' if total_incidents > 0 else 'alert-success'} mb-4">
        <h3 class="alert-heading">
            <i class="fas {'fa-exclamation-triangle' if total_incidents > 0 else 'fa-check-circle'} me-2"></i>
            Security Assessment Report
        </h3>
        <p class="text-white"><strong>Status:</strong> {'Incidents Detected - Action Required' if total_incidents > 0 else 'No Incidents - Normal Operations'}</p>
    </div>
    """
    
    # Update the job with the new report
    job['report'] = header + cleaned_text
    logger.info(f"Report successfully generated from text for job {job['video_path']}")

def fallback_report(job):
    """Generate a fallback report based on detection data"""
    # Generate a simple fallback report based on the detection data but in HTML format
    fight_incidents = [p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)]
    total_incidents = len(fight_incidents)
    
    job['report'] = f"""
    <div class="alert alert-info mb-4">
        <h3 class="alert-heading">
            <i class="fas fa-info-circle me-2"></i>
            System-Generated Security Report
        </h3>
        <p class="text-white"><strong>Note:</strong> AI-powered analysis unavailable. Showing system-generated report.</p>
    </div>
    
    <h3 class="mt-4 mb-3 text-white">Executive Summary</h3>
    <p class="text-white">This system-generated report provides an assessment of the analyzed video footage from the stadium security system.</p>
    
    <h3 class="mt-4 mb-3 text-white">Threat Analysis</h3>
    <p class="text-white">Based on the automated detection system, the security threat level is <strong class="text-white">{'ELEVATED' if total_incidents > 0 else 'NORMAL'}</strong>.</p>
    
    <div class="card mb-4">
        <div class="card-header bg-{'danger' if total_incidents > 0 else 'success'} text-white">
            <h4 class="mb-0">Security Assessment</h4>
        </div>
        <div class="card-body bg-dark">
            <p class="text-white">{'The system has detected potential security incidents that require attention.' if total_incidents > 0 else 'No security incidents were detected in the analyzed footage.'}</p>
            <ul class="text-white">
                <li>Total frames analyzed: {job['results'].get('total_frames', 'Unknown')}</li>
                <li>Processing time: {job['results'].get('processing_time_seconds', 0):.2f} seconds</li>
                <li>Detection threshold: {job['results'].get('threshold', 0.8)}</li>
            </ul>
        </div>
    </div>
    
    <h3 class="mt-4 mb-3 text-white">Security Recommendations</h3>
    <div class="alert alert-{'warning' if total_incidents > 0 else 'info'}">
        <p><strong>Recommended Actions:</strong></p>
        <ul>
            <li>{'Review the highlighted timestamps to confirm incidents' if total_incidents > 0 else 'Continue standard monitoring protocols'}</li>
            <li>{'Consider increasing security presence in affected areas' if total_incidents > 0 else 'Maintain current security staffing levels'}</li>
            <li>{'Investigate the cause of detected incidents' if total_incidents > 0 else 'No additional actions required at this time'}</li>
        </ul>
    </div>
    
    <h3 class="mt-4 mb-3 text-white">Follow-up Procedures</h3>
    <p class="text-white">{'If incidents are confirmed, follow standard incident response protocols and document all findings.' if total_incidents > 0 else 'Continue regular security sweeps and monitoring.'}</p>
    """
    logger.info(f"Fallback report generated for job {job['video_path']}")

@app.route('/api/chat/<job_id>', methods=['POST'])
def chat_with_assistant(job_id):
    if job_id not in processing_jobs:
        return jsonify({'status': 'error', 'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({
            'status': 'error',
            'error': job.get('error', 'Processing not complete')
        }), 400
    
    # Get message from request
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({
            'status': 'error',
            'error': 'No message provided'
        }), 400
    
    try:
        # Log the chat request
        logger.info(f"Chat request for job {job_id}: {user_message}")
        
        # Format incidents for the context
        fight_incidents = [p for p in job['results'].get('predictions', []) if p.get('fight_detected', False)]
        total_incidents = len(fight_incidents)
        incidents_context = ""
        
        for i, incident in enumerate(fight_incidents):
            incidents_context += f"""
            Incident #{i+1}:
            - Time: {incident['start_time']} to {incident['end_time']}
            - Frames: {incident['chunk_start_frame']} to {incident['chunk_end_frame']}
            - Confidence: {incident['fight_probability']:.2f}
            
            """
        
        # Initialize the Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Create the prompt
        prompt = f"""
        You are a security assistant for a stadium security monitoring system that detects fights and violent incidents.

        ## Security Analysis Context
        Video filename: {os.path.basename(job['video_path'])}
        Total incidents detected: {total_incidents}
        
        {incidents_context if total_incidents > 0 else "No incidents were detected in this video."}
        
        ## User Question
        The security officer has asked: "{user_message}"
        
        ## Instructions
        - Respond directly and concisely to the user's question
        - Focus on security-related information about the detected incidents
        - Provide factual information based on the detection data
        - Use a professional, helpful tone appropriate for security personnel
        - DO NOT use markdown formatting in your response
        - DO NOT say "Based on the provided information" or similar phrases
        - DO NOT reference yourself as an AI or assistant
        - Keep responses under 150 words unless detailed explanation is needed
        - detect people in the video, who starts the fight, and what did they throw and other details
        
        Respond directly:
        """
        
        # Generate content with prompt
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=prompt,
        )
        
        # Get response text
        response_text = response.text.strip()
        logger.info(f"Chat response for job {job_id}: {response_text[:100]}...")
        
        return jsonify({
            'status': 'success',
            'response': response_text
        })
    
    except Exception as e:
        error_msg = f"Error in chat: {str(e)}"
        logger.error(error_msg)
        logger.exception("Detailed exception information:")
        
        # Return a more direct fallback response
        return jsonify({
            'status': 'success',
            'response': "I'm analyzing the security footage now. Could you please try your question again in a moment?"
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)