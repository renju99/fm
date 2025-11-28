# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID
from datetime import datetime, timedelta

def create_demo_workorders(env):
    """Create demo work orders with current dates"""
    
    # Get or create demo records
    facility = env['facilities.facility'].search([('name', '=', 'Demo Facility')], limit=1)
    if not facility:
        facility = env['facilities.facility'].create({
            'name': 'Demo Facility',
            'address': '123 Demo Street, Demo City',
            'phone': '+1-555-0123',
            'email': 'demo@facility.com'
        })
    
    asset = env['facilities.asset'].search([('name', '=', 'Demo Asset 1')], limit=1)
    if not asset:
        asset = env['facilities.asset'].create({
            'name': 'Demo Asset 1',
            'asset_code': 'DEMO-001',
            'facility_id': facility.id
        })
    
    sla = env['facilities.sla'].search([('name', '=', 'Demo SLA')], limit=1)
    if not sla:
        sla = env['facilities.sla'].create({
            'name': 'Demo SLA',
            'response_time_hours': 24,
            'resolution_time_hours': 48
        })
    
    technician = env['hr.employee'].search([('name', '=', 'Demo Technician')], limit=1)
    if not technician:
        technician = env['hr.employee'].create({
            'name': 'Demo Technician',
            'work_email': 'technician@demo.com'
        })
    
    team = env['maintenance.team'].search([('name', '=', 'Demo Team')], limit=1)
    if not team:
        team = env['maintenance.team'].create({
            'name': 'Demo Team',
            'leader_id': technician.id
        })
    
    # Create work orders with current dates
    today = datetime.now().date()
    
    work_orders = [
        {
            'name': 'WO-DEMO-001',
            'work_order_type': 'preventive',
            'state': 'draft',
            'priority': '3',
            'start_date': today + timedelta(days=1),
            'end_date': today + timedelta(days=2),
            'estimated_duration': 4.0
        },
        {
            'name': 'WO-DEMO-002',
            'work_order_type': 'corrective',
            'state': 'in_progress',
            'priority': '4',
            'start_date': today,
            'end_date': today + timedelta(days=1),
            'estimated_duration': 2.0
        },
        {
            'name': 'WO-DEMO-003',
            'work_order_type': 'predictive',
            'state': 'assigned',
            'priority': '2',
            'start_date': today + timedelta(days=3),
            'end_date': today + timedelta(days=4),
            'estimated_duration': 6.0
        }
    ]
    
    for wo_data in work_orders:
        wo_data.update({
            'asset_id': asset.id,
            'sla_id': sla.id,
            'technician_id': technician.id,
            'maintenance_team_id': team.id
        })
        
        # Check if work order already exists
        existing = env['facilities.workorder'].search([('name', '=', wo_data['name'])], limit=1)
        if not existing:
            env['facilities.workorder'].create(wo_data)
            print(f"Created work order: {wo_data['name']}")
        else:
            print(f"Work order already exists: {wo_data['name']}")

def post_init_hook(env):
    """Post-install hook to create demo work orders"""
    create_demo_workorders(env)
