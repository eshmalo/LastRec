#!/usr/bin/env python3
import csv
import sys
from decimal import Decimal

# Read CSV file from command line argument or default
filename = sys.argv[1] if len(sys.argv) > 1 else "Output/Reports/tenant_billing_WAT_cam_20250508_221705.csv"

with open(filename, 'r') as f:
    reader = csv.reader(f)
    headers = next(reader)
    rows = list(reader)

print(f'Number of tenants: {len(rows)}')

# Check each tenant
property_gl_values = []
total_share = 0
total_cam = 0

for row in rows:
    tenant_id = row[0]
    tenant_name = row[1]
    share_pct_str = row[8].strip('%')
    property_gl_str = row[9].replace('$', '').replace(',', '')
    cam_total_str = row[10].replace('$', '').replace(',', '')
    admin_fee_base_str = row[12].replace('$', '').replace(',', '')
    admin_fee_str = row[13].replace('$', '').replace(',', '')
    tenant_admin_fee_str = row[14].replace('$', '').replace(',', '')
    admin_fee_pct_str = row[15].strip('%')
    
    # Convert to Decimal
    share_pct = Decimal(share_pct_str) / 100 if share_pct_str else Decimal('0')
    property_gl = Decimal(property_gl_str) if property_gl_str else Decimal('0')
    cam_total = Decimal(cam_total_str) if cam_total_str else Decimal('0')
    admin_fee_base = Decimal(admin_fee_base_str) if admin_fee_base_str else Decimal('0')
    admin_fee = Decimal(admin_fee_str) if admin_fee_str else Decimal('0')
    tenant_admin_fee = Decimal(tenant_admin_fee_str) if tenant_admin_fee_str else Decimal('0')
    admin_fee_pct = Decimal(admin_fee_pct_str) / 100 if admin_fee_pct_str else Decimal('0')
    
    property_gl_values.append(float(property_gl))
    total_share += float(share_pct)
    total_cam += float(cam_total)
    
    # Calculate expected values
    expected_cam = property_gl * share_pct
    expected_admin_fee = admin_fee_base * admin_fee_pct
    expected_tenant_admin_fee = admin_fee * share_pct
    
    # Calculate differences
    cam_diff = cam_total - expected_cam
    admin_fee_diff = admin_fee - expected_admin_fee
    tenant_admin_fee_diff = tenant_admin_fee - expected_tenant_admin_fee
    
    # Print tenant info and validation
    print(f"\nTenant {tenant_id} - {tenant_name}:")
    print(f"Share %: {float(share_pct):.4f} ({row[8]})")
    print(f"Property GL: ${float(property_gl):.2f}")
    print(f"CAM Total: ${float(cam_total):.2f}")
    print(f"Expected CAM: ${float(expected_cam):.2f}, Diff: ${float(cam_diff):.2f}")
    print(f"Admin Fee Base: ${float(admin_fee_base):.2f}")
    print(f"Admin Fee %: {float(admin_fee_pct):.4f} ({row[15]})")
    print(f"Expected Admin Fee: ${float(expected_admin_fee):.2f}, Diff: ${float(admin_fee_diff):.2f}")
    print(f"Expected Tenant Admin Fee: ${float(expected_tenant_admin_fee):.2f}, Actual: ${float(tenant_admin_fee):.2f}, Diff: ${float(tenant_admin_fee_diff):.2f}")

# Print summary stats
property_gl_set = set(property_gl_values)
print(f"\nSummary:")
print(f"All Property GL values are identical: {len(property_gl_set) == 1}")
print(f"Property GL value: ${property_gl_values[0]:.2f}")
print(f"Total tenant shares: {total_share:.4f}")
print(f"Total CAM amounts: ${total_cam:.2f}")