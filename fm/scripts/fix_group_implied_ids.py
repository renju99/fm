#!/usr/bin/env python3
"""
Script to fix the implied_ids for facilities management groups.
This corrects the group hierarchy so internal users don't get portal access.
"""

print(f"\n{'='*70}")
print("FACILITIES MANAGEMENT - Fix Group Implied IDs")
print(f"{'='*70}\n")

# Get reference groups
portal_group = env.ref('base.group_portal')
internal_group = env.ref('base.group_user')

# Get facilities management groups
maintenance_tech = env.ref('fm.group_maintenance_technician')
facilities_user = env.ref('fm.group_facilities_user')
facilities_manager = env.ref('fm.group_facilities_manager')
sla_manager = env.ref('fm.group_sla_escalation_manager')
tenant_user = env.ref('fm.group_tenant_user')

print("🔧 Fixing group hierarchies...\n")

# Fix Maintenance Technician - should imply internal user, NOT portal
print(f"1. Maintenance Technician")
print(f"   Current implied_ids: {[g.name for g in maintenance_tech.implied_ids]}")
maintenance_tech.write({'implied_ids': [(6, 0, [internal_group.id])]})
print(f"   ✓ Updated to: {[g.name for g in maintenance_tech.implied_ids]}\n")

# Fix Facilities User - should imply maintenance technician (which implies internal)
print(f"2. Facilities Management User")
print(f"   Current implied_ids: {[g.name for g in facilities_user.implied_ids]}")
facilities_user.write({'implied_ids': [(6, 0, [maintenance_tech.id])]})
print(f"   ✓ Updated to: {[g.name for g in facilities_user.implied_ids]}\n")

# Fix Facilities Manager - should imply facilities user
print(f"3. Facilities Management Manager")
print(f"   Current implied_ids: {[g.name for g in facilities_manager.implied_ids]}")
facilities_manager.write({'implied_ids': [(6, 0, [facilities_user.id])]})
print(f"   ✓ Updated to: {[g.name for g in facilities_manager.implied_ids]}\n")

# Fix SLA Escalation Manager - should imply facilities manager
print(f"4. SLA Escalation Manager")
print(f"   Current implied_ids: {[g.name for g in sla_manager.implied_ids]}")
sla_manager.write({'implied_ids': [(6, 0, [facilities_manager.id])]})
print(f"   ✓ Updated to: {[g.name for g in sla_manager.implied_ids]}\n")

# Fix Tenant User - should imply portal (this one is correct, but let's ensure it)
print(f"5. Tenant Portal User")
print(f"   Current implied_ids: {[g.name for g in tenant_user.implied_ids]}")
tenant_user.write({'implied_ids': [(6, 0, [portal_group.id])]})
print(f"   ✓ Updated to: {[g.name for g in tenant_user.implied_ids]}\n")

print(f"{'-'*70}\n")
print("✅ Verifying new hierarchy:\n")

for group_name, group in [
    ('Maintenance Technician', maintenance_tech),
    ('Facilities User', facilities_user),
    ('Facilities Manager', facilities_manager),
    ('SLA Escalation Manager', sla_manager),
    ('Tenant User', tenant_user),
]:
    has_portal = portal_group in group.trans_implied_ids or group == portal_group
    has_internal = internal_group in group.trans_implied_ids or group == internal_group
    
    print(f"{group_name}:")
    if has_portal and has_internal:
        print(f"  🚨 ERROR: Still has BOTH portal and internal!")
    elif has_portal:
        print(f"  → Portal user ✓")
    elif has_internal:
        print(f"  → Internal user ✓")
    else:
        print(f"  ⚠️  No user type assigned")

print(f"\n{'='*70}")
print("✓ Group hierarchy fixed successfully!")
print(f"{'='*70}\n")

# Commit changes
env.cr.commit()
print("✓ Changes committed to database.\n")

