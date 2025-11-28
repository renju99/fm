/* Enhanced Work Order Calendar Functionality */

console.log('Work Order Calendar JavaScript loaded successfully');

// Function to initialize calendar enhancements
function initializeCalendarEnhancements() {
    console.log('Initializing calendar enhancements');
    // Wait for calendar to be rendered
    setTimeout(() => {
        enhanceCalendarEvents();
        addCalendarLegend();
        initializeObserver();
        console.log('Calendar enhancements applied');
    }, 1000);
}

// Wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCalendarEnhancements);
} else {
    // DOM is already ready
    initializeCalendarEnhancements();
}

// Function to enhance calendar events with styling and tooltips
function enhanceCalendarEvents() {
    const events = document.querySelectorAll('.fc-event');
    events.forEach(event => {
        addEventAttributes(event);
        addEventTooltips(event);
    });
}

// Add data attributes for CSS styling
function addEventAttributes(event) {
    const eventData = getEventData(event);
    if (eventData) {
        // Add data attributes for CSS styling
        if (eventData.priority) {
            event.setAttribute('data-priority', eventData.priority);
        }
        if (eventData.state) {
            event.setAttribute('data-state', eventData.state);
        }
        if (eventData.sla_status) {
            event.setAttribute('data-sla-status', eventData.sla_status);
        }
        if (eventData.work_order_type) {
            event.setAttribute('data-work-order-type', eventData.work_order_type);
        }

        // Add special classes for overdue and at-risk work orders
        if (isOverdue(eventData)) {
            event.classList.add('overdue');
        }
        if (isSLAAtRisk(eventData)) {
            event.classList.add('sla-at-risk');
        }
    }
}

// Extract event data from DOM element
function getEventData(event) {
    const title = event.querySelector('.fc-title')?.textContent;
    const time = event.querySelector('.fc-time')?.textContent;
    
    return {
        title: title,
        time: time,
        priority: event.dataset.priority,
        state: event.dataset.state,
        sla_status: event.dataset.slaStatus,
        work_order_type: event.dataset.workOrderType,
        sla_deadline: event.dataset.slaDeadline
    };
}

// Check if work order is overdue
function isOverdue(eventData) {
    if (!eventData.sla_deadline) return false;
    const deadline = new Date(eventData.sla_deadline);
    const now = new Date();
    return deadline < now && eventData.state !== 'completed' && eventData.state !== 'cancelled';
}

// Check if work order is at risk
function isSLAAtRisk(eventData) {
    if (!eventData.sla_deadline) return false;
    const deadline = new Date(eventData.sla_deadline);
    const now = new Date();
    const hoursUntilDeadline = (deadline - now) / (1000 * 60 * 60);
    return hoursUntilDeadline <= 24 && hoursUntilDeadline > 0 && eventData.state !== 'completed';
}

// Add rich tooltips to events
function addEventTooltips(event) {
    const eventData = getEventData(event);
    if (eventData) {
        let tooltipContent = `<strong>${eventData.title}</strong>`;
        
        if (eventData.time) {
            tooltipContent += `<br/>Time: ${eventData.time}`;
        }
        
        if (eventData.priority) {
            const priorityLabels = {
                '0': 'Very Low',
                '1': 'Low', 
                '2': 'Normal',
                '3': 'High',
                '4': 'Critical'
            };
            tooltipContent += `<br/>Priority: ${priorityLabels[eventData.priority] || eventData.priority}`;
        }
        
        if (eventData.state) {
            const stateLabels = {
                'draft': 'Draft',
                'assigned': 'Assigned',
                'in_progress': 'In Progress',
                'on_hold': 'On Hold',
                'completed': 'Completed',
                'cancelled': 'Cancelled'
            };
            tooltipContent += `<br/>Status: ${stateLabels[eventData.state] || eventData.state}`;
        }
        
        if (eventData.sla_status) {
            const slaLabels = {
                'on_time': 'On Time',
                'at_risk': 'At Risk',
                'breached': 'Breached',
                'completed': 'Completed'
            };
            tooltipContent += `<br/>SLA: ${slaLabels[eventData.sla_status] || eventData.sla_status}`;
        }
        
        if (eventData.work_order_type) {
            const typeLabels = {
                'preventive': 'Preventive',
                'corrective': 'Corrective',
                'predictive': 'Predictive',
                'inspection': 'Inspection'
            };
            tooltipContent += `<br/>Type: ${typeLabels[eventData.work_order_type] || eventData.work_order_type}`;
        }
        
        event.setAttribute('title', tooltipContent);
    }
}

