#!/bin/bash
# Quick start script for Odoo 19 with Facilities Management module

echo "Starting Odoo 19 with Facilities Management module..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Start services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to initialize..."
sleep 5

# Check service status
echo ""
echo "Service status:"
docker-compose ps

echo ""
echo "Odoo should be available at: http://localhost:8069"
echo ""
echo "To view logs: docker-compose logs -f odoo"
echo "To stop: docker-compose down"
echo ""

