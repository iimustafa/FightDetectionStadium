document.addEventListener('DOMContentLoaded', function() {
    // Update range slider values
    const sequenceLengthSlider = document.getElementById('sequence_length');
    const sequenceLengthValue = document.getElementById('sequence_length_value');
    const thresholdSlider = document.getElementById('threshold');
    const thresholdValue = document.getElementById('threshold_value');
    const frameRateSlider = document.getElementById('output_frame_rate');
    const frameRateValue = document.getElementById('output_frame_rate_value');

    // Update sequence length value display
    if (sequenceLengthSlider && sequenceLengthValue) {
        sequenceLengthSlider.addEventListener('input', function() {
            sequenceLengthValue.textContent = this.value;
        });
    }

    // Update threshold value display with 2 decimal places
    if (thresholdSlider && thresholdValue) {
        thresholdSlider.addEventListener('input', function() {
            thresholdValue.textContent = parseFloat(this.value).toFixed(2);
        });
    }

    // Update frame rate value display
    if (frameRateSlider && frameRateValue) {
        frameRateSlider.addEventListener('input', function() {
            frameRateValue.textContent = this.value;
        });
    }

    // Handle form submission
    const form = document.getElementById('video-upload-form');
    const processingStatus = document.getElementById('processing-status');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validate file size
            const videoInput = document.getElementById('video');
            const maxSize = 300 * 1024 * 1024; // 300MB
            
            if (videoInput.files[0] && videoInput.files[0].size > maxSize) {
                alert('File size exceeds the maximum limit of 300MB.');
                return;
            }
            
            // Show processing status
            if (processingStatus) {
                processingStatus.style.display = 'block';
            }
            
            // Disable form submission button
            const submitButton = document.getElementById('upload-button');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
            
            // Submit form using fetch API
            const formData = new FormData(form);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                // Start polling for job status
                pollJobStatus(data.job_id);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error uploading video: ' + error.message);
                
                // Hide processing status and re-enable form
                if (processingStatus) {
                    processingStatus.style.display = 'none';
                }
                
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = '<i class="fas fa-upload me-2"></i>Upload and Analyze';
                }
            });
        });
    }

    function pollJobStatus(jobId) {
        const processingMessage = document.getElementById('processing-message');
        
        const checkStatus = () => {
            fetch(`/status/${jobId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'completed') {
                        // Redirect to results page
                        window.location.href = `/results/${jobId}`;
                    } else if (data.status === 'failed') {
                        throw new Error(data.error || 'Processing failed');
                    } else {
                        // Update processing message if processing time is available
                        if (processingMessage && data.processing_time) {
                            processingMessage.textContent = `Processing... (${Math.round(data.processing_time)}s elapsed)`;
                        }
                        
                        // Continue polling
                        setTimeout(checkStatus, 2000);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error checking job status: ' + error.message);
                    
                    // Hide processing status and re-enable form
                    if (processingStatus) {
                        processingStatus.style.display = 'none';
                    }
                    
                    const submitButton = document.getElementById('upload-button');
                    if (submitButton) {
                        submitButton.disabled = false;
                        submitButton.innerHTML = '<i class="fas fa-upload me-2"></i>Upload and Analyze';
                    }
                });
        };
        
        // Start polling
        setTimeout(checkStatus, 2000);
    }
});