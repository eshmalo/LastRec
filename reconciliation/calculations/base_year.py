#!/usr/bin/env python3
"""
Base Year Calculation Module

This module calculates base year adjustments for reconciliation.
It determines if a base year applies and calculates the adjusted amount 
that exceeds the base year threshold.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


def is_base_year_applicable(
    recon_year: int,
    base_year_setting: Optional[str],
    settings: Dict[str, Any]
) -> bool:
    """
    Determine if base year adjustment applies to the current reconciliation.
    
    Args:
        recon_year: Current reconciliation year
        base_year_setting: Base year setting from settings dictionary
        settings: Full settings dictionary
        
    Returns:
        True if base year adjustment applies, False otherwise
    """
    # If no base year specified, then no adjustment applies
    if not base_year_setting:
        return False
    
    # Try to convert base year to int
    try:
        base_year = int(base_year_setting)
    except (ValueError, TypeError):
        logger.error(f"Invalid base year format: {base_year_setting}")
        return False
    
    # Base year adjustment only applies if reconciliation year is after base year
    return recon_year > base_year


def get_base_year_amount(settings: Dict[str, Any]) -> Decimal:
    """
    Get the base year amount from settings.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Base year amount as Decimal
    """
    base_year_amount_str = settings.get('settings', {}).get('base_year_amount', '0')
    
    # Handle empty string or None
    if not base_year_amount_str:
        return Decimal('0')
    
    try:
        return Decimal(str(base_year_amount_str))
    except (ValueError, TypeError):
        logger.error(f"Invalid base year amount: {base_year_amount_str}, using 0")
        return Decimal('0')


def calculate_base_year_adjustment(
    recon_year: int,
    base_year_total: Decimal,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate base year adjustment for the reconciliation.
    
    Args:
        recon_year: Current reconciliation year
        base_year_total: Total amount subject to base year adjustment
        settings: Settings dictionary
        
    Returns:
        Dictionary with base year calculation results
    """
    base_year_setting = settings.get('settings', {}).get('base_year')
    
    # Check if base year adjustment applies
    applies = is_base_year_applicable(recon_year, base_year_setting, settings)
    
    # If base year doesn't apply, return full amount
    if not applies:
        logger.info("Base year adjustment does not apply")
        return {
            'base_year_applies': False,
            'base_year': None,
            'base_year_amount': Decimal('0'),
            'total_before_adjustment': base_year_total,
            'after_base_adjustment': base_year_total
        }
    
    # Get base year amount
    base_amount = get_base_year_amount(settings)
    
    # Calculate amount after base year adjustment (never less than zero)
    after_base = max(Decimal('0'), base_year_total - base_amount)
    
    # Log the calculation
    logger.info(
        f"Base year adjustment: {base_year_total} - {base_amount} = {after_base}"
    )
    
    return {
        'base_year_applies': True,
        'base_year': base_year_setting,
        'base_year_amount': base_amount,
        'total_before_adjustment': base_year_total,
        'after_base_adjustment': after_base
    }


def apply_base_year_exclusions(
    cam_tax_admin_results: Dict[str, Any],
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply base year exclusions to the calculation.
    
    This function processes the filtered GL entries and recalculates totals
    after applying any base year-specific exclusions.
    
    Args:
        cam_tax_admin_results: Results from CAM/TAX/Admin calculations
        settings: Settings dictionary
        
    Returns:
        Updated CAM/TAX/Admin results with base year exclusions applied
    """
    # Create a copy of original results to modify
    adjusted_results = cam_tax_admin_results.copy()
    
    # Get GL exclusions for base year calculations
    base_exclusions = settings.get('settings', {}).get('gl_exclusions', {}).get('base', [])
    
    # If no exclusions, just return the original results
    if not base_exclusions:
        return adjusted_results
    
    # Get filtered GL data that's specifically for base year calculations
    filtered_gl = cam_tax_admin_results.get('filtered_gl', {})
    base_entries = filtered_gl.get('base', [])
    
    # If we have base-specific entries after GL filtering, use those
    if base_entries:
        # Calculate new base year total from filtered entries
        base_year_total = sum(entry.get('Net Amount', Decimal('0')) for entry in base_entries)
        logger.info(f"Applied base year exclusions: {len(filtered_gl.get('cam', [])) - len(base_entries)} "
                  f"entries excluded, base year total: {base_year_total}")
        
        # Update the base year total in results
        adjusted_results['base_year_total'] = base_year_total
    
    return adjusted_results


def calculate_base_year(
    recon_year: int,
    cam_tax_admin_results: Dict[str, Any],
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main function to calculate base year adjustments.
    
    Args:
        recon_year: Current reconciliation year
        cam_tax_admin_results: Results from CAM/TAX/Admin calculations
        settings: Settings dictionary
        
    Returns:
        Dictionary with base year calculation results
    """
    # Apply any base year exclusions
    adjusted_results = apply_base_year_exclusions(cam_tax_admin_results, settings)
    
    # Get the total amount subject to base year adjustment
    base_year_total = adjusted_results.get('base_year_total', Decimal('0'))
    
    # Calculate base year adjustment
    base_year_results = calculate_base_year_adjustment(
        recon_year,
        base_year_total,
        settings
    )
    
    # Return comprehensive results
    return {
        'cam_tax_admin_results': adjusted_results,
        'base_year_results': base_year_results,
        'total_after_base_year': base_year_results.get('after_base_adjustment', Decimal('0'))
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    recon_year = 2024
    
    mock_cam_tax_admin = {
        'cam_total': Decimal('6000.00'),
        'tax_total': Decimal('12000.00'),
        'admin_fee_base': Decimal('6000.00'),
        'admin_fee_amount': Decimal('900.00'),  # 15% of 6000
        'combined_total': Decimal('18000.00'),  # 6000 + 12000
        'cap_base_total': Decimal('18900.00'),  # 18000 + 900
        'base_year_total': Decimal('18900.00'),  # 18000 + 900
        'include_admin_in_cap': True,
        'include_admin_in_base': True
    }
    
    # Case 1: Base year applies
    mock_settings_1 = {
        'settings': {
            'base_year': '2023',
            'base_year_amount': '10000.00'
        }
    }
    
    # Case 2: Base year doesn't apply
    mock_settings_2 = {
        'settings': {
            'base_year': '2024',  # Same as recon year
            'base_year_amount': '10000.00'
        }
    }
    
    # Case 3: No base year specified
    mock_settings_3 = {
        'settings': {
            'base_year': '',
            'base_year_amount': ''
        }
    }
    
    # Test all cases
    for i, settings in enumerate([mock_settings_1, mock_settings_2, mock_settings_3], 1):
        print(f"\n--- Case {i} ---")
        result = calculate_base_year(recon_year, mock_cam_tax_admin, settings)
        
        base_results = result.get('base_year_results', {})
        print(f"Base Year Applies: {base_results.get('base_year_applies')}")
        
        if base_results.get('base_year_applies'):
            print(f"Base Year: {base_results.get('base_year')}")
            print(f"Base Year Amount: ${float(base_results.get('base_year_amount')):,.2f}")
            print(f"Total Before Adjustment: ${float(base_results.get('total_before_adjustment')):,.2f}")
            print(f"After Base Adjustment: ${float(base_results.get('after_base_adjustment')):,.2f}")
        else:
            print(f"Total (No Adjustment): ${float(base_results.get('total_before_adjustment')):,.2f}")