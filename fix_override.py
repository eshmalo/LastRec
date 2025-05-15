import json
import os
from decimal import Decimal

# Path to the most recent GL detail report for tenant 1407
# Use the pattern from your earlier findings
gl_report_path = "/Users/elazarshmalo/PycharmProjects/LastRec/Output/Reports/GL_Details/WAT_2024/Tenant_1407_New_Cingular_Wireless_PCS,_LLC/GL_detail_1407_2024_20250513_230733.csv"

# Print current values
with open(gl_report_path, 'r') as f:
    lines = f.readlines()
    # Get the totals line
    totals_line = [line for line in lines if line.startswith('TOTAL,')][0]
    print(f"Current totals line: {totals_line}")
    
    # Extract the override amount from the totals line
    fields = totals_line.split(',')
    override_amount_index = 25  # Based on the CSV structure
    current_override = fields[override_amount_index]
    print(f"Current override amount in report: {current_override}")

# Load the actual override amount from custom_overrides.json
overrides_path = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides', 'custom_overrides.json')
with open(overrides_path, 'r') as f:
    overrides = json.load(f)
    # Find the override for tenant 1407
    tenant_1407_override = next((o for o in overrides if o.get('tenant_id') == 1407 and o.get('property_id') == 'WAT'), None)
    actual_override = tenant_1407_override.get('override_amount', 0) if tenant_1407_override else 0
    print(f"Actual override amount in JSON: {actual_override}")

print("\nBased on this investigation, there appears to be scaling or annualization happening to the override amount.")
print("The override amount in the JSON file (-7353.92) is being scaled to -10,725.50 in the GL report.")
print("The scaling factor is approximately: ", abs(float(current_override.strip('\"$-'))/actual_override))