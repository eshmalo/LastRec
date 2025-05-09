#!/usr/bin/env python3
"""
Payment Tracker Module

This module extracts old monthly payment information and calculates new monthly
payment amounts for tenant billing comparisons. It uses the MatchedEstimate
field from Tenant CAM data as the reference for the old monthly amount.
"""

import os
import json
import csv
import logging
import datetime
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Union

# Configure decimal context for money calculations
getcontext().prec = 12  # Precision for calculations
MONEY_QUANTIZE = Decimal('0.01')  # Round to 2 decimal places
PCT_QUANTIZE = Decimal('0.1')     # Round percentages to 1 decimal place

# Configure logging
logger = logging.getLogger(__name__)

# Default path to the Tenant CAM data - can be overridden
DEFAULT_TENANT_CAM_DATA_PATH = os.path.join('Output', 'JSON', 'Tenant CAM data1.json')

# Module-level cache for tenant CAM data
_TENANT_CAM_CACHE = None


def load_tenant_cam_data(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load the Tenant CAM data from JSON file, using cache if available.
    
    Args:
        file_path: Optional override for the data file path
        
    Returns:
        List of tenant CAM data records
    """
    global _TENANT_CAM_CACHE
    
    # Use cached data if available
    if _TENANT_CAM_CACHE is not None:
        return _TENANT_CAM_CACHE
    
    # Determine file path
    cam_data_path = file_path or os.environ.get('TENANT_CAM_DATA_PATH', DEFAULT_TENANT_CAM_DATA_PATH)
    
    try:
        if os.path.exists(cam_data_path):
            with open(cam_data_path, 'r', encoding='utf-8') as f:
                _TENANT_CAM_CACHE = json.load(f)
                logger.info(f"Loaded tenant CAM data with {len(_TENANT_CAM_CACHE)} records")
                return _TENANT_CAM_CACHE
        else:
            # Try alternative path structure
            alternative_path = os.path.join('Output', 'JSON', 'Tenant CAM data1.json')
            if os.path.exists(alternative_path):
                with open(alternative_path, 'r', encoding='utf-8') as f:
                    _TENANT_CAM_CACHE = json.load(f)
                    logger.info(f"Loaded tenant CAM data from alternative path with {len(_TENANT_CAM_CACHE)} records")
                    return _TENANT_CAM_CACHE
            
            logger.warning(f"Tenant CAM data file not found at {cam_data_path} or alternative locations")
            _TENANT_CAM_CACHE = []
            return []
    except Exception as e:
        logger.error(f"Error loading Tenant CAM data: {str(e)}")
        _TENANT_CAM_CACHE = []
        return []


def get_tenant_data(tenant_id: str, property_id: str) -> Dict[str, Any]:
    """
    Get tenant data including name and old monthly payment.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        
    Returns:
        Dictionary with tenant data including name and old monthly payment
    """
    # Convert tenant_id to consistent string format
    tenant_id_str = str(tenant_id)
    
    # Load tenant CAM data (uses cache if available)
    tenant_cam_data = load_tenant_cam_data()
    
    # Default values
    result = {
        'tenant_name': '',
        'old_monthly': Decimal('0')
    }
    
    # Find the record for this tenant and property
    for record in tenant_cam_data:
        record_tenant_id = str(record.get('TenantID', ''))
        record_property_id = record.get('PropertyID', '')
        
        if record_tenant_id == tenant_id_str and record_property_id == property_id:
            # Get the tenant name
            result['tenant_name'] = record.get('TenantName', '')
            
            # Get the MatchedEstimate value
            matched_estimate = record.get('MatchedEstimate', '')
            
            try:
                if matched_estimate and matched_estimate != '':
                    amount = Decimal(str(matched_estimate)).quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)
                    logger.debug(f"Found old monthly payment for tenant {tenant_id}: {amount}")
                    result['old_monthly'] = amount
                else:
                    logger.debug(f"Empty MatchedEstimate value for tenant {tenant_id} in property {property_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid MatchedEstimate value for tenant {tenant_id}: {matched_estimate} - {str(e)}")
                logger.debug(f"Full record: {record}")
            
            # Return early once the tenant is found
            return result
    
    # No record found
    logger.debug(f"No tenant data found for tenant {tenant_id} in property {property_id}")
    return result

def get_old_monthly_payment(tenant_id: str, property_id: str) -> Decimal:
    """
    Get the old monthly payment amount for a tenant from the MatchedEstimate field.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        
    Returns:
        Old monthly payment amount as Decimal, rounded to 2 decimal places
    """
    # Get tenant data including old monthly payment
    tenant_data = get_tenant_data(tenant_id, property_id)
    
    # Return old monthly payment amount
    return tenant_data['old_monthly']


def calculate_new_monthly_payment(
    final_amount: Decimal,
    periods_count: int = 12
) -> Decimal:
    """
    Calculate the new monthly payment amount based on the total reconciliation amount.
    
    Args:
        final_amount: Final reconciliation amount for the year
        periods_count: Number of periods to divide by (default: 12 months)
        
    Returns:
        New monthly payment amount as Decimal, rounded to 2 decimal places
    """
    if periods_count <= 0:
        logger.warning(f"Invalid periods_count: {periods_count}, using default of 12")
        periods_count = 12
    
    # Calculate and round to 2 decimal places
    return (final_amount / Decimal(periods_count)).quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def calculate_percentage_change(old_amount: Decimal, new_amount: Decimal) -> Dict[str, Any]:
    """
    Calculate percentage change between old and new amounts.
    
    Args:
        old_amount: Old amount
        new_amount: New amount
        
    Returns:
        Dictionary with percentage change information
    """
    # Calculate the raw difference
    difference = new_amount - old_amount
    
    # Handle special case for percentage change
    if old_amount == Decimal('0'):
        if new_amount == Decimal('0'):
            percentage_change = Decimal('0')
            change_type = "no_change"
        else:
            percentage_change = Decimal('100')
            change_type = "first_billing"
    else:
        percentage_change = (difference / old_amount * Decimal('100')).quantize(
            PCT_QUANTIZE, rounding=ROUND_HALF_UP
        )
        
        if percentage_change > Decimal('0'):
            change_type = "increase"
        elif percentage_change < Decimal('0'):
            change_type = "decrease"
        else:
            change_type = "no_change"
    
    # Flag large changes (over 20%)
    is_significant = abs(percentage_change) >= Decimal('20')
    
    return {
        "difference": difference,
        "percentage_change": percentage_change,
        "change_type": change_type,
        "is_significant": is_significant
    }


def get_payment_comparison(
    tenant_id: str,
    property_id: str,
    final_amount: Decimal,
    periods_count: int = 12,
    tenant_name: str = None
) -> Dict[str, Any]:
    """
    Get a comparison between old and new monthly payment amounts.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        final_amount: Final reconciliation amount for the year
        periods_count: Number of periods for new amount calculation (default: 12)
        tenant_name: Optional tenant name for logging purposes
        
    Returns:
        Dictionary with payment comparison details
    """
    # Get tenant data including old monthly payment and name
    tenant_data = get_tenant_data(tenant_id, property_id)
    old_monthly = tenant_data['old_monthly']
    
    # Use provided tenant name or fall back to data lookup
    if tenant_name is None:
        tenant_name = tenant_data['tenant_name']
    
    # Calculate new monthly payment
    new_monthly = calculate_new_monthly_payment(final_amount, periods_count)
    
    # Calculate change metrics
    change_info = calculate_percentage_change(old_monthly, new_monthly)
    
    # Build complete comparison record
    comparison = {
        'tenant_id': tenant_id,
        'property_id': property_id,
        'tenant_name': tenant_name,
        'old_monthly': old_monthly,
        'new_monthly': new_monthly,
        'difference': change_info['difference'],
        'percentage_change': change_info['percentage_change'],
        'change_type': change_info['change_type'],
        'is_significant': change_info['is_significant']
    }
    
    # Log significant changes
    if comparison['is_significant']:
        tenant_display = f"{tenant_name} (ID: {tenant_id})" if tenant_name else f"tenant {tenant_id}"
        logger.warning(
            f"Significant payment change for {tenant_display}: "
            f"${float(old_monthly):.2f} → ${float(new_monthly):.2f} "
            f"({float(change_info['percentage_change']):.1f}%)"
        )
    
    return comparison


def clear_cache() -> None:
    """Clear the tenant CAM data cache."""
    global _TENANT_CAM_CACHE
    _TENANT_CAM_CACHE = None
    logger.debug("Tenant CAM data cache cleared")


def generate_payment_change_report(
    comparisons: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> str:
    """
    Generate a formatted payment change report from a list of payment comparisons.
    
    Args:
        comparisons: List of payment comparison dictionaries
        output_path: Optional output path for the report
        
    Returns:
        Path to the generated report file
    """
    # Create default output path if not provided
    if not output_path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join('Output', 'Reports')
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"payment_changes_{timestamp}.csv")
    
    # Determine fields based on available data
    fields = [
        'tenant_id', 'tenant_name', 'property_id',
        'old_monthly', 'new_monthly', 'difference', 
        'percentage_change', 'change_type', 'is_significant'
    ]
    
    # Write the CSV file
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()
            
            for comparison in comparisons:
                # Convert Decimal values to strings for CSV writing
                row = {}
                for key, value in comparison.items():
                    if key in fields:
                        if isinstance(value, Decimal):
                            if key == 'percentage_change':
                                row[key] = f"{float(value):.1f}%"
                            else:
                                row[key] = f"${float(value):.2f}"
                        elif key == 'is_significant':
                            row[key] = "Yes" if value else "No"
                        else:
                            row[key] = value
                
                writer.writerow(row)
        
        logger.info(f"Generated payment change report with {len(comparisons)} rows: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating payment change report: {str(e)}")
        return ""


if __name__ == "__main__":
    # Example usage
    import sys
    import csv
    import datetime
    
    # Configure logging for direct script execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command-line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--report':
        # Report generation mode
        if len(sys.argv) > 2:
            input_json = sys.argv[2]
        else:
            # Look for most recent payment_changes JSON file
            import glob
            json_files = sorted(glob.glob(os.path.join('Output', 'payment_changes_*.json')), reverse=True)
            input_json = json_files[0] if json_files else None
            
        if input_json and os.path.exists(input_json):
            # Load comparison data from JSON
            with open(input_json, 'r') as f:
                comparison_data = json.load(f)
                
            # Convert numeric values to Decimal
            for item in comparison_data:
                for key in ['old_monthly', 'new_monthly', 'difference', 'percentage_change']:
                    if key in item:
                        item[key] = Decimal(str(item[key]))
            
            # Generate report
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join('Output', 'Reports', f"payment_changes_report_{timestamp}.csv")
            generate_payment_change_report(comparison_data, report_path)
            
            print(f"Generated report: {report_path}")
        else:
            print("No payment comparison data found.")
        
        sys.exit(0)
    
    # Default test data
    test_tenant_id = "1001"
    test_property_id = "ELW"
    
    # Check if command-line parameters provided
    if len(sys.argv) > 2:
        test_tenant_id = sys.argv[1]
        test_property_id = sys.argv[2]
    
    # Test getting old payment
    old_payment = get_old_monthly_payment(test_tenant_id, test_property_id)
    
    print(f"\nOld Monthly Payment:")
    print(f"Amount: ${float(old_payment):.2f}")
    
    # Test payment comparison with different scenarios
    test_cases = [
        ("No change", Decimal(str(old_payment)) * 12),
        ("Small increase (5%)", Decimal(str(old_payment)) * Decimal('12.05')),
        ("Large increase (30%)", Decimal(str(old_payment)) * Decimal('15.6')),
        ("Decrease (-10%)", Decimal(str(old_payment)) * Decimal('10.8')),
        ("First billing", Decimal('12000'))
    ]
    
    # Store comparisons for report
    comparisons = []
    
    for case_name, amount in test_cases:
        # Clear cache before each test to ensure clean state
        clear_cache()
        
        print(f"\n--- Test Case: {case_name} ---")
        comparison = get_payment_comparison(
            test_tenant_id,
            test_property_id,
            amount
        )
        
        comparisons.append(comparison)
        
        print(f"Old Monthly: ${float(comparison['old_monthly']):.2f}")
        print(f"New Monthly: ${float(comparison['new_monthly']):.2f}")
        print(f"Difference: ${float(comparison['difference']):.2f}")
        print(f"Percentage Change: {float(comparison['percentage_change']):.1f}%")
        print(f"Change Type: {comparison['change_type']}")
        print(f"Significant Change: {'Yes' if comparison['is_significant'] else 'No'}")
    
    # Generate test report
    if comparisons:
        print("\nGenerating test report...")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join('Output', 'Reports', f"payment_changes_test_{timestamp}.csv")
        generate_payment_change_report(comparisons, report_path)
        print(f"Report generated: {report_path}")