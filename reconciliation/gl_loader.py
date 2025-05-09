#!/usr/bin/env python3
"""
GL Loader Module

This module loads and processes General Ledger (GL) entries for reconciliation.
It provides functions to filter and group GL entries based on account categories.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from decimal import Decimal

from reconciliation.utils.helpers import load_json, is_in_range

# Configure logging
logger = logging.getLogger(__name__)

# Path to the GL categories file
GL_CATEGORIES_PATH = os.path.join('Data', 'ManualInputs', 'gl_categories_with_property_and_periods.json')


def load_gl_data(property_id: str) -> List[Dict[str, Any]]:
    """
    Load GL data for a specific property.
    
    Args:
        property_id: Property identifier
        
    Returns:
        List of GL transactions
    """
    gl_file_path = os.path.join('Output', 'JSON', 'GL Master 3.json')
    
    try:
        gl_data = load_json(gl_file_path)
        
        # Filter for the specific property
        property_gl = [
            transaction for transaction in gl_data 
            if transaction.get('Property ID') == property_id
        ]
        
        logger.info(f"Loaded {len(property_gl)} GL transactions for property {property_id}")
        return property_gl
    except Exception as e:
        logger.error(f"Error loading GL data: {str(e)}")
        return []


def load_gl_categories() -> Dict[str, Any]:
    """
    Load GL account categories mapping.
    
    Returns:
        Dictionary mapping GL account ranges to categories
    """
    try:
        return load_json(GL_CATEGORIES_PATH)
    except Exception as e:
        logger.error(f"Error loading GL categories: {str(e)}")
        return {"gl_account_lookup": {}}


def get_gl_category(gl_account: str, gl_categories: Dict[str, Any]) -> Optional[str]:
    """
    Determine the category of a GL account.
    
    Args:
        gl_account: GL account number
        gl_categories: GL categories dictionary
        
    Returns:
        Category string ('cam', 'ret', etc.) or None if not found
    """
    # Clean the GL account by removing any 'MR' prefix
    clean_account = gl_account.replace('MR', '') if gl_account else ''
    
    # Handle empty categories dictionary
    if not gl_categories.get('gl_account_lookup'):
        logger.warning("No GL account lookup configured, account categorization may be incomplete")
        return None
    
    # Regular categorization from the lookup
    for range_key, range_info in gl_categories.get('gl_account_lookup', {}).items():
        start, end = range_key.split('-')
        clean_start = start.replace('MR', '')
        clean_end = end.replace('MR', '')
        
        if clean_start <= clean_account <= clean_end:
            return range_info.get('category')
    
    # If we get here, the account didn't match any range in the lookup
    logger.debug(f"Account {gl_account} did not match any GL category range")
    return None


def is_included(gl_account: str, inclusions: List[str], exclusions: List[str]) -> bool:
    """
    Check if a GL account should be included based on inclusion/exclusion rules.
    
    Args:
        gl_account: GL account number
        inclusions: List of inclusion patterns
        exclusions: List of exclusion patterns
        
    Returns:
        True if the account should be included, False otherwise
    """
    # Normalize the account for consistent comparison
    clean_account = gl_account.replace('MR', '')
    
    # If no inclusions specified, assume all are included
    is_included_flag = len(inclusions) == 0
    logger.debug(f"GL account {gl_account}: Initial inclusion state (no inclusions specified): {is_included_flag}")
    
    # Check inclusions first
    for inclusion in inclusions:
        inclusion_rule = inclusion.strip()
        if '-' in inclusion_rule:  # It's a range
            if is_in_range(gl_account, inclusion_rule):
                is_included_flag = True
                logger.debug(f"GL account {gl_account} is included based on range inclusion rule: {inclusion_rule}")
                break
        else:  # It's a single account
            clean_incl = inclusion_rule.replace('MR', '')
            if clean_incl == clean_account:
                is_included_flag = True
                logger.debug(f"GL account {gl_account} is included based on exact inclusion rule: {inclusion_rule}")
                break
    
    # If not included based on inclusion rules, no need to check exclusions
    if not is_included_flag:
        logger.debug(f"GL account {gl_account} is not included based on inclusion rules, skipping exclusion checks")
        return False
    
    # Check exclusions - this is critical for excluding specific accounts
    for exclusion in exclusions:
        exclusion_rule = exclusion.strip()
        if '-' in exclusion_rule:  # It's a range
            if is_in_range(gl_account, exclusion_rule):
                logger.info(f"Excluding GL account {gl_account} based on range exclusion: {exclusion_rule}")
                return False
        else:  # It's a single account
            clean_excl = exclusion_rule.replace('MR', '')
            if clean_excl == clean_account:
                logger.info(f"Excluding GL account {gl_account} based on exact exclusion: {exclusion_rule}")
                return False
    
    logger.debug(f"GL account {gl_account} final inclusion status: {is_included_flag}")
    return is_included_flag


def filter_gl_entries(
    gl_data: List[Dict[str, Any]], 
    settings: Dict[str, Any],
    recon_periods: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Filter and group GL entries based on settings and categories.
    
    Args:
        gl_data: List of GL transactions
        settings: Settings dictionary with inclusions/exclusions
        recon_periods: List of periods to include (YYYYMM format)
        
    Returns:
        Dictionary with grouped GL entries by category
    """
    gl_categories = load_gl_categories()
    
    # Get inclusion/exclusion settings
    gl_settings = settings.get('settings', {})
    inclusions = gl_settings.get('gl_inclusions', {})
    exclusions = gl_settings.get('gl_exclusions', {})
    
    # Log exclusions for debugging
    logger.info(f"GL exclusions configuration: {exclusions}")
    
    # Initialize result structure
    result = {
        'cam': [],
        'ret': [],
        'other': [],
        'base': [],  # For base year calculations
        'cap': []    # For cap calculations
    }
    
    # Debug counters
    debug_counted = 0
    filtered_by_gl = 0
    filtered_by_period = 0
    filtered_by_amount = 0
    period_distribution = {}
    gl_distribution = {}
    
    # Filter and group transactions
    for transaction in gl_data:
        debug_counted += 1
        gl_account = transaction.get('GL Account', '')
        period = transaction.get('PERIOD', '')
        gl_distribution[gl_account] = gl_distribution.get(gl_account, 0) + 1
        
        # Skip transactions with missing data
        if not gl_account or not period:
            continue
            
        period_distribution[period] = period_distribution.get(period, 0) + 1
        
        # Convert period to string for consistent comparison
        period_str = str(period)
        
        # Skip transactions outside the reconciliation periods
        if period_str not in recon_periods:
            filtered_by_period += 1
            continue
        
        # Convert Net Amount to Decimal for accurate calculations
        try:
            net_amount = Decimal(transaction.get('Net Amount', '0') or '0')
        except:
            logger.warning(f"Invalid Net Amount '{transaction.get('Net Amount')}' for {gl_account}")
            net_amount = Decimal('0')
        
        # Skip transactions with zero amount
        if net_amount == 0:
            filtered_by_amount += 1
            continue
        
        # Update the transaction with the Decimal amount
        transaction['Net Amount'] = net_amount
            
        # First attempt to categorize based on GL account ranges defined in settings
        # Check for special accounts in exclusion lists
        cam_exclusions = exclusions.get('cam', [])
        ret_exclusions = exclusions.get('ret', [])
        
        # Log inclusion/exclusion configuration for specific GL accounts of interest
        # For CAM accounts in the 700000 range
        if gl_account == 'MR700000' or gl_account.replace('MR', '') == '700000':
            logger.info(f"Processing MR700000 account - CAM exclusions: {cam_exclusions}, RET exclusions: {ret_exclusions}")
        
        # For RET accounts in the 500000 range
        if gl_account.startswith('MR5') or (gl_account.isdigit() and gl_account.startswith('5')):
            account_num = gl_account.replace('MR', '')
            if account_num.isdigit() and 500000 <= int(account_num) <= 509999:
                logger.info(f"Processing RET account {gl_account} - RET exclusions: {ret_exclusions}")
        
        # Apply inclusion/exclusion rules
        cam_included = is_included(gl_account, inclusions.get('cam', []), cam_exclusions)
        ret_included = is_included(gl_account, inclusions.get('ret', []), ret_exclusions)
        
        # DEBUG - Check if account is included in the expected category based on settings
        # This is only for logging/debugging purposes to identify possible miscategorizations
        if not ret_included and is_in_range(gl_account, "MR500000-MR509999"):
            logger.debug(f"Note: Account {gl_account} is in 500000-509999 range but not included in RET")
            
        if not cam_included and is_in_range(gl_account, "MR510000-MR799999"):
            logger.debug(f"Note: Account {gl_account} is in 510000-799999 range but not included in CAM")
        
        if ret_included:
            result['ret'].append(transaction)
            
            # Also add to base and cap lists unless specifically excluded
            base_included = True
            if exclusions.get('base', []):
                # Explicitly check base exclusions
                base_included = not is_included(gl_account, [], exclusions.get('base', []))
                if not base_included:
                    logger.info(f"Account {gl_account} excluded from base by exclusion rule")
            
            if base_included:
                result['base'].append(transaction)
                
            cap_included = True
            if exclusions.get('cap', []):
                # Explicitly check cap exclusions
                cap_included = not is_included(gl_account, [], exclusions.get('cap', []))
                if not cap_included:
                    logger.info(f"Account {gl_account} excluded from cap by exclusion rule")
            
            if cap_included:
                result['cap'].append(transaction)
                
        elif cam_included:
            result['cam'].append(transaction)
            
            # Also add to base and cap lists unless specifically excluded
            base_included = True
            if exclusions.get('base', []):
                # Explicitly check base exclusions
                base_included = not is_included(gl_account, [], exclusions.get('base', []))
                if not base_included:
                    logger.info(f"Account {gl_account} excluded from base by exclusion rule")
            
            if base_included:
                result['base'].append(transaction)
                
            cap_included = True
            if exclusions.get('cap', []):
                # Explicitly check cap exclusions
                cap_included = not is_included(gl_account, [], exclusions.get('cap', []))
                if not cap_included:
                    logger.info(f"Account {gl_account} excluded from cap by exclusion rule")
            
            if cap_included:
                result['cap'].append(transaction)
        else:
            # Put in 'other' category if not cam or ret
            result['other'].append(transaction)
            filtered_by_gl += 1
    
    # Log the results
    logger.info(f"Filtered GL entries: CAM: {len(result['cam'])}, RET: {len(result['ret'])}, Other: {len(result['other'])}")
    logger.info(f"Base year eligible: {len(result['base'])}, Cap eligible: {len(result['cap'])}")
    
    # Debug logs
    logger.info(f"Debug stats: Total transactions: {debug_counted}")
    logger.info(f"Filtered by period: {filtered_by_period}")
    logger.info(f"Filtered by amount: {filtered_by_amount}")
    logger.info(f"Filtered by GL account: {filtered_by_gl}")
    
    logger.info(f"Period distribution: {sorted(period_distribution.items())}")
    
    # Log accounts that were included in CAM or RET categories
    included_accounts = []
    for transaction in result['ret']:
        gl_account = transaction.get('GL Account', '')
        if gl_account and gl_account not in included_accounts:
            included_accounts.append(gl_account)
            logger.info(f"Included in RET: {gl_account} with amount {transaction.get('Net Amount')}")
            
    for transaction in result['cam']:
        gl_account = transaction.get('GL Account', '')
        if gl_account and gl_account not in included_accounts:
            included_accounts.append(gl_account)
            logger.info(f"Included in CAM: {gl_account} with amount {transaction.get('Net Amount')}")
    
    # No need to check target_gl_accounts as we now log each included account individually
        
    # Debug is_included function
    test_accounts = ['MR500000', 'MR510000', 'MR600000', 'MR750200']
    for test_account in test_accounts:
        ret_test = is_included(test_account, inclusions.get('ret', []), exclusions.get('ret', []))
        cam_test = is_included(test_account, inclusions.get('cam', []), exclusions.get('cam', []))
        logger.info(f"is_included test - {test_account}: RET={ret_test}, CAM={cam_test}")
        
    # Log inclusion/exclusion settings for debugging
    logger.info(f"RET inclusions: {inclusions.get('ret', [])}")
    logger.info(f"RET exclusions: {exclusions.get('ret', [])}")
    logger.info(f"CAM inclusions: {inclusions.get('cam', [])}")
    logger.info(f"CAM exclusions: {exclusions.get('cam', [])}")
    
    return result


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
    
    # Log admin fee inclusions/exclusions for debugging
    logger.info(f"Admin fee inclusions: {admin_inclusions}")
    logger.info(f"Admin fee exclusions: {admin_exclusions}")
    
    admin_fee_transactions = []
    admin_fee_base = Decimal('0')
    
    for transaction in cam_entries:
        gl_account = transaction.get('GL Account', '')
        
        # Apply admin fee inclusion/exclusion rules
        admin_included = is_included(gl_account, admin_inclusions, admin_exclusions)
        
        if admin_included:
            admin_fee_transactions.append(transaction)
            admin_fee_base += transaction.get('Net Amount', Decimal('0'))
        else:
            # Log exclusions of specific accounts for debugging
            if gl_account == 'MR700000' or gl_account.replace('MR', '') == '700000':
                logger.info(f"MR700000 excluded from admin fee calculation")
    
    logger.info(f"Admin fee base: {admin_fee_base} from {len(admin_fee_transactions)} transactions")
    
    return admin_fee_transactions, admin_fee_base


