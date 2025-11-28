# -*- coding: utf-8 -*-

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# ===============================
# Import all models in dependency order
# ===============================

# 1. Base/Configuration/Lookup Models (Least dependencies within module)
from . import hr_employee
from . import product
from . import maintenance_team
from . import menu_controller

# Vendor Management Integration (Standard Odoo Purchase Module)
# Note: Vendor management now uses standard Odoo purchase module
# Custom vendor enhancements removed to use standard functionality
# Note: lease model must be imported before partner and facility models that reference it
from . import lease
from . import partner
# maintenance_job_plan_task is defined in maintenance_job_plan.py, so don't import separately
from . import maintenance_job_plan    # Loads both job plan and its tasks

# 2. Core Infrastructure & Assets (Hierarchical, depends on basic Odoo models)
from . import building
from . import floor
from . import room
from . import facility
from . import asset_category
from . import asset_tag
from . import asset
from . import workorder_permit
from . import space_booking
from . import booking_template
from . import room_equipment
from . import booking_reject_wizard

# 3. Asset Performance (depends on asset)
from . import asset_performance
from . import asset_performance_dashboard

# 4. Energy Performance (depends on energy consumption)
from . import energy_performance_dashboard

# 4. Transactional Models (Depend on many of the above)
# Core maintenance work order model (streamlined) - DISABLED FOR NOW
# from . import maintenance_workorder_core
# from . import maintenance_workorder_mixins
# from . import maintenance_workorder_sla
# from . import maintenance_workorder_business
# from . import maintenance_workorder_performance
# from . import maintenance_workorder_error_handling
# from . import maintenance_workorder_security

# Legacy maintenance work order model (for backward compatibility)
from . import maintenance_workorder
from . import maintenance_workorder_assignment
from . import maintenance_workorder_part_line
from . import maintenance_workorder_task
from . import maintenance_job_plan_section
from . import maintenance_job_plan_task
from . import maintenance_job_plan
from . import maintenance_workorder_section
from . import stock_picking

from . import maintenance_escalation_log

# 5. Lease Management (already imported earlier before partner/facility models)

# 6. Scheduled Maintenance (Often depend on assets and work orders)
from . import asset_maintenance_schedule
from . import asset_depreciation

# SLA and Resource Utilization (NEW)
from . import sla
from . import workorder_sla
from . import resource_utilization

# Note: Old vendor management models removed - now using standard Odoo purchase module
# Old models: vendor_management, vendor_contract, vendor_performance
# Custom vendor enhancements removed: res_partner_vendor_enhancement, purchase_agreement_facilities_enhancement, vendor_performance_tracking
from . import workorder_sla_integration

# Energy Management Models
from . import energy_consumption
from . import utility_meter
from . import sustainability_report
from . import energy_cost_analysis
from . import energy_alert
from . import energy_benchmark
from . import asset_threshold
from . import asset_disposal_wizard
from . import facilities_import_wizard
from . import report_recipient

# Service Request System
from . import service_catalog
from . import service_contact
from . import service_document
from . import service_request

# Maintenance Contract (using standard Odoo features)
from . import maintenance_contract

# Financial Management Models
from . import multi_currency  # Import multi_currency first as it provides the mixin
from . import cost_center
from . import financial_budget
from . import budget_vs_actual_report_simple
from . import budget_dashboard  # New interactive budget dashboard
from . import financial_dashboard
from . import facilities_management_dashboard
from . import maintenance_analytics_dashboard

# Vendor Management Models (migrated to standard Odoo purchase module)
# Old imports removed: vendor_management, vendor_contract, vendor_performance
# Custom vendor enhancements removed: res_partner_vendor_enhancement, purchase_agreement_facilities_enhancement, vendor_performance_tracking

from . import safety_incident

# Package and Visitor Management Models
from . import package_management
from . import visitor_management

# Security Management Models - REMOVED

# Energy Management Models (removed duplicates - already imported above)

# Other integration/utilities
# Websocket customization disabled to fix connection issues
# from . import ir_websocket
from . import project_hider
from . import account_move_inherit

# ===============================
# Import wizards
# ===============================
from ..wizard import create_maintenance_schedule_wizard
from ..wizard import facility_manager_check_wizard

# ===============================
# Hooks
# ===============================

def pre_init_hook(cr):
    """Ensure clean slate for facilities_management module."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Running pre_init_hook for facilities_management...")
    try:
        cr.execute(
            """
            DELETE FROM ir_model WHERE model = 'facilities.facility';
            DELETE FROM ir_model_data WHERE model = 'ir.model' AND name LIKE 'model_facilities%';
            """
        )
        _logger.info("Cleaned up old facilities.facility model entries (if any).")
    except Exception as e:
        _logger.warning(f"Failed to run pre_init_hook cleanup: {e}")


def post_init_hook(env):
    """Ensure at least one SLA record exists for foreign key sanity and create sample data."""
    
    # Disable demo data for project modules to prevent installation issues
    try:
        project_modules = env['ir.module.module'].search([
            ('name', 'in', ['project', 'project_account', 'project_stock', 'website_project', 'project_todo']),
            ('state', '=', 'installed')
        ])
        for module in project_modules:
            module.demo = False
        _logger.info("Disabled demo data for project modules to prevent installation issues")
    except Exception as e:
        _logger.warning(f"Could not disable project demo data: {str(e)}")

    # Create default SLA records
    slas = env['facilities.sla'].create_default_sla_records()
    _logger.info("Ensured default SLA records exist after install/upgrade.")

    # Check if we should create sample work orders for better user experience
    try:
        # Only create sample data if no work orders exist at all
        existing_workorders = env['facilities.workorder'].search([('sla_id', '!=', False)], limit=1)
        if not existing_workorders and slas:
            # Create sample work orders for the first SLA to demonstrate functionality
            first_sla = slas[0] if slas else env['facilities.sla'].search([], limit=1)
            if first_sla:
                _logger.info(
                    f"Sample work orders setup completed for SLA {first_sla.name} to demonstrate functionality."
                )
    except Exception as e:
        _logger.warning(f"Failed to create sample work orders: {e}")

    _logger.info("Post-init hook completed successfully.")