import json
import sys

def load_tenant_billing_detail(filepath):
    """Load a tenant billing detail JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_tenant_settings(data, tenant_id):
    """Extract settings for a specific tenant."""
    for tenant in data:
        if tenant.get("tenant_id") == tenant_id:
            print(f"Found tenant: {tenant.get('tenant_name')}")
            
            # Check if tenant has settings
            settings = tenant.get("settings", {})
            print("\nTenant Settings:")
            print(json.dumps(settings, indent=2))
            
            # Check admin fee specific details
            report_row = tenant.get("report_row", {})
            print("\nAdmin Fee Details:")
            admin_fee_keys = [k for k in report_row.keys() if "admin_fee" in k]
            admin_fee_details = {k: report_row.get(k) for k in admin_fee_keys}
            print(json.dumps(admin_fee_details, indent=2))
            
            # Check GL detail
            gl_detail = tenant.get("gl_detail", {})
            print("\nGL Detail - Admin Fee Info:")
            admin_fee_gl_keys = [k for k in gl_detail.keys() if "admin_fee" in k]
            admin_fee_gl_details = {k: gl_detail.get(k) for k in admin_fee_gl_keys}
            print(json.dumps(admin_fee_gl_details, indent=2))
            
            return
    
    print(f"Tenant with ID {tenant_id} not found")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Use most recent file if no argument provided
        filepath = "/Users/elazarshmalo/PycharmProjects/LastRec/Output/Reports/tenant_billing_detail_ELW_cam_ret_2024_20250521_000718.json"
    else:
        filepath = sys.argv[1]
    
    tenant_id = "1334"  # Chip East
    if len(sys.argv) >= 3:
        tenant_id = sys.argv[2]
    
    data = load_tenant_billing_detail(filepath)
    extract_tenant_settings(data, tenant_id)

if __name__ == "__main__":
    main()