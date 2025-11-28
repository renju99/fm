#!/usr/bin/env python3
"""
Quick script to check work orders in the system
Run this to see if you have any work orders and their date fields
"""

# Run this in Odoo shell:
# ./odoo-bin shell -c odoo.conf -d your_database

# Check total work orders
workorders = env['facilities.workorder'].search([])
print(f"\n{'='*60}")
print(f"TOTAL WORK ORDERS IN SYSTEM: {len(workorders)}")
print(f"{'='*60}\n")

if len(workorders) == 0:
    print("❌ NO WORK ORDERS FOUND!")
    print("You need to create work orders first.")
    print("\nTo create work orders:")
    print("Go to: Facilities → Work Orders → Create")
else:
    print(f"✅ Found {len(workorders)} work orders\n")
    
    # Check date fields
    with_start_date = workorders.filtered(lambda w: w.start_date)
    with_actual_start = workorders.filtered(lambda w: w.actual_start_date)
    with_create_date = workorders.filtered(lambda w: w.create_date)
    
    print("DATE FIELD STATISTICS:")
    print(f"  - With start_date: {len(with_start_date)}")
    print(f"  - With actual_start_date: {len(with_actual_start)}")
    print(f"  - With create_date: {len(with_create_date)} (should be all)")
    
    # Check states
    print("\nWORK ORDER STATES:")
    for state in ['draft', 'assigned', 'in_progress', 'completed', 'cancelled']:
        count = len(workorders.filtered(lambda w: w.state == state))
        if count > 0:
            print(f"  - {state}: {count}")
    
    # Check date ranges
    print("\nDATE RANGES:")
    if with_start_date:
        start_dates = [w.start_date for w in with_start_date if w.start_date]
        print(f"  - start_date range: {min(start_dates)} to {max(start_dates)}")
    
    if with_create_date:
        create_dates = [w.create_date.date() for w in with_create_date if w.create_date]
        print(f"  - create_date range: {min(create_dates)} to {max(create_dates)}")
    
    # Show sample work orders
    print(f"\nSAMPLE WORK ORDERS (first 5):")
    for wo in workorders[:5]:
        print(f"  - {wo.name} | State: {wo.state} | Start: {wo.start_date} | Created: {wo.create_date.date() if wo.create_date else 'N/A'}")

print(f"\n{'='*60}\n")


