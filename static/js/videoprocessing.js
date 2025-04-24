document.addEventListener('DOMContentLoaded', function() {
    console.log("Video processing script loaded");
    
    // Get data from HTML data attributes
    const resultsData = JSON.parse(document.getElementById('results-data').getAttribute('data-results'));
    const fightSegments = JSON.parse(document.getElementById('fight-data').getAttribute('data-fight-segments'));
    
    console.log("Results data loaded, total frames:", resultsData.total_frames);
    
    // Initialize video player
    const player = videojs('processed-video', {
        controls: true,
        autoplay: false,
        preload: 'auto',
        fluid: true,
        responsive: true
    });
    
    player.ready(function() {
        console.log("Video player ready, duration:", player.duration());
    });
    
    // Timeline interaction
    const timelineSegments = document.querySelectorAll('.timeline-segment');
    const segmentInfo = document.getElementById('segment-info');
    const segmentTimeRange = document.getElementById('segment-time-range');
    const segmentFrames = document.getElementById('segment-frames');
    const segmentProbability = document.getElementById('segment-probability');
    const segmentStatus = document.getElementById('segment-status');
    const jumpToSegment = document.getElementById('jump-to-segment');
    
    let selectedSegment = null;
    
    console.log("Total timeline segments found:", timelineSegments.length);
    
    // Make all segments visually clickable with stronger styling
    timelineSegments.forEach(segment => {
        segment.style.cursor = 'pointer';
        segment.setAttribute('title', 'Click to jump to this segment');
    });
    
    // Helper function to jump to a specific time in the video
    function jumpToVideoTime(timeInSeconds) {
        console.log(`Attempting to jump to ${timeInSeconds} seconds`);
        
        if (player && !isNaN(timeInSeconds) && timeInSeconds >= 0) {
            try {
                player.currentTime(timeInSeconds);
                
                // Show a visual indicator that we're jumping
                const toast = document.createElement('div');
                toast.className = 'position-fixed top-50 start-50 translate-middle bg-dark text-white p-3 rounded';
                toast.style.zIndex = '9999';
                toast.style.opacity = '0.8';
                toast.innerHTML = `<i class="fas fa-play-circle me-2"></i>Playing segment at ${timeInSeconds.toFixed(2)}s`;
                document.body.appendChild(toast);
                
                // Remove toast after 2 seconds
                setTimeout(() => {
                    if (toast.parentNode) {
                        document.body.removeChild(toast);
                    }
                }, 2000);
                
                // Play the video
                player.play().catch(e => {
                    console.error("Error playing video:", e);
                    // Try again with a slight delay
                    setTimeout(() => {
                        player.play().catch(err => console.error("Second play attempt failed:", err));
                    }, 300);
                });
                
                return true;
            } catch (error) {
                console.error("Error jumping to time:", error);
                return false;
            }
        } else {
            console.error("Invalid time or player not ready:", timeInSeconds);
            return false;
        }
    }
    
    // Function to update segment info display
    function updateSegmentInfo(segment) {
        if (!segment) return;
        
        const startFrame = parseInt(segment.getAttribute('data-start-frame'));
        const endFrame = parseInt(segment.getAttribute('data-end-frame'));
        const startTime = segment.getAttribute('data-start-time');
        const endTime = segment.getAttribute('data-end-time');
        const probability = segment.getAttribute('data-probability');
        const isFight = segment.classList.contains('fight');
        
        // Update segment info display
        segmentTimeRange.textContent = `${startTime} - ${endTime}`;
        segmentFrames.textContent = `${startFrame} - ${endFrame}`;
        segmentProbability.textContent = `${probability}`;
        
        if (isFight) {
            segmentStatus.textContent = 'Fight Detected';
            segmentStatus.className = 'badge bg-danger';
        } else {
            segmentStatus.textContent = 'No Fight';
            segmentStatus.className = 'badge bg-success';
        }
        
        // Force show segment info
        segmentInfo.style.display = 'block';
        
        return {
            startFrame,
            endFrame,
            startTime,
            endTime,
            probability,
            isFight
        };
    }
    
    // Direct click handler for timeline segments
    for (let i = 0; i < timelineSegments.length; i++) {
        const segment = timelineSegments[i];
        
        // Use direct onclick property in addition to addEventListener
        segment.onclick = function(e) {
            console.log(`Timeline segment ${i} clicked via onclick`);
            
            // Update visual selection
            if (selectedSegment) {
                selectedSegment.style.outline = 'none';
            }
            selectedSegment = this;
            this.style.outline = '2px solid white';
            
            // Update info panel
            const segmentData = updateSegmentInfo(this);
            
            // Calculate video time and jump
            const duration = player.duration();
            if (isNaN(duration) || duration <= 0) {
                console.error("Video duration not available yet");
                return;
            }
            
            const fps = resultsData.total_frames / duration;
            const timeToJump = segmentData.startFrame / fps;
            
            console.log(`Segment ${i}: Jumping to ${timeToJump}s (frame ${segmentData.startFrame})`);
            
            // Store time for jump button
            jumpToSegment.setAttribute('data-time', timeToJump);
            
            // Jump to video position
            jumpToVideoTime(timeToJump);
        };
        
        // Also keep the addEventListener for redundancy
        segment.addEventListener('click', function(e) {
            console.log(`Timeline segment ${i} clicked via addEventListener`);
            // The onclick handler above will handle the actual logic
        });
    }
    
    // Jump to segment button
    if (jumpToSegment) {
        jumpToSegment.addEventListener('click', function() {
            const timeToJump = parseFloat(this.getAttribute('data-time'));
            if (!isNaN(timeToJump)) {
                console.log(`Jump button clicked, going to ${timeToJump}s`);
                jumpToVideoTime(timeToJump);
            }
        });
    }
    
    // Incident items in the summary
    const incidentItems = document.querySelectorAll('.incident-item');
    console.log("Total incident items found:", incidentItems.length);
    
    incidentItems.forEach((item, index) => {
        item.addEventListener('click', function() {
            console.log(`Incident item ${index} clicked`);
            const startFrame = parseInt(this.getAttribute('data-start-frame'));
            const startTime = this.getAttribute('data-start-time');
            
            console.log(`Incident data: time: ${startTime}, frame: ${startFrame}`);
            
            // Find the corresponding timeline segment and trigger a click
            let segmentFound = false;
            for (let i = 0; i < timelineSegments.length; i++) {
                const segment = timelineSegments[i];
                if (parseInt(segment.getAttribute('data-start-frame')) === startFrame) {
                    // Use the direct onclick handler
                    segment.onclick();
                    segmentFound = true;
                    break;
                }
            }
            
            if (!segmentFound) {
                console.log(`No matching timeline segment found for frame ${startFrame}`);
                
                // Even if we don't find a matching segment, still try to jump to the time
                const duration = player.duration();
                if (!isNaN(duration) && duration > 0) {
                    const fps = resultsData.total_frames / duration;
                    const timeToJump = startFrame / fps;
                    console.log(`Direct jump to time: ${timeToJump}s (${startFrame} / ${fps})`);
                    jumpToVideoTime(timeToJump);
                }
            }
        });
    });
    
    // Handle video seeking and update highlighted segment
    player.on('timeupdate', function() {
        const currentTime = player.currentTime();
        const duration = player.duration();
        if (!isNaN(duration) && duration > 0) {
            // Estimate current frame based on time and total frames
            const currentFrame = Math.floor((currentTime / duration) * resultsData.total_frames);
            
            // Find the segment that contains this frame
            let foundSegment = null;
            timelineSegments.forEach(segment => {
                const startFrame = parseInt(segment.getAttribute('data-start-frame'));
                const endFrame = parseInt(segment.getAttribute('data-end-frame'));
                
                if (currentFrame >= startFrame && currentFrame <= endFrame) {
                    foundSegment = segment;
                }
            });
            
            // If found and different from the current selected segment, update the UI
            if (foundSegment && foundSegment !== selectedSegment) {
                // Update the UI without triggering a click event
                if (selectedSegment) {
                    selectedSegment.style.outline = 'none';
                }
                selectedSegment = foundSegment;
                foundSegment.style.outline = '2px solid white';
                
                // Update the segment info without jumping
                updateSegmentInfo(foundSegment);
                
                // Calculate video time for the jump button
                const startFrame = parseInt(foundSegment.getAttribute('data-start-frame'));
                const fps = resultsData.total_frames / duration;
                const timeToJump = startFrame / fps;
                jumpToSegment.setAttribute('data-time', timeToJump);
            }
        }
    });
    
    // Ensure video player is ready before trying to interact
    player.on('loadedmetadata', function() {
        console.log("Video metadata loaded, duration:", player.duration());
    });
    
    // Log that initialization is complete
    console.log("Video timeline processing initialized");
});