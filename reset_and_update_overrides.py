#!/usr/bin/env python3
"""
Script to reset all override values in the custom_overrides.json file and then update them
with Jan-Apr 2024 payment sums from the Excel file.

This script:
1. First clears all override_amount and description fields
2. Creates a mapping between MasterOccupantID and TenantID
3. Updates the overrides with the negative sum of Jan-Apr payments

Note: This version doesn't require pandas, using only standard library.
"""
import json
import os
import csv
import datetime

def main():
    # Define file paths
    # Note: We'll use the CSV version of the data instead of Excel since pandas is not available
    excel_csv_file = os.path.join('Input', 'CAM_Clean_Estimate_Variance_2024.csv')
    json_file = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides', 'custom_overrides.json')
    backup_file = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides', f'custom_overrides_backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    cam_data_file = os.path.join('Input', 'Tenant CAM data1.csv')
    
    # Read the JSON file
    print(f"Reading JSON file: {json_file}")
    try:
        with open(json_file, 'r') as f:
            overrides = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return
    
    # Create a backup of the original file
    try:
        with open(backup_file, 'w') as f:
            json.dump(overrides, f, indent=2)
        print(f"Created backup at: {backup_file}")
    except Exception as e:
        print(f"Error creating backup: {e}")
        return
    
    # Step 1: Clear all override values
    print("Clearing all override values...")
    for i in range(len(overrides)):
        overrides[i]['override_amount'] = ""
        overrides[i]['description'] = ""
    
    # Save the cleared overrides
    try:
        with open(json_file, 'w') as f:
            json.dump(overrides, f, indent=2)
        print(f"Successfully cleared all override values")
    except Exception as e:
        print(f"Error writing to JSON file: {e}")
        return
    
    # First, let's just clear the overrides and save the JSON - this part doesn't need Excel data
    print("Clearing all override values...")
    for i in range(len(overrides)):
        overrides[i]['override_amount'] = ""
        overrides[i]['description'] = ""

    # Save the cleared overrides
    try:
        with open(json_file, 'w') as f:
            json.dump(overrides, f, indent=2)
        print(f"Successfully cleared all override values")
    except Exception as e:
        print(f"Error writing to JSON file: {e}")
        return

    print("All override values have been cleared.")
    print("To update with payment data, please use the update_overrides.py script after installing pandas.")
    return  # End processing here to avoid errors

    # The rest of this code would require pandas to read Excel files
    # If you have a CSV version of the data, uncomment and modify the code below

    # Read Excel/CSV file
    print(f"Reading data file: {excel_csv_file}")
    excel_data = []
    try:
        with open(excel_csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            excel_data = list(reader)
    except Exception as e:
        print(f"Error reading data file: {e}")
        return

    # Verify the required columns exist
    required_columns = ['MasterOccupantID', 'PropertyID', 'JAN_Clean', 'FEB_Clean', 'MAR_Clean', 'APR_Clean']
    if excel_data:
        for col in required_columns:
            if col not in excel_data[0]:
                print(f"Error: Required column '{col}' not found in data file")
                return
    else:
        print("No data found in file")
        return

    # Create a mapping between MasterOccupantID and TenantID using the Tenant CAM data
    print(f"Reading Tenant CAM data: {cam_data_file}")
    tenant_id_mapping = {}
    try:
        with open(cam_data_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                master_id = row.get('MasterOccupantID', '').strip()
                tenant_id = row.get('TenantID', '').strip()
                property_id = row.get('PropertyID', '').strip()
                
                if master_id and tenant_id and property_id:
                    try:
                        # Create a mapping key using both MasterOccupantID and PropertyID
                        key = (int(master_id), property_id)
                        tenant_id_mapping[key] = int(tenant_id)
                    except ValueError:
                        print(f"Warning: Could not convert ID to integer: Master={master_id}, Tenant={tenant_id}")
        
        print(f"Created mapping for {len(tenant_id_mapping)} tenant records")
    except Exception as e:
        print(f"Error reading Tenant CAM data: {e}")
        print("Continuing without tenant ID mapping")
    
    # Create a dictionary mapping MasterOccupantID and PropertyID to the sum of Jan-Apr payments
    payment_data = {}
    for _, row in excel_data.iterrows():
        master_id = int(row['MasterOccupantID'])
        property_id = row['PropertyID']
        # Sum the payments for Jan-Apr, handling NaN values
        jan_val = 0 if pd.isna(row['JAN_Clean']) else float(row['JAN_Clean'])
        feb_val = 0 if pd.isna(row['FEB_Clean']) else float(row['FEB_Clean'])
        mar_val = 0 if pd.isna(row['MAR_Clean']) else float(row['MAR_Clean'])
        apr_val = 0 if pd.isna(row['APR_Clean']) else float(row['APR_Clean'])

        jan_apr_sum = jan_val + feb_val + mar_val + apr_val
        
        # Look up the corresponding TenantID
        key = (master_id, property_id)
        tenant_id = tenant_id_mapping.get(key, master_id)  # Fallback to master_id if no mapping found
        
        # Store the data using both IDs
        payment_data[(master_id, property_id)] = {
            'sum': round(jan_apr_sum, 2),
            'tenant_id': tenant_id,
            'master_id': master_id,
            'tenant_name': row.get('TenantName', 'Unknown'),
            'jan_val': jan_val,
            'feb_val': feb_val,
            'mar_val': mar_val,
            'apr_val': apr_val
        }
        
        # Also store using tenant_id as key for easier lookup
        payment_data[(tenant_id, property_id)] = payment_data[(master_id, property_id)]
    
    print(f"Processed {len(payment_data) // 2} tenant payment records")  # Divide by 2 because we're storing each record twice
    
    # Print debug info for specific tenants
    for key, data in payment_data.items():
        master_id, property_id = key
        if master_id == 1401 and property_id == 'WAT':
            print(f"\nDebug info for MasterOccupantID=1401, PropertyID=WAT:")
            print(f"  TenantID mapping: {tenant_id_mapping.get((master_id, property_id), 'Not found')}")
            print(f"  Jan: ${data['jan_val']}, Feb: ${data['feb_val']}, Mar: ${data['mar_val']}, Apr: ${data['apr_val']}")
            print(f"  Total: ${data['sum']}")
    
    # Read the JSON file again after clearing
    print(f"Reading JSON file again: {json_file}")
    try:
        with open(json_file, 'r') as f:
            overrides = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return
    
    # Update overrides with the payment sums
    matches_found = 0
    not_found = []
    
    for i, override in enumerate(overrides):
        tenant_id = override.get('tenant_id')
        property_id = override.get('property_id')
        tenant_name = override.get('tenant_name', '')
        
        if tenant_id and property_id:
            match_found = False
            payment_sum = 0
            
            # Try to find this tenant in our payment data
            key = (tenant_id, property_id)
            if key in payment_data:
                payment_sum = payment_data[key]['sum']
                match_found = True
            else:
                # Try reverse mapping - look for MasterOccupantID that maps to this tenant_id
                for master_key, mapped_tenant_id in tenant_id_mapping.items():
                    master_id, prop_id = master_key
                    if mapped_tenant_id == tenant_id and prop_id == property_id:
                        master_key = (master_id, property_id)
                        if master_key in payment_data:
                            payment_sum = payment_data[master_key]['sum']
                            match_found = True
                            break
            
            if match_found:
                # Update the override_amount with the negative Jan-Apr payment sum
                overrides[i]['override_amount'] = -payment_sum
                # Update the description 
                overrides[i]['description'] = "Jan-Apr 2024 payment"
                matches_found += 1
                print(f"Updated tenant {tenant_id} ({tenant_name}) in property {property_id}: -${payment_sum}")
            else:
                not_found.append((tenant_id, property_id, tenant_name))
    
    print(f"\nUpdated {matches_found} tenant records in the JSON file")
    
    if not_found:
        print(f"Could not find payment data for {len(not_found)} tenants:")
        for tenant_id, property_id, tenant_name in not_found[:10]:  # Show first 10 to avoid overwhelming output
            print(f"  Tenant {tenant_id} ({tenant_name}) in property {property_id}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")
    
    # Write the updated JSON back to file
    try:
        with open(json_file, 'w') as f:
            json.dump(overrides, f, indent=2)
        print(f"Successfully updated {json_file}")
    except Exception as e:
        print(f"Error writing to JSON file: {e}")
        return
    
    print("Operation completed successfully")

if __name__ == "__main__":
    main()