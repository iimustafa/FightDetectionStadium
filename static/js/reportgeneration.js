document.addEventListener('DOMContentLoaded', function() {
    // This script handles report generation and display
    // It's included for future enhancements, but the main report 
    // generation is done server-side using the Gemini API
    
    // Format the report content for better readability
    const reportContent = document.getElementById('report-content');
    if (reportContent) {
        // Replace any markdown-style headers with HTML headers
        let content = reportContent.innerHTML;
        
        // Replace markdown headers with HTML headers
        content = content.replace(/#{3,6}\s+(.*?)(?:<br>|$)/g, '<h5>$1</h5>');
        content = content.replace(/#{2}\s+(.*?)(?:<br>|$)/g, '<h4>$1</h4>');
        content = content.replace(/#{1}\s+(.*?)(?:<br>|$)/g, '<h3>$1</h3>');
        
        // Replace markdown lists with HTML lists
        content = content.replace(/(\*|\-|\d+\.)\s+(.*?)(?:<br>)/g, '<li>$2</li>');
        
        // Add emphasis and strong formatting
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Apply the formatted content
        reportContent.innerHTML = content;
    }
    
    // Add support for printing or exporting the report
    const addPrintButton = () => {
        const reportCard = document.querySelector('.card:has(#report-content)');
        if (reportCard) {
            const cardHeader = reportCard.querySelector('.card-header');
            if (cardHeader) {
                // Create print button
                const printButton = document.createElement('button');
                printButton.className = 'btn btn-sm btn-outline-secondary';
                printButton.innerHTML = '<i class="fas fa-print me-1"></i> Print Report';
                printButton.onclick = () => {
                    // Get report content
                    const reportContent = document.getElementById('report-content').innerHTML;
                    
                    // Create a printable document
                    const printWindow = window.open('', '_blank');
                    printWindow.document.write(`
                        <html>
                        <head>
                            <title>Fight Detection Report</title>
                            <style>
                                body { font-family: Arial, sans-serif; margin: 20px; }
                                h1 { color: #333; }
                                h3, h4, h5 { margin-top: 20px; }
                                li { margin-bottom: 5px; }
                            </style>
                        </head>
                        <body>
                            <h1>Stadium Fight Detection Report</h1>
                            <hr>
                            <div>${reportContent}</div>
                        </body>
                        </html>
                    `);
                    
                    // Print the document
                    printWindow.document.close();
                    setTimeout(() => {
                        printWindow.print();
                    }, 500);
                };
                
                // Make the header a flex container for title and button
                cardHeader.style.display = 'flex';
                cardHeader.style.justifyContent = 'space-between';
                cardHeader.style.alignItems = 'center';
                
                // Add the button to the header
                cardHeader.appendChild(printButton);
            }
        }
    };
    
    // Call the function to add the print button
    addPrintButton();
});
