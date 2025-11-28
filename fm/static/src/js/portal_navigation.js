/* Facilities Management Portal Navigation JavaScript */

document.addEventListener('DOMContentLoaded', function() {
    // Highlight active navigation link based on current URL
    function highlightActiveNavLink() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.facilities-nav .nav-link');
        
        navLinks.forEach(function(link) {
            // Remove active class from all links
            link.classList.remove('active');
            
            // Check if current path matches link href
            const linkHref = link.getAttribute('href');
            if (linkHref && currentPath === linkHref) {
                link.classList.add('active');
            }
            
            // Special handling for service request detail pages
            if (currentPath.startsWith('/my/service-request/') && linkHref === '/my/service-requests') {
                link.classList.add('active');
            }
            
            // Special handling for service catalog request pages
            if (currentPath.includes('/service-catalog/') && linkHref === '/my/service-catalog') {
                link.classList.add('active');
            }
        });
    }
    
    // Initialize active link highlighting
    highlightActiveNavLink();
    
    // Handle mobile menu toggle
    const navbarToggler = document.querySelector('.facilities-nav .navbar-toggler');
    const navbarCollapse = document.querySelector('.facilities-nav .navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            // Add smooth transition
            navbarCollapse.style.transition = 'all 0.3s ease';
        });
    }
    
    // Close mobile menu when clicking on a link
    const mobileNavLinks = document.querySelectorAll('.facilities-nav .nav-link');
    mobileNavLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            // Check if mobile menu is open
            if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                // Close the mobile menu
                const bsCollapse = new bootstrap.Collapse(navbarCollapse, {
                    toggle: false
                });
                bsCollapse.hide();
            }
        });
    });
    
    // Add smooth scrolling for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                e.preventDefault();
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading state to navigation links
    const navigationLinks = document.querySelectorAll('.facilities-nav .nav-link[href]');
    navigationLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            // Add loading class to the clicked link
            this.classList.add('loading');
            
            // Remove loading class after a short delay (in case page doesn't change)
            setTimeout(() => {
                this.classList.remove('loading');
            }, 2000);
        });
    });
});

// Add CSS for loading state
const style = document.createElement('style');
style.textContent = `
    .facilities-nav .nav-link.loading {
        opacity: 0.6;
        pointer-events: none;
    }
    
    .facilities-nav .nav-link.loading::after {
        content: '';
        display: inline-block;
        width: 12px;
        height: 12px;
        border: 2px solid #007bff;
        border-radius: 50%;
        border-top-color: transparent;
        animation: spin 1s linear infinite;
        margin-left: 8px;
    }
    
    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
`;
document.head.appendChild(style);
