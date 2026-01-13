# -*- coding: utf-8 -*-
"""Migration script to assign Facilities Management category to all FM groups"""

def migrate(cr, version):
    """Update all FM security groups to have the Facilities Management category"""
    
    # Get the category ID
    cr.execute("""
        SELECT id FROM ir_module_category 
        WHERE name = 'Facilities Management'
        LIMIT 1
    """)
    category_result = cr.fetchone()
    
    if not category_result:
        # Category doesn't exist, create it
        cr.execute("""
            INSERT INTO ir_module_category (name, description, sequence, create_uid, create_date, write_uid, write_date)
            VALUES ('Facilities Management', 'Helps you manage facilities, assets, and maintenance operations.', 10, 2, NOW(), 2, NOW())
            RETURNING id
        """)
        category_result = cr.fetchone()
    
    category_id = category_result[0]
    
    # List of all FM group external IDs
    fm_groups = [
        'fm.group_maintenance_technician',
        'fm.group_facilities_user',
        'fm.group_facilities_manager',
        'fm.group_sla_escalation_manager',
        'fm.group_tenant_user',
        'fm.group_facilities_focused_user',
        'fm.group_hide_project_elements',
        'fm.group_facilities_security_admin',
        'fm.group_facilities_security_auditor',
        'fm.group_facilities_high_priority',
    ]
    
    # Update each group
    for group_xmlid in fm_groups:
        cr.execute("""
            UPDATE res_groups 
            SET category_id = %s
            WHERE id IN (
                SELECT res_id FROM ir_model_data 
                WHERE module = 'fm' AND name = %s
            )
        """, (category_id, group_xmlid.split('.')[-1]))
    
    cr.execute("COMMIT")

