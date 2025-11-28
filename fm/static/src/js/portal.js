// Simple vanilla JavaScript for service request portal
document.addEventListener('DOMContentLoaded', function() {
    
    // Form validation
    const form = document.querySelector('form[action="/service-request/submit"]');
    if (form) {
        form.addEventListener('submit', function(e) {
            const title = document.getElementById('title');
            const description = document.getElementById('description');
            const serviceType = document.getElementById('service_type');
            
            // Basic validation
            if (!title.value.trim() || !description.value.trim() || !serviceType.value) {
                e.preventDefault();
                showError('Please fill in all required fields.');
                return false;
            }
            
            // Show loading state
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Submitting...';
            }
        });
    }
    
    // Service type change handler
    const serviceTypeSelect = document.getElementById('service_type');
    if (serviceTypeSelect) {
        serviceTypeSelect.addEventListener('change', function() {
            const prioritySelect = document.getElementById('priority');
            if (prioritySelect) {
                const serviceType = this.value;
                
                // Set default priority based on service type
                if (serviceType === 'maintenance') {
                    prioritySelect.value = '3'; // High priority for maintenance
                } else if (serviceType === 'it_support') {
                    prioritySelect.value = '2'; // Normal priority for IT
                } else {
                    prioritySelect.value = '2'; // Normal priority by default
                }
            }
        });
    }
    
    // Priority calculation based on urgency
    const urgencySelect = document.getElementById('urgency');
    
    if (urgencySelect) {
        const updatePriority = function() {
            const urgency = urgencySelect.value;
            const prioritySelect = document.getElementById('priority');
            
            if (urgency && prioritySelect) {
                const priorityMapping = {
                    'low': '1',
                    'medium': '2',
                    'high': '3',
                    'critical': '4',
                };
                
                const calculatedPriority = priorityMapping[urgency] || '2';
                prioritySelect.value = calculatedPriority;
            }
        };
        
        urgencySelect.addEventListener('change', updatePriority);
    }
    
    function showError(message) {
        // Remove existing alerts
        const existingAlerts = document.querySelectorAll('.alert-danger');
        existingAlerts.forEach(alert => alert.remove());
        
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = message + 
            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
            '<span aria-hidden="true">&times;</span>' +
            '</button>';
        
        // Insert at the beginning of the form
        if (form) {
            form.insertBefore(alertDiv, form.firstChild);
        }
        
        // Auto-hide after 5 seconds
        setTimeout(function() {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
});
