# Odoo 19 Docker Setup for Facilities Management Module

This guide explains how to run the Facilities Management module in Odoo 19 using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- At least 4GB of available RAM
- Ports 8069 (Odoo) and 5432 (PostgreSQL) available

## Quick Start

1. **Start the services:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f odoo
   ```

3. **Access Odoo:**
   - Open your browser and navigate to: `http://localhost:8069`
   - Create a new database or use an existing one
   - The module should be available for installation

## Configuration

### Database Setup

The default database configuration:
- **Database:** postgres
- **User:** odoo
- **Password:** odoo
- **Host:** db (internal Docker network)

### Module Path

The module is mounted at `/mnt/extra-addons/fm` inside the container.

### Running in Development Mode

By default, the docker-compose.yml is configured to run with `--stop-after-init` for initial setup. To run Odoo continuously:

1. Edit `docker-compose.yml`
2. Comment out the `command` section or modify it to remove `--stop-after-init`
3. Restart: `docker-compose restart odoo`

### Running in Production Mode

For production, modify the `command` in docker-compose.yml:

```yaml
command:
  - --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
  - --workers=4
  - --max-cron-threads=2
```

## Useful Commands

### Stop services:
```bash
docker-compose down
```

### Stop and remove volumes (clean slate):
```bash
docker-compose down -v
```

### Restart Odoo:
```bash
docker-compose restart odoo
```

### Access Odoo shell:
```bash
docker-compose exec odoo odoo shell -d your_database_name
```

### Update module:
```bash
docker-compose exec odoo odoo -u fm -d your_database_name --stop-after-init
```

### View database:
```bash
docker-compose exec db psql -U odoo -d postgres
```

## Troubleshooting

### Module not appearing
- Check that the module path is correct in docker-compose.yml
- Verify the module is in the `fm` directory
- Check Odoo logs: `docker-compose logs odoo`

### Database connection issues
- Ensure the `db` service is healthy: `docker-compose ps`
- Check database logs: `docker-compose logs db`

### Permission issues
- Ensure Docker has proper permissions to access the module directory
- On Linux, you may need to adjust file permissions

## Module Information

- **Module Name:** Facilities Management
- **Version:** 19.0.1.2.11
- **Odoo Version:** 19.0
- **Category:** Operations/Facility Management

## Notes

- The module is automatically updated on container start with `--update=all`
- Initial database setup is done with `--init=all`
- For production, remove `--stop-after-init` and configure proper workers

