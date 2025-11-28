# Facilities Management Security Fix - Summary

## Date: October 27, 2025

## Problem Identified

When trying to assign "Facilities Management Manager" or other facilities management groups to users, the system was showing the error:

```
Validation Error: The user cannot have more than one user types.
```

## Root Cause

The security groups were incorrectly configured with a circular hierarchy where:
- Internal user groups (Maintenance Technician, Facilities User, Manager) were implying **Portal** access
- This created a conflict because a user cannot be both an Internal User and a Portal User simultaneously

## Solution Applied

### 1. Restructured Security Groups

**Internal User Groups** (for employees):
```
Maintenance Technician
├── Implies: base.group_user (Internal User)
│
Facilities Management User  
├── Implies: Maintenance Technician
│   └── Implies: Internal User
│
Facilities Management Manager
├── Implies: Facilities Management User
│   └── Implies: Maintenance Technician
│       └── Implies: Internal User
│
SLA Escalation Manager
└── Implies: Facilities Management Manager
    └── Implies: Facilities Management User
        └── Implies: Maintenance Technician
            └── Implies: Internal User
```

**Portal User Group** (for external users/tenants):
```
Tenant Portal User
└── Implies: base.group_portal (Portal User)
```

### 2. Files Modified

1. **`security/facilities_security_groups.xml`**
   - Removed the conflicting group hierarchy
   - Created separate chains for internal and portal users
   - Moved `group_tenant_user` to a hidden category to avoid confusion

2. **`security/security.xml`**
   - **DELETED** - This file was not being loaded and contained duplicate/conflicting group definitions

3. **Created Documentation**:
   - `security/SECURITY_GROUPS_GUIDE.md` - Complete guide for using security groups
   - `security/SECURITY_FIX_SUMMARY.md` - This file

### 3. Scripts Created

Several utility scripts were created in `scripts/` directory:
- `fix_user_groups.py` - Detect and fix users with conflicting groups
- `check_group_hierarchy.py` - Verify group hierarchy is correct
- `fix_group_implied_ids.py` - Directly fix implied_ids in database

## How to Assign Groups Now

### For Internal Employees:

1. Go to **Settings → Users & Companies → Users**
2. Create or edit a user
3. Ensure "User Type" is set to **"Internal User"**
4. In the "Access Rights" tab, select ONE of:
   - **Maintenance Technician** - For field technicians (view & update assigned work orders)
   - **Facilities Management User** - For facilities staff (full access except delete)
   - **Facilities Management Manager** - For managers (full access including delete)
   - **SLA Escalation Manager** - For senior managers (includes SLA management)

### For External Users (Tenants/Portal):

1. Go to **Settings → Users & Companies → Users**
2. Create a user with "User Type" set to **"Portal"**
3. In the "Access Rights" tab, enable **"Tenant Portal User"**
4. The user will only see their own service requests and facilities

## Testing the Fix

To verify the fix is working:

1. Open a user form
2. Set "User Type" to "Internal User"
3. Try selecting "Facilities Management Manager"
4. ✅ It should save without errors

If you still get the error:
1. Check if the user was previously a portal user
2. Remove all portal-related groups first
3. Then assign the facilities management groups

## Prevention

- **Never** manually assign `base.group_portal` to facilities management users
- **Never** manually assign `facilities_management.group_tenant_user` to internal users
- Always check the "User Type" field before assigning groups
- Use the provided scripts to diagnose issues if they occur

## Support

For issues or questions:
1. Check `/home/ranjith/odoo/custom_addons/facilities_management/security/SECURITY_GROUPS_GUIDE.md`
2. Run the diagnostic script: `python3 odoo-bin shell -c odoo.conf -d your_db < custom_addons/facilities_management/scripts/check_group_hierarchy.py`
3. Contact the module maintainer

---

**Status**: ✅ **RESOLVED**  
**Module Version**: 1.2.10  
**Odoo Version**: 18.0 Community Edition

