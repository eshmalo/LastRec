#!/usr/bin/env python3
"""
Unified CAM Reconciliation Calculator

This script provides a streamlined, linear approach to CAM reconciliation calculations.
It maintains compatibility with the existing data structure while simplifying the
calculation flow and standardizing decimal handling.

Usage:
  python unified_cam_reconciliation.py --property_id PROPERTY_ID --recon_year YEAR [--tenant_id TENANT_ID] [--last_bill YYYYMM] [--output_dir OUTPUT_DIR]

Example:
  python unified_cam_reconciliation.py --property_id WAT --recon_year 2024 --tenant_id 1330
"""

import os
import sys
import json
import csv
import argparse
import logging
import datetime
import decimal
from decimal import Decimal, ROUND_HALF_UP, getcontext, InvalidOperation
from typing import Dict, Any, List, Optional, Union, Tuple
from collections import defaultdict

# Configure decimal context for consistent financial calculations
getcontext().prec = 12  # Precision for calculations
MONEY_QUANTIZE = Decimal('0.01')  # Round to 2 decimal places
PCT_QUANTIZE = Decimal('0.001')  # Round percentages to 3 decimal places

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('Output', 'unified_cam_reconciliation.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
PORTFOLIO_SETTINGS_PATH = os.path.join('Data', 'ProcessedOutput', 'PortfolioSettings', 'portfolio_settings.json')
PROPERTY_SETTINGS_BASE_PATH = os.path.join('Data', 'ProcessedOutput', 'PropertySettings')
TENANT_CAM_DATA_PATH = os.path.join('Output', 'JSON', 'Tenant CAM data1.json')
GL_DATA_PATH = os.path.join('Output', 'JSON', 'GL Master 3.json')
OVERRIDES_PATH = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides', 'custom_overrides.json')
CAP_HISTORY_PATH = os.path.join('Data', 'cap_history.json')
REPORTS_PATH = os.path.join('Output', 'Reports')

# Create necessary directories if they don't exist
for directory in [REPORTS_PATH]:
    os.makedirs(directory, exist_ok=True)


# ========== UTILITY FUNCTIONS ==========

def load_json(file_path: str) -> Dict[str, Any]:
    """Load a JSON file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        return {}


def save_json(file_path: str, data: Any, indent: int = 2) -> bool:
    """Save data to a JSON file."""
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False


def parse_date(date_str: str) -> Optional[datetime.date]:
    """Parse a date string in various formats."""
    if not date_str or date_str == "":
        return None

    formats = [
        "%m/%d/%Y",  # MM/DD/YYYY
        "%Y-%m-%d",  # YYYY-MM-DD
        "%m/%d/%Y %H:%M:%S %p"  # MM/DD/YYYY HH:MM:SS AM/PM
    ]

    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.date()
        except ValueError:
            continue

    logger.error(f"Could not parse date: {date_str}")
    return None


def parse_period(period_str: str) -> Optional[datetime.date]:
    """Parse a period string in YYYYMM format."""
    try:
        if len(period_str) != 6:
            logger.error(f"Invalid period format (expected YYYYMM): {period_str}")
            return None

        year = int(period_str[:4])
        month = int(period_str[4:6])

        if not (1 <= month <= 12):
            logger.error(f"Invalid month in period: {period_str}")
            return None

        return datetime.date(year, month, 1)
    except ValueError:
        logger.error(f"Could not parse period: {period_str}")
        return None


def to_decimal(value: Any, default: str = '0') -> Decimal:
    """Convert a value to Decimal with consistent handling."""
    if value is None or value == "":
        return Decimal(default)

    try:
        # Handle percentage signs
        if isinstance(value, str) and '%' in value:
            value = value.replace('%', '')
            return Decimal(value) / Decimal('100')

        # Handle currency signs and commas
        if isinstance(value, str):
            value = value.replace('$', '').replace(',', '')

        return Decimal(str(value))
    except (ValueError, InvalidOperation):
        logger.error(f"Could not convert to Decimal: {value}")
        return Decimal(default)


def format_decimal(value: Decimal, places: int = 2) -> Decimal:
    """Format a Decimal value with consistent rounding."""
    return value.quantize(Decimal(f'0.{"0" * places}'), rounding=ROUND_HALF_UP)


def format_currency(amount: Union[Decimal, float, str, int]) -> str:
    """Format a value as currency."""
    try:
        if isinstance(amount, (float, int)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = to_decimal(amount)

        formatted = format_decimal(amount)
        return f"${float(formatted):,.2f}"
    except (ValueError, InvalidOperation):
        logger.error(f"Could not format as currency: {amount}")
        return "$0.00"


def format_percentage(value: Union[Decimal, float, str, int], precision: int = 2) -> str:
    """Format a value as a percentage with specified precision."""
    try:
        if isinstance(value, (float, int)):
            value = Decimal(str(value))
        elif isinstance(value, str):
            # Remove % sign if present
            value = value.replace('%', '')
            value = to_decimal(value)

        # If value already appears to be a decimal percentage (e.g., 0.15), convert to percentage format
        if value < Decimal('1') and value > Decimal('0'):
            value = value * Decimal('100')

        formatted = format_decimal(value, precision)
        return f"{float(formatted):.{precision}f}%"
    except (ValueError, InvalidOperation):
        logger.error(f"Could not format as percentage: {value}")
        return "0.00%"


def is_in_range(gl_account: str, account_range: str) -> bool:
    """Check if a GL account is within a specified range."""
    try:
        start, end = account_range.split('-')

        # Remove any 'MR' prefix for consistent comparison
        clean_account = gl_account.replace('MR', '')
        clean_start = start.replace('MR', '')
        clean_end = end.replace('MR', '')

        # Try numeric comparison first
        try:
            account_num = int(clean_account)
            start_num = int(clean_start)
            end_num = int(clean_end)

            result = start_num <= account_num <= end_num
            logger.debug(f"Numeric range check: {start_num} <= {account_num} <= {end_num} = {result}")
            return result
        except ValueError:
            # Fall back to string comparison
            result = clean_start <= clean_account <= clean_end
            logger.debug(f"String range check: {clean_start} <= {clean_account} <= {clean_end} = {result}")
            return result
    except Exception as e:
        logger.error(f"Error in range check for {gl_account} in range {account_range}: {str(e)}")
        return False


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with dict2 values taking precedence."""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # For non-dict values or keys not in dict1, use dict2's value
            # Only override if the value is not empty/None
            if value is not None and value != "":
                result[key] = value

    return result


# ========== PERIOD CALCULATION ==========

def generate_recon_periods(recon_year: int) -> List[str]:
    """Generate reconciliation periods (YYYYMM) for a given year."""
    return [f"{recon_year}{month:02d}" for month in range(1, 13)]


def get_period_info(period: str) -> Dict[str, Any]:
    """Get detailed information about a period."""
    period_date = parse_period(period)

    if not period_date:
        return {'valid': False, 'period': period}

    # Calculate first and last day of the month
    year, month = period_date.year, period_date.month
    first_day = datetime.date(year, month, 1)

    if month == 12:
        last_day = datetime.date(year, 12, 31)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    days_in_month = (last_day - first_day).days + 1
    month_name = period_date.strftime("%B")

    return {
        'valid': True,
        'period': period,
        'year': year,
        'month': month,
        'month_name': month_name,
        'days_in_month': days_in_month,
        'first_day': first_day,
        'last_day': last_day
    }


def calculate_periods(recon_year: int, last_bill_date: Optional[str] = None) -> Dict[str, List[str]]:
    """Calculate reconciliation and catch-up periods."""
    # Generate reconciliation periods (all months in reconciliation year)
    recon_periods = generate_recon_periods(recon_year)

    # Generate catch-up periods if last_bill_date is provided
    catchup_periods = []
    if last_bill_date:
        last_date = parse_period(last_bill_date)

        if last_date and last_date.year > recon_year:
            catchup_year = recon_year + 1
            while catchup_year < last_date.year:
                # Add all months for full years
                for month in range(1, 13):
                    catchup_periods.append(f"{catchup_year}{month:02d}")
                catchup_year += 1

            # Add months for final year
            for month in range(1, last_date.month + 1):
                catchup_periods.append(f"{last_date.year}{month:02d}")

    # Combine recon and catch-up periods for the full period
    full_period = recon_periods + [p for p in catchup_periods if p not in recon_periods]

    return {
        'recon_periods': recon_periods,
        'catchup_periods': catchup_periods,
        'full_period': full_period
    }


# ========== SETTINGS LOADING ==========

def load_portfolio_settings() -> Dict[str, Any]:
    """Load portfolio-level settings."""
    try:
        return load_json(PORTFOLIO_SETTINGS_PATH)
    except Exception:
        logger.warning("Could not load portfolio settings. Using empty default.")
        return {
            "name": "Default Portfolio",
            "settings": {
                "gl_inclusions": {"ret": [], "cam": [], "admin_fee": []},
                "gl_exclusions": {"ret": [], "cam": [], "admin_fee": [], "base": [], "cap": []},
                "prorate_share_method": "",
                "admin_fee_percentage": "",
                "base_year": "",
                "base_year_amount": "",
                "min_increase": "",
                "max_increase": "",
                "stop_amount": "",
                "cap_settings": {
                    "cap_percentage": "",
                    "cap_type": "",
                    "override_cap_year": "",
                    "override_cap_amount": ""
                },
                "admin_fee_in_cap_base": ""
            }
        }


def load_property_settings(property_id: str) -> Dict[str, Any]:
    """Load property-level settings."""
    property_settings_path = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'property_settings.json')

    try:
        return load_json(property_settings_path)
    except Exception:
        logger.warning(f"Could not load property settings for {property_id}. Using empty default.")
        return {
            "property_id": property_id,
            "name": f"Property {property_id}",
            "total_rsf": 0,
            "capital_expenses": [],
            "settings": {
                "gl_inclusions": {"ret": [], "cam": [], "admin_fee": []},
                "gl_exclusions": {"ret": [], "cam": [], "admin_fee": [], "base": [], "cap": []},
                "square_footage": "",
                "prorate_share_method": "",
                "admin_fee_percentage": "",
                "base_year": "",
                "base_year_amount": "",
                "min_increase": "",
                "max_increase": "",
                "stop_amount": "",
                "cap_settings": {
                    "cap_percentage": "",
                    "cap_type": "",
                    "override_cap_year": "",
                    "override_cap_amount": ""
                },
                "admin_fee_in_cap_base": ""
            }
        }


