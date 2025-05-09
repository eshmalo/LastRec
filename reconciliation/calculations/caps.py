#!/usr/bin/env python3
"""
Cap Enforcement Module

This module handles cap limit enforcement for reconciliation calculations.
It calculates the maximum allowable increase based on cap settings and
applies cap limits to ensure expenses don't exceed the allowed threshold.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Union

from reconciliation.cap_override_handler import get_reference_amount, load_cap_history

# Configure logging
logger = logging.getLogger(__name__)


def get_cap_percentage(settings: Dict[str, Any]) -> Decimal:
    """
    Get the cap percentage from settings.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Cap percentage as Decimal (e.g., 0.05 for 5%)
    """
    cap_percentage_str = settings.get('settings', {}).get('cap_settings', {}).get('cap_percentage', '0')
    
    # Handle empty string or None
    if not cap_percentage_str:
        return Decimal('0')
    
    try:
        return Decimal(str(cap_percentage_str))
    except (ValueError, TypeError):
        logger.error(f"Invalid cap percentage: {cap_percentage_str}, using 0")
        return Decimal('0')


def get_cap_type(settings: Dict[str, Any]) -> str:
    """
    Get the cap type from settings.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Cap type string ('previous_year' or 'highest_previous_year')
    """
    cap_type = settings.get('settings', {}).get('cap_settings', {}).get('cap_type', 'previous_year')
    
    # Handle empty string
    if not cap_type:
        return 'previous_year'  # Default
    
    # Validate cap type
    if cap_type not in ('previous_year', 'highest_previous_year'):
        logger.warning(f"Unknown cap type: {cap_type}, using 'previous_year'")
        return 'previous_year'
    
    return cap_type


def get_min_max_increase(settings: Dict[str, Any]) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Get minimum and maximum increase percentages from settings.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Tuple of (min_increase, max_increase) as Decimals or None if not specified
    """
    min_increase_str = settings.get('settings', {}).get('min_increase', '')
    max_increase_str = settings.get('settings', {}).get('max_increase', '')
    
    # Convert min_increase to Decimal or None
    min_increase = None
    if min_increase_str:
        try:
            min_increase = Decimal(str(min_increase_str))
        except (ValueError, TypeError):
            logger.error(f"Invalid min increase: {min_increase_str}")
    
    # Convert max_increase to Decimal or None
    max_increase = None
    if max_increase_str:
        try:
            max_increase = Decimal(str(max_increase_str))
        except (ValueError, TypeError):
            logger.error(f"Invalid max increase: {max_increase_str}")
    
    return min_increase, max_increase


def get_stop_amount(settings: Dict[str, Any]) -> Optional[Decimal]:
    """
    Get the stop amount per square foot from settings.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Stop amount as Decimal or None if not specified
    """
    stop_amount_str = settings.get('settings', {}).get('stop_amount', '')
    
    if not stop_amount_str:
        return None
    
    try:
        return Decimal(str(stop_amount_str))
    except (ValueError, TypeError):
        logger.error(f"Invalid stop amount: {stop_amount_str}")
        return None