def load_and_filter_gl(
    property_id: str, 
    settings: Dict[str, Any],
    recon_periods: List[str]
) -> Dict[str, Any]:
    """
    Main function to load and filter GL data.
    
    Args:
        property_id: Property identifier
        settings: Settings dictionary
        recon_periods: List of periods to include
        
    Returns:
        Dictionary with filtered GL data and calculated totals
    """
    # Load GL data
    gl_data = load_gl_data(property_id)
    
    # Debug log for settings
    logger.info(f"Property ID: {property_id}, Settings: {settings.get('property_id')}")
    logger.info(f"GL Inclusions: {settings.get('settings', {}).get('gl_inclusions', {})}")
    logger.info(f"GL Exclusions: {settings.get('settings', {}).get('gl_exclusions', {})}")
    logger.info(f"Recon periods: {recon_periods}")
    
    # Filter and group GL entries
    filtered_gl = filter_gl_entries(gl_data, settings, recon_periods)
    
    # Calculate admin fee base
    admin_transactions, admin_fee_base = calculate_admin_fee_base(
        filtered_gl['cam'], 
        settings
    )
    
    # Calculate CAM and RET totals
    cam_total = sum(tx.get('Net Amount', Decimal('0')) for tx in filtered_gl['cam'])
    ret_total = sum(tx.get('Net Amount', Decimal('0')) for tx in filtered_gl['ret'])
    
    # Calculate admin fee amount
    admin_fee_percentage_str = settings.get('settings', {}).get('admin_fee_percentage', '')
    admin_fee_percentage = Decimal('0')
    
    # Only calculate admin fee if a percentage is explicitly set
    if admin_fee_percentage_str and str(admin_fee_percentage_str).strip():
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
                
            logger.info(f"Using admin fee percentage: {admin_fee_percentage * 100}%")
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            logger.error(f"Invalid admin fee percentage: {admin_fee_percentage_str}, error: {str(e)}, using 0")
            admin_fee_percentage = Decimal('0')
    
    admin_fee_amount = admin_fee_base * admin_fee_percentage
    
    # Return comprehensive result
    return {
        'filtered_gl': filtered_gl,
        'admin_transactions': admin_transactions,
        'totals': {
            'cam_total': cam_total,
            'ret_total': ret_total,
            'admin_fee_base': admin_fee_base,
            'admin_fee_amount': admin_fee_amount
        }
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python gl_loader.py <property_id>")
        sys.exit(1)
    
    property_id = sys.argv[1]
    
    # Example settings - in real use, this would come from settings_loader
    example_settings = {
        "settings": {
            "gl_inclusions": {
                "cam": [],
                "ret": [],
                "admin_fee": []
            },
            "gl_exclusions": {
                "cam": [],
                "ret": [],
                "admin_fee": []
            },
            "admin_fee_percentage": 0.15
        }
    }
    
    # Example periods - in real use, these would come from period_calculator
    example_periods = ["202401", "202402", "202403"]
    
    # Load and filter GL data
    result = load_and_filter_gl(property_id, example_settings, example_periods)
    
    # Display summary
    print(f"CAM Total: ${float(result['totals']['cam_total']):,.2f}")
    print(f"RET Total: ${float(result['totals']['ret_total']):,.2f}")
    print(f"Admin Fee Base: ${float(result['totals']['admin_fee_base']):,.2f}")
    print(f"Admin Fee Amount: ${float(result['totals']['admin_fee_amount']):,.2f}")
    print(f"Total CAM Transactions: {len(result['filtered_gl']['cam'])}")
    print(f"Total RET Transactions: {len(result['filtered_gl']['ret'])}")
    print(f"Admin Fee Eligible Transactions: {len(result['admin_transactions'])}")