// Add legend to calendar views
function addCalendarLegend() {
    // Check if legend already exists
    if (document.querySelector('.calendar-legend')) {
        return;
    }
    
    const legend = document.createElement('div');
    legend.className = 'calendar-legend';
    legend.innerHTML = `
        <div class="legend-item">
            <div class="legend-color" style="background-color: #dc3545;"></div>
            <span>Critical Priority</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #fd7e14;"></div>
            <span>High Priority</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #28a745;"></div>
            <span>Normal Priority</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #17a2b8;"></div>
            <span>Low Priority</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #6c757d;"></div>
            <span>Very Low Priority</span>
        </div>
    `;
    
    // Insert legend after the calendar toolbar
    const toolbar = document.querySelector('.fc-toolbar');
    if (toolbar) {
        toolbar.parentNode.insertBefore(legend, toolbar.nextSibling);
    }
}

// Utility functions for calendar enhancements
window.CalendarUtils = {
    /**
     * Get priority color for a given priority level
     */
    getPriorityColor: function(priority) {
        const colors = {
            '0': '#6c757d', // Very Low - Gray
            '1': '#17a2b8', // Low - Blue
            '2': '#28a745', // Normal - Green
            '3': '#fd7e14', // High - Orange
            '4': '#dc3545'  // Critical - Red
        };
        return colors[priority] || colors['2'];
    },

    /**
     * Get status color for a given status
     */
    getStatusColor: function(state) {
        const colors = {
            'draft': '#6c757d',      // Gray
            'assigned': '#007bff',   // Blue
            'in_progress': '#ffc107', // Yellow
            'on_hold': '#fd7e14',    // Orange
            'completed': '#28a745',  // Green
            'cancelled': '#dc3545'   // Red
        };
        return colors[state] || colors['draft'];
    },

    /**
     * Get SLA status color
     */
    getSLAStatusColor: function(slaStatus) {
        const colors = {
            'on_time': '#28a745',    // Green
            'at_risk': '#ffc107',    // Yellow
            'breached': '#dc3545',   // Red
            'completed': '#17a2b8'   // Cyan
        };
        return colors[slaStatus] || colors['on_time'];
    },

    /**
     * Get work order type color
     */
    getWorkOrderTypeColor: function(type) {
        const colors = {
            'preventive': '#28a745',  // Green
            'corrective': '#dc3545',  // Red
            'predictive': '#6f42c1',  // Purple
            'inspection': '#17a2b8'   // Cyan
        };
        return colors[type] || colors['corrective'];
    },

    /**
     * Check if a work order is overdue
     */
    isOverdue: function(slaDeadline, state) {
        if (!slaDeadline) return false;
        const deadline = new Date(slaDeadline);
        const now = new Date();
        return deadline < now && state !== 'completed' && state !== 'cancelled';
    },

    /**
     * Check if a work order is at risk
     */
    isAtRisk: function(slaDeadline, state) {
        if (!slaDeadline) return false;
        const deadline = new Date(slaDeadline);
        const now = new Date();
        const hoursUntilDeadline = (deadline - now) / (1000 * 60 * 60);
        return hoursUntilDeadline <= 24 && hoursUntilDeadline > 0 && state !== 'completed';
    }
};

// Re-run enhancement when calendar is updated
let observer = null;

function initializeObserver() {
    if (observer) {
        observer.disconnect();
    }
    
    if (document.body) {
        observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // Check if new calendar events were added
                    const newEvents = document.querySelectorAll('.fc-event:not([data-enhanced])');
                    if (newEvents.length > 0) {
                        newEvents.forEach(event => {
                            event.setAttribute('data-enhanced', 'true');
                            addEventAttributes(event);
                            addEventTooltips(event);
                        });
                    }
                }
            });
        });

        // Start observing
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        console.log('MutationObserver initialized');
    } else {
        console.log('Document body not ready, retrying...');
        setTimeout(initializeObserver, 100);
    }
}