import json
import sys

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

def compare_tenant_shares(data):
    """Compare tenant shares and admin fee bases."""
    print(f"{'Tenant ID':<10} {'Tenant Name':<30} {'Share %':<10} {'CAM Share':<15} {'Admin Base':<15} {'% of CAM':<10} {'Admin Fee':<12}")
    print("-" * 100)
    
    cam_net_total = None
    
    # First, get the CAM net total
    for tenant in data:
        report_row = tenant.get("report_row", {})
        if "cam_net_total" in report_row:
            cam_net_total = clean_currency(report_row.get("cam_net_total"))
            break
    
    # Then analyze each tenant
    for tenant in data:
        tenant_id = tenant.get("tenant_id", "Unknown")
        tenant_name = tenant.get("tenant_name", "Unknown")
        
        report_row = tenant.get("report_row", {})
        if not report_row:
            continue
            
        # Extract values
        share_percentage = clean_percentage(report_row.get("share_percentage", "0"))
        admin_fee_base = clean_currency(report_row.get("admin_fee_base_amount", "0"))
        admin_fee = clean_currency(report_row.get("admin_fee_net", "0"))
        
        # Calculate tenant's share of CAM
        expected_cam_share = cam_net_total * share_percentage if cam_net_total else 0
        
        # Calculate admin fee base as percentage of expected CAM share
        percent_of_cam = (admin_fee_base / expected_cam_share) * 100 if expected_cam_share > 0 else 0
        
        # Format output
        print(f"{tenant_id:<10} {tenant_name[:28]:<30} {share_percentage*100:8.4f}% {expected_cam_share:13,.2f} {admin_fee_base:13,.2f} {percent_of_cam:8.2f}% {admin_fee:10,.2f}")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Use most recent file if no argument provided
        filepath = "/Users/elazarshmalo/PycharmProjects/LastRec/Output/Reports/tenant_billing_detail_ELW_cam_ret_2024_20250521_000718.json"
    else:
        filepath = sys.argv[1]
    
    data = load_tenant_billing_detail(filepath)
    compare_tenant_shares(data)

if __name__ == "__main__":
    main()