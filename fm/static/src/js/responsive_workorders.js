/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

// Patch the FormController to add responsive enhancements for workorders
patch(FormController.prototype, {
    setup() {
        super.setup();
        try {
            // Add responsive enhancements if this is a workorder form
            if (this.isWorkorderModel()) {
                this.setupResponsiveEnhancements();
            }
        } catch (error) {
            console.warn('Responsive workorder enhancements failed to load:', error);
        }
    },

    isWorkorderModel() {
        // Check if model and model.root exist and if it's a workorder model
        return this.model && 
               this.model.root && 
               this.model.root.resModel === 'facilities.workorder';
    },

    setupResponsiveEnhancements() {
        // Add responsive enhancements for workorders
        console.log("Responsive workorder enhancements loaded");
        
        // Add mobile-specific event listeners
        onMounted(() => {
            this.setupResponsiveEventListeners();
        });
    },

    setupResponsiveEventListeners() {
        // Add responsive event listeners here
        const form = document.querySelector('.o_responsive_form');
        if (form) {
            // Add touch event listeners for mobile gestures
            this.setupSwipeGestures(form);
            
            // Add responsive button enhancements
            this.setupResponsiveButtons(form);
            
            // Add responsive form enhancements
            this.setupResponsiveForm(form);
        }
    },

    setupSwipeGestures(element) {
        // Only add swipe gestures on mobile devices
        if (window.innerWidth <= 768) {
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
        }
    },

    setupResponsiveButtons(element) {
        // Add loading states to buttons
        element.querySelectorAll('.btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (!btn.classList.contains('btn-loading')) {
                    btn.classList.add('btn-loading');
                    setTimeout(() => {
                        btn.classList.remove('btn-loading');
                    }, 2000);
                }
            });
        });
    },

    setupResponsiveForm(element) {
        // Add responsive form enhancements
        const cards = element.querySelectorAll('.card');
        cards.forEach(card => {
            // Add hover effects for desktop
            if (window.innerWidth > 768) {
                card.addEventListener('mouseenter', () => {
                    card.classList.add('hover');
                });
                card.addEventListener('mouseleave', () => {
                    card.classList.remove('hover');
                });
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
 * Responsive Workorder Utilities
 */
export const ResponsiveWorkorderUtils = {
    /**
     * Check if device is mobile
     */
    isMobile() {
        // Check if device config is available (if we have access to env)
        if (typeof window !== 'undefined' && window.odoo && window.odoo.__WOWL_DEBUG__) {
            return window.innerWidth <= 768;
        }
        // Fallback to window width detection
        return window.innerWidth <= 768;
    },

    /**
     * Check if device is tablet
     */
    isTablet() {
        return window.innerWidth > 768 && window.innerWidth <= 1024;
    },

    /**
     * Check if device is desktop
     */
    isDesktop() {
        return window.innerWidth > 1024;
    },

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
    },

    /**
     * Scroll to top of form (useful for mobile)
     */
    scrollToTop() {
        if (this.isMobile()) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    },

    /**
     * Show mobile-friendly notification
     */
    showNotification(message, type = 'info') {
        const notification = useService("notification");
        notification.add(message, { type });
    }
};
