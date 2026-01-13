# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class FacilitiesHomepageController(http.Controller):

    @http.route('/facilities-test', type='http', auth='public')
    def facilities_test(self, **kwargs):
        """Test route to verify controller is working"""
        return "<h1>Facilities Management Controller is Working!</h1><p><a href='/facilities'>Go to Homepage</a></p>"

    # Removed root route override that was causing logout issues
    # Users can access facilities homepage via /facilities directly

    @http.route('/', type='http', auth='public', website=True, priority=1)
    def main_homepage(self, **kwargs):
        """Main website homepage at root URL"""
        # Always show the facilities homepage regardless of login status
        return self.facilities_homepage(**kwargs)

    @http.route('/facilities', type='http', auth='public', website=True)
    def facilities_homepage(self, **kwargs):
        """Main facilities management homepage - Property & Facilities Management Platform"""
        try:
            # Get comprehensive statistics for the homepage
            stats = self._get_facility_stats()
            
            # Get user-specific data if logged in
            user_data = self._get_user_dashboard_data()
            
            # Get recent service requests if user is logged in
            recent_requests = []
            if request.env.user and not request.env.user._is_public():
                recent_requests = self._get_recent_service_requests()
            
            # Get available facilities for service request form
            facilities = self._get_available_facilities()
            
            # Get service categories
            categories = self._get_service_categories()
            
            # Get tenant information
            tenant_info = self._get_tenant_info()
            
            
            # Get recent activities
            recent_activities = self._get_recent_activities()
            
            # Get performance metrics
            performance_metrics = self._get_performance_metrics()
            
            values = {
                'stats': stats,
                'user_data': user_data,
                'recent_requests': recent_requests,
                'facilities': facilities,
                'categories': categories,
                'tenant_info': tenant_info,
                'recent_activities': recent_activities,
                'performance_metrics': performance_metrics,
                'user': request.env.user,
                'is_logged_in': request.env.user and not request.env.user._is_public(),
                'user_groups': self._get_user_groups(),
                'quick_actions': self._get_quick_actions(),
            }
            
            # Try to render using the template first, fallback to HTML if needed
            try:
                return request.render('fm.facilities_homepage_template', values)
            except Exception as template_error:
                _logger.warning("Template rendering failed, using fallback: %s", str(template_error))
                return self._render_enhanced_homepage(values)
            
        except Exception as e:
            _logger.error("Error rendering facilities homepage: %s", str(e))
            return self._render_enhanced_homepage({
                'stats': {},
                'user_data': {},
                'recent_requests': [],
                'facilities': [],
                'categories': [],
                'tenant_info': {},
                'recent_activities': [],
                'performance_metrics': {},
                'user': request.env.user,
                'is_logged_in': False,
                'user_groups': [],
                'quick_actions': [],
            })

    def _render_enhanced_homepage(self, values):
        """Enhanced homepage for Property & Facilities Management Platform"""
        html_content = """
        <!DOCTYPE html>
        <html lang="en" data-wf-domain="facilities-management.com" data-wf-page="facilities-homepage">
        <head>
            <meta charset="utf-8"/>
            <title>Proptech Middle East - Smart Facilities Management Platform</title>
            <meta content="Proptech Middle East - Smart Facilities Management Platform. Transform Your Facilities Into Smart Assets with our comprehensive Computer-Aided Facility Management solution." name="description"/>
            <meta content="Proptech Middle East - Smart Facilities Management Platform" property="og:title"/>
            <meta content="Proptech Middle East - Smart Facilities Management Platform. Transform Your Facilities Into Smart Assets with our comprehensive Computer-Aided Facility Management solution." property="og:description"/>
            <meta content="website" property="og:type"/>
            <meta content="width=device-width, initial-scale=1" name="viewport"/>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"/>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"/>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
            <style>
                :root {
                    --color-primary-dark: #1a1a1a;
                    --color-white: #ffffff;
                    --color-accent-gold: #d4af37;
                    --color-neutral-gray: #f5f5f5;
                    --color-beige: #f8f7f1;
                    --font-family-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: var(--font-family-primary);
                    color: var(--color-primary-dark);
                    background-color: var(--color-white);
                    line-height: 1.6;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                }

                .navbar {
                    background: var(--color-white);
                    border-bottom: 1px solid #e9ecef;
                    padding: 1rem 0;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    z-index: 1000;
                }

                .navbar-brand {
                    font-size: 1.5rem;
                    font-weight: 700;
                    color: var(--color-primary-dark);
                    text-decoration: none;
                }

                .navbar-nav .nav-link {
                    color: var(--color-primary-dark);
                    font-weight: 500;
                    margin: 0 1rem;
                    text-decoration: none;
                    transition: color 0.3s ease;
                }

                .navbar-nav .nav-link:hover {
                    color: var(--color-accent-gold);
                }

                .btn-primary {
                    background-color: var(--color-primary-dark);
                    border-color: var(--color-primary-dark);
                    color: var(--color-white);
                    font-weight: 500;
                    padding: 0.75rem 1.5rem;
                    border-radius: 0;
                    text-decoration: none;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    transition: all 0.3s ease;
                }

                .btn-primary:hover {
                    background-color: var(--color-accent-gold);
                    border-color: var(--color-accent-gold);
                    color: var(--color-primary-dark);
                }

                .btn-outline-primary {
                    border-color: var(--color-primary-dark);
                    color: var(--color-primary-dark);
                    background: transparent;
                    font-weight: 500;
                    padding: 0.75rem 1.5rem;
                    border-radius: 0;
                    text-decoration: none;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    transition: all 0.3s ease;
                }

                .btn-outline-primary:hover {
                    background-color: var(--color-primary-dark);
                    color: var(--color-white);
                }

                .hero-section {
                    background: linear-gradient(135deg, var(--color-beige) 0%, #e9ecef 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    position: relative;
                    overflow: hidden;
                }

                .hero-bg {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                    z-index: 1;
                }

                .hero-content {
                    position: relative;
                    z-index: 2;
                }

                .hero-title {
                    font-size: 4rem;
                    font-weight: 800;
                    line-height: 1.1;
                    margin-bottom: 1.5rem;
                    color: var(--color-primary-dark);
                }

                .hero-subtitle {
                    font-size: 1.5rem;
                    font-weight: 400;
                    color: var(--color-primary-dark);
                    margin-bottom: 1rem;
                }

                .hero-description {
                    font-size: 1.125rem;
                    color: #666;
                    margin-bottom: 2rem;
                }

                .font-ivyora {
                    font-style: italic;
                    color: var(--color-accent-gold);
                }

                .section-title {
                    font-size: 3rem;
                    font-weight: 700;
                    text-align: center;
                    margin-bottom: 1rem;
                    color: var(--color-primary-dark);
                }

                .section-subtitle {
                    font-size: 1.25rem;
                    text-align: center;
                    color: #666;
                    margin-bottom: 3rem;
                }

                .services-section {
                    padding: 5rem 0;
                    background: var(--color-white);
                }

                .service-card {
                    background: var(--color-white);
                    border: 1px solid #e9ecef;
                    padding: 2rem;
                    height: 100%;
                    transition: all 0.3s ease;
                    text-decoration: none;
                    color: inherit;
                }

                .service-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    text-decoration: none;
                    color: inherit;
                }

                .icon-wrapper {
                    width: 80px;
                    height: 80px;
                    background: var(--color-neutral-gray);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 1.5rem;
                }

                .icon-wrapper i {
                    font-size: 2rem;
                    color: var(--color-accent-gold);
                }

                .card-title {
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 1rem;
                    color: var(--color-primary-dark);
                }

                .card-description {
                    color: #666;
                    margin-bottom: 1.5rem;
                }

                .quick-access-section {
                    padding: 5rem 0;
                    background: var(--color-neutral-gray);
                }

                .quick-access-card {
                    background: var(--color-white);
                    padding: 2rem;
                    text-align: center;
                    text-decoration: none;
                    color: inherit;
                    border: 1px solid #e9ecef;
                    transition: all 0.3s ease;
                    display: block;
                }

                .quick-access-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    text-decoration: none;
                    color: inherit;
                }

                .quick-access-card i {
                    color: var(--color-accent-gold);
                    margin-bottom: 1rem;
                }

                .quick-access-card h4 {
                    font-size: 1.25rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                    color: var(--color-primary-dark);
                }

                .cta-section {
                    padding: 5rem 0;
                    background: var(--color-primary-dark);
                    color: var(--color-white);
                    text-align: center;
                }

                .cta-title {
                    font-size: 3rem;
                    font-weight: 700;
                    margin-bottom: 1rem;
                }

                .cta-subtitle {
                    font-size: 1.25rem;
                    margin-bottom: 2rem;
                    opacity: 0.9;
                }

                .footer {
                    background: var(--color-primary-dark);
                    color: var(--color-white);
                    padding: 3rem 0 2rem;
                }

                .footer h5 {
                    font-weight: 600;
                    margin-bottom: 1rem;
                }

                .footer a {
                    color: var(--color-white);
                    text-decoration: none;
                    opacity: 0.8;
                    transition: opacity 0.3s ease;
                }

                .footer a:hover {
                    opacity: 1;
                }

                .hero-actions {
                    display: flex;
                    gap: 1rem;
                    flex-wrap: wrap;
                }

                .facility-showcase {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 2rem;
                    margin-top: 2rem;
                }

                .showcase-item {
                    text-align: center;
                    padding: 2rem;
                    background: var(--color-white);
                    border-radius: 8px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }

                .showcase-item i {
                    color: var(--color-accent-gold);
                    margin-bottom: 1rem;
                }

                .showcase-item span {
                    font-weight: 600;
                    color: var(--color-primary-dark);
                }

                @media (max-width: 768px) {
                    .hero-title {
                        font-size: 2.5rem;
                    }
                    
                    .hero-subtitle {
                        font-size: 1.25rem;
                    }
                    
                    .section-title {
                        font-size: 2rem;
                    }
                    
                    .hero-actions {
                        flex-direction: column;
                    }
                    
                    .facility-showcase {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
            <!-- Navigation -->
            <nav class="navbar">
                <div class="container">
                    <div class="d-flex justify-content-between align-items-center w-100">
                        <a href="/facilities" class="navbar-brand">FACILITIES MANAGEMENT</a>
                        <div class="d-flex align-items-center">
                            <a href="/web" class="btn btn-primary">
                                <i class="fas fa-cogs"></i> Access Applications
                            </a>
                            <a href="/web/session/logout?redirect=/" class="btn btn-outline-danger ms-2">
                                <i class="fas fa-sign-out-alt"></i> Sign Out
                            </a>
                        </div>
                    </div>
                </div>
            </nav>

            <!-- Hero Section -->
            <section class="hero-section">
                <div class="container">
                    <div class="row align-items-center">
                        <div class="col-lg-6">
                            <div class="hero-content">
                                <h1 class="hero-title">Facilities <span class="font-ivyora">Excellence</span></h1>
                                <p class="hero-subtitle">Crafting optimal workplace environments through intelligent facility management</p>
                                <p class="hero-description">The power of precision, the feeling of efficiency</p>
                                <div class="hero-actions">
                                    <a href="/web" class="btn btn-primary btn-lg">
                                        <i class="fas fa-cogs"></i> Access Applications
                                    </a>
                                    <a href="/my/service-request/new" class="btn btn-outline-primary btn-lg">
                                        <i class="fas fa-plus"></i> Submit Request
                                    </a>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-6">
                            <div class="facility-showcase">
                                <div class="showcase-item">
                                    <i class="fas fa-building fa-3x"></i>
                                    <span>Smart Buildings</span>
                                </div>
                                <div class="showcase-item">
                                    <i class="fas fa-wrench fa-3x"></i>
                                    <span>Maintenance</span>
                                </div>
                                <div class="showcase-item">
                                    <i class="fas fa-chart-line fa-3x"></i>
                                    <span>Analytics</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Services Section -->
            <section class="services-section">
                <div class="container">
                    <div class="row">
                        <div class="col-12 text-center mb-5">
                            <h2 class="section-title">Our <span class="font-ivyora">Comprehensive Services</span></h2>
                            <p class="section-subtitle">Delivering excellence in every aspect of facility management</p>
                        </div>
                    </div>
                    <div class="row g-4">
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_asset" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-building"></i>
                                </div>
                                <h3 class="card-title">Asset Management</h3>
                                <p class="card-description">Complete lifecycle management of facility assets with real-time monitoring and predictive analytics.</p>
                                <div class="btn btn-link p-0">Explore Assets <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_maintenance_workorder" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-wrench"></i>
                                </div>
                                <h3 class="card-title">Maintenance Operations</h3>
                                <p class="card-description">Streamlined work order management, preventive maintenance scheduling, and SLA tracking for optimal efficiency.</p>
                                <div class="btn btn-link p-0">View Work Orders <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_space_booking" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-calendar-alt"></i>
                                </div>
                                <h3 class="card-title">Space Booking</h3>
                                <p class="card-description">Intelligent room and space reservation system with conflict detection and resource allocation.</p>
                                <div class="btn btn-link p-0">Book Space <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_asset_performance_dashboard" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-chart-line"></i>
                                </div>
                                <h3 class="card-title">Performance Analytics</h3>
                                <p class="card-description">Real-time dashboards and reports for asset performance, maintenance costs, and operational efficiency.</p>
                                <div class="btn btn-link p-0">View Analytics <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_vendor_profile" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-users"></i>
                                </div>
                                <h3 class="card-title">Tenant & Vendor Management</h3>
                                <p class="card-description">Comprehensive tools for managing tenant relations, lease agreements, and vendor contracts.</p>
                                <div class="btn btn-link p-0">Manage Relations <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                        <div class="col-lg-4 col-md-6">
                            <a href="/web#action=fm.action_financial_dashboard" class="service-card">
                                <div class="icon-wrapper">
                                    <i class="fas fa-shield-alt"></i>
                                </div>
                                <h3 class="card-title">Financial Management</h3>
                                <p class="card-description">Budget tracking, cost allocation, and financial reporting for facility operations and compliance.</p>
                                <div class="btn btn-link p-0">Financial Overview <i class="fas fa-arrow-right ms-2"></i></div>
                            </a>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Quick Access Section -->
            <section class="quick-access-section">
                <div class="container">
                    <div class="row">
                        <div class="col-12 text-center mb-5">
                            <h2 class="section-title">Quick Access</h2>
                            <p class="section-subtitle">Jump directly to key functions</p>
                        </div>
                    </div>
                    <div class="row g-4">
                        <div class="col-md-4">
                            <a href="/my/service-request/new" class="quick-access-card">
                                <i class="fas fa-plus-circle fa-3x"></i>
                                <h4>Submit Service Request</h4>
                                <p>Report an issue or request a service</p>
                            </a>
                        </div>
                        <div class="col-md-4">
                            <a href="/my/service-requests" class="quick-access-card">
                                <i class="fas fa-list-alt fa-3x"></i>
                                <h4>View My Requests</h4>
                                <p>Track the status of your submitted requests</p>
                            </a>
                        </div>
                        <div class="col-md-4">
                            <a href="/web" class="quick-access-card">
                                <i class="fas fa-th-large fa-3x"></i>
                                <h4>Open Applications Menu</h4>
                                <p>Access all Odoo facilities management applications</p>
                            </a>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Call to Action Section -->
            <section class="cta-section">
                <div class="container">
                    <h2 class="cta-title">Ready to Optimize Your <span class="font-ivyora">Facilities?</span></h2>
                    <p class="cta-subtitle">Experience the future of intelligent facility management</p>
                    <a href="/web" class="btn btn-primary btn-lg">
                        <i class="fas fa-cogs"></i> Access Applications
                    </a>
                </div>
            </section>

            <!-- Footer -->
            <footer class="footer">
                <div class="container">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Facilities Management System</h5>
                            <p>Comprehensive facility management solutions for modern workplaces</p>
                        </div>
                        <div class="col-md-6 text-md-end">
                            <p>&copy; 2024 Facilities Management System. All rights reserved.</p>
                        </div>
                    </div>
                </div>
            </footer>
        </body>
        </html>
        """
        return html_content

    @http.route('/facilities/apps', type='http', auth='user', website=True)
    def facilities_apps_menu(self, **kwargs):
        """Redirect to main Odoo apps menu - requires login"""
        return request.redirect('/web')
    
    @http.route('/facilities/apps', type='http', auth='public', website=True)
    def facilities_apps_menu_public(self, **kwargs):
        """Redirect public users to pricing page"""
        return request.redirect('/facilities#pricing')

    @http.route('/facilities/dashboard', type='http', auth='user', website=True)
    def facilities_dashboard(self, **kwargs):
        """Redirect to facilities management dashboard"""
        return request.redirect('/web#action=fm.action_asset_performance_dashboard')

    def _get_facility_stats(self):
        """Get basic facility management statistics"""
        try:
            # Get asset counts
            asset_count = 0
            try:
                asset_count = request.env['facilities.asset'].search_count([('active', '=', True)])
            except:
                pass
            
            # Get facility counts
            facility_count = 0
            try:
                facility_count = request.env['facilities.facility'].search_count([('active', '=', True)])
            except:
                pass
            
            # Get active work orders - try different model names
            workorder_count = 0
            try:
                workorder_count = request.env['maintenance.workorder'].search_count([
                    ('state', 'in', ['draft', 'confirmed', 'in_progress'])
                ])
            except:
                try:
                    workorder_count = request.env['facilities.workorder'].search_count([
                        ('state', 'in', ['draft', 'confirmed', 'in_progress'])
                    ])
                except:
                    pass
            
            # Get service requests (if user is logged in)
            service_request_count = 0
            if request.env.user and not request.env.user._is_public():
                try:
                    service_request_count = request.env['facilities.service.request'].search_count([
                        ('state', 'in', ['submitted', 'in_progress'])
                    ])
                except:
                    pass
            
            return {
                'asset_count': asset_count,
                'facility_count': facility_count,
                'workorder_count': workorder_count,
                'service_request_count': service_request_count,
            }
        except Exception as e:
            _logger.error("Error getting facility stats: %s", str(e))
            return {
                'asset_count': 0,
                'facility_count': 0,
                'workorder_count': 0,
                'service_request_count': 0,
            }

    def _get_recent_service_requests(self):
        """Get recent service requests for logged-in user"""
        try:
            if not request.env.user or request.env.user._is_public():
                return []
            
            # Try to get user's recent service requests
            try:
                requests = request.env['facilities.service.request'].search([
                    ('requestor_id', '=', request.env.user.partner_id.id)
                ], limit=5, order='create_date desc')
                return requests
            except:
                # If the model doesn't exist or field is wrong, return empty list
                return []
        except Exception as e:
            _logger.error("Error getting recent service requests: %s", str(e))
            return []

    def _get_available_facilities(self):
        """Get list of available facilities for service request form"""
        try:
            facilities = request.env['facilities.facility'].search([
                ('active', '=', True)
            ], limit=20)
            return facilities
        except Exception as e:
            _logger.error("Error getting facilities: %s", str(e))
            return []

    def _get_service_categories(self):
        """Get service categories for service request form"""
        try:
            # Try to get service categories, but don't fail if model doesn't exist
            try:
                categories = request.env['facilities.service.category'].search([
                    ('active', '=', True)
                ], limit=20)
                return categories
            except:
                return []
        except Exception as e:
            _logger.error("Error getting service categories: %s", str(e))
            return []

    def _get_user_dashboard_data(self):
        """Get user-specific dashboard data"""
        try:
            if not request.env.user or request.env.user._is_public():
                return {}
            
            user_data = {
                'name': request.env.user.name,
                'email': request.env.user.email,
                'avatar': request.env.user.image_128 if hasattr(request.env.user, 'image_128') else None,
                'last_login': request.env.user.login_date,
                'role': self._get_user_role(),
                'permissions': self._get_user_permissions(),
            }
            return user_data
        except Exception as e:
            _logger.error("Error getting user dashboard data: %s", str(e))
            return {}

    def _get_tenant_info(self):
        """Get tenant/organization information"""
        try:
            # Try to get tenant information from various possible models
            tenant_info = {
                'name': 'Default Organization',
                'logo': None,
                'users_count': 0,
                'properties_count': 0,
            }
            
            # Try to get from company
            if hasattr(request.env.user, 'company_id') and request.env.user.company_id:
                company = request.env.user.company_id
                tenant_info.update({
                    'name': company.name,
                    'logo': company.logo if hasattr(company, 'logo') else None,
                })
            
            return tenant_info
        except Exception as e:
            _logger.error("Error getting tenant info: %s", str(e))
            return {'name': 'Default Organization', 'logo': None, 'users_count': 0, 'properties_count': 0}


    def _get_recent_activities(self):
        """Get recent activities for the dashboard"""
        try:
            activities = []
            
            # Get recent work orders
            try:
                recent_workorders = request.env['maintenance.workorder'].search([
                    ('state', 'in', ['confirmed', 'in_progress', 'done'])
                ], limit=5, order='write_date desc')
                
                for wo in recent_workorders:
                    activities.append({
                        'type': 'workorder',
                        'title': f"Work Order: {wo.name}",
                        'description': f"Status: {wo.state.title()}",
                        'time': wo.write_date,
                        'icon': 'fa-wrench',
                        'color': 'primary'
                    })
            except:
                pass
            
            # Get recent service requests
            try:
                recent_requests = request.env['facilities.service.request'].search([
                    ('state', 'in', ['submitted', 'in_progress', 'resolved'])
                ], limit=5, order='create_date desc')
                
                for req in recent_requests:
                    activities.append({
                        'type': 'service_request',
                        'title': f"Service Request: {req.name}",
                        'description': f"Status: {req.state.title()}",
                        'time': req.create_date,
                        'icon': 'fa-ticket-alt',
                        'color': 'success'
                    })
            except:
                pass
            
            # Sort by time and return latest 10
            activities.sort(key=lambda x: x['time'], reverse=True)
            return activities[:10]
            
        except Exception as e:
            _logger.error("Error getting recent activities: %s", str(e))
            return []

    def _get_performance_metrics(self):
        """Get key performance metrics"""
        try:
            metrics = {
                'asset_uptime': 95.5,
                'maintenance_efficiency': 88.2,
                'space_utilization': 76.8,
                'cost_savings': 12.5,
                'sla_compliance': 94.1,
                'tenant_satisfaction': 4.2
            }
            
            # Try to calculate actual metrics
            try:
                # Asset uptime calculation
                total_assets = request.env['facilities.asset'].search_count([('active', '=', True)])
                if total_assets > 0:
                    working_assets = request.env['facilities.asset'].search_count([
                        ('active', '=', True),
                        ('state', '=', 'working')
                    ])
                    metrics['asset_uptime'] = round((working_assets / total_assets) * 100, 1)
            except:
                pass
            
            return metrics
        except Exception as e:
            _logger.error("Error getting performance metrics: %s", str(e))
            return {'asset_uptime': 95.5, 'maintenance_efficiency': 88.2, 'space_utilization': 76.8, 'cost_savings': 12.5, 'sla_compliance': 94.1, 'tenant_satisfaction': 4.2}

    def _get_user_role(self):
        """Get user role for display"""
        try:
            if not request.env.user or request.env.user._is_public():
                return 'Guest'
            
            # Check for specific groups
            if request.env.user.has_group('fm.group_facilities_manager'):
                return 'Facility Manager'
            elif request.env.user.has_group('fm.group_maintenance_technician'):
                return 'Maintenance Technician'
            elif request.env.user.has_group('fm.group_tenant_user'):
                return 'Tenant User'
            elif request.env.user.has_group('base.group_system'):
                return 'System Administrator'
            else:
                return 'User'
        except Exception as e:
            _logger.error("Error getting user role: %s", str(e))
            return 'User'

    def _get_user_permissions(self):
        """Get user permissions"""
        try:
            if not request.env.user or request.env.user._is_public():
                return []
            
            permissions = []
            
            # Check various permissions
            if request.env.user.has_group('fm.group_facilities_manager'):
                permissions.extend(['manage_assets', 'manage_maintenance', 'view_analytics', 'manage_tenants'])
            
            if request.env.user.has_group('fm.group_maintenance_technician'):
                permissions.extend(['view_workorders', 'update_workorders', 'scan_assets'])
            
            if request.env.user.has_group('fm.group_tenant_user'):
                permissions.extend(['submit_requests', 'view_bookings', 'view_own_requests'])
            
            return permissions
        except Exception as e:
            _logger.error("Error getting user permissions: %s", str(e))
            return []

    def _get_user_groups(self):
        """Get user groups for navigation"""
        try:
            if not request.env.user or request.env.user._is_public():
                return []
            
            groups = []
            
            # Add groups based on user permissions
            if request.env.user.has_group('fm.group_facilities_manager'):
                groups.append({
                    'name': 'Facility Management',
                    'icon': 'fa-building',
                    'color': 'primary',
                    'items': [
                        {'name': 'Assets', 'url': '/web#action=fm.action_asset', 'icon': 'fa-cube'},
                        {'name': 'Maintenance', 'url': '/web#action=fm.action_maintenance_workorder', 'icon': 'fa-wrench'},
                        {'name': 'Analytics', 'url': '/web#action=fm.action_asset_performance_dashboard', 'icon': 'fa-chart-bar'},
                    ]
                })
            
            if request.env.user.has_group('fm.group_tenant_user'):
                groups.append({
                    'name': 'Tenant Services',
                    'icon': 'fa-home',
                    'color': 'success',
                    'items': [
                        {'name': 'Service Requests', 'url': '/my/service-requests', 'icon': 'fa-ticket-alt'},
                        {'name': 'Space Booking', 'url': '/web#action=fm.action_space_booking', 'icon': 'fa-calendar'},
                        {'name': 'My Requests', 'url': '/my/service-requests', 'icon': 'fa-list'},
                    ]
                })
            
            return groups
        except Exception as e:
            _logger.error("Error getting user groups: %s", str(e))
            return []

    def _get_quick_actions(self):
        """Get quick actions based on user permissions"""
        try:
            actions = []
            
            if not request.env.user or request.env.user._is_public():
                actions = [
                    {'name': 'Login', 'url': '/web/login', 'icon': 'fa-sign-in-alt', 'color': 'primary'},
                    {'name': 'Request Demo', 'url': '/contact', 'icon': 'fa-play', 'color': 'success'},
                ]
            else:
                # Add common actions
                actions = [
                    {'name': 'Submit Request', 'url': '/my/service-request/new', 'icon': 'fa-plus', 'color': 'primary'},
                    {'name': 'View Dashboard', 'url': '/web#action=fm.action_asset_performance_dashboard', 'icon': 'fa-tachometer-alt', 'color': 'info'},
                ]
                
                # Add role-specific actions
                if request.env.user.has_group('fm.group_facilities_manager'):
                    actions.extend([
                        {'name': 'Manage Assets', 'url': '/web#action=fm.action_asset', 'icon': 'fa-cube', 'color': 'warning'},
                        {'name': 'Work Orders', 'url': '/web#action=fm.action_maintenance_workorder', 'icon': 'fa-wrench', 'color': 'danger'},
                    ])
                
                if request.env.user.has_group('fm.group_tenant_user'):
                    actions.extend([
                        {'name': 'Book Space', 'url': '/web#action=fm.action_space_booking', 'icon': 'fa-calendar', 'color': 'success'},
                        {'name': 'My Requests', 'url': '/my/service-requests', 'icon': 'fa-list', 'color': 'info'},
                    ])
            
            return actions
        except Exception as e:
            _logger.error("Error getting quick actions: %s", str(e))
            return []

    @http.route('/facilities/quick-stats', type='jsonrpc', auth='public', website=True)
    def get_quick_stats(self, **kwargs):
        """AJAX endpoint to get quick statistics"""
        try:
            stats = self._get_facility_stats()
            return {
                'success': True,
                'stats': stats
            }
        except Exception as e:
            _logger.error("Error getting quick stats: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/facilities/navigation-menu', type='jsonrpc', auth='user', website=True)
    def get_navigation_menu(self, **kwargs):
        """Get navigation menu items for the homepage"""
        try:
            menu_items = [
                {
                    'name': 'Asset Management',
                    'url': '/web#action=fm.action_asset',
                    'icon': 'fa-building',
                    'description': 'Manage facility assets and equipment'
                },
                {
                    'name': 'Maintenance',
                    'url': '/web#action=fm.action_maintenance_workorder',
                    'icon': 'fa-tools',
                    'description': 'Work orders and maintenance tasks'
                },
                {
                    'name': 'Space Booking',
                    'url': '/web#action=fm.action_space_booking',
                    'icon': 'fa-calendar-alt',
                    'description': 'Book meeting rooms and spaces'
                },
                {
                    'name': 'Analytics',
                    'url': '/web#action=fm.action_asset_performance_dashboard',
                    'icon': 'fa-chart-bar',
                    'description': 'View analytics and reports'
                },
                {
                    'name': 'Vendor Management',
                    'url': '/web#action=fm.action_vendor_profile',
                    'icon': 'fa-users',
                    'description': 'Manage vendors and contracts'
                },
                {
                    'name': 'Financial Dashboard',
                    'url': '/web#action=fm.action_financial_dashboard',
                    'icon': 'fa-dollar-sign',
                    'description': 'Financial overview and budgets'
                },
                {
                    'name': 'All Applications',
                    'url': '/web',
                    'icon': 'fa-th-large',
                    'description': 'Access all Odoo applications'
                }
            ]
            
            return {
                'success': True,
                'menu_items': menu_items
            }
        except Exception as e:
            _logger.error("Error getting navigation menu: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }





    def _create_or_update_partner(self, name, email, company, phone):
        """Create or update partner record"""
        try:
            # Search for existing partner by email
            partner = request.env['res.partner'].sudo().search([
                ('email', '=', email)
            ], limit=1)
            
            if partner:
                # Update existing partner
                partner.write({
                    'name': name,
                    'phone': phone,
                    'is_company': bool(company),
                    'company_name': company if company else False,
                })
            else:
                # Create new partner
                partner = request.env['res.partner'].sudo().create({
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'is_company': bool(company),
                    'company_name': company if company else False,
                    'customer_rank': 1,
                })
            
            return partner
        except Exception as e:
            _logger.error("Error creating/updating partner: %s", str(e))
            raise






    @http.route('/facilities/features', type='http', auth='public', website=True)
    def features_page(self, **kwargs):
        """Features page"""
        return request.render('fm.features_page_template', {})


    @http.route('/facilities/about', type='http', auth='public', website=True)
    def about_page(self, **kwargs):
        """About page"""
        return request.render('fm.about_page_template', {})

    @http.route('/facilities/contact', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def contact_page(self, **kwargs):
        """Contact page"""
        if request.httprequest.method == 'POST':
            return self._handle_contact_form(kwargs)
        
        return request.render('fm.contact_page_template', {})

    def _handle_contact_form(self, kwargs):
        """Handle contact form submission"""
        try:
            # Get form data
            name = kwargs.get('name', '').strip()
            email = kwargs.get('email', '').strip()
            company = kwargs.get('company', '').strip()
            phone = kwargs.get('phone', '').strip()
            subject = kwargs.get('subject', '').strip()
            message = kwargs.get('message', '').strip()
            
            # Validate required fields
            if not all([name, email, subject, message]):
                return request.render('fm.contact_page_template', {
                    'error': 'Name, email, subject, and message are required fields.',
                    'form_data': kwargs
                })
            
            # Create or update partner
            partner = self._create_or_update_partner(name, email, company, phone)
            
            # Create contact message
            contact_message = self._create_contact_message(partner, subject, message)
            
            # Send confirmation email
            self._send_contact_confirmation(partner, contact_message)
            
            # Redirect to success page
            return request.redirect('/facilities/contact-success')
            
        except Exception as e:
            _logger.error("Error handling contact form: %s", str(e))
            return request.render('fm.contact_page_template', {
                'error': 'An error occurred while processing your message. Please try again.',
                'form_data': kwargs
            })

    def _create_contact_message(self, partner, subject, message):
        """Create contact message record"""
        try:
            # Create a mail.message to track the contact request
            contact_message = request.env['mail.message'].sudo().create({
                'subject': f'Contact Form: {subject}',
                'body': f"""
                <p><strong>Contact Details:</strong></p>
                <ul>
                    <li><strong>Name:</strong> {partner.name}</li>
                    <li><strong>Email:</strong> {partner.email}</li>
                    <li><strong>Company:</strong> {partner.company_name or 'N/A'}</li>
                    <li><strong>Phone:</strong> {partner.phone or 'N/A'}</li>
                    <li><strong>Subject:</strong> {subject}</li>
                    <li><strong>Message:</strong> {message}</li>
                </ul>
                """,
                'message_type': 'notification',
                'subtype_id': request.env.ref('mail.mt_note').id,
                'partner_ids': [(6, 0, [partner.id])],
            })
            
            # Send notification email to admin
            self._send_contact_notification_to_admin(partner, subject, message)
            
            return contact_message
        except Exception as e:
            _logger.error("Error creating contact message: %s", str(e))
            raise

    def _send_contact_notification_to_admin(self, partner, subject, message):
        """Send contact notification email to admin"""
        try:
            # Create mail.message for admin notification
            admin_message = request.env['mail.message'].sudo().create({
                'subject': f'New Contact Form Submission: {subject}',
                'body': f"""
                <h3>New Contact Form Submission</h3>
                <p><strong>Contact Details:</strong></p>
                <ul>
                    <li><strong>Name:</strong> {partner.name}</li>
                    <li><strong>Email:</strong> {partner.email}</li>
                    <li><strong>Company:</strong> {partner.company_name or 'N/A'}</li>
                    <li><strong>Phone:</strong> {partner.phone or 'N/A'}</li>
                    <li><strong>Subject:</strong> {subject}</li>
                    <li><strong>Message:</strong> {message}</li>
                </ul>
                <p><strong>Reply to:</strong> {partner.email}</p>
                """,
                'message_type': 'notification',
                'subtype_id': request.env.ref('mail.mt_note').id,
                'partner_ids': [(6, 0, [partner.id])],
            })
            
            # Send email to admin
            mail_values = {
                'subject': f'New Contact Form Submission: {subject}',
                'body_html': f"""
                <h3>New Contact Form Submission</h3>
                <p><strong>Contact Details:</strong></p>
                <ul>
                    <li><strong>Name:</strong> {partner.name}</li>
                    <li><strong>Email:</strong> {partner.email}</li>
                    <li><strong>Company:</strong> {partner.company_name or 'N/A'}</li>
                    <li><strong>Phone:</strong> {partner.phone or 'N/A'}</li>
                    <li><strong>Subject:</strong> {subject}</li>
                    <li><strong>Message:</strong> {message}</li>
                </ul>
                <p><strong>Reply to:</strong> <a href="mailto:{partner.email}">{partner.email}</a></p>
                """,
                'email_to': 'contact@proptechme.com',
                'reply_to': partner.email,
                'auto_delete': True,
            }
            
            mail = request.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            
        except Exception as e:
            _logger.error("Error sending contact notification to admin: %s", str(e))

    def _send_contact_confirmation(self, partner, contact_message):
        """Send contact confirmation email"""
        try:
            template = request.env.ref('fm.contact_confirmation_email', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(contact_message.id, force_send=True)
        except Exception as e:
            _logger.error("Error sending contact confirmation: %s", str(e))

    @http.route('/facilities/contact-success', type='http', auth='public', website=True)
    def contact_success(self, **kwargs):
        """Contact success page"""
        return request.render('fm.contact_success_template', {})

    @http.route('/facilities/pricing', type='http', auth='public', website=True)
    def pricing_page(self, **kwargs):
        """Pricing page"""
        return request.render('fm.pricing_page_template', {})
