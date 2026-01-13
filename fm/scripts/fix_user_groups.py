#!/usr/bin/env python3
"""
Script to fix user group conflicts in Facilities Management module.
This script removes conflicting group assignments where users have both
internal and portal groups.

Run this script from Odoo shell:
python3 odoo-bin shell -c odoo.conf -d your_database < fix_user_groups.py
"""

# Get all users
users = env['res.users'].search([])

# Define the problematic groups
portal_group = env.ref('base.group_portal')
internal_group = env.ref('base.group_user')
tenant_group = env.ref('fm.group_tenant_user', raise_if_not_found=False)

print(f"\n{'='*60}")
print("FACILITIES MANAGEMENT - User Group Conflict Fixer")
print(f"{'='*60}\n")

fixed_count = 0
issues_found = []

for user in users:
    has_portal = portal_group in user.groups_id
    has_internal = internal_group in user.groups_id
    has_tenant = tenant_group and (tenant_group in user.groups_id)
    
    # Check for conflicts
    if has_portal and has_internal:
        issue = f"User '{user.name}' ({user.login}) has BOTH portal and internal user groups!"
        issues_found.append(issue)
        print(f"⚠ {issue}")
        
        # If user has internal group, remove portal-related groups
        if has_internal:
            print(f"  → Removing portal and tenant groups from {user.name}")
            groups_to_remove = [portal_group.id]
            if tenant_group and has_tenant:
                groups_to_remove.append(tenant_group.id)
            
            user.write({'groups_id': [(3, gid) for gid in groups_to_remove]})
            fixed_count += 1
            print(f"  ✓ Fixed! User is now internal only.")
    
    elif has_internal and has_tenant:
        issue = f"User '{user.name}' ({user.login}) is internal but has tenant group (which implies portal)!"
        issues_found.append(issue)
        print(f"⚠ {issue}")
        print(f"  → Removing tenant group from {user.name}")
        user.write({'groups_id': [(3, tenant_group.id)]})
        fixed_count += 1
        print(f"  ✓ Fixed! User is now internal only.")

print(f"\n{'='*60}")
print(f"Summary:")
print(f"  • Total users checked: {len(users)}")
print(f"  • Conflicts found: {len(issues_found)}")
print(f"  • Conflicts fixed: {fixed_count}")
print(f"{'='*60}\n")

if fixed_count > 0:
    print("✓ All conflicts resolved! Users can now be assigned facilities management roles.")
else:
    print("✓ No conflicts found. All user groups are properly configured.")

# Commit the changes
env.cr.commit()
print("\n✓ Changes committed to database.\n")