def load_tenant_settings(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """Load tenant-level settings."""
    tenant_settings_dir = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'TenantSettings')

    if not os.path.exists(tenant_settings_dir):
        logger.warning(f"Tenant settings directory not found for property {property_id}")
        return {}

    # Find the tenant file by looking for a file that contains the tenant ID
    tenant_files = [f for f in os.listdir(tenant_settings_dir) if tenant_id in f and f.endswith('.json')]

    if not tenant_files:
        logger.warning(f"No tenant settings file found for tenant ID {tenant_id} in property {property_id}")
        return {}

    tenant_file_path = os.path.join(tenant_settings_dir, tenant_files[0])

    try:
        return load_json(tenant_file_path)
    except Exception:
        logger.warning(f"Could not load tenant settings for tenant {tenant_id} in property {property_id}")
        return {}


def find_all_tenants_for_property(property_id: str) -> List[Tuple[str, str]]:
    """Find all tenants for a given property."""
    tenant_settings_dir = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'TenantSettings')

    if not os.path.exists(tenant_settings_dir):
        logger.warning(f"Tenant settings directory not found for property {property_id}")
        return []

    tenants = []

    for filename in os.listdir(tenant_settings_dir):
        if filename.endswith('.json'):
            try:
                file_path = os.path.join(tenant_settings_dir, filename)
                tenant_data = load_json(file_path)
                tenant_id = tenant_data.get('tenant_id')
                tenant_name = tenant_data.get('name', '')

                if tenant_id:
                    tenants.append((str(tenant_id), tenant_name))
            except Exception:
                logger.warning(f"Could not process tenant file: {filename}")

    return sorted(tenants, key=lambda x: x[0])  # Sort by tenant_id


def merge_settings(property_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Load and merge settings from portfolio, property, and tenant levels."""
    # Load portfolio settings (base level)
    portfolio_settings = load_portfolio_settings()

    # Load property settings
    property_settings = load_property_settings(property_id)

    # Create a new deep copy of the portfolio settings
    result = portfolio_settings.copy()
    result["property_id"] = property_id
    result["property_name"] = property_settings.get("name", f"Property {property_id}")
    result["total_rsf"] = property_settings.get("total_rsf", 0)
    result["property_capital_expenses"] = property_settings.get("capital_expenses", [])

    # Merge property settings into result
    for key, value in property_settings.get("settings", {}).items():
        if key in result["settings"]:
            if isinstance(value, dict) and isinstance(result["settings"][key], dict):
                # Special handling for gl_inclusions and gl_exclusions
                if key in ["gl_inclusions", "gl_exclusions"]:
                    # For inclusion/exclusion settings, we want to MERGE the values by category
                    merged_dict = result["settings"][key].copy()

                    # Check if property settings object is empty for inclusions
                    if key == "gl_inclusions" and not value:
                        # If property has empty inclusions object, preserve portfolio settings
                        logger.info(f"Property has empty {key}, preserving portfolio-level settings")
                        pass  # Keep the merged_dict as is (with portfolio settings)
                    else:
                        # For each category in property settings
                        for category, category_values in value.items():
                            if category in merged_dict:
                                # Different handling for inclusions vs exclusions
                                if key == "gl_exclusions":
                                    # For exclusions, we APPEND property-level exclusions to portfolio exclusions
                                    if isinstance(category_values, list) and isinstance(merged_dict[category], list):
                                        # Create a list of ALL exclusions from both levels
                                        merged_dict[category] = merged_dict[category] + [val for val in category_values if val not in merged_dict[category]]
                                else:
                                    # For inclusions, if property specifies something, it overrides
                                    # ONLY if the category_values is not empty
                                    if category_values:  # Only override if non-empty
                                        merged_dict[category] = category_values
                            else:
                                # If category doesn't exist at all, add it
                                merged_dict[category] = category_values

                    result["settings"][key] = merged_dict
                else:
                    # Deep merge for other dictionaries
                    result["settings"][key] = deep_merge(result["settings"][key], value)
            elif value is not None and value != "":
                # Override with property value if not empty
                result["settings"][key] = value
        else:
            # Add new key from property settings
            result["settings"][key] = value

    # If tenant_id is provided, merge tenant settings
    if tenant_id:
        tenant_settings = load_tenant_settings(property_id, tenant_id)

        # Merge tenant settings into result
        for key, value in tenant_settings.get("settings", {}).items():
            if key in result["settings"]:
                if isinstance(value, dict) and isinstance(result["settings"][key], dict):
                    # Special handling for gl_inclusions and gl_exclusions
                    if key in ["gl_inclusions", "gl_exclusions"]:
                        # For inclusion/exclusion settings, we want to MERGE the values by category
                        merged_dict = result["settings"][key].copy()

                        # Check if tenant settings object is empty for inclusions
                        if key == "gl_inclusions" and not value:
                            # If tenant has empty inclusions object, preserve existing settings
                            logger.info(f"Tenant has empty {key}, preserving higher-level settings")
                            pass  # Keep the merged_dict as is (with portfolio/property settings)
                        else:
                            # For each category in tenant settings
                            for category, category_values in value.items():
                                if category in merged_dict:
                                    # Different handling for inclusions vs exclusions
                                    if key == "gl_exclusions":
                                        # For exclusions, we APPEND tenant-level exclusions to existing exclusions
                                        if isinstance(category_values, list) and isinstance(merged_dict[category], list):
                                            # Create a list of ALL exclusions from both levels
                                            merged_dict[category] = merged_dict[category] + [val for val in category_values if val not in merged_dict[category]]
                                    else:
                                        # For inclusions, if tenant specifies something, it overrides
                                        # ONLY if the category_values is not empty
                                        if category_values:  # Only override if non-empty
                                            merged_dict[category] = category_values
                                else:
                                    # If category doesn't exist at all, add it
                                    merged_dict[category] = category_values

                        result["settings"][key] = merged_dict
                    else:
                        # Deep merge for other dictionaries
                        result["settings"][key] = deep_merge(result["settings"][key], value)
                elif value is not None and value != "":
                    # Override with tenant value if not empty
                    result["settings"][key] = value
            else:
                # Add new key from tenant settings
                result["settings"][key] = value

        # Include tenant-specific attributes
        tenant_specific = {
            "tenant_id": tenant_settings.get("tenant_id"),
            "tenant_name": tenant_settings.get("name", ""),
            "lease_start": tenant_settings.get("lease_start", ""),
            "lease_end": tenant_settings.get("lease_end", ""),
            "suite": tenant_settings.get("suite", ""),
            "capital_expenses": tenant_settings.get("capital_expenses", [])
        }
        result.update(tenant_specific)

    # Set default values for essential settings if they're empty
    if not result["settings"].get("prorate_share_method"):
        result["settings"]["prorate_share_method"] = "RSF"  # Default to RSF method

    if not result["settings"].get("cap_settings", {}).get("cap_type"):
        if "cap_settings" not in result["settings"]:
            result["settings"]["cap_settings"] = {}
        result["settings"]["cap_settings"]["cap_type"] = "previous_year"  # Default cap type

    return result


# ========== GL DATA LOADING & FILTERING ==========

def load_gl_data(property_id: str) -> List[Dict[str, Any]]:
    """Load GL data for a specific property."""
    try:
        gl_data = load_json(GL_DATA_PATH)

        # Filter for the specific property
        property_gl = [
            transaction for transaction in gl_data
            if transaction.get('Property ID') == property_id
        ]

        # Standardize and convert numeric fields for all transactions
        for transaction in property_gl:
            # Convert Net Amount to Decimal
            if 'Net Amount' in transaction:
                transaction['Net Amount'] = to_decimal(transaction['Net Amount'])

        logger.info(f"Loaded {len(property_gl)} GL transactions for property {property_id}")
        return property_gl
    except Exception as e:
        logger.error(f"Error loading GL data: {str(e)}")
        return []


def is_gl_account_included(gl_account: str, inclusions: List[str], exclusions: List[str]) -> bool:
    """Determine if a GL account should be included based on inclusion/exclusion rules."""
    # Normalize the account for consistent comparison
    clean_account = gl_account.replace('MR', '')

    # EXCLUSIONS FIRST: Check exclusions - these take absolute precedence
    # If account matches any exclusion rule, it's immediately excluded
    for exclusion in exclusions:
        exclusion_rule = exclusion.strip()
        if '-' in exclusion_rule:  # It's a range
            if is_in_range(gl_account, exclusion_rule):
                logger.debug(f"GL account {gl_account} EXCLUDED by range rule: {exclusion_rule}")
                return False
        else:  # It's a single account
            clean_excl = exclusion_rule.replace('MR', '')
            if clean_excl == clean_account:
                logger.debug(f"GL account {gl_account} EXCLUDED by exact match: {exclusion_rule}")
                return False

    # INCLUSIONS SECOND: Check inclusions
    # If there are inclusion rules, account must match at least one to be included
    if inclusions:
        is_included = False
        for inclusion in inclusions:
            inclusion_rule = inclusion.strip()
            if '-' in inclusion_rule:  # It's a range
                if is_in_range(gl_account, inclusion_rule):
                    logger.debug(f"GL account {gl_account} INCLUDED by range rule: {inclusion_rule}")
                    is_included = True
                    break
            else:  # It's a single account
                clean_incl = inclusion_rule.replace('MR', '')
                if clean_incl == clean_account:
                    logger.debug(f"GL account {gl_account} INCLUDED by exact match: {inclusion_rule}")
                    is_included = True
                    break
        return is_included

    # DEFAULT BEHAVIOR CHANGED: If no inclusion rules specified, EXCLUDE by default for safety
    # This prevents including unintended accounts when inclusions list is empty
    logger.debug(f"GL account {gl_account} EXCLUDED by default (no inclusion rules)")
    return False


def filter_gl_accounts(
        gl_data: List[Dict[str, Any]],
        settings: Dict[str, Any],
        recon_periods: List[str],
        categories: List[str] = ['cam', 'ret']
) -> Dict[str, Any]:
    """Filter GL entries and categorize them for CAM reconciliation."""
    # Get inclusion/exclusion settings
    gl_settings = settings.get('settings', {})
    inclusions = gl_settings.get('gl_inclusions', {})
    exclusions = gl_settings.get('gl_exclusions', {})

    # Ensure we have properly structured inclusions and exclusions
    # This is just to make sure all categories have entries in the dictionaries
    for category in categories:
        if category not in inclusions:
            inclusions[category] = []
        if category not in exclusions:
            exclusions[category] = []

    # Log inclusion/exclusion settings
    logger.info(f"GL inclusions from settings: {inclusions}")
    logger.info(f"GL exclusions from settings: {exclusions}")

    # Initialize result containers for each category
    filtered_entries = {
        'cam': [],
        'ret': [],
        'admin_fee': [],
        'base': [],
        'cap': [],
        'other': []
    }

    # List of GL accounts included in each category
    included_accounts = {
        'cam': set(),
        'ret': set(),
        'admin_fee': set()
    }

    # Filter and categorize transactions
    for transaction in gl_data:
        gl_account = transaction.get('GL Account', '')
        period = transaction.get('PERIOD', '')
        net_amount = to_decimal(transaction.get('Net Amount', Decimal('0')))
        account_type = transaction.get('Account Type', '')  # Get the account type if available

        # Skip transactions with missing data or zero amount
        if not gl_account or not period or net_amount == 0:
            continue

        # Skip transactions outside the reconciliation periods
        if str(period) not in recon_periods:
            continue

        # Make a copy of the transaction to avoid modifying the original
        processed_transaction = transaction.copy()

        # For CAM/RET calculations, correct the sign of revenue/expense entries:
        # - For expenses (normally credits with negative Net Amount), keep as negative
        # - For income/revenue (normally credits with negative Net Amount), keep as negative
        # This preserves the accounting convention where expenses reduce the account balance
        # and income/revenue increases it
        processed_transaction['Net Amount'] = net_amount

        # Check and categorize the transaction
        for category in categories:
            # Skip categories that aren't requested
            if category not in ['cam', 'ret', 'admin_fee']:
                continue

            # Check inclusion/exclusion for this category
            category_inclusions = inclusions.get(category, [])
            category_exclusions = exclusions.get(category, [])

            if is_gl_account_included(gl_account, category_inclusions, category_exclusions):
                filtered_entries[category].append(processed_transaction)
                included_accounts[category].add(gl_account)

                # Also add to base and cap categories unless specifically excluded
                if category in ['cam', 'ret']:
                    # Check base year exclusions
                    base_exclusions = exclusions.get('base', [])
                    if not is_gl_account_included(gl_account, [], base_exclusions):
                        filtered_entries['base'].append(processed_transaction)

                    # Check cap exclusions
                    cap_exclusions = exclusions.get('cap', [])
                    if not is_gl_account_included(gl_account, [], cap_exclusions):
                        filtered_entries['cap'].append(processed_transaction)

        # If transaction wasn't categorized, add to 'other'
        if all(gl_account not in included_accounts[cat] for cat in ['cam', 'ret', 'admin_fee'] if cat in categories):
            filtered_entries['other'].append(processed_transaction)

    # Calculate totals for each category
    category_totals = {}

    for category, entries in filtered_entries.items():
        # For CAM/RET expenses, preserve accounting sign convention (expenses are negative)
        total = sum(entry['Net Amount'] for entry in entries)
        category_totals[category] = total
        logger.info(f"Category {category}: {len(entries)} entries, total: {float(total):.2f}")

    # Log included GL accounts for each category
    for category, accounts in included_accounts.items():
        if accounts:
            logger.info(f"Category {category} includes {len(accounts)} unique GL accounts: {sorted(accounts)}")

    return {
        'filtered_entries': filtered_entries,
        'category_totals': category_totals,
        'included_accounts': included_accounts
    }


# ========== CAM, TAX, ADMIN FEE CALCULATIONS ==========

def calculate_admin_fee_percentage(settings: Dict[str, Any]) -> Decimal:
    """Calculate the admin fee percentage from settings with standardized handling."""
    admin_fee_percentage_str = settings.get('settings', {}).get('admin_fee_percentage', '0')

    if not admin_fee_percentage_str or admin_fee_percentage_str == "":
        return Decimal('0')

    # Convert to decimal
    admin_fee_percentage = to_decimal(admin_fee_percentage_str)

    # Standardize to decimal format (e.g., 0.15 for 15%)
    # If >= 1, assume it's a percentage (15%) and convert to decimal (0.15)
    if admin_fee_percentage >= Decimal('1'):
        admin_fee_percentage = admin_fee_percentage / Decimal('100')

    return format_decimal(admin_fee_percentage, 4)  # 4 decimal places for percentages


def is_admin_fee_included_in(settings: Dict[str, Any], calculation_type: str) -> bool:
    """Determine if admin fee should be included in base or cap calculations."""
    admin_fee_in_cap_base = settings.get('settings', {}).get('admin_fee_in_cap_base', '')
    return calculation_type in admin_fee_in_cap_base.lower()


def calculate_cam_tax_admin(
        gl_filtered_data: Dict[str, Any],
        settings: Dict[str, Any],
        categories: List[str] = ['cam', 'ret']
) -> Dict[str, Any]:
    """Calculate CAM, TAX, and admin fee amounts with consistent handling."""
    category_totals = gl_filtered_data['category_totals']

    # Calculate CAM and TAX totals
    cam_total = category_totals.get('cam', Decimal('0')) if 'cam' in categories else Decimal('0')
    ret_total = category_totals.get('ret', Decimal('0')) if 'ret' in categories else Decimal('0')

    # Calculate admin fee
    admin_fee_percentage = calculate_admin_fee_percentage(settings)
    admin_fee_amount = cam_total * admin_fee_percentage

    # Determine if admin fee is included in cap and base year calculations
    include_in_cap = is_admin_fee_included_in(settings, 'cap')
    include_in_base = is_admin_fee_included_in(settings, 'base')

    # Calculate combined totals
    combined_total = cam_total + ret_total

    # For cap calculation
    cap_base_total = combined_total
    if include_in_cap:
        cap_base_total += admin_fee_amount

    # For base year calculation
    base_year_total = combined_total
    if include_in_base:
        base_year_total += admin_fee_amount

    # Log key calculations
    logger.info(f"CAM total: {float(cam_total):.2f}")
    logger.info(f"RET total: {float(ret_total):.2f}")
    logger.info(
        f"Admin fee: {float(admin_fee_amount):.2f} ({float(admin_fee_percentage) * 100:.1f}% of {float(cam_total):.2f})")
    logger.info(f"Admin fee in cap: {include_in_cap}, in base: {include_in_base}")

    # Return comprehensive results
    return {
        'cam_total': cam_total,
        'ret_total': ret_total,
        'admin_fee_amount': admin_fee_amount,
        'admin_fee_percentage': admin_fee_percentage,
        'combined_total': combined_total,
        'cap_base_total': cap_base_total,
        'base_year_total': base_year_total,
        'include_admin_in_cap': include_in_cap,
        'include_admin_in_base': include_in_base
    }


# ========== BASE YEAR CALCULATIONS ==========

def is_base_year_applicable(recon_year: int, base_year_setting: Optional[str]) -> bool:
    """Determine if base year adjustment applies to the current reconciliation."""
    if not base_year_setting:
        return False

    try:
        base_year = int(base_year_setting)
        return recon_year > base_year
    except (ValueError, TypeError):
        logger.error(f"Invalid base year format: {base_year_setting}")
        return False


def calculate_base_year_adjustment(
        recon_year: int,
        base_year_total: Decimal,
        settings: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate base year adjustment for the reconciliation."""
    base_year_setting = settings.get('settings', {}).get('base_year')

    # Check if base year adjustment applies
    applies = is_base_year_applicable(recon_year, base_year_setting)

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
    base_year_amount_str = settings.get('settings', {}).get('base_year_amount', '0')
    base_amount = to_decimal(base_year_amount_str)

    # Calculate amount after base year adjustment (never less than zero)
    after_base = max(Decimal('0'), base_year_total - base_amount)

    # Log the calculation
    logger.info(
        f"Base year adjustment: {float(base_year_total):.2f} - {float(base_amount):.2f} = {float(after_base):.2f}")

    return {
        'base_year_applies': True,
        'base_year': base_year_setting,
        'base_year_amount': base_amount,
        'total_before_adjustment': base_year_total,
        'after_base_adjustment': after_base
    }


# ========== CAP CALCULATIONS ==========

def load_cap_history() -> Dict[str, Dict[str, float]]:
    """Load cap history from file."""
    try:
        if os.path.exists(CAP_HISTORY_PATH):
            return load_json(CAP_HISTORY_PATH)
        else:
            logger.info(f"Cap history file not found at {CAP_HISTORY_PATH}. Creating a new one.")
            return {}
    except Exception as e:
        logger.error(f"Error loading cap history: {str(e)}")
        return {}


def save_cap_history(cap_history: Dict[str, Dict[str, float]]) -> bool:
    """Save cap history to file."""
    return save_json(CAP_HISTORY_PATH, cap_history)


def get_reference_amount(
        tenant_id: str,
        recon_year: int,
        cap_type: str,
        cap_history: Dict[str, Dict[str, float]]
) -> Decimal:
    """Get the reference amount for cap calculations."""
    # Convert tenant_id to string for dictionary lookup
    tenant_id_str = str(tenant_id)

    # Get tenant's cap history
    tenant_history = cap_history.get(tenant_id_str, {})

    if not tenant_history:
        logger.warning(f"No cap history found for tenant {tenant_id}")
        return Decimal('0')

    # Calculate previous year
    prev_year = str(recon_year - 1)

    if cap_type == "previous_year":
        # Use previous year's amount
        amount = tenant_history.get(prev_year, 0.0)
        logger.info(f"Using previous year cap for tenant {tenant_id}: {amount}")
        return Decimal(str(amount))
    elif cap_type == "highest_previous_year":
        # Find the highest amount from all previous years
        highest_amount = 0.0
        highest_year = None

        for year, amount in tenant_history.items():
            if int(year) < recon_year and amount > highest_amount:
                highest_amount = amount
                highest_year = year

        logger.info(
            f"Using highest previous year cap for tenant {tenant_id}: {highest_amount} from year {highest_year}")
        return Decimal(str(highest_amount))
    else:
        logger.error(f"Unknown cap type: {cap_type}")
        return Decimal('0')


def calculate_cap_limit(
        tenant_id: str,
        recon_year: int,
        settings: Dict[str, Any],
        cap_history: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """Calculate the cap limit based on settings and cap history."""
    # Get cap settings
    cap_settings = settings.get('settings', {}).get('cap_settings', {})

    # Get cap percentage
    cap_percentage_str = cap_settings.get('cap_percentage', '0')
    cap_percentage = to_decimal(cap_percentage_str)

    # Get cap type
    cap_type = cap_settings.get('cap_type', 'previous_year')

    # Get min/max increase
    min_increase_str = settings.get('settings', {}).get('min_increase', '')
    max_increase_str = settings.get('settings', {}).get('max_increase', '')

    min_increase = to_decimal(min_increase_str) if min_increase_str else None
    max_increase = to_decimal(max_increase_str) if max_increase_str else None

    # Get stop amount
    stop_amount_str = settings.get('settings', {}).get('stop_amount', '')
    stop_amount = to_decimal(stop_amount_str) if stop_amount_str else None

    # Check for cap override
    override_year = cap_settings.get('override_cap_year', '')
    override_amount_str = cap_settings.get('override_cap_amount', '')

    # Apply cap override if specified
    if override_year and override_amount_str:
        override_amount = to_decimal(override_amount_str)
        logger.info(f"Using cap override: {float(override_amount):.2f} from year {override_year}")

        # Update cap history with override
        tenant_id_str = str(tenant_id)
        if tenant_id_str not in cap_history:
            cap_history[tenant_id_str] = {}

        cap_history[tenant_id_str][override_year] = float(override_amount)
        save_cap_history(cap_history)

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
            logger.info(f"Min increase limit applied: {float(min_limit):.2f}")

    # Apply maximum increase if specified
    if max_increase is not None and ref_amount > 0:
        max_limit = ref_amount * (Decimal('1') + max_increase)
        if max_limit < result['effective_cap_limit']:
            result['effective_cap_limit'] = max_limit
            result['max_increase_applied'] = True
            logger.info(f"Max increase limit applied: {float(max_limit):.2f}")

    # Apply stop amount if specified
    if stop_amount is not None:
        # Calculate stop amount based on tenant square footage
        square_footage_str = settings.get('settings', {}).get('square_footage', '0')
        square_footage = to_decimal(square_footage_str)

        if square_footage > 0:
            total_stop_amount = stop_amount * square_footage
            if total_stop_amount < result['effective_cap_limit']:
                result['effective_cap_limit'] = total_stop_amount
                result['stop_amount_applied'] = True
                logger.info(f"Stop amount limit applied: {float(total_stop_amount):.2f}")
                result['stop_amount'] = stop_amount
                result['square_footage'] = square_footage

    return result


def enforce_cap(
        tenant_id: str,
        recon_year: int,
        after_base_amount: Decimal,
        subject_to_cap_amount: Decimal,
        excluded_from_cap_amount: Decimal,
        settings: Dict[str, Any],
        cap_history: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """Enforce cap limits on the reconciliation amount."""
    # Calculate cap limit
    cap_limit_results = calculate_cap_limit(tenant_id, recon_year, settings, cap_history)

    # Determine if cap applies (only if we have a reference amount)
    cap_applies = cap_limit_results.get('reference_amount', Decimal('0')) > 0

    # Log cap settings for debugging
    logger.info(f"Tenant {tenant_id} cap settings:")
    logger.info(f"  Reference amount: {float(cap_limit_results.get('reference_amount', Decimal('0'))):.2f}")
    logger.info(f"  Cap applies: {cap_applies}")
    logger.info(f"  Amount subject to cap: {float(subject_to_cap_amount):.2f}")
    logger.info(f"  Excluded amount: {float(excluded_from_cap_amount):.2f}")
    logger.info(f"  Cap limit: {float(cap_limit_results.get('effective_cap_limit', Decimal('0'))):.2f}")

    # Apply cap limits ONLY to the amount subject to cap
    capped_subject_amount = subject_to_cap_amount
    cap_limited = False

    if cap_applies and subject_to_cap_amount > cap_limit_results.get('effective_cap_limit', Decimal('0')):
        capped_subject_amount = cap_limit_results.get('effective_cap_limit', Decimal('0'))
        cap_limited = True
        logger.info(
            f"Cap limit applied: {float(subject_to_cap_amount):.2f} reduced to {float(capped_subject_amount):.2f}")

    # Calculate final amount by adding back excluded amounts
    final_capped_amount = capped_subject_amount + excluded_from_cap_amount

    logger.info(
        f"Final capped amount: {float(final_capped_amount):.2f} = {float(capped_subject_amount):.2f} (capped) + {float(excluded_from_cap_amount):.2f} (excluded)")

    # Return comprehensive results
    return {
        'cap_applies': cap_applies,
        'amount_subject_to_cap': subject_to_cap_amount,
        'excluded_amount': excluded_from_cap_amount,
        'cap_limit_results': cap_limit_results,
        'capped_subject_amount': capped_subject_amount,
        'final_capped_amount': final_capped_amount,
        'cap_limited': cap_limited
    }


def update_cap_history(
        tenant_id: str,
        recon_year: int,
        amount: Decimal,
        cap_history: Dict[str, Dict[str, float]] = None
) -> Dict[str, Dict[str, float]]:
    """Update cap history with the new amount for the current reconciliation."""
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()

    # Convert recon_year to string
    recon_year_str = str(recon_year)

    # Initialize tenant entry if it doesn't exist
    tenant_id_str = str(tenant_id)
    if tenant_id_str not in cap_history:
        cap_history[tenant_id_str] = {}

    # Update the entry
    cap_history[tenant_id_str][recon_year_str] = float(amount)
    logger.info(f"Updated cap history for tenant {tenant_id}, year {recon_year}: {float(amount):.2f}")

    # Save the updated cap history
    save_cap_history(cap_history)

    return cap_history


# ========== CAPITAL EXPENSES CALCULATION ==========

def calculate_capital_expenses(
        settings: Dict[str, Any],
        recon_year: int,
        periods: List[str]
) -> Dict[str, Any]:
    """Calculate amortized capital expenses for the reconciliation."""
    # Get capital expenses from settings
    property_expenses = settings.get('property_capital_expenses', [])
    tenant_expenses = settings.get('capital_expenses', [])

    # Create a dictionary of expenses by id (tenant expenses take precedence)
    merged_expenses = {}

    # Add property expenses
    for expense in property_expenses:
        expense_id = expense.get('id')
        if expense_id and expense.get('description') and expense.get('amount'):
            merged_expenses[expense_id] = expense

    # Add/override with tenant expenses
    for expense in tenant_expenses:
        expense_id = expense.get('id')
        if expense_id and expense.get('description') and expense.get('amount'):
            merged_expenses[expense_id] = expense

    # Calculate amortized amount for each expense
    amortized_expenses = []
    total_capital_expense = Decimal('0')

    for expense_id, expense in merged_expenses.items():
        # Extract expense details
        expense_year = to_decimal(expense.get('year', '0'), '0')
        expense_amount = to_decimal(expense.get('amount', '0'), '0')
        amort_years = to_decimal(expense.get('amort_years', '1'), '1')

        # Ensure amortization period is at least 1 year
        if amort_years < 1:
            amort_years = Decimal('1')

        # Check if expense applies to current year
        expense_year_int = int(expense_year)
        if expense_year_int > recon_year or expense_year_int + int(amort_years) <= recon_year:
            continue

        # Calculate annual amortized amount
        annual_amount = expense_amount / amort_years

        # Apply proration based on occupancy if tenant settings are provided
        prorated_amount = annual_amount
        if 'tenant_id' in settings:
            lease_start = settings.get('lease_start')
            lease_end = settings.get('lease_end')

            if lease_start or lease_end:
                # Calculate occupancy factors
                occupancy_factors = calculate_occupancy_factors(periods, lease_start, lease_end)

                # Calculate average occupancy
                if occupancy_factors:
                    avg_occupancy = sum(occupancy_factors.values()) / Decimal(len(periods))
                    prorated_amount = annual_amount * avg_occupancy

        # Add to amortized expenses if there's an amount
        if prorated_amount > 0:
            amortized_expenses.append({
                'id': expense_id,
                'description': expense.get('description', ''),
                'year': expense_year_int,
                'amount': expense_amount,
                'amort_years': int(amort_years),
                'annual_amount': annual_amount,
                'prorated_amount': prorated_amount
            })

            total_capital_expense += prorated_amount

    logger.info(
        f"Calculated capital expenses: {len(amortized_expenses)} items, total: {float(total_capital_expense):.2f}")

    return {
        'capital_expenses': amortized_expenses,
        'total_capital_expenses': total_capital_expense
    }


# ========== OCCUPANCY CALCULATION ==========

def calculate_occupancy_factors(
        periods: List[str],
        lease_start: Optional[str] = None,
        lease_end: Optional[str] = None
) -> Dict[str, Decimal]:
    """Calculate occupancy factors for a list of periods."""
    # Parse lease dates
    start_date = parse_date(lease_start) if lease_start else None
    end_date = parse_date(lease_end) if lease_end else None

    # Calculate factors for each period
    factors = {}

    for period in periods:
        period_info = get_period_info(period)

        if not period_info['valid']:
            factors[period] = Decimal('0')
            continue

        # Get period start and end dates
        period_start = period_info['first_day']
        period_end = period_info['last_day']
        days_in_month = period_info['days_in_month']

        # If no lease dates provided, assume full occupancy
        if not start_date and not end_date:
            factors[period] = Decimal('1')
            continue

        # If only end date is provided, assume start before period
        if not start_date:
            start_date = datetime.date(1900, 1, 1)  # Use very early date

        # If only start date is provided, assume end after period
        if not end_date:
            end_date = datetime.date(2100, 12, 31)  # Use very future date

        # Check if lease period completely outside of period
        if end_date < period_start or start_date > period_end:
            factors[period] = Decimal('0')
            continue

        # Calculate actual first day of overlap
        overlap_start = max(start_date, period_start)

        # Calculate actual last day of overlap
        overlap_end = min(end_date, period_end)

        # Calculate number of days in overlap
        overlap_days = (overlap_end - overlap_start).days + 1

        # Calculate occupancy factor
        factor = Decimal(overlap_days) / Decimal(days_in_month)
        factors[period] = factor

    # Log summary
    occupied_periods = sum(1 for f in factors.values() if f > 0)
    full_periods = sum(1 for f in factors.values() if f >= Decimal('1'))
    partial_periods = sum(1 for f in factors.values() if Decimal('0') < f < Decimal('1'))

    logger.info(
        f"Calculated occupancy factors: {len(periods)} periods, "
        f"{occupied_periods} occupied, {full_periods} full, {partial_periods} partial"
    )

    return factors


def apply_occupancy_adjustment(
        amount: Decimal,
        occupancy_factors: Dict[str, Decimal]
) -> Decimal:
    """Apply occupancy adjustment to an amount."""
    # If no occupancy factors, use the full amount
    if not occupancy_factors:
        return amount

    # Calculate average occupancy factor
    avg_occupancy = sum(occupancy_factors.values()) / len(occupancy_factors)

    # Apply occupancy adjustment
    adjusted_amount = amount * avg_occupancy

    logger.info(
        f"Applied occupancy adjustment: {float(amount):.2f} × {float(avg_occupancy):.4f} = {float(adjusted_amount):.2f}")

    return adjusted_amount


# ========== TENANT SHARE CALCULATION ==========

def calculate_tenant_share_percentage(
        tenant_settings: Dict[str, Any],
        property_settings: Dict[str, Any]
) -> Decimal:
    """Calculate tenant's share percentage based on settings."""
    # Get tenant's share method
    share_method = tenant_settings.get('settings', {}).get('prorate_share_method', '')

    # Fixed share percentage
    if share_method == "Fixed":
        fixed_share_str = tenant_settings.get('settings', {}).get('fixed_pyc_share', '0')

        try:
            fixed_share = to_decimal(fixed_share_str)

            # Convert from percentage (e.g., 5.138) to decimal (0.05138)
            fixed_share = fixed_share / Decimal('100')
            logger.info(f"Using fixed share percentage: {float(fixed_share) * 100:.4f}%")
            return fixed_share
        except (ValueError, decimal.InvalidOperation) as e:
            logger.error(f"Invalid fixed share percentage: {fixed_share_str}. Error: {str(e)}")
            # Fall back to RSF calculation below

    # RSF-based calculation (default)
    tenant_sf_str = tenant_settings.get('settings', {}).get('square_footage', '0')
    property_sf_str = property_settings.get('total_rsf', '0')

    tenant_sf = to_decimal(tenant_sf_str)
    property_sf = to_decimal(property_sf_str)

    if property_sf > 0:
        share_pct = tenant_sf / property_sf
        logger.info(f"Using RSF-based share: {float(tenant_sf)}/{float(property_sf)} = {float(share_pct):.6f}")
        return share_pct
    else:
        logger.error("Property square footage is zero or invalid")
        return Decimal('0')


def calculate_tenant_share(amount: Decimal, share_percentage: Decimal) -> Decimal:
    """Calculate tenant's share of an amount."""
    tenant_share = amount * share_percentage
    logger.info(
        f"Calculated tenant share: {float(amount):.2f} × {float(share_percentage):.6f} = {float(tenant_share):.2f}")
    return tenant_share


# ========== MANUAL OVERRIDE HANDLING ==========

def load_manual_overrides() -> List[Dict[str, Any]]:
    """Load manual overrides from file."""
    try:
        if os.path.exists(OVERRIDES_PATH):
            overrides = load_json(OVERRIDES_PATH)
            logger.info(f"Loaded {len(overrides)} manual overrides from {OVERRIDES_PATH}")
            return overrides
        else:
            logger.warning(f"Manual overrides file not found at {OVERRIDES_PATH}")
            return []
    except Exception as e:
        logger.error(f"Error loading manual overrides: {str(e)}")
        return []


def create_override_lookup(
        overrides: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Create a lookup dictionary for overrides by tenant_id and property_id."""
    override_lookup = {}

    for override in overrides:
        tenant_id = override.get('tenant_id')
        property_id = override.get('property_id')

        if tenant_id is not None and property_id is not None:
            # Create a unique key from tenant_id and property_id
            key = f"{tenant_id}_{property_id}"
            override_lookup[key] = override

    logger.info(f"Created override lookup with {len(override_lookup)} entries")
    return override_lookup


def get_tenant_override(
        tenant_id: str,
        property_id: str
) -> Dict[str, Any]:
    """Get override information for a specific tenant and property."""
    # Load all overrides
    overrides = load_manual_overrides()
    override_lookup = create_override_lookup(overrides)

    # Create the lookup key
    key = f"{tenant_id}_{property_id}"

    # Get the override entry
    override = override_lookup.get(key)

    if not override:
        return {
            'tenant_id': tenant_id,
            'property_id': property_id,
            'has_override': False,
            'override_amount': Decimal('0'),
            'override_description': ""
        }

    # Get the override amount and description
    override_amount_str = override.get('override_amount', '0')
    override_amount = to_decimal(override_amount_str)
    override_description = override.get('description', '')

    return {
        'tenant_id': tenant_id,
        'property_id': property_id,
        'has_override': override_amount != 0,
        'override_amount': override_amount,
        'override_description': override_description
    }


# ========== TENANT PAYMENT TRACKING ==========

def get_old_monthly_payment(tenant_id: str, property_id: str) -> Decimal:
    """Get the old monthly payment amount for a tenant."""
    # Load tenant CAM data
    tenant_cam_data = load_json(TENANT_CAM_DATA_PATH)

    # Convert tenant_id to string for comparison
    tenant_id_str = str(tenant_id)

    # Find the record for this tenant and property
    for record in tenant_cam_data:
        record_tenant_id = str(record.get('TenantID', ''))
        record_property_id = record.get('PropertyID', '')

        if record_tenant_id == tenant_id_str and record_property_id == property_id:
            # Get the MatchedEstimate value
            matched_estimate = record.get('MatchedEstimate', '')

            try:
                if matched_estimate and matched_estimate != '':
                    amount = to_decimal(matched_estimate)
                    logger.debug(f"Found old monthly payment for tenant {tenant_id}: {float(amount):.2f}")
                    return amount
                else:
                    logger.debug(f"Empty MatchedEstimate value for tenant {tenant_id} in property {property_id}")
            except (ValueError, decimal.InvalidOperation) as e:
                logger.warning(f"Invalid MatchedEstimate value for tenant {tenant_id}: {matched_estimate} - {str(e)}")

    logger.debug(f"No valid payment info found for tenant {tenant_id} in property {property_id}")
    return Decimal('0')


def calculate_new_monthly_payment(
        final_amount: Decimal,
        periods_count: int = 12
) -> Decimal:
    """Calculate the new monthly payment amount based on the total reconciliation amount."""
    if periods_count <= 0:
        logger.warning(f"Invalid periods_count: {periods_count}, using default of 12")
        periods_count = 12

    # Calculate and round to 2 decimal places
    return format_decimal(final_amount / Decimal(periods_count))


def calculate_payment_change(
        old_monthly: Decimal,
        new_monthly: Decimal
) -> Dict[str, Any]:
    """Calculate percentage change and categorize the change."""
    # Calculate the raw difference
    difference = new_monthly - old_monthly

    # Handle special case for percentage change
    if old_monthly == Decimal('0'):
        if new_monthly == Decimal('0'):
            percentage_change = Decimal('0')
            change_type = "no_change"
        else:
            percentage_change = Decimal('100')
            change_type = "first_billing"
    else:
        percentage_change = (difference / old_monthly * Decimal('100')).quantize(
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


# ========== REPORTING FUNCTIONS ==========

def generate_csv_report(
        report_rows: List[Dict[str, Any]],
        property_id: str,
        recon_year: int,
        categories: List[str] = ['cam', 'ret']
) -> str:
    """Generate a CSV report from tenant billing results."""
    # Create output directory if it doesn't exist
    os.makedirs(REPORTS_PATH, exist_ok=True)

    # Create filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    category_str = "_".join(categories)
    output_path = os.path.join(REPORTS_PATH,
                               f"tenant_billing_{property_id}_{category_str}_{recon_year}_{timestamp}.csv")

    # Define columns for the report
    columns = [
        # Basic tenant information
        'tenant_id', 'tenant_name', 'property_id', 'property_name', 'suite',
        'lease_start', 'lease_end', 'share_method', 'share_percentage',

        # Property totals before tenant share
        'property_gl_total',

        # Tenant expense breakdown
        'cam_total', 'ret_total', 'admin_fee_percentage', 'admin_fee_amount',
        'combined_total',

        # Base year details
        'base_year', 'base_year_amount',
        'total_before_base_adjustment', 'after_base_adjustment',

        # Cap limit details
        'cap_reference_amount', 'cap_percentage', 'cap_limit',
        'amount_subject_to_cap', 'excluded_amount',
        'capped_subject_amount', 'cap_limited',

        # Occupancy adjustments
        'average_occupancy', 'occupancy_adjusted_amount',

        # Capital expenses
        'capital_expenses_total',

        # Override and final amounts
        'base_billing', 'override_amount', 'final_billing',

        # Payment tracking
        'old_monthly', 'new_monthly', 'monthly_difference',
        'percentage_change', 'change_type', 'is_significant'
    ]

    # Write the CSV file
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()

            for row in report_rows:
                # Filter the row to include only the defined columns
                filtered_row = {col: row.get(col, '') for col in columns}
                writer.writerow(filtered_row)

        logger.info(f"Generated CSV report with {len(report_rows)} rows: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating CSV report: {str(e)}")
        return ""


def generate_json_report(
        billing_results: List[Dict[str, Any]],
        property_id: str,
        recon_year: int,
        categories: List[str] = ['cam', 'ret']
) -> str:
    """Generate a detailed JSON report from tenant billing calculations."""
    # Create output directory if it doesn't exist
    os.makedirs(REPORTS_PATH, exist_ok=True)

    # Create filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    category_str = "_".join(categories)
    output_path = os.path.join(REPORTS_PATH,
                               f"tenant_billing_detail_{property_id}_{category_str}_{recon_year}_{timestamp}.json")

    # JSON encoder class to handle Decimal objects
    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return str(obj)
            # Let the base class default method handle other types
            return super(DecimalEncoder, self).default(obj)

    # Recursively convert all Decimal objects in complex nested structures
    def convert_decimals(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(convert_decimals(item) for item in obj)
        else:
            return obj

    # Apply the recursive conversion to make the results JSON serializable
    serializable_results = convert_decimals(billing_results)

    # Write the JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, cls=DecimalEncoder)

        logger.info(f"Generated detailed JSON report with {len(billing_results)} entries: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating JSON report: {str(e)}")
        return ""


# ========== MAIN CALCULATION FUNCTION ==========

def calculate_tenant_reconciliation(
        tenant_id: str,
        property_id: str,
        recon_year: int,
        periods_dict: Dict[str, List[str]],
        categories: List[str] = ['cam', 'ret'],
        skip_cap_update: bool = False
) -> Dict[str, Any]:
    """
    Calculate CAM reconciliation for a single tenant with a linear flow.

    Steps:
    1. Load settings (portfolio, property, tenant)
    2. Load and filter GL data
    3. Calculate CAM, TAX, admin fee
    4. Apply base year adjustment
    5. Apply cap limits
    6. Add capital expenses
    7. Calculate pro-rata share
    8. Apply occupancy adjustment
    9. Apply any overrides
    10. Calculate final billing amount
    """
    logger.info(f"===== Starting reconciliation for tenant {tenant_id} in property {property_id} =====")
    logger.info(f"Categories: {categories}, Year: {recon_year}")

    # STEP 1: Load all settings with inheritance
    settings = merge_settings(property_id, tenant_id)
    property_settings = merge_settings(property_id)  # For property-level calculations

    logger.info(f"Loaded settings for tenant {tenant_id} in property {property_id}")

    # STEP 2: Load and filter GL data
    gl_data = load_gl_data(property_id)
    logger.info(f"Loaded {len(gl_data)} raw GL entries for property {property_id}")

    # For reconciliation calculations, only use the reconciliation periods
    recon_periods = periods_dict['recon_periods']

    gl_filtered_data = filter_gl_accounts(gl_data, settings, recon_periods, categories)
    logger.info(
        f"Filtered GL data to {sum(len(entries) for entries in gl_filtered_data['filtered_entries'].values())} entries")

    # STEP 3: Calculate CAM, TAX, admin fee - PROPERTY LEVEL FIRST
    property_cam_tax_admin = calculate_cam_tax_admin(gl_filtered_data, property_settings, categories)

    # Total property expenses (for reporting)
    property_gl_total = property_cam_tax_admin['combined_total']
    logger.info(f"Property total (CAM+TAX): {float(property_gl_total):.2f}")

    # STEP 4: Calculate CAM, TAX, admin fee - TENANT SPECIFIC
    tenant_cam_tax_admin = calculate_cam_tax_admin(gl_filtered_data, settings, categories)

    # STEP 5: Apply base year adjustment
    base_year_result = calculate_base_year_adjustment(
        recon_year,
        tenant_cam_tax_admin['base_year_total'],
        settings
    )

    after_base_amount = base_year_result['after_base_adjustment']
    logger.info(f"After base year adjustment: {float(after_base_amount):.2f}")

    # STEP 6: Prepare amounts for cap calculation - IMPORTANT FOR CORRECT CAP ENFORCEMENT
    # Separate amounts subject to cap from amounts excluded from cap
    cap_exclusions = settings.get('settings', {}).get('gl_exclusions', {}).get('cap', [])

    # If there are cap exclusions, calculate amount subject to cap and excluded amount
    # Otherwise, all the amount after base adjustment is subject to cap
    amount_subject_to_cap = Decimal('0')
    excluded_from_cap_amount = Decimal('0')

    # Get entries that are and aren't subject to cap
    cap_entries = gl_filtered_data['filtered_entries'].get('cap', [])

    # Handle caps based on filtered entries
    if cap_entries:
        # Calculate amount subject to cap from filtered cap entries
        amount_subject_to_cap = sum(entry['Net Amount'] for entry in cap_entries)

        # Calculate excluded amount as the difference between total and amount subject to cap
        excluded_from_cap_amount = after_base_amount - amount_subject_to_cap
    else:
        # If no specific cap entries found, all of after_base_amount is subject to cap
        amount_subject_to_cap = after_base_amount
        excluded_from_cap_amount = Decimal('0')

    logger.info(f"Amount subject to cap: {float(amount_subject_to_cap):.2f}")
    logger.info(f"Amount excluded from cap: {float(excluded_from_cap_amount):.2f}")

    # STEP 7: Apply cap limits
    cap_history = load_cap_history()

    cap_result = enforce_cap(
        tenant_id,
        recon_year,
        after_base_amount,
        amount_subject_to_cap,
        excluded_from_cap_amount,
        settings,
        cap_history
    )

    # After applying caps, get the result
    after_cap_amount = cap_result['final_capped_amount']
    logger.info(f"After cap enforcement: {float(after_cap_amount):.2f}")

    # STEP 8: Calculate capital expenses
    capital_expenses_result = calculate_capital_expenses(settings, recon_year, recon_periods)
    capital_expenses_amount = capital_expenses_result['total_capital_expenses']
    logger.info(f"Capital expenses: {float(capital_expenses_amount):.2f}")

    # STEP 9: Calculate tenant share using pro-rata percentage
    tenant_share_percentage = calculate_tenant_share_percentage(settings, property_settings)
    tenant_share = calculate_tenant_share(after_cap_amount, tenant_share_percentage)
    logger.info(f"Tenant share ({float(tenant_share_percentage) * 100:.6f}%): {float(tenant_share):.2f}")

    # STEP 10: Apply capital expenses (already tenant-specific or pro-rated)
    subtotal_after_capital = tenant_share + capital_expenses_amount
    logger.info(f"After capital expenses: {float(subtotal_after_capital):.2f}")

    # STEP 11: Calculate occupancy adjustment
    occupancy_factors = calculate_occupancy_factors(
        recon_periods,
        settings.get('lease_start'),
        settings.get('lease_end')
    )

    occupancy_adjusted_amount = apply_occupancy_adjustment(subtotal_after_capital, occupancy_factors)
    logger.info(f"After occupancy adjustment: {float(occupancy_adjusted_amount):.2f}")

    # STEP 12: Apply any tenant override
    override_info = get_tenant_override(tenant_id, property_id)
    override_amount = override_info['override_amount']

    # Calculate base billing (before override)
    base_billing = occupancy_adjusted_amount

    # Calculate final billing (with override if applicable)
    final_billing = base_billing
    if override_amount != 0:
        logger.info(f"Applying override amount: {float(override_amount):.2f}")
        final_billing = override_amount

    logger.info(f"Final billing amount: {float(final_billing):.2f}")

    # STEP 13: Update cap history unless skipped
    if not skip_cap_update:
        cap_history = update_cap_history(tenant_id, recon_year, base_billing)

    # STEP 14: Calculate payment tracking information
    old_monthly = get_old_monthly_payment(tenant_id, property_id)

    # Calculate new monthly amount
    recon_period_count = len(recon_periods)
    new_monthly = calculate_new_monthly_payment(final_billing, recon_period_count)

    # Calculate payment change metrics
    payment_change = calculate_payment_change(old_monthly, new_monthly)

    # STEP 15: Create a detailed report row
    share_method = settings.get('settings', {}).get('prorate_share_method', 'RSF')

    # Calculate average occupancy
    avg_occupancy = Decimal('1')
    if occupancy_factors:
        avg_occupancy = sum(occupancy_factors.values()) / len(occupancy_factors)

    # Number of full/partial months
    occupied_months = sum(1 for f in occupancy_factors.values() if f > 0)
    full_months = sum(1 for f in occupancy_factors.values() if f >= Decimal('1'))
    partial_months = sum(1 for f in occupancy_factors.values() if Decimal('0') < f < Decimal('1'))

    # Format report row
    report_row = {
        # Basic tenant information
        'tenant_id': tenant_id,
        'tenant_name': settings.get('tenant_name', ''),
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'suite': settings.get('suite', ''),
        'lease_start': settings.get('lease_start', ''),
        'lease_end': settings.get('lease_end', ''),

        # Share method information
        'share_method': share_method,
        'share_percentage': format_percentage(tenant_share_percentage * Decimal('100'), 4),

        # Property grand total
        'property_gl_total': format_currency(property_gl_total),

        # Expense breakdown
        'cam_total': format_currency(tenant_cam_tax_admin['cam_total']),
        'ret_total': format_currency(tenant_cam_tax_admin['ret_total']),
        'admin_fee_percentage': format_percentage(tenant_cam_tax_admin['admin_fee_percentage'] * Decimal('100'), 2),
        'admin_fee_amount': format_currency(tenant_cam_tax_admin['admin_fee_amount']),
        'combined_total': format_currency(tenant_cam_tax_admin['combined_total']),

        # Base year details
        'base_year': base_year_result['base_year'],
        'base_year_amount': format_currency(base_year_result['base_year_amount']),
        'total_before_base_adjustment': format_currency(base_year_result['total_before_adjustment']),
        'after_base_adjustment': format_currency(base_year_result['after_base_adjustment']),

        # Cap details
        'cap_reference_amount': format_currency(cap_result['cap_limit_results']['reference_amount']),
        'cap_percentage': format_percentage(cap_result['cap_limit_results']['cap_percentage'] * Decimal('100'), 2),
        'cap_limit': format_currency(cap_result['cap_limit_results']['effective_cap_limit']),
        'amount_subject_to_cap': format_currency(cap_result['amount_subject_to_cap']),
        'excluded_amount': format_currency(cap_result['excluded_amount']),
        'capped_subject_amount': format_currency(cap_result['capped_subject_amount']),
        'cap_limited': 'Yes' if cap_result['cap_limited'] else 'No',

        # Occupancy details
        'average_occupancy': f"{float(avg_occupancy):.4f}",
        'occupied_months': occupied_months,
        'full_months': full_months,
        'partial_months': partial_months,
        'occupancy_adjusted_amount': format_currency(occupancy_adjusted_amount),

        # Capital expenses
        'capital_expenses_total': format_currency(capital_expenses_amount),

        # Final amounts
        'base_billing': format_currency(base_billing),
        'override_amount': format_currency(override_amount),
        'final_billing': format_currency(final_billing),

        # Payment tracking
        'old_monthly': format_currency(old_monthly),
        'new_monthly': format_currency(new_monthly),
        'monthly_difference': format_currency(payment_change['difference']),
        'percentage_change': format_percentage(payment_change['percentage_change'], 1),
        'change_type': payment_change['change_type'],
        'is_significant': 'Yes' if payment_change['is_significant'] else 'No'
    }

    # Return comprehensive results
    return {
        'tenant_id': tenant_id,
        'tenant_name': settings.get('tenant_name', ''),
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'recon_year': recon_year,
        'categories': categories,
        'periods': periods_dict,

        # Calculation components
        'property_gl_total': property_gl_total,
        'tenant_cam_tax_admin': tenant_cam_tax_admin,
        'base_year_result': base_year_result,
        'cap_result': cap_result,
        'capital_expenses_result': capital_expenses_result,
        'tenant_share_percentage': tenant_share_percentage,
        'occupancy_factors': occupancy_factors,
        'override_info': override_info,

        # Final amounts and payment tracking
        'base_billing': base_billing,
        'final_billing': final_billing,
        'old_monthly': old_monthly,
        'new_monthly': new_monthly,
        'payment_change': payment_change,

        # Report row for CSV export
        'report_row': report_row
    }


def process_property_reconciliation(
        property_id: str,
        recon_year: int,
        last_bill: Optional[str] = None,
        tenant_id: Optional[str] = None,
        categories: List[str] = ['cam', 'ret'],
        skip_cap_update: bool = False
) -> Dict[str, Any]:
    """Process reconciliation for a property (all tenants or one tenant)."""
    logger.info(f"Starting reconciliation for property {property_id}, year {recon_year}")

    # Calculate periods for reconciliation
    periods = calculate_periods(recon_year, last_bill)

    # If tenant_id provided, process only that tenant
    if tenant_id:
        tenants_to_process = [(tenant_id, "")]
    else:
        # Find all tenants for this property
        tenants_to_process = find_all_tenants_for_property(property_id)

    logger.info(f"Processing {len(tenants_to_process)} tenants")

    # Process each tenant
    tenant_results = []
    report_rows = []

    for tenant_id, _ in tenants_to_process:
        # Process tenant
        result = calculate_tenant_reconciliation(
            tenant_id,
            property_id,
            recon_year,
            periods,
            categories,
            skip_cap_update
        )

        tenant_results.append(result)
        report_rows.append(result['report_row'])

    # Generate reports
    csv_report_path = generate_csv_report(report_rows, property_id, recon_year, categories)
    json_report_path = generate_json_report(tenant_results, property_id, recon_year, categories)

    # Return results
    return {
        'property_id': property_id,
        'recon_year': recon_year,
        'categories': categories,
        'periods': periods,
        'tenant_count': len(tenant_results),
        'tenant_results': tenant_results,
        'csv_report_path': csv_report_path,
        'json_report_path': json_report_path
    }


# ========== MAIN FUNCTION ==========

def main():
    """Main entry point for the reconciliation process."""
    parser = argparse.ArgumentParser(description='Unified CAM Reconciliation Calculator')

    parser.add_argument(
        '--property_id',
        type=str,
        required=True,
        help='Property identifier (e.g., ELW)'
    )
    parser.add_argument(
        '--recon_year',
        type=int,
        required=True,
        help='Reconciliation year (e.g., 2024)'
    )
    parser.add_argument(
        '--last_bill',
        type=str,
        help='Last billing date in YYYYMM format (e.g., 202505)'
    )
    parser.add_argument(
        '--tenant_id',
        type=str,
        help='Optional tenant ID to process only one tenant'
    )
    parser.add_argument(
        '--categories',
        type=str,
        default='cam,ret',
        help='Comma-separated list of expense categories to include (e.g., cam,ret)'
    )
    parser.add_argument(
        '--skip_cap_update',
        action='store_true',
        help='Skip updating cap history (for testing)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse categories
    categories = [cat.strip().lower() for cat in args.categories.split(',') if cat.strip()]

    try:
        # Process property reconciliation
        start_time = datetime.datetime.now()

        results = process_property_reconciliation(
            args.property_id,
            args.recon_year,
            args.last_bill,
            args.tenant_id,
            categories,
            args.skip_cap_update
        )

        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        # Print summary
        print("\n" + "=" * 80)
        print(f"RECONCILIATION COMPLETE - {elapsed_time:.2f}s")
        print("=" * 80)
        print(f"Property: {results['property_id']}")
        print(f"Year: {results['recon_year']}")
        print(f"Tenants Processed: {results['tenant_count']}")
        print(f"Categories: {', '.join(results['categories'])}")

        print(f"\nReports Generated:")
        print(f"- CSV: {results['csv_report_path']}")
        print(f"- JSON: {results['json_report_path']}")

        print("=" * 80 + "\n")

        return 0  # Success

    except Exception as e:
        logger.exception(f"Error during reconciliation: {str(e)}")
        print(f"\nERROR: {str(e)}")
        return 1  # Error


if __name__ == "__main__":
    sys.exit(main())