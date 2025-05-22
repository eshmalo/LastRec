import json
import os
import sys
from decimal import Decimal

def load_tenant_billing_detail(filepath):
    """Load a tenant billing detail JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def clean_currency(value):
    """Clean currency string to float."""
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(value.strip("$").replace(",", ""))

def clean_percentage(value):
    """Clean percentage string to float."""
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) / 100
    if "%" in value:
        return float(value.strip("%")) / 100
    return float(value)

def analyze_admin_fee_calculations(data):
    """Analyze admin fee calculations for all tenants in the data."""
    print(f"Analyzing admin fee calculations for {len(data)} tenants")
    print("-" * 80)
    
    for tenant in data:
        tenant_id = tenant.get("tenant_id", "Unknown")
        tenant_name = tenant.get("tenant_name", "Unknown")
        
        # Get values from report_row
        report_row = tenant.get("report_row", {})
        if not report_row:
            print(f"Tenant {tenant_id} has no report_row data, skipping")
            continue
            
        # Extract values safely
        share_percentage = clean_percentage(report_row.get("share_percentage", "0"))
        cam_gross = clean_currency(report_row.get("cam_gross_total", "0"))
        cam_net = clean_currency(report_row.get("cam_net_total", "0"))
        admin_fee_base = clean_currency(report_row.get("admin_fee_base_amount", "0"))
        admin_fee_percentage = clean_percentage(report_row.get("admin_fee_percentage", "0"))
        admin_fee_net = clean_currency(report_row.get("admin_fee_net", "0"))
        
        # Calculate expected admin fee
        expected_admin_fee = admin_fee_base * admin_fee_percentage
        discrepancy_amount = admin_fee_base - cam_net
        discrepancy_percentage = (discrepancy_amount / cam_net) * 100 if cam_net > 0 else 0
        
        # Output results
        print(f"Tenant: {tenant_id} - {tenant_name}")
        print(f"  Share Percentage: {share_percentage:.4f}")
        print(f"  CAM Gross: ${cam_gross:,.2f}")
        print(f"  CAM Net: ${cam_net:,.2f}")
        print(f"  Admin Fee Base Amount: ${admin_fee_base:,.2f}")
        print(f"  Admin Fee Percentage: {admin_fee_percentage:.2%}")
        print(f"  Admin Fee (calculated): ${expected_admin_fee:,.2f}")
        print(f"  Admin Fee (reported): ${admin_fee_net:,.2f}")
        print(f"  Admin Fee Base Discrepancy: ${discrepancy_amount:,.2f} ({discrepancy_percentage:.2f}%)")
        
        # Check for large discrepancies
        if abs(discrepancy_percentage) > 95:
            print(f"  ⚠️ MAJOR DISCREPANCY: Admin fee base differs from CAM net by {abs(discrepancy_percentage):.1f}%")
            # Check for specific GL exclusions
            if "gl_detail" in tenant and "admin_fee_exclusions_list" in tenant["gl_detail"]:
                exclusion_list = tenant["gl_detail"]["admin_fee_exclusions_list"]
                if exclusion_list:
                    print(f"  Admin Fee Exclusions: {exclusion_list}")
            
            # Check for tenant-specific admin fee overrides
            tenant_settings = tenant.get("settings", {})
            admin_fee_override = tenant_settings.get("admin_fee_percentage", "")
            if admin_fee_override:
                print(f"  Admin Fee Override: {admin_fee_override}")
        
        print("-" * 80)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Use most recent file if no argument provided
        reports_dir = "/Users/elazarshmalo/PycharmProjects/LastRec/Output/Reports"
        json_files = [f for f in os.listdir(reports_dir) if f.startswith("tenant_billing_detail_") and f.endswith(".json")]
        if not json_files:
            print("No tenant billing detail files found!")
            return
        
        # Sort by modification time to get most recent
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)), reverse=True)
        latest_file = os.path.join(reports_dir, json_files[0])
        print(f"Using most recent file: {latest_file}")
        filepath = latest_file
    else:
        filepath = sys.argv[1]
    
    data = load_tenant_billing_detail(filepath)
    analyze_admin_fee_calculations(data)

if __name__ == "__main__":
    main()