def calculate_cap_limit(
    tenant_id: str,
    recon_year: Union[str, int],
    settings: Dict[str, Any],
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    """
    Calculate the cap limit based on settings and cap history.
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        settings: Settings dictionary
        cap_history: Optional cap history dictionary, if None will be loaded from file
        
    Returns:
        Dictionary with cap limit calculation results
    """
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()
    
    # Get cap settings
    cap_percentage = get_cap_percentage(settings)
    cap_type = get_cap_type(settings)
    min_increase, max_increase = get_min_max_increase(settings)
    stop_amount = get_stop_amount(settings)
    
    # Convert recon_year to string if needed
    recon_year_str = str(recon_year)
    
    # Get reference amount from cap history
    ref_amount = get_reference_amount(tenant_id, recon_year, cap_type, cap_history)
    
    # Calculate standard cap limit
    standard_cap_limit = ref_amount * (Decimal('1') + cap_percentage)
    
    # Initialize the result
    result = {
        'reference_amount': ref_amount,
        'cap_percentage': cap_percentage,
        'cap_type': cap_type,
        'standard_cap_limit': standard_cap_limit,
        'effective_cap_limit': standard_cap_limit,  # Will be adjusted below
        'min_increase_applied': False,
        'max_increase_applied': False,
        'stop_amount_applied': False
    }
    
    # Apply minimum increase if specified
    if min_increase is not None and ref_amount > 0:
        min_limit = ref_amount * (Decimal('1') + min_increase)
        if min_limit > result['effective_cap_limit']:
            result['effective_cap_limit'] = min_limit
            result['min_increase_applied'] = True
            logger.info(f"Min increase limit applied: {min_limit}")
    
    # Apply maximum increase if specified
    if max_increase is not None and ref_amount > 0:
        max_limit = ref_amount * (Decimal('1') + max_increase)
        if max_limit < result['effective_cap_limit']:
            result['effective_cap_limit'] = max_limit
            result['max_increase_applied'] = True
            logger.info(f"Max increase limit applied: {max_limit}")
    
    # Apply stop amount if specified
    if stop_amount is not None:
        # Calculate stop amount based on tenant square footage
        square_footage = Decimal(str(settings.get('settings', {}).get('square_footage', '0') or '0'))
        
        if square_footage > 0:
            total_stop_amount = stop_amount * square_footage
            if total_stop_amount < result['effective_cap_limit']:
                result['effective_cap_limit'] = total_stop_amount
                result['stop_amount_applied'] = True
                logger.info(f"Stop amount limit applied: {total_stop_amount}")
                result['stop_amount'] = stop_amount
                result['square_footage'] = square_footage
    
    return result


def apply_cap_exclusions(
    after_base_amount: Decimal,
    gl_data: Dict[str, Any],
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply cap exclusions to the base amount.
    
    This function correctly handles cap exclusions by:
    1. Identifying GL entries subject to cap limits
    2. Separately tracking cap-excluded entries
    3. Returning both amounts for proper cap enforcement
    
    Args:
        after_base_amount: Amount after base year adjustment
        gl_data: GL data dictionary
        settings: Settings dictionary
        
    Returns:
        Dictionary with cap calculation components:
        - amount_subject_to_cap: Amount that should have cap limits applied
        - excluded_amount: Amount exempt from cap limits (to be added back after cap enforcement)
    """
    # Get filtered GL data for both the recovery category and cap-specific entries
    filtered_gl = gl_data.get('filtered_gl', {})
    
    # Get the recovery category (cam or ret) from the requested categories
    # Default to cam if not specified
    categories = settings.get('categories', ['cam'])
    recovery_category = categories[0] if categories else 'cam'
    
    # Get entries for the recovery category and cap-specific entries
    recovery_entries = filtered_gl.get(recovery_category, [])
    cap_entries = filtered_gl.get('cap', [])
    
    # Log the recovery category being used
    logger.info(f"Using recovery category '{recovery_category}' for cap calculations")
    logger.info(f"Recovery entries: {len(recovery_entries)}, Cap entries: {len(cap_entries)}")
    
    # Initialize amounts
    amount_subject_to_cap = Decimal('0')
    excluded_amount = Decimal('0')
    
    # Process differently based on whether we have cap-specific entries
    if cap_entries and recovery_entries:
        # Create sets of GL account numbers for easy comparison
        recovery_gl_accounts = {entry.get('GL Account') for entry in recovery_entries}
        cap_gl_accounts = {entry.get('GL Account') for entry in cap_entries}
        
        # Identify excluded accounts (in recovery but not in cap)
        excluded_gl_accounts = recovery_gl_accounts - cap_gl_accounts
        
        logger.info(f"GL accounts subject to exclusion: {excluded_gl_accounts}")
        
        # Calculate amounts for entries subject to cap and excluded from cap
        for entry in recovery_entries:
            gl_account = entry.get('GL Account')
            amount = entry.get('Net Amount', Decimal('0'))
            
            if gl_account in excluded_gl_accounts:
                excluded_amount += amount
                logger.debug(f"Excluded from cap: {gl_account} with amount {amount}")
            else:
                amount_subject_to_cap += amount
                logger.debug(f"Subject to cap: {gl_account} with amount {amount}")
        
        # Get admin fee settings for cap calculations
        admin_fee_in_cap_base = settings.get('settings', {}).get('admin_fee_in_cap_base', '')
        admin_fee_amount = gl_data.get('totals', {}).get('admin_fee_amount', Decimal('0'))
        
        # Apply admin fee based on settings
        if admin_fee_in_cap_base:
            if 'cap' in admin_fee_in_cap_base:
                # Admin fee is subject to cap
                amount_subject_to_cap += admin_fee_amount
                logger.info(f"Including admin fee in cap amount: {admin_fee_amount}")
            else:
                # Admin fee is excluded from cap
                excluded_amount += admin_fee_amount
                logger.info(f"Admin fee excluded from cap: {admin_fee_amount}")
        else:
            # Default behavior - include admin fee in cap calculations
            amount_subject_to_cap += admin_fee_amount
            logger.info(f"Default: Including admin fee in cap amount: {admin_fee_amount}")
        
        # Log the results
        logger.info(f"Amount subject to cap: {amount_subject_to_cap}")
        logger.info(f"Amount excluded from cap: {excluded_amount}")
        logger.info(f"Total amount: {amount_subject_to_cap + excluded_amount}")
        
        # Total should match after_base_amount unless there are administrative adjustments
        if abs((amount_subject_to_cap + excluded_amount) - after_base_amount) > Decimal('0.01'):
            logger.warning(f"Cap calculation total {amount_subject_to_cap + excluded_amount} "
                          f"differs from after_base_amount {after_base_amount}")
    else:
        # If we don't have both recovery and cap entries, use the original amount
        # This is a fallback case and should be investigated if it occurs frequently
        logger.warning(f"Missing recovery or cap entries. Using after_base_amount: {after_base_amount}")
        amount_subject_to_cap = after_base_amount
        excluded_amount = Decimal('0')
    
    return {
        'amount_subject_to_cap': amount_subject_to_cap,
        'excluded_amount': excluded_amount,
        'total_amount': amount_subject_to_cap + excluded_amount
    }


def enforce_cap(
    tenant_id: str,
    recon_year: Union[str, int],
    after_base_amount: Decimal,
    gl_data: Dict[str, Any],
    settings: Dict[str, Any],
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    """
    Enforce cap limits on the reconciliation amount.
    
    This function:
    1. Separates amounts subject to cap and excluded from cap
    2. Applies cap limits only to the portion subject to caps
    3. Adds back excluded amounts after applying caps
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        after_base_amount: Amount after base year adjustment
        gl_data: GL data dictionary
        settings: Settings dictionary
        cap_history: Optional cap history dictionary
        
    Returns:
        Dictionary with cap enforcement results
    """
    # Apply cap exclusions - now returns a dictionary with detailed results
    cap_exclusion_results = apply_cap_exclusions(after_base_amount, gl_data, settings)
    
    # Extract the amounts from the results
    amount_subject_to_cap = cap_exclusion_results.get('amount_subject_to_cap', Decimal('0'))
    excluded_amount = cap_exclusion_results.get('excluded_amount', Decimal('0'))
    total_amount = cap_exclusion_results.get('total_amount', Decimal('0'))
    
    logger.info(f"After applying cap exclusions: amount_subject_to_cap={amount_subject_to_cap}, "
               f"excluded_amount={excluded_amount}, total={total_amount} (from {after_base_amount})")
    
    # Calculate cap limit
    cap_limit_results = calculate_cap_limit(tenant_id, recon_year, settings, cap_history)
    
    # Determine if cap applies (only if we have a reference amount)
    cap_applies = cap_limit_results.get('reference_amount', Decimal('0')) > 0
    
    # Log cap settings for debugging
    logger.info(f"Tenant {tenant_id} cap settings:")
    logger.info(f"  Reference amount: {cap_limit_results.get('reference_amount', Decimal('0'))}")
    logger.info(f"  Cap applies: {cap_applies}")
    logger.info(f"  Amount subject to cap: {amount_subject_to_cap}")
    logger.info(f"  Excluded amount: {excluded_amount}")
    logger.info(f"  Cap limit: {cap_limit_results.get('effective_cap_limit', Decimal('0'))}")
    
    # Check if there's a cap override in the settings
    cap_override_year = settings.get("settings", {}).get("cap_settings", {}).get("override_cap_year")
    cap_override_amount = settings.get("settings", {}).get("cap_settings", {}).get("override_cap_amount")
    
    if cap_override_year and cap_override_amount:
        logger.info(f"Tenant {tenant_id} has cap override: year={cap_override_year}, amount={cap_override_amount}")
    
    # Apply cap limits ONLY to the amount subject to cap
    capped_subject_amount = amount_subject_to_cap
    cap_limited = False
    
    if cap_applies and amount_subject_to_cap > cap_limit_results.get('effective_cap_limit', Decimal('0')):
        capped_subject_amount = cap_limit_results.get('effective_cap_limit', Decimal('0'))
        cap_limited = True
        logger.info(f"Cap limit applied: {amount_subject_to_cap} reduced to {capped_subject_amount}")
    
    # Calculate final amount by adding back excluded amounts
    final_capped_amount = capped_subject_amount + excluded_amount
    
    logger.info(f"Final capped amount: {final_capped_amount} = {capped_subject_amount} (capped) + {excluded_amount} (excluded)")
    
    # Return comprehensive results including all components
    return {
        'cap_applies': cap_applies,
        'amount_subject_to_cap': amount_subject_to_cap,
        'excluded_amount': excluded_amount,
        'cap_limit_results': cap_limit_results,
        'capped_subject_amount': capped_subject_amount,
        'final_capped_amount': final_capped_amount,
        'cap_limited': cap_limited,
        'cap_exclusion_results': cap_exclusion_results  # Include detailed cap exclusion results
    }


def calculate_caps(
    tenant_id: str,
    recon_year: Union[str, int],
    base_year_results: Dict[str, Any],
    gl_data: Dict[str, Any],
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main function to calculate cap enforcement.
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        base_year_results: Results from base year calculations
        gl_data: GL data dictionary
        settings: Settings dictionary
        
    Returns:
        Dictionary with cap calculation results
    """
    # Get the amount after base year adjustment
    after_base_amount = base_year_results.get('total_after_base_year', Decimal('0'))
    
    # Pass categories to enforce_cap via settings
    if 'categories' not in settings and 'categories' in gl_data:
        settings['categories'] = gl_data.get('categories', ['cam'])
    
    # Enforce cap limits
    cap_results = enforce_cap(tenant_id, recon_year, after_base_amount, gl_data, settings)
    
    # Log detailed breakdown for clarity
    logger.info(f"Cap calculation for tenant {tenant_id}:")
    logger.info(f"  After base year amount: {after_base_amount}")
    logger.info(f"  Amount subject to cap: {cap_results.get('amount_subject_to_cap', Decimal('0'))}")
    logger.info(f"  Capped amount: {cap_results.get('capped_subject_amount', Decimal('0'))} (cap applied: {cap_results.get('cap_limited', False)})")
    logger.info(f"  Excluded amount: {cap_results.get('excluded_amount', Decimal('0'))}")
    logger.info(f"  Final recoverable amount: {cap_results.get('final_capped_amount', Decimal('0'))}")
    
    # Return comprehensive results using the new final_capped_amount field
    return {
        'base_year_results': base_year_results,
        'cap_results': cap_results,
        'final_recoverable_amount': cap_results.get('final_capped_amount', Decimal('0')),
        'cap_breakdown': {
            'amount_subject_to_cap': cap_results.get('amount_subject_to_cap', Decimal('0')),
            'capped_subject_amount': cap_results.get('capped_subject_amount', Decimal('0')),
            'excluded_amount': cap_results.get('excluded_amount', Decimal('0')),
            'cap_limited': cap_results.get('cap_limited', False)
        }
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    tenant_id = "1234"
    recon_year = 2024
    
    # Mock base year results
    mock_base_year_results = {
        'base_year_applies': True,
        'base_year': '2022',
        'base_year_amount': Decimal('10000.00'),
        'total_before_adjustment': Decimal('18000.00'),
        'total_after_base_year': Decimal('8000.00')  # 18000 - 10000
    }
    
    # Mock GL data
    mock_gl_data = {
        'filtered_gl': {
            'cam': [],
            'ret': []
        },
        'totals': {}
    }
    
    # Mock settings
    mock_settings = {
        'tenant_id': tenant_id,
        'settings': {
            'square_footage': '1000',
            'cap_settings': {
                'cap_percentage': '0.05',  # 5%
                'cap_type': 'previous_year'
            },
            'min_increase': '0.03',  # 3%
            'max_increase': '0.08',  # 8%
            'stop_amount': '7.50'    # $7.50 per sq ft
        }
    }
    
    # Mock cap history - assume $7000 in previous year
    mock_cap_history = {
        tenant_id: {
            '2023': 7000.00
        }
    }
    
    # Calculate caps
    result = calculate_caps(
        tenant_id, 
        recon_year, 
        mock_base_year_results, 
        mock_gl_data, 
        mock_settings
    )
    
    # Print results
    print("\nCap Calculation Results:")
    cap_results = result.get('cap_results', {})
    cap_limit_results = cap_results.get('cap_limit_results', {})
    
    print(f"Cap Applies: {cap_results.get('cap_applies')}")
    print(f"Reference Amount: ${float(cap_limit_results.get('reference_amount', 0)):,.2f}")
    print(f"Cap Percentage: {float(cap_limit_results.get('cap_percentage', 0)) * 100:.1f}%")
    print(f"Cap Type: {cap_limit_results.get('cap_type')}")
    print(f"Standard Cap Limit: ${float(cap_limit_results.get('standard_cap_limit', 0)):,.2f}")
    
    if cap_limit_results.get('min_increase_applied'):
        print(f"Min Increase Applied")
    
    if cap_limit_results.get('max_increase_applied'):
        print(f"Max Increase Applied")
    
    if cap_limit_results.get('stop_amount_applied'):
        stop_amount = cap_limit_results.get('stop_amount', 0)
        square_footage = cap_limit_results.get('square_footage', 0)
        print(f"Stop Amount Applied: ${float(stop_amount):,.2f}/sq ft × {float(square_footage):,.0f} sq ft")
    
    print(f"Effective Cap Limit: ${float(cap_limit_results.get('effective_cap_limit', 0)):,.2f}")
    print(f"Amount Before Cap: ${float(cap_results.get('amount_before_cap', 0)):,.2f}")
    print(f"Cap Limited: {cap_results.get('cap_limited')}")
    print(f"Final Recoverable Amount: ${float(result.get('final_recoverable_amount', 0)):,.2f}")