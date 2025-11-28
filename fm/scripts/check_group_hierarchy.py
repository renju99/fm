#!/usr/bin/env python3
"""
Script to check the group hierarchy in Facilities Management module
and identify any circular or conflicting implied_ids relationships.
"""

print(f"\n{'='*70}")
print("FACILITIES MANAGEMENT - Group Hierarchy Checker")
print(f"{'='*70}\n")

# Get facilities management groups
fm_groups = env['res.groups'].search([
    ('name', 'ilike', 'facilities'),
])

# Get important base groups
portal_group = env.ref('base.group_portal')
internal_group = env.ref('base.group_user')

print("📋 Facilities Management Groups:")
print(f"{'-'*70}\n")

for group in fm_groups:
    print(f"Group: {group.name} (ID: {group.id})")
    print(f"  XML ID: {group.get_external_id().get(group.id, 'N/A')}")
    print(f"  Category: {group.category_id.name if group.category_id else 'None'}")
    
    if group.implied_ids:
        print(f"  Implies:")
        for implied in group.implied_ids:
            print(f"    → {implied.name}")
            # Check if any implied group leads to portal
            if portal_group in implied.trans_implied_ids:
                print(f"      ⚠️  WARNING: This chain leads to PORTAL access!")
            if internal_group in implied.trans_implied_ids:
                print(f"      ✓ Leads to INTERNAL user access")
    else:
        print(f"  Implies: (none)")
    
    # Check if this group has both portal and internal in its chain
    has_portal = portal_group in group.trans_implied_ids or group == portal_group
    has_internal = internal_group in group.trans_implied_ids or group == internal_group
    
    if has_portal and has_internal:
        print(f"\n  🚨 CRITICAL: This group has BOTH portal and internal in its chain!")
        print(f"     This will cause the 'user cannot have more than one user types' error!")
    
    print()

print(f"{'-'*70}\n")

# Check for the specific groups we're interested in
print("🔍 Checking specific facilities management groups:\n")

groups_to_check = [
    'facilities_management.group_maintenance_technician',
    'facilities_management.group_facilities_user',
    'facilities_management.group_facilities_manager',
    'facilities_management.group_sla_escalation_manager',
    'facilities_management.group_tenant_user',
]

for xml_id in groups_to_check:
    try:
        group = env.ref(xml_id, raise_if_not_found=False)
        if group:
            print(f"✓ {xml_id}")
            print(f"  Name: {group.name}")
            
            # Check chain
            has_portal = portal_group in group.trans_implied_ids or group == portal_group
            has_internal = internal_group in group.trans_implied_ids or group == internal_group
            
            if has_portal:
                print(f"  → Grants PORTAL access")
            if has_internal:
                print(f"  → Grants INTERNAL user access")
            if has_portal and has_internal:
                print(f"  🚨 CONFLICT! Has both portal and internal access!")
        else:
            print(f"✗ {xml_id} - NOT FOUND")
    except Exception as e:
        print(f"✗ {xml_id} - ERROR: {e}")
    print()

print(f"{'='*70}\n")

