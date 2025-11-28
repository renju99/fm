// Facilities Management Homepage JavaScript
document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // Initialize homepage functionality
    initFacilitiesHomepage();

    function initFacilitiesHomepage() {
        initAnimations();
        initDashboardWidgets();
        initScrollEffects();
        initSmoothScrolling();
        initLoadingStates();
    }

    function initAnimations() {
        // Add fade-in animation to elements as they come into view
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in-visible');
                }
            });
        }, { threshold: 0.1 });

        // Observe all cards and sections
        document.querySelectorAll('.feature-card, .dashboard-widget, .testimonial-card, .service-card').forEach(el => {
            el.classList.add('fade-in');
            observer.observe(el);
        });
    }

    function initDashboardWidgets() {
        // Simulate real-time data updates for dashboard widgets
        updateWidgetData();
        setInterval(updateWidgetData, 30000); // Update every 30 seconds
    }

    function updateWidgetData() {
        // Update temperature widget with random variation
        const tempWidget = document.querySelector('.dashboard-widget .widget-value');
        if (tempWidget && tempWidget.textContent.includes('°C')) {
            const currentTemp = parseInt(tempWidget.textContent);
            const variation = (Math.random() - 0.5) * 2; // ±1 degree variation
            const newTemp = Math.max(18, Math.min(26, currentTemp + variation));
            tempWidget.textContent = Math.round(newTemp) + '°C';
        }

        // Update power usage with random variation
        const powerWidgets = document.querySelectorAll('.dashboard-widget');
        powerWidgets.forEach(widget => {
            const powerValue = widget.querySelector('.widget-value');
            const progressBar = widget.querySelector('.progress-bar');
            if (powerValue && powerValue.textContent.includes('kW')) {
                const currentPower = parseInt(powerValue.textContent.replace(/,/g, ''));
                const variation = (Math.random() - 0.5) * 100; // ±50 kW variation
                const newPower = Math.max(800, Math.min(1500, currentPower + variation));
                powerValue.textContent = Math.round(newPower).toLocaleString() + ' kW';
                
                // Update progress bar
                if (progressBar) {
                    const percentage = (newPower / 1500) * 100;
                    progressBar.style.width = Math.min(100, percentage) + '%';
                }
            }
        });

        // Update occupancy with random variation
        const occupancyWidget = document.querySelector('.widget-value');
        if (occupancyWidget && !occupancyWidget.textContent.includes('°C') && !occupancyWidget.textContent.includes('kW')) {
            const currentOccupancy = parseInt(occupancyWidget.textContent);
            const variation = Math.floor((Math.random() - 0.5) * 20); // ±10 people variation
            const newOccupancy = Math.max(200, Math.min(500, currentOccupancy + variation));
            occupancyWidget.textContent = newOccupancy;
            
            // Update gauge
            const gaugeFill = document.querySelector('.gauge-fill');
            const gaugeLabel = document.querySelector('.gauge-label');
            if (gaugeFill && gaugeLabel) {
                const percentage = (newOccupancy / 500) * 100;
                gaugeFill.style.width = Math.min(100, percentage) + '%';
                gaugeLabel.textContent = Math.round(percentage) + '% Capacity';
            }
        }
    }

    function initScrollEffects() {
        // Add parallax effect to hero background
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const heroBackground = document.querySelector('.hero-bg-image');
            if (heroBackground) {
                heroBackground.style.transform = `translateY(${scrolled * 0.5}px)`;
            }
        });
    }

    function initSmoothScrolling() {
        // Add smooth scrolling for all anchor links
        document.addEventListener('click', function(e) {
            if (e.target.matches('a[href^="#"]')) {
                const href = e.target.getAttribute('href');
                if (href && href !== '#') {
                    const target = document.querySelector(href);
                    if (target) {
                        e.preventDefault();
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            }
        });

        // Handle features button click
        document.addEventListener('click', function(e) {
            if (e.target.matches('.btn[href="#features"]')) {
                e.preventDefault();
                const featuresSection = document.getElementById('features');
                if (featuresSection) {
                    featuresSection.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    }

    function initLoadingStates() {
        // Add loading states and animations
        document.addEventListener('mouseenter', function(e) {
            if (e.target.matches('.dashboard-widget, .feature-card, .service-card')) {
                e.target.style.transition = 'all 0.3s ease';
            }
        });

        // Handle widget refresh
        document.addEventListener('click', function(e) {
            if (e.target.matches('.dashboard-widget')) {
                const widget = e.target;
                widget.classList.add('loading');
                
                setTimeout(() => {
                    widget.classList.remove('loading');
                    updateWidgetData();
                }, 1000);
            }
        });
    }
});