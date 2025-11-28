# -*- coding: utf-8 -*-

# Core facility and asset views
from . import building_views
from . import floor_views
from . import room_views
from . import facility_views
from . import asset_category_views
from . import asset_views
from . import asset_dashboard_views
from . import asset_calendar_views
from . import asset_maintenance_calendar_views
from . import asset_maintenance_schedule_views
from . import asset_maintenance_scheduled_actions
from . import asset_performance_views
from . import asset_performance_dashboard_views
from . import energy_performance_dashboard_views
from . import asset_disposal_wizard_views

# Maintenance work order views
from . import maintenance_workorder_views
from . import maintenance_workorder_improved_form
# from . import maintenance_workorder_error_views
# from . import maintenance_workorder_security_views
# from . import maintenance_workorder_simplified_views

from . import maintenance_workorder_assignment_views
from . import maintenance_workorder_calendar_views
from . import maintenance_workorder_kanban
from . import maintenance_workorder_mobile_form
from . import maintenance_workorder_part_line_views
from . import maintenance_workorder_permit_views
from . import maintenance_workorder_task_actions

# Job plan and team views
from . import maintenance_job_plan_views
from . import maintenance_team_views

# SLA and performance views
from . import sla_views
from . import technician_performance_dashboard_views

# Space booking views
from . import space_booking_views
from . import space_booking_analytics_views
from . import booking_template_views
from . import booking_reject_wizard_views

# Room and equipment views
from . import room_equipment_views

# Employee and HR views
from . import hr_employee_views
from . import hr_employee_tree_technician

# Product and stock views
from . import product_views
from . import stock_picking_inherit_views

# Energy Management Views
from . import energy_consumption_views
from . import utility_meter_views
from . import energy_alert_views
from . import energy_benchmark_views
from . import sustainability_report_views
from . import energy_cost_analysis_views
from . import energy_management_menus

# Vendor Management Views (Using Standard Odoo Purchase Module)
# Note: vendor_management_enhanced_views removed - using standard purchase module

# Wizard and utility views
from . import facilities_import_wizard_views
from . import assign_technician_wizard_view
from . import monthly_building_report_wizard_view
from . import monthly_building_report_wizard_action
from . import facility_report_wizard_view
from . import facility_report_wizard_action
from . import facility_manager_check_wizard_views
from . import workorder_reopen_wizard_views

# Report views
from . import maintenance_report_views

# Email templates
from . import email_templates

# Search and menu views
from . import facility_asset_search
from . import facility_asset_menus