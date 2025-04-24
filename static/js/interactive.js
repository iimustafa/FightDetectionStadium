document.addEventListener('DOMContentLoaded', function() {
    // Report generation functionality
    const regenerateButton = document.getElementById('regenerate-report');
    const reportContent = document.getElementById('report-content');
    
    if (regenerateButton) {
        console.log("Report button found, attaching listener");
        regenerateButton.addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            console.log("Regenerate report clicked for job:", jobId);
            
            // Disable button and show loading state
            regenerateButton.disabled = true;
            regenerateButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Analyzing...';
            
            // Add loading indicator to report content
            reportContent.innerHTML = `
                <div class="text-center py-5 text-white">
                    <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <h4 class="mt-3">Analyzing Video with AI</h4>
                    <p>Uploading video to Gemini and generating security analysis...</p>
                    <div class="progress mt-3 mb-2" style="height: 10px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <p class="text-muted small">This process typically takes 1-2 minutes</p>
                </div>
            `;
            
            // Send request to regenerate
            fetch(`/api/regenerate-report/${jobId}`, {
                method: 'POST',
            })
            .then(response => response.json())
            .then(data => {
                console.log("Report response received:", data.status);
                if (data.status === 'success') {
                    // Update the report content with the new report
                    reportContent.innerHTML = data.report;
                    
                    // Show success toast
                    const toast = document.createElement('div');
                    toast.className = 'toast position-fixed top-0 end-0 m-3';
                    toast.setAttribute('role', 'alert');
                    toast.setAttribute('aria-live', 'assertive');
                    toast.setAttribute('aria-atomic', 'true');
                    toast.innerHTML = `
                        <div class="toast-header bg-success text-white">
                            <i class="fas fa-check-circle me-2"></i>
                            <strong class="me-auto">Analysis Complete</strong>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                        </div>
                        <div class="toast-body">
                            Video analysis and security report have been successfully generated.
                        </div>
                    `;
                    document.body.appendChild(toast);
                    const bsToast = new bootstrap.Toast(toast);
                    bsToast.show();
                } else {
                    // Show error message in report content
                    reportContent.innerHTML = `
                        <div class="alert alert-danger">
                            <h4 class="alert-heading">Error Analyzing Video</h4>
                            <p class="text-dark">${data.error || 'An unknown error occurred.'}</p>
                            <hr>
                            <p class="text-dark mb-0">Please try again or contact support if the problem persists.</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                // Show error message in report content
                reportContent.innerHTML = `
                    <div class="alert alert-danger">
                        <h4 class="alert-heading">Connection Error</h4>
                        <p class="text-dark">Failed to communicate with the server. Please check your network connection.</p>
                        <hr>
                        <p class="text-dark mb-0">Technical details: ${error.message}</p>
                    </div>
                `;
            })
            .finally(() => {
                // Re-enable button
                regenerateButton.disabled = false;
                regenerateButton.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Analyze with Gemini';
            });
        });
    }
    
    // Chatbot functionality
    const chatbotContainer = document.getElementById('security-chatbot');
    const chatbotHeader = document.getElementById('chatbot-header');
    const chatbotBody = document.getElementById('chatbot-body');
    const chatMessages = document.getElementById('chat-messages');
    const userMessageInput = document.getElementById('user-message');
    const sendMessageBtn = document.getElementById('send-message');
    const minimizeBtn = document.getElementById('chatbot-minimize');
    const closeBtn = document.getElementById('chatbot-close');
    const notification = document.getElementById('chatbot-notification');
    const chatContainer = document.getElementById('chat-container');
    
    if (chatContainer) {
        console.log("Chat container found");
        const jobId = chatContainer.getAttribute('data-job-id');
        console.log("Chat job ID:", jobId);
        
        // Handle chatbot minimize/maximize
        let isChatbotMinimized = false;
        
        function toggleChatbot() {
            isChatbotMinimized = !isChatbotMinimized;
            chatbotContainer.classList.toggle('chatbot-minimized', isChatbotMinimized);
            chatbotBody.style.display = isChatbotMinimized ? 'none' : 'flex';
            notification.style.display = isChatbotMinimized ? 'flex' : 'none';
        }
        
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleChatbot();
            });
        }
        
        if (chatbotHeader) {
            chatbotHeader.addEventListener('click', function() {
                if(isChatbotMinimized) {
                    toggleChatbot();
                }
            });
        }
        
        if (closeBtn) {
            closeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                chatbotContainer.style.display = 'none';
            });
        }
        
        // Send message function
        function sendMessage() {
            const message = userMessageInput.value.trim();
            if (!message) return;
            
            console.log("Sending message:", message);
            
            // Add user message to chat
            addMessage(message, 'user');
            
            // Clear input
            userMessageInput.value = '';
            
            // Show typing indicator
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'message bot-message typing-indicator';
            typingIndicator.innerHTML = '<span></span><span></span><span></span>';
            chatMessages.appendChild(typingIndicator);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Prepare the request data
            const requestData = {
                message: message
            };
            
            console.log("Sending chat request to:", `/api/chat/${jobId}`);
            console.log("Request payload:", JSON.stringify(requestData));
            
            // Send message to server
            fetch(`/api/chat/${jobId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData),
            })
            .then(response => {
                console.log("Chat response status:", response.status);
                if (!response.ok) {
                    console.error("Response not OK:", response.status, response.statusText);
                }
                return response.json();
            })
            .then(data => {
                console.log("Chat response received:", data);
                // Remove typing indicator
                if (typingIndicator.parentNode) {
                    chatMessages.removeChild(typingIndicator);
                }
                
                // Add bot response
                if (data.status === 'success') {
                    addMessage(data.response, 'bot');
                } else {
                    console.error("Error from API:", data.error);
                    addMessage(`Sorry, I encountered an error: ${data.error || 'Unknown error'}. Please try again.`, 'bot');
                }
            })
            .catch(error => {
                console.error('Error in chat request:', error);
                // Remove typing indicator
                if (typingIndicator.parentNode) {
                    chatMessages.removeChild(typingIndicator);
                }
                addMessage("Sorry, there was a communication error. Please try again later.", 'bot');
            });
        }
        
        // Add message to chat
        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;
            messageDiv.innerHTML = `<div class="message-content">${text}</div>`;
            chatMessages.appendChild(messageDiv);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        // Event listeners
        if (sendMessageBtn) {
            console.log("Send message button found, attaching listener");
            sendMessageBtn.addEventListener('click', sendMessage);
        }
        
        if (userMessageInput) {
            userMessageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
        }
        
        // Set up alert sound
        try {
            const fightData = document.getElementById('fight-data');
            const fightSegments = parseInt(fightData.getAttribute('data-fight-segments') || '0');
            
            if (fightSegments > 0) {
                console.log("Fight segments detected:", fightSegments);
                // Auto-open chatbot if incidents detected
                setTimeout(() => {
                    if (isChatbotMinimized) {
                        notification.style.display = 'flex';
                        notification.classList.add('pulse');
                    }
                    
                    // Make a notification sound
                    try {
                        // Use URL from data attribute
                        const alertSoundElement = document.getElementById('alert-sound');
                        if (alertSoundElement) {
                            const alertSoundUrl = alertSoundElement.getAttribute('data-sound-url');
                            console.log("Playing alert sound from:", alertSoundUrl);
                            const audio = new Audio(alertSoundUrl);
                            audio.volume = 0.5; // Set volume to 50%
                            audio.play().catch(e => console.log('Audio play failed: Browser requires user interaction first'));
                        }
                    } catch (err) {
                        console.log('Audio notification not supported:', err);
                    }
                }, 3000);
            }
        } catch (err) {
            console.error("Error setting up fight alerts:", err);
        }
    }
}); 