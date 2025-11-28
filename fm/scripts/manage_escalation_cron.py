#!/usr/bin/env python3
"""
SLA Escalation Cron Management Script

This script helps manage the SLA escalation cron job in the facilities management module.
It can be used to enable/disable the escalation cron job and check its status.

Usage:
    python manage_escalation_cron.py --action status
    python manage_escalation_cron.py --action enable
    python manage_escalation_cron.py --action disable
    python manage_escalation_cron.py --action test
"""

import argparse
import sys
import os

# Add the Odoo path to sys.path
sys.path.insert(0, '/home/ranjith/odoo/odoo-18.0')

def get_odoo_env():
    """Get Odoo environment"""
    try:
        import odoo
        from odoo import api, SUPERUSER_ID
        
        # Initialize Odoo
        odoo.cli.server.server()
        
        # Get the registry
        registry = odoo.registry('odoo')
        
        # Get the environment
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            return env
    except Exception as e:
        print(f"Error initializing Odoo: {e}")
        return None

def get_escalation_cron(env):
    """Get the escalation cron job"""
    try:
        cron_job = env['ir.cron'].search([
            ('name', '=', 'Auto Escalate Maintenance Work Orders')
        ], limit=1)
        return cron_job
    except Exception as e:
        print(f"Error finding escalation cron job: {e}")
        return None

def check_status(env):
    """Check the status of the escalation cron job"""
    cron_job = get_escalation_cron(env)
    if not cron_job:
        print("❌ Escalation cron job not found!")
        return False
    
    print("📊 SLA Escalation Cron Job Status:")
    print(f"   Name: {cron_job.name}")
    print(f"   Active: {'✅ Yes' if cron_job.active else '❌ No'}")
    print(f"   Model: {cron_job.model_id.model}")
    print(f"   Interval: {cron_job.interval_number} {cron_job.interval_type}")
    print(f"   Next Run: {cron_job.nextcall}")
    print(f"   Last Run: {cron_job.lastcall}")
    
    return True

def enable_escalation(env):
    """Enable the escalation cron job"""
    # Security check: Only system administrators should be able to run this script
    if not env.user.has_group('base.group_system'):
        print("❌ Access denied: Only system administrators can manage escalation cron jobs")
        return False
    
    cron_job = get_escalation_cron(env)
    if not cron_job:
        print("❌ Escalation cron job not found!")
        return False
    
    if cron_job.active:
        print("ℹ️  Escalation cron job is already enabled")
        return True
    
    try:
        cron_job.write({'active': True})
        print("✅ Escalation cron job enabled successfully")
        return True
    except Exception as e:
        print(f"❌ Error enabling escalation cron job: {e}")
        return False

def disable_escalation(env):
    """Disable the escalation cron job"""
    # Security check: Only system administrators should be able to run this script
    if not env.user.has_group('base.group_system'):
        print("❌ Access denied: Only system administrators can manage escalation cron jobs")
        return False
    
    cron_job = get_escalation_cron(env)
    if not cron_job:
        print("❌ Escalation cron job not found!")
        return False
    
    if not cron_job.active:
        print("ℹ️  Escalation cron job is already disabled")
        return True
    
    try:
        cron_job.write({'active': False})
        print("✅ Escalation cron job disabled successfully")
        return True
    except Exception as e:
        print(f"❌ Error disabling escalation cron job: {e}")
        return False

def test_escalation(env):
    """Test the escalation functionality"""
    try:
        workorder_model = env['facilities.workorder']
        result = workorder_model.cron_auto_escalate_workorders()
        
        print("🧪 Testing SLA Escalation:")
        print(f"   Work orders checked: {result.get('total_checked', 0)}")
        print(f"   Escalations triggered: {result.get('escalated_count', 0)}")
        
        if 'error' in result:
            print(f"   Error: {result['error']}")
            return False
        elif 'message' in result:
            print(f"   Message: {result['message']}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing escalation: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Manage SLA Escalation Cron Job')
    parser.add_argument('--action', choices=['status', 'enable', 'disable', 'test'], 
                       required=True, help='Action to perform')
    
    args = parser.parse_args()
    
    print("🔧 SLA Escalation Cron Management Tool")
    print("=" * 50)
    
    # Get Odoo environment
    env = get_odoo_env()
    if not env:
        print("❌ Failed to initialize Odoo environment")
        sys.exit(1)
    
    success = False
    
    if args.action == 'status':
        success = check_status(env)
    elif args.action == 'enable':
        success = enable_escalation(env)
    elif args.action == 'disable':
        success = disable_escalation(env)
    elif args.action == 'test':
        success = test_escalation(env)
    
    if success:
        print("\n✅ Operation completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Operation failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
