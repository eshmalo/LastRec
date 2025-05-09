#!/usr/bin/env python3
"""
CAM/TAX/Admin Fee Calculation Module

This module calculates CAM, TAX, and Admin Fee amounts based on filtered GL data
and the property/tenant settings.
"""

import logging
import decimal
from decimal import Decimal
from typing import Dict, Any, List, Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)


def calculate_cam_total(cam_entries: List[Dict[str, Any]]) -> Decimal:
    """
    Calculate the total CAM amount from filtered entries.
    
    Args:
        cam_entries: List of CAM transactions
        
    Returns:
        Total CAM amount
    """
    total = sum(entry.get('Net Amount', Decimal('0')) for entry in cam_entries)
    logger.info(f"Calculated CAM total: {total}")
    return total


def calculate_tax_total(tax_entries: List[Dict[str, Any]]) -> Decimal:
    """
    Calculate the total TAX (RET) amount from filtered entries.
    
    Args:
        tax_entries: List of TAX transactions
        
    Returns:
        Total TAX amount
    """
    total = sum(entry.get('Net Amount', Decimal('0')) for entry in tax_entries)
    logger.info(f"Calculated TAX total: {total}")
    return total


def calculate_admin_fee_base(
    cam_entries: List[Dict[str, Any]],
    settings: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Calculate the admin fee base based on filtered CAM entries.
    
    Args:
        cam_entries: List of CAM transactions
        settings: Settings dictionary with admin fee inclusions/exclusions
        
    Returns:
        Tuple of (list of admin fee eligible transactions, total admin fee base amount)
    """
    gl_settings = settings.get('settings', {})
    admin_inclusions = gl_settings.get('gl_inclusions', {}).get('admin_fee', [])
    admin_exclusions = gl_settings.get('gl_exclusions', {}).get('admin_fee', [])
    
    admin_fee_transactions = []
    admin_fee_base = Decimal('0')
    
    # If no specific admin fee inclusions, use all CAM transactions as the base
    use_all_cam = len(admin_inclusions) == 0
    
    for transaction in cam_entries:
        gl_account = transaction.get('GL Account', '')
        
        # Check if this transaction should be included in admin fee base
        include_in_base = use_all_cam
        
        # Check inclusions
        for inclusion in admin_inclusions:
            if '-' in inclusion:  # Range
                start, end = inclusion.split('-')
                clean_account = gl_account.replace('MR', '')
                if start <= clean_account <= end:
                    include_in_base = True
                    break
            elif inclusion == gl_account or inclusion == gl_account.replace('MR', ''):
                include_in_base = True
                break
        
        # If not explicitly included, skip
        if not include_in_base:
            continue
        
        # Check exclusions
        for exclusion in admin_exclusions:
            if '-' in exclusion:  # Range
                start, end = exclusion.split('-')
                clean_account = gl_account.replace('MR', '')
                if start <= clean_account <= end:
                    include_in_base = False
                    break
            elif exclusion == gl_account or exclusion == gl_account.replace('MR', ''):
                include_in_base = False
                break
        
        # If should be included in admin fee base
        if include_in_base:
            admin_fee_transactions.append(transaction)
            admin_fee_base += transaction.get('Net Amount', Decimal('0'))
    
    logger.info(f"Admin fee base: {admin_fee_base} from {len(admin_fee_transactions)} transactions")
    
    return admin_fee_transactions, admin_fee_base


def calculate_admin_fee_amount(admin_fee_base: Decimal, settings: Dict[str, Any]) -> Decimal:
    """
    Calculate the admin fee amount based on base and percentage.
    
    Args:
        admin_fee_base: Base amount for admin fee calculation
        settings: Settings dictionary with admin fee percentage
        
    Returns:
        Admin fee amount
    """
    admin_fee_percentage_str = settings.get('settings', {}).get('admin_fee_percentage', '')
    
    # Only calculate admin fee if a percentage is explicitly set
    if not admin_fee_percentage_str or not admin_fee_percentage_str.strip():
        logger.info(f"No admin fee percentage specified, setting admin fee to 0")
        return Decimal('0')
    
    # Try to parse the admin fee percentage
    try:
        # Make sure we have a proper decimal - handle percentage format
        admin_fee_percentage_str = str(admin_fee_percentage_str).strip()
        
        # Remove % sign if present
        if admin_fee_percentage_str.endswith('%'):
            admin_fee_percentage_str = admin_fee_percentage_str[:-1]
            
        # Convert to decimal and handle percentage conversion
        admin_fee_percentage = Decimal(admin_fee_percentage_str)
        
        # If it's a percentage like 15, convert to 0.15
        if admin_fee_percentage > 1:
            admin_fee_percentage = admin_fee_percentage / Decimal('100')
            
        admin_fee_amount = admin_fee_base * admin_fee_percentage
        logger.info(f"Calculated admin fee amount: {admin_fee_amount} ({admin_fee_percentage * 100}% of {admin_fee_base})")
        return admin_fee_amount
    except (ValueError, TypeError, decimal.InvalidOperation) as e:
        logger.error(f"Invalid admin fee percentage: {admin_fee_percentage_str}, error: {str(e)}, using 0")
        return Decimal('0')


def is_admin_fee_in_cap_base(settings: Dict[str, Any]) -> bool:
    """
    Determine if admin fee should be included in cap base.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        True if admin fee should be included in cap base, False otherwise
    """
    admin_fee_in_cap_base = settings.get('settings', {}).get('admin_fee_in_cap_base', '')
    
    # It should be included if the setting contains "cap"
    return 'cap' in admin_fee_in_cap_base.lower()


def is_admin_fee_in_base_year(settings: Dict[str, Any]) -> bool:
    """
    Determine if admin fee should be included in base year calculations.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        True if admin fee should be included in base year, False otherwise
    """
    admin_fee_in_cap_base = settings.get('settings', {}).get('admin_fee_in_cap_base', '')
    
    # It should be included if the setting contains "base"
    return 'base' in admin_fee_in_cap_base.lower()


def calculate_cam_tax_admin(
    filtered_gl: Dict[str, List[Dict[str, Any]]],
    settings: Dict[str, Any],
    categories: List[str] = None
) -> Dict[str, Any]:
    """
    Main function to calculate CAM, TAX, and admin fee amounts.
    
    Args:
        filtered_gl: Dictionary with filtered GL entries by category
        settings: Settings dictionary
        categories: Optional list of categories to include in calculation
                   (defaults to ['cam', 'ret'] if not provided)
        
    Returns:
        Dictionary with calculation results
    """
    # Default to both categories if not specified
    if categories is None:
        categories = ['cam', 'ret']
    
    logger.info(f"Calculating CAM/TAX/Admin with categories: {categories}")
    
    # Calculate CAM total (only if CAM category was requested)
    cam_total = Decimal('0')
    if 'cam' in categories:
        cam_total = calculate_cam_total(filtered_gl.get('cam', []))
        logger.info(f"CAM total calculated: {cam_total}")
    else:
        logger.info("CAM category not requested, setting CAM total to 0")
    
    # Calculate TAX total (only if RET category was requested)
    tax_total = Decimal('0')
    if 'ret' in categories:
        tax_total = calculate_tax_total(filtered_gl.get('ret', []))
        logger.info(f"TAX total calculated: {tax_total}")
    else:
        logger.info("RET category not requested, setting TAX total to 0")
    
    # Calculate admin fee base and amount (based on CAM entries)
    # Only calculate if CAM category is included
    admin_eligible = []
    admin_fee_base = Decimal('0')
    admin_fee_amount = Decimal('0')
    admin_fee_percentage = Decimal('0')
    
    if 'cam' in categories:
        admin_eligible, admin_fee_base = calculate_admin_fee_base(
            filtered_gl.get('cam', []),
            settings
        )
        admin_fee_amount = calculate_admin_fee_amount(admin_fee_base, settings)
        
        # Get the admin fee percentage for reports
        admin_fee_percentage_str = settings.get('settings', {}).get('admin_fee_percentage', '')
        # Parse percentage for reporting
        if admin_fee_percentage_str and admin_fee_percentage_str.strip():
            try:
                admin_fee_percentage_str = str(admin_fee_percentage_str).strip()
                if admin_fee_percentage_str.endswith('%'):
                    admin_fee_percentage_str = admin_fee_percentage_str[:-1]
                admin_fee_percentage = Decimal(admin_fee_percentage_str)
                if admin_fee_percentage > 1:
                    admin_fee_percentage = admin_fee_percentage / Decimal('100')
            except:
                admin_fee_percentage = Decimal('0')
        
        logger.info(f"Admin fee amount calculated: {admin_fee_amount} ({admin_fee_percentage * 100}%)")
    else:
        logger.info("CAM category not requested, setting admin fee to 0")
    
    # Determine if admin fee should be included in cap and base year
    include_in_cap = is_admin_fee_in_cap_base(settings)
    include_in_base = is_admin_fee_in_base_year(settings)
    
    # Calculate combined totals based only on requested categories
    combined_total = cam_total + tax_total
    logger.info(f"Combined total (CAM + TAX): {combined_total}")
    
    # For cap calculation
    cap_base_total = combined_total
    if include_in_cap and 'cam' in categories:  # Only include admin if CAM was requested
        cap_base_total += admin_fee_amount
        logger.info(f"Including admin fee in cap base, total: {cap_base_total}")
    
    # For base year calculation
    base_year_total = combined_total
    if include_in_base and 'cam' in categories:  # Only include admin if CAM was requested
        base_year_total += admin_fee_amount
        logger.info(f"Including admin fee in base year, total: {base_year_total}")
    
    # Return comprehensive results with admin fee percentage for reporting
    return {
        'cam_total': cam_total,
        'tax_total': tax_total,
        'admin_fee_base': admin_fee_base,
        'admin_fee_amount': admin_fee_amount,
        'admin_fee_percentage': admin_fee_percentage,  # Add admin fee percentage for reporting
        'combined_total': combined_total,
        'cap_base_total': cap_base_total,
        'base_year_total': base_year_total,
        'include_admin_in_cap': include_in_cap,
        'include_admin_in_base': include_in_base,
        'admin_eligible_transactions': admin_eligible
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    mock_filtered_gl = {
        'cam': [
            {'GL Account': '5001', 'Net Amount': Decimal('1000.00')},
            {'GL Account': '5002', 'Net Amount': Decimal('2000.00')},
            {'GL Account': '5003', 'Net Amount': Decimal('3000.00')}
        ],
        'ret': [
            {'GL Account': '6001', 'Net Amount': Decimal('5000.00')},
            {'GL Account': '6002', 'Net Amount': Decimal('7000.00')}
        ]
    }
    
    mock_settings = {
        'settings': {
            'admin_fee_percentage': 0.15,
            'admin_fee_in_cap_base': 'cap,base',
            'gl_inclusions': {
                'admin_fee': []  # Empty means include all CAM
            },
            'gl_exclusions': {
                'admin_fee': []
            }
        }
    }
    
    # Calculate CAM/TAX/Admin
    result = calculate_cam_tax_admin(mock_filtered_gl, mock_settings)
    
    # Print results
    print("\nCAM/TAX/Admin Fee Calculation Results:")
    print(f"CAM Total: ${float(result['cam_total']):,.2f}")
    print(f"TAX Total: ${float(result['tax_total']):,.2f}")
    print(f"Admin Fee Base: ${float(result['admin_fee_base']):,.2f}")
    print(f"Admin Fee Amount: ${float(result['admin_fee_amount']):,.2f}")
    print(f"Combined Total: ${float(result['combined_total']):,.2f}")
    print(f"Cap Base Total: ${float(result['cap_base_total']):,.2f}")
    print(f"Base Year Total: ${float(result['base_year_total']):,.2f}")
    print(f"Include Admin in Cap: {result['include_admin_in_cap']}")
    print(f"Include Admin in Base: {result['include_admin_in_base']}")