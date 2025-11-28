/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

// Patch the FormController to add mobile enhancements for workorders
patch(FormController.prototype, {
    setup() {
        super.setup();
        try {
            // Add mobile-specific setup if needed
            const isMobile = this.isMobileDevice();
            if (isMobile && this.isWorkorderModel()) {
                this.setupMobileEnhancements();
            }
        } catch (error) {
            console.warn('Mobile workorder enhancements failed to load:', error);
        }
    },

    isWorkorderModel() {
        // Check if model and model.root exist and if it's a workorder model
        return this.model && 
               this.model.root && 
               this.model.root.resModel === 'facilities.workorder';
    },

    isMobileDevice() {
        // Check if device config is available
        if (this.env.config && this.env.config.device) {
            return this.env.config.device.isMobile;
        }
        // Fallback to window width detection
        return window.innerWidth <= 768;
    },

    setupMobileEnhancements() {
        // Mobile-specific enhancements for workorders
        console.log("Mobile workorder enhancements loaded");
        
        // Add mobile-specific event listeners
        onMounted(() => {
            this.setupMobileEventListeners();
        });
    },

    setupMobileEventListeners() {
        // Add mobile-specific event listeners here
        const form = document.querySelector('.o_mobile_form');
        if (form) {
            // Add touch event listeners for mobile gestures
            this.setupSwipeGestures(form);
        }
    },

    setupSwipeGestures(element) {
        let startX, startY, endX, endY;
        
        element.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        });
        
        element.addEventListener('touchend', (e) => {
            endX = e.changedTouches[0].clientX;
            endY = e.changedTouches[0].clientY;
            
            const diffX = startX - endX;
            const diffY = startY - endY;
            
            // Swipe left (next workorder)
            if (diffX > 50 && Math.abs(diffY) < 50) {
                this.navigateToNextWorkorder();
            }
            // Swipe right (previous workorder)
            else if (diffX < -50 && Math.abs(diffY) < 50) {
                this.navigateToPreviousWorkorder();
            }
        });
    },

    navigateToNextWorkorder() {
        const notification = useService("notification");
        notification.add('Swipe left detected - Next workorder', { type: 'info' });
    },

    navigateToPreviousWorkorder() {
        const notification = useService("notification");
        notification.add('Swipe right detected - Previous workorder', { type: 'info' });
    }
});

/**
 * Mobile-specific utilities
 */
export const MobileWorkorderUtils = {
    /**
     * Format duration for display
     */
    formatDuration(hours) {
        if (!hours) return '0h 0m';
        
        const h = Math.floor(hours);
        const m = Math.round((hours - h) * 60);
        
        return `${h}h ${m}m`;
    },

    /**
     * Get status color class
     */
    getStatusColor(status) {
        const colors = {
            'draft': 'info',
            'in_progress': 'warning',
            'completed': 'success',
            'cancelled': 'danger',
            'on_hold': 'secondary'
        };
        return colors[status] || 'secondary';
    },

    /**
     * Get priority color class
     */
    getPriorityColor(priority) {
        const colors = {
            '0': 'info',
            '1': 'secondary',
            '2': 'primary',
            '3': 'warning',
            '4': 'danger'
        };
        return colors[priority] || 'secondary';
    },

    /**
     * Get SLA status color class
     */
    getSLAStatusColor(status) {
        const colors = {
            'on_time': 'success',
            'at_risk': 'warning',
            'breached': 'danger',
            'completed': 'success'
        };
        return colors[status] || 'secondary';
    }
};