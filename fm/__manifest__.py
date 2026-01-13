{
    'name': 'Facilities Management',
    'version': '19.0.1.2.11',
    'summary': 'Comprehensive Facility and Asset Management including Maintenance, Bookings, Analytics, and Energy Management',
    'description': """
Facility and Asset Management System

Features:
- Facilities, Buildings, Floors, Rooms with Google Maps integration
- Asset lifecycle tracking and depreciation
- Maintenance scheduling (preventive, corrective)
- Work order management, assignments, and SLAs
- Resource utilization and technician workload
- Space/Room booking system with conflict detection
- Bulk import/export functionality for CSV/Excel
- Advanced analytics and reporting
- Email notifications and reminders
- Mobile and portal views
- Tenant and landlord management with lease agreements
- Lease tracking, renewals, and expiration monitoring
- Property rental management and payment terms
- Financial management with budget allocation and cost centers
- Multi-currency support and financial reporting dashboards
- Vendor management integrated with standard Odoo purchase module
- Uses standard Odoo purchase functionality for vendor management
- Safety incident reporting and investigation system
- Energy Management Module with utility meter tracking
- Energy consumption monitoring and analysis
- Sustainability reporting and carbon footprint tracking
- Energy efficiency dashboards and performance metrics
- Integration with existing asset management system
""",
    'author': 'Your Name or Company',
    'website': 'https://yourcompany.com',
    'category': 'Operations/Facility Management',
    'depends': [
        'base',
        'mail',
        'hr',
        'product',
        'stock',
        'web',
        'account',
        'analytic',
        'purchase',
        'portal',
        'website',
    ],
    'external_dependencies': {
        'python': ['qrcode', 'Pillow', 'matplotlib'],
    },
    'data': [
        # Security
        'security/facilities_security_groups.xml',
        'security/hide_project_security.xml',
        'security/hide_link_tracker_security.xml',
        'security/hide_unrelated_menus_security.xml',

        # User Form Customization (must be loaded early)
        'views/res_users_views.xml',

        # Data
        'data/sequences.xml',
        'data/email_templates.xml',
        'data/facilities_email_templates.xml',
        'data/sla_configurations.xml',
        'data/maintenance_cron.xml',
        'data/predictive_parameters.xml',
        'data/space_booking_mail_template.xml',
        'data/space_booking_data.xml',
        'data/space_booking_enhanced_data.xml',
        'data/asset_threshold_cron.xml',
        'data/mail_activity_types.xml',
        'data/service_request_email_templates.xml',
        'data/service_request_demo.xml',
        'data/website_pages.xml',
        'data/hide_project_module.xml',
        'data/lease_sequences.xml',
        'data/lease_cron.xml',
        'data/lease_demo_data.xml',
        'data/lease_config_data.xml',
        'data/lease_email_template.xml',
        'data/facilities_lease_data.xml',
        'data/financial_sequences.xml',
        # 'data/performance_indexes.xml',
        'data/default_user_groups.xml',
        'data/energy_sequences.xml',
        'data/default_dashboard_data.xml',
        'data/package_visitor_sequences.xml',
        'data/package_visitor_email_templates.xml',

        # Reports
        'reports/maintenance_report.xml',
        'reports/monthly_building_report_pdf.xml',
        'reports/monthly_building_report_pdf_action.xml',
        'reports/workorder_maintenance_report.xml',
        'reports/facility_workorder_report.xml',
        'reports/asset_performance_dashboard_report.xml',
        'reports/asset_performance_standard_report.xml',
        'reports/energy_performance_dashboard_report.xml',
        'reports/safety_incident_report.xml',

        # Views - Core Facilities
        'views/facility_views.xml',
        'views/room_views.xml',
        'views/floor_views.xml',
        'views/building_views.xml',

        # Views - Assets
        'views/asset_calendar_views.xml',
        'views/asset_category_views.xml',
        'views/asset_dashboard_views.xml',
        'views/asset_performance_views.xml',
        'views/asset_performance_dashboard_views.xml',
        'views/space_booking_dashboard_views.xml',
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/asset_maintenance_scheduled_actions.xml',

        # Views - Asset Management
        'views/asset_disposal_wizard_views.xml',
        'views/facilities_import_wizard_views.xml',

        # Wizard Views (must be loaded before asset views that reference them)
        'wizard/create_maintenance_schedule_wizard_views.xml',
        'wizard/facility_manager_check_wizard_views.xml',
        'wizard/overwrite_workorder_wizard_views.xml',
        'wizard/generate_workorder_wizard_views.xml',
        'wizard/workorder_reopen_wizard_views.xml',
        'wizard/service_request_workorder_wizard_views.xml',
        'wizard/workorder_onhold_wizard_views.xml',
        'wizard/workorder_start_permit_wizard_views.xml',
        'wizard/package_collect_wizard_views.xml',
        'wizard/visitor_deny_wizard_views.xml',

        # Views - Maintenance
        'views/maintenance_team_views.xml',
        'views/maintenance_analytics_dashboards.xml',
        'views/maintenance_workorder_views.xml',
        'views/maintenance_workorder_improved_form.xml',
        'views/maintenance_workorder_planned_views.xml',
        'views/maintenance_workorder_responsive_form.xml',
        'views/maintenance_workorder_part_line_views.xml',
        'views/maintenance_workorder_permit_views.xml',
        'views/maintenance_workorder_kanban.xml',
        'views/maintenance_workorder_task_actions.xml',
        'views/maintenance_workorder_mobile_form.xml',
        'views/maintenance_workorder_assignment_views.xml',
        'views/maintenance_job_plan_views.xml',
        'views/maintenance_report_views.xml',
        'views/maintenance_escalation_log_views.xml',


        # Views - Other
        'views/sla_views.xml',
        'views/stock_picking_inherit_views.xml',
        'views/assign_technician_wizard_view.xml',
        'views/space_booking_views.xml',
        'views/space_booking_analytics_views.xml',
        'views/booking_template_views.xml',
        'views/room_equipment_views.xml',
        'views/booking_reject_wizard_views.xml',
        'views/facility_asset_search.xml',
        'views/monthly_building_report_wizard_action.xml',
        'views/monthly_building_report_wizard_view.xml',
        'views/facility_report_wizard_action.xml',
        'views/facility_report_wizard_view.xml',
        'views/report_recipient_views.xml',
        'views/technician_performance_dashboard_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_employee_tree_technician.xml',
        'views/product_views.xml',

        # Service Request Views
        'views/service_request_views.xml',
        'views/service_catalog_views.xml',
        'views/service_contact_views.xml',
        'views/service_document_views.xml',
        'views/portal_templates.xml',
        'views/portal_service_request_create_from_qr.xml',
        'views/website_templates.xml',
        'views/pricing_page_template.xml',
        'views/project_hider_views.xml',
        
        # Tenant & Landlord Management Views
        'views/tenant_views.xml',
        'views/landlord_views.xml',
        'views/lease_views.xml',
        
        # Maintenance Contract Views (using standard Odoo features)
        'views/maintenance_contract_views.xml',
        
        # Financial Management Views
        'views/financial_budget_views.xml',
        'views/cost_center_views.xml',
        # 'views/budget_vs_actual_report_views.xml',  # Temporarily commented out
        # 'views/budget_vs_actual_report_line_views.xml',  # Temporarily commented out
        'views/financial_dashboard_views.xml',
        'views/multi_currency_views.xml',
        
        # Vendor Management Views (Using Standard Odoo Purchase Module)
        # Note: vendor_management_enhanced_views.xml removed - using standard purchase module
        
        'views/safety_incident_views.xml',
        
        # Energy Management Views (must be loaded before menus that reference them)
        'views/utility_meter_views.xml',
        'views/energy_consumption_views.xml',
        'views/sustainability_report_views.xml',
        'views/energy_cost_analysis_views.xml',
        'views/energy_alert_views.xml',
        'views/energy_benchmark_views.xml',
        'views/energy_performance_dashboard_views.xml',
        
        # Views - Menus (must be loaded after views that define actions)
        'views/facility_asset_menus.xml',
        # Package and Visitor Management Views (must be after menus)
        'views/visitor_management_views.xml',
        'views/package_management_views.xml',
        'views/energy_management_menus.xml',

        # Asset Views (must be loaded after wizard views)
        'views/facility_asset_views.xml',
        
        # Security Access Control
        'security/ir.model.access.csv',
        # 'security/maintenance_workorder_security.xml',
        
        # Homepage Template
        'views/facilities_homepage_template.xml',
        
        
        # Budget vs Actual Report Views (after menus are loaded)
        'views/budget_vs_actual_report_simple_views.xml',
        'views/budget_dashboard_views.xml',  # New interactive budget dashboard
        
        # Facilities Management Dashboard Views
        'views/facilities_management_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm/static/src/css/facilities.css',
            'fm/static/src/css/facilities_management_dashboard.css',
            'fm/static/src/css/portal.css',
            'fm/static/src/css/maintenance_message_widget.css',
            'fm/static/src/css/asset_performance_dashboard.css',
            'fm/static/src/css/budget_dashboard.css',
            'fm/static/src/css/space_booking_dashboard.css',
            'fm/static/src/css/responsive_workorders.css',
            'fm/static/src/css/autofill_enhancements.css',
            'fm/static/src/css/workorder_calendar_simple.css',
            'fm/static/src/css/facilities_analytics_dashboard.css',
            ('include', 'web._assets_helpers'),
            'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
            'fm/static/src/js/dashboard_widgets.js',
            'fm/static/src/js/facilities_analytics_dashboard.js',
            'fm/static/src/js/asset_performance_dashboard_kpi.js',
            'fm/static/src/js/maintenance_analytics_dashboards.js',
            'fm/static/src/js/mobile_workorder.js',
            'fm/static/src/js/responsive_workorders.js',
            'fm/static/src/js/autofill_enhancements.js',
            # 'fm/static/src/js/menu_access_control.js',  # Removed: incompatible with Odoo 19, use security groups instead
            'fm/static/src/js/mobile_workorders_enhanced_action.js',
            'fm/static/src/js/maintenance_message_widget.js',
            'fm/static/src/js/asset_performance_dashboard.js',
            'fm/static/src/js/budget_dashboard.js',
            'fm/static/src/js/energy_performance_dashboard.js',
            'fm/static/src/js/space_booking_dashboard.js',
            'fm/static/src/js/workorder_calendar_simple.js',
            'fm/static/src/js/facilities_management_dashboard.js',
            'fm/static/src/xml/mobile_workorders_enhanced.xml',
            'fm/static/src/xml/facilities_management_dashboard.xml',
            'fm/static/src/xml/asset_performance_dashboard.xml',
            'fm/static/src/xml/facilities_analytics_dashboard.xml',
            'fm/static/src/xml/asset_performance_dashboard_kpi.xml',
            'fm/static/src/xml/budget_dashboard.xml',
            'fm/static/src/xml/maintenance_analytics_dashboards.xml',
            'fm/static/src/xml/*.xml',
        ],
        'web.assets_frontend': [
            'fm/static/src/css/portal.css',
            'fm/static/src/css/portal_navigation.css',
            'fm/static/src/css/facilities_homepage.css',
            'fm/static/src/js/facilities_homepage.js',
            'fm/static/src/js/portal_navigation.js',
        ],
    },
    'demo': [
        # Demo data files - only loaded with --demo or without-demo=False flag
        'demo/facility_demo.xml',
        'demo/energy_management_data.xml',
        'demo/safety_hse_demo_data.xml',
        'demo/partner_demo_data.xml',
        'demo/asset_demo_data.xml',
        'demo/asset_instances_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}