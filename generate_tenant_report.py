#!/usr/bin/env python3
"""
Generate Tenant Payment Report

This script takes a payment changes JSON file and generates a detailed report
with tenant names from the Tenant CAM data.
"""

import os
import sys
import json
import csv
import argparse
from decimal import Decimal


def load_tenant_cam_data(file_path=None):
    """
    Load the Tenant CAM data from JSON file.
    
    Args:
        file_path: Optional override for the data file path
        
    Returns:
        List of tenant CAM data records
    """
    # Determine file path
    default_path = os.path.join('Output', 'JSON', 'Tenant CAM data1.json')
    cam_data_path = file_path or os.environ.get('TENANT_CAM_DATA_PATH', default_path)
    
    try:
        if os.path.exists(cam_data_path):
            with open(cam_data_path, 'r', encoding='utf-8') as f:
                tenant_cam_data = json.load(f)
                print(f"Loaded tenant CAM data with {len(tenant_cam_data)} records")
                return tenant_cam_data
        else:
            print(f"Error: Tenant CAM data file not found at {cam_data_path}")
            return []
    except Exception as e:
        print(f"Error loading Tenant CAM data: {str(e)}")
        return []


def get_tenant_name(tenant_id, tenant_cam_data):
    """
    Get tenant name from tenant ID.
    
    Args:
        tenant_id: Tenant identifier
        tenant_cam_data: Tenant CAM data records
        
    Returns:
        Tenant name if found, otherwise empty string
    """
    tenant_id_str = str(tenant_id)
    
    for record in tenant_cam_data:
        record_tenant_id = str(record.get('TenantID', ''))
        
        if record_tenant_id == tenant_id_str:
            return record.get('TenantName', '')
    
    return ''


def generate_tenant_report(input_file, output_file=None):
    """
    Generate tenant payment report with names.
    
    Args:
        input_file: Payment changes JSON file
        output_file: Optional output file path
        
    Returns:
        Path to the generated report
    """
    # Load payment changes data
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            payment_data = json.load(f)
    except Exception as e:
        print(f"Error loading payment changes data: {str(e)}")
        return None
    
    # Load tenant CAM data
    tenant_cam_data = load_tenant_cam_data()
    
    # Generate default output path if not provided
    if not output_file:
        dirname = os.path.dirname(input_file)
        basename = os.path.basename(input_file)
        name, ext = os.path.splitext(basename)
        output_file = os.path.join(dirname, f"{name}_with_names.csv")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Define CSV fields
    fields = [
        'tenant_id', 'tenant_name', 'property_id',
        'old_monthly', 'new_monthly', 'difference', 
        'percentage_change', 'change_type', 'is_significant'
    ]
    
    # Write the CSV file
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()
            
            for record in payment_data:
                tenant_id = record.get('tenant_id', '')
                
                # Get tenant name
                tenant_name = get_tenant_name(tenant_id, tenant_cam_data)
                
                # Create row with tenant name
                row = {
                    'tenant_id': tenant_id,
                    'tenant_name': tenant_name,
                    'property_id': record.get('property_id', ''),
                    'old_monthly': f"${float(record.get('old_monthly', 0)):.2f}",
                    'new_monthly': f"${float(record.get('new_monthly', 0)):.2f}",
                    'difference': f"${float(record.get('difference', 0)):.2f}",
                    'percentage_change': f"{float(record.get('percentage_change', 0)):.1f}%",
                    'change_type': record.get('change_type', ''),
                    'is_significant': "Yes" if record.get('is_significant', False) else "No"
                }
                
                writer.writerow(row)
        
        print(f"Generated tenant report with {len(payment_data)} rows: {output_file}")
        return output_file
    except Exception as e:
        print(f"Error generating tenant report: {str(e)}")
        return None


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Generate tenant payment report with names')
    
    parser.add_argument(
        'input_file',
        help='Path to payment changes JSON file'
    )
    parser.add_argument(
        '--output_file',
        help='Path to output CSV file'
    )
    
    args = parser.parse_args()
    
    # Find the latest payment changes file if not specified
    input_file = args.input_file
    if input_file == 'latest':
        # Look for most recent payment_changes JSON file
        import glob
        json_files = sorted(glob.glob(os.path.join('Output', 'payment_changes_*.json')), reverse=True)
        input_file = json_files[0] if json_files else None
    
    if not input_file or not os.path.exists(input_file):
        print(f"Error: Input file not found - {args.input_file}")
        sys.exit(1)
    
    # Generate the report
    report_path = generate_tenant_report(input_file, args.output_file)
    
    if report_path:
        print(f"Successfully generated tenant report: {report_path}")
        sys.exit(0)
    else:
        print("Failed to generate tenant report")
        sys.exit(1)


if __name__ == "__main__":
    main()