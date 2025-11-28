# Facilities Management - Security Groups Guide

## Overview

This document explains the security groups structure for the Facilities Management module in Odoo 18. The security model has been properly structured to separate **internal users** from **portal users** to prevent user type conflicts.

## Security Group Hierarchy

### Internal User Groups (For Employees)

These groups are for internal company users and follow a hierarchical structure where higher-level groups inherit permissions from lower-level groups.

```
Facilities Management
├── Maintenance Technician (base level)
│   ├── Inherits: base.group_user (Internal User)
│   ├── Can view and update assigned work orders
│   └── Read-only access to most facilities data
│
├── Facilities Management User
│   ├── Inherits: Maintenance Technician
│   ├── Full access to facilities management features
│   ├── Can create and manage work orders, service requests
│   └── Can manage assets, buildings, rooms, etc.
│
├── Facilities Management Manager
│   ├── Inherits: Facilities Management User
│   ├── Full administrative access
│   ├── Can delete records
│   └── Access to configuration and reports
│
└── SLA Escalation Manager
    ├── Inherits: Facilities Management Manager
    └── Can manage SLA escalation settings
```

### Portal User Groups (For External Users)

These groups are for external users (customers, tenants) who access the system through the portal.

```
Tenant Portal User
├── Inherits: base.group_portal (Portal User)
├── Can submit service requests
├── Can view their own facilities and work orders
└── Limited read-only access to their data
```

## Important Notes

### User Type Separation

- **Internal users** and **portal users** are mutually exclusive in Odoo
- A user CANNOT be both an internal user and a portal user simultaneously
- This is why Tenant Portal User is kept separate from the internal user hierarchy

### Assigning Groups to Users

#### For Internal Employees:
1. Go to Settings → Users & Companies → Users
2. Create or edit a user
3. In the "Access Rights" tab, select one of:
   - Maintenance Technician (for field technicians)
   - Facilities Management User (for facilities staff)
   - Facilities Management Manager (for facilities managers)
   - SLA Escalation Manager (for senior managers)

#### For Portal Users (Tenants/External):
1. Go to Settings → Users & Companies → Users
2. Create a portal user (User Type: Portal)
3. In the "Access Rights" tab, enable "Tenant Portal User"
4. The user will only see their own service requests and facilities

## Access Rights Summary

### Maintenance Technician
- **Read**: All facilities, buildings, rooms, assets, service requests
- **Write**: Assigned work orders and tasks
- **Create**: No
- **Delete**: No

### Facilities Management User
- **Read**: Everything
- **Write**: Everything
- **Create**: Everything (except deletion)
- **Delete**: No (except own records in some cases)

### Facilities Management Manager
- **Read**: Everything
- **Write**: Everything
- **Create**: Everything
- **Delete**: Everything

### Tenant Portal User
- **Read**: Own facilities (where tenant_partner_id matches), own service requests, own work orders
- **Write**: Own service requests (limited fields)
- **Create**: Service requests only
- **Delete**: No

## Record Rules

Record rules control which records each group can access:

### For Portal Users:
- Can only see facilities where `tenant_partner_id` matches their partner
- Can only see work orders they submitted
- Can only see service requests they created

### For Technicians:
- Can see all facilities (read-only)
- Can edit work orders assigned to them
- Can update service requests assigned to them

### For Users and Managers:
- Full access to all records within their permission levels

## Troubleshooting

### Error: "The user cannot have more than one user types"

**Cause**: You tried to assign a portal group to an internal user (or vice versa)

**Solution**:
1. Check the user's "User Type" field
2. If "User Type" is "Internal User":
   - Remove any portal groups
   - Only assign internal groups (Technician, User, Manager)
3. If "User Type" is "Portal":
   - Remove any internal groups
   - Only assign "Tenant Portal User"

### Migration from Old Security Structure

If you're upgrading from an older version where the security groups were structured differently:

1. **Upgrade the module**:
   ```bash
   ./odoo-bin -u facilities_management -d your_database
   ```

2. **Reassign user groups**:
   - Check all users who had facilities management access
   - Verify their user type (Internal vs Portal)
   - Reassign appropriate groups based on user type

3. **Test access**:
   - Log in as different user types
   - Verify they can access appropriate features
   - Check that record rules are working correctly

## Best Practices

1. **Use the lowest privilege necessary**: Don't make everyone a manager
2. **Separate portal and internal users**: Never mix user types
3. **Test access rights**: Always test new users' access before giving them the account
4. **Document custom changes**: If you add custom groups, document them clearly
5. **Use groups consistently**: Don't bypass security with sudo() unless absolutely necessary

## File Structure

- `security/facilities_security_groups.xml` - Main security groups and record rules
- `security/ir.model.access.csv` - Model-level access control (ACL)
- `security/hide_*.xml` - Additional security rules for hiding specific menus/features

## Support

For issues or questions about security configuration, contact the facilities management module maintainer.

---

**Last Updated**: 2025-10-27  
**Module Version**: 1.2.10  
**Odoo Version**: 18.0 Community Edition

