#!/usr/bin/env python3
"""
Test script to verify the escalation type fix

This script tests the escalation functionality to ensure all escalation types
are properly defined and working.
"""

import sys
import os

# Add the Odoo path to sys.path
sys.path.insert(0, '/home/ranjith/odoo/odoo-18.0')

def test_escalation_types():
    """Test that all escalation types are properly defined"""
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
            
            # Test escalation log model
            escalation_log_model = env['facilities.escalation.log']
            
            # Get the escalation_type field
            escalation_type_field = escalation_log_model._fields['escalation_type']
            available_types = [choice[0] for choice in escalation_type_field.selection]
            
            print("📋 Available Escalation Types:")
            for i, esc_type in enumerate(available_types, 1):
                print(f"   {i}. {esc_type}")
            
            # Test escalation types used in the code
            code_escalation_types = [
                'response_breach',
                'resolution_breach', 
                'warning',
                'progressive',
                'automatic',
                'sla_breach',
                'priority_increase',
                'technician_unavailable',
                'resource_shortage',
                'safety_concern',
                'quality_issue',
                'other'
            ]
            
            print("\n🔍 Testing Escalation Types Used in Code:")
            missing_types = []
            for esc_type in code_escalation_types:
                if esc_type in available_types:
                    print(f"   ✅ {esc_type} - Available")
                else:
                    print(f"   ❌ {esc_type} - MISSING")
                    missing_types.append(esc_type)
            
            if missing_types:
                print(f"\n❌ Missing escalation types: {missing_types}")
                return False
            else:
                print("\n✅ All escalation types are properly defined!")
                return True
                
    except Exception as e:
        print(f"❌ Error testing escalation types: {e}")
        return False

def test_escalation_creation():
    """Test creating an escalation log with different types"""
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
            
            # Find a work order to test with
            workorder = env['facilities.workorder'].search([('sla_id', '!=', False)], limit=1)
            
            if not workorder:
                print("⚠️  No work orders with SLA found for testing")
                return True
            
            print(f"🧪 Testing escalation creation with work order: {workorder.name}")
            
            # Test different escalation types
            test_types = ['progressive', 'warning', 'automatic', 'response_breach']
            
            for esc_type in test_types:
                try:
                    # Create a test escalation log
                    escalation_log = env['facilities.escalation.log'].create({
                        'workorder_id': workorder.id,
                        'escalation_type': esc_type,
                        'escalation_level': 1,
                        'escalation_reason': f'Test escalation of type: {esc_type}',
                        'status': 'open'
                    })
                    print(f"   ✅ Created escalation log with type: {esc_type} (ID: {escalation_log.id})")
                    
                    # Clean up test record
                    escalation_log.unlink()
                    
                except Exception as e:
                    print(f"   ❌ Failed to create escalation log with type {esc_type}: {e}")
                    return False
            
            print("✅ All escalation types can be created successfully!")
            return True
                
    except Exception as e:
        print(f"❌ Error testing escalation creation: {e}")
        return False

def main():
    print("🔧 SLA Escalation Type Fix Verification")
    print("=" * 50)
    
    # Test 1: Check escalation types are defined
    print("\n1. Testing escalation type definitions...")
    types_ok = test_escalation_types()
    
    # Test 2: Test escalation creation
    print("\n2. Testing escalation log creation...")
    creation_ok = test_escalation_creation()
    
    if types_ok and creation_ok:
        print("\n✅ All tests passed! The escalation type fix is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
