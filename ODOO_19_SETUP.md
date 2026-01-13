# Odoo 19 Setup Guide - Facilities Management Module

## Overview

This guide explains how to run the Facilities Management module on Odoo 19 using Docker.

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available
- Ports 8069 (Odoo) and 5432 (PostgreSQL) available

## Quick Start

### Option 1: Using the Quick Start Script

```bash
./run_odoo.sh
```

### Option 2: Manual Start

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f odoo

# Access Odoo
# Open browser: http://localhost:8069
```

## Module Information

- **Module Name:** Facilities Management
- **Module Directory:** `fm`
- **Version:** 19.0.1.2.11
- **Odoo Version:** 19.0
- **Category:** Operations/Facility Management

## Migration from Odoo 18

The module has been migrated from Odoo 18 to Odoo 19. Key changes:

1. **Version Update:** Manifest version updated to `19.0.1.2.11`
2. **Asset Paths:** Updated from `facilities_management/` to `fm/` to match module directory
3. **API Compatibility:** All code uses modern Odoo 19 compatible APIs
4. **No Deprecated Features:** Removed all deprecated patterns

See `fm/migrations/19.0.1.2.11/MIGRATION_NOTES.md` for detailed migration information.

## Docker Services

### Services Overview

1. **db** - PostgreSQL 15 database
   - Database: `postgres`
   - User: `odoo`
   - Password: `odoo`
   - Port: `5432`

2. **odoo** - Odoo 19 application server
   - Port: `8069`
   - Module path: `/mnt/extra-addons/fm`
   - Log level: `info`

### Volume Mounts

- `./fm` → `/mnt/extra-addons/fm` (Module code)
- `odoo-web-data` → `/var/lib/odoo` (Odoo data)
- `odoo-config` → `/etc/odoo` (Configuration)
- `odoo-db-data` → PostgreSQL data directory

## Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove All Data (Clean Slate)
```bash
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs -f

# Odoo only
docker-compose logs -f odoo

# Database only
docker-compose logs -f db
```

### Restart Services
```bash
docker-compose restart odoo
```

### Access Odoo Shell
```bash
docker-compose exec odoo odoo shell -d your_database_name
```

### Update Module
```bash
docker-compose exec odoo odoo -u fm -d your_database_name --stop-after-init
```

### Access Database
```bash
docker-compose exec db psql -U odoo -d postgres
```

## Development Mode

To enable development mode with auto-reload, edit `docker-compose.yml` and uncomment:

```yaml
command:
  - --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
  - --log-level=info
  - --dev=reload,qweb,werkzeug,xml
```

Then restart:
```bash
docker-compose restart odoo
```

## Production Configuration

For production, modify the `command` in `docker-compose.yml`:

```yaml
command:
  - --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
  - --workers=4
  - --max-cron-threads=2
  - --log-level=warn
```

## Troubleshooting

### Module Not Appearing

1. Check module path in docker-compose.yml
2. Verify module is in `fm` directory
3. Check Odoo logs: `docker-compose logs odoo`
4. Ensure module is in Apps list and click "Update Apps List"

### Database Connection Issues

1. Check database service is healthy: `docker-compose ps`
2. Verify database logs: `docker-compose logs db`
3. Check environment variables in docker-compose.yml

### Permission Issues

On Linux, you may need to adjust file permissions:

```bash
sudo chown -R $USER:$USER ./fm
```

### Port Already in Use

If port 8069 is already in use:

1. Change port in docker-compose.yml:
   ```yaml
   ports:
     - "8070:8069"  # Use 8070 instead
   ```

2. Restart: `docker-compose restart odoo`

### Static Assets Not Loading

1. Clear browser cache
2. Restart Odoo: `docker-compose restart odoo`
3. Check asset paths in `__manifest__.py` match module directory name (`fm`)

## Module Features

The Facilities Management module includes:

- Facilities, Buildings, Floors, Rooms with Google Maps integration
- Asset lifecycle tracking and depreciation
- Maintenance scheduling (preventive, corrective)
- Work order management, assignments, and SLAs
- Resource utilization and technician workload
- Space/Room booking system with conflict detection
- Bulk import/export functionality for CSV/Excel
- Advanced analytics and reporting
- Email notifications and reminders
- Mobile and portal views
- Tenant and landlord management with lease agreements
- Financial management with budget allocation
- Energy Management Module
- Safety incident reporting
- Package and Visitor Management

## Support

For issues or questions:
1. Check the migration notes: `fm/migrations/19.0.1.2.11/MIGRATION_NOTES.md`
2. Review Odoo logs: `docker-compose logs odoo`
3. Check Odoo 19 documentation: https://www.odoo.com/documentation/19.0/

## License

LGPL-3

