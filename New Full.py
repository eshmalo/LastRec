#!/usr/bin/env python3
"""
Enhanced CAM Reconciliation Calculator with GL Detail Reports

This script provides a streamlined, linear approach to CAM reconciliation calculations
with enhanced payment tracking, balance calculation features, and detailed GL breakdowns.

Enhancements:
  - Tracking of actual tenant payments during the reconciliation period
  - Calculation of reconciliation year balance (expected - paid)
  - Support for catch-up period calculations
  - Tracking of total balances (reconciliation + catch-up)
  - Detailed GL line item reports per tenant
  - Letter generation fields
  - Automatic property name mapping from Properties.json

Usage:
"""

import os
import sys
import json
import csv
import argparse
import logging
import datetime
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from collections import defaultdict

# Import letter generator module
try:
    # First try the enhanced letter generator with GL breakdown and more features
    try:
        from enhanced_letter_generator import generate_letters_from_results
        letter_generator_type = "enhanced"
    except ImportError:
        # Fall back to the simple LaTeX letter generator
        from letter_generator import generate_letters_from_results
        letter_generator_type = "latex"
except ImportError:
    print("Letter generator module not found - letters will not be generated automatically")
    generate_letters_from_results = None
    letter_generator_type = None

# Configure decimal context for consistent financial calculations
getcontext().prec = 12  # Precision for calculations
MONEY_QUANTIZE = Decimal('0.01')  # Round to 2 decimal places
PCT_QUANTIZE = Decimal('0.001')  # Round percentages to 3 decimal places

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('Output', 'enhanced_cam_reconciliation.log')),
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
PROPERTIES_JSON_PATH = os.path.join('Output', 'JSON', '1. Properties.json')  # NEW
REPORTS_PATH = os.path.join('Output', 'Reports')
GL_DETAILS_PATH = os.path.join('Output', 'Reports', 'GL_Details')

# Create necessary directories if they don't exist
for directory in [REPORTS_PATH, GL_DETAILS_PATH]:
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

        # For display purposes, value will be shown as-is (already in percentage form)
        # No automatic conversion from decimal to percentage, as this is handled elsewhere
        # Special case for very small values (likely already in decimal form)
        
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


# NEW: Property name mapping function
def load_property_name_mapping() -> Dict[str, str]:
    """Load property name mapping from Properties.json."""
    try:
        properties_data = load_json(PROPERTIES_JSON_PATH)

        # Create mapping from Property ID to Property Name
        mapping = {}
        for prop in properties_data:
            property_id = prop.get('Property ID', '')
            property_name = prop.get('Property Name', '')
            if property_id and property_name:
                mapping[property_id] = property_name

        logger.info(f"Loaded property name mapping for {len(mapping)} properties")
        return mapping
    except Exception as e:
        logger.error(f"Error loading property name mapping: {str(e)}")
        return {}


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
    """Load and merge settings from portfolio, property, and tenant levels with proper inheritance."""
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

    # Merge property settings into result - with improved handling of GL inclusions/exclusions
    property_settings_dict = property_settings.get("settings", {})

    # Handle special cases for gl_inclusions and gl_exclusions
    if "gl_inclusions" in property_settings_dict:
        # Get portfolio and property inclusions
        portfolio_inclusions = result["settings"].get("gl_inclusions", {})
        property_inclusions = property_settings_dict.get("gl_inclusions", {})

        # Start with portfolio inclusions
        merged_inclusions = {}
        for category, values in portfolio_inclusions.items():
            merged_inclusions[category] = values.copy() if isinstance(values, list) else values

        # Only override with property inclusions if they exist AND have content
        for category, values in property_inclusions.items():
            # Check if property has actual values for this category (not empty list or dict)
            if values and (isinstance(values, list) and len(values) > 0):
                # Replace portfolio inclusions with property inclusions for this category
                merged_inclusions[category] = values.copy()
                logger.info(f"Property overrides portfolio inclusions for {category}")
            elif category in property_inclusions and category in merged_inclusions:
                # Property specifically includes this category, but with empty list
                # Preserve it - empty property list would override portfolio settings
                logger.info(f"Property has empty {category} inclusions, preserving portfolio settings")

        # Update the result
        result["settings"]["gl_inclusions"] = merged_inclusions

    # Handle exclusions separately - they are ADDITIVE across levels
    if "gl_exclusions" in property_settings_dict:
        # Get portfolio and property exclusions
        portfolio_exclusions = result["settings"].get("gl_exclusions", {})
        property_exclusions = property_settings_dict.get("gl_exclusions", {})

        # Start with portfolio exclusions
        merged_exclusions = {}
        for category, values in portfolio_exclusions.items():
            merged_exclusions[category] = values.copy() if isinstance(values, list) else values

        # Add (not replace) property exclusions
        for category, values in property_exclusions.items():
            if category not in merged_exclusions:
                # If category doesn't exist at portfolio level, add it with property values
                merged_exclusions[category] = values.copy() if isinstance(values, list) else values
            elif values and isinstance(values, list) and isinstance(merged_exclusions[category], list):
                # Combine exclusions without duplicates
                existing_exclusions = merged_exclusions[category]
                new_exclusions = [val for val in values if val not in existing_exclusions]
                merged_exclusions[category] = existing_exclusions + new_exclusions
                logger.info(f"Added {len(new_exclusions)} property-level exclusions to {category}")

        # Update the result
        result["settings"]["gl_exclusions"] = merged_exclusions

    # Merge other property settings
    for key, value in property_settings_dict.items():
        if key not in ["gl_inclusions", "gl_exclusions"]:  # We've already handled these
            if key in result["settings"]:
                if isinstance(value, dict) and isinstance(result["settings"][key], dict):
                    # Deep merge for dictionaries
                    result["settings"][key] = deep_merge(result["settings"][key], value)
                elif value is not None and value != "":
                    # Override with property value if not empty
                    result["settings"][key] = value
            else:
                # Add new key from property settings
                result["settings"][key] = value

    # If tenant_id is provided, merge tenant settings with the same logic
    if tenant_id:
        tenant_settings = load_tenant_settings(property_id, tenant_id)
        tenant_settings_dict = tenant_settings.get("settings", {})

        # Apply the same logic for tenant GL inclusions/exclusions
        if "gl_inclusions" in tenant_settings_dict:
            # Get current inclusions and tenant inclusions
            current_inclusions = result["settings"].get("gl_inclusions", {})
            tenant_inclusions = tenant_settings_dict.get("gl_inclusions", {})

            # Only override if tenant has actual values for a category
            for category, values in tenant_inclusions.items():
                if values and (isinstance(values, list) and len(values) > 0):
                    # Replace with tenant inclusions for this category
                    current_inclusions[category] = values.copy()
                    logger.info(f"Tenant overrides inclusions for {category}")

        # Handle tenant exclusions (additive)
        if "gl_exclusions" in tenant_settings_dict:
            # Get current exclusions and tenant exclusions
            current_exclusions = result["settings"].get("gl_exclusions", {})
            tenant_exclusions = tenant_settings_dict.get("gl_exclusions", {})

            # Add tenant exclusions to existing exclusions
            for category, values in tenant_exclusions.items():
                if category not in current_exclusions:
                    # If category doesn't exist, add it with tenant values
                    current_exclusions[category] = values.copy() if isinstance(values, list) else values
                elif values and isinstance(values, list) and isinstance(current_exclusions[category], list):
                    # Add tenant exclusions without duplicates
                    existing_exclusions = current_exclusions[category]
                    new_exclusions = [val for val in values if val not in existing_exclusions]
                    current_exclusions[category] = existing_exclusions + new_exclusions
                    logger.info(f"Added {len(new_exclusions)} tenant-level exclusions to {category}")

        # Merge other tenant settings
        for key, value in tenant_settings_dict.items():
            if key not in ["gl_inclusions", "gl_exclusions"]:  # We've already handled these
                if key in result["settings"]:
                    if isinstance(value, dict) and isinstance(result["settings"][key], dict):
                        # Deep merge for dictionaries
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

    # Add debugging output to verify the final merged settings
    logger.info(f"Final GL inclusions: {result['settings'].get('gl_inclusions', {})}")
    logger.info(f"Final GL exclusions: {result['settings'].get('gl_exclusions', {})}")

    return result


# ========== GL DATA LOADING & FILTERING ==========

def load_gl_data(property_id: str) -> List[Dict[str, Any]]:
    """Load GL data for a specific property."""
    try:
        gl_data = load_json(GL_DATA_PATH)

        # Filter for the specific property (case-insensitive)
        property_gl = [
            transaction for transaction in gl_data
            if transaction.get('Property ID', '').upper() == property_id.upper()
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


def check_account_inclusion(gl_account: str, inclusion_rules: List[str]) -> bool:
    """Check if a GL account should be included based on inclusion rules."""
    # No inclusion rules means don't include by default
    if not inclusion_rules:
        return False

    # Normalize the account for consistent comparison
    clean_account = gl_account.replace('MR', '')

    # Check if account matches any inclusion rule
    for rule in inclusion_rules:
        rule = rule.strip()
        if '-' in rule:  # It's a range
            if is_in_range(gl_account, rule):
                logger.debug(f"GL account {gl_account} included by range rule: {rule}")
                return True
        else:  # It's a single account
            clean_rule = rule.replace('MR', '')
            if clean_rule == clean_account:
                logger.debug(f"GL account {gl_account} included by exact match: {rule}")
                return True

    # Account didn't match any inclusion rule
    return False


def check_account_exclusion(gl_account: str, exclusion_rules: List[str]) -> bool:
    """Check if a GL account should be excluded based on exclusion rules."""
    # No exclusion rules means don't exclude
    if not exclusion_rules:
        return False

    # Normalize the account for consistent comparison
    clean_account = gl_account.replace('MR', '')

    # Check if account matches any exclusion rule
    for rule in exclusion_rules:
        rule = rule.strip()
        if '-' in rule:  # It's a range
            if is_in_range(gl_account, rule):
                logger.debug(f"GL account {gl_account} excluded by range rule: {rule}")
                return True
        else:  # It's a single account
            clean_rule = rule.replace('MR', '')
            if clean_rule == clean_account:
                logger.debug(f"GL account {gl_account} excluded by exact match: {rule}")
                return True

    # Account didn't match any exclusion rule
    return False


def filter_gl_accounts_with_detail(
        gl_data: List[Dict[str, Any]],
        settings: Dict[str, Any],
        recon_periods: List[str],
        categories: List[str] = ['cam', 'ret'],
        catchup_periods: List[str] = None
) -> Dict[str, Any]:
    """Enhanced version of filter_gl_accounts that tracks detailed information for reporting.
    
    When catchup_periods are provided, the function uses reconciliation year data (recon_periods)
    for GL filtering. This is because catch-up calculations should be based on the 
    reconciliation year's GL data, not the catch-up period's actual GL data.
    for GL filtering, which is needed for catch-up calculations.
    """
    # Get inclusion/exclusion settings
    gl_settings = settings.get('settings', {})
    inclusions = gl_settings.get('gl_inclusions', {})
    exclusions = gl_settings.get('gl_exclusions', {})

    # Log inclusion/exclusion settings
    logger.info(f"GL inclusions used for filtering: {inclusions}")
    logger.info(f"GL exclusions used for filtering: {exclusions}")

    # Initialize result containers
    gross_entries = {cat: [] for cat in categories + ['base', 'cap']}
    exclusion_entries = {cat: [] for cat in categories + ['base', 'cap']}
    net_entries = {cat: [] for cat in categories + ['base', 'cap', 'other']}

    # Track amounts
    gross_amounts = {cat: Decimal('0') for cat in categories + ['base', 'cap']}
    exclusion_amounts = {cat: Decimal('0') for cat in categories + ['base', 'cap']}

    # Track GL accounts
    included_accounts = {cat: set() for cat in categories + ['base', 'cap']}
    excluded_accounts = {cat: set() for cat in categories + ['base', 'cap']}

    # NEW: Track GL line detail for reporting with complete tracking
    gl_line_details = {}  # gl_account -> detailed info
    gl_account_names = {}  # gl_account -> description
    negative_balance_gl_accounts = {}  # Track GL accounts with negative balances

    # First pass: Calculate total amounts per GL account across all periods for included accounts only
    gl_account_totals = {}  # Track total amount per GL account
    for transaction in gl_data:
        gl_account = transaction.get('GL Account', '')
        period = transaction.get('PERIOD', '')
        net_amount = to_decimal(transaction.get('Net Amount', Decimal('0')))
        
        # Skip invalid transactions or outside recon periods
        if not gl_account or not period or net_amount == 0 or str(period) not in recon_periods:
            continue
            
        # Check if this GL account would be included in ANY category
        is_included_anywhere = False
        included_in_categories = []
        for category in categories:
            if check_account_inclusion(gl_account, inclusions.get(category, [])):
                is_included_anywhere = True
                included_in_categories.append(category)
                
        # Only accumulate totals for accounts that would be included
        if is_included_anywhere:
            logger.debug(f"GL account {gl_account} included in categories: {included_in_categories}")
            if gl_account not in gl_account_totals:
                gl_account_totals[gl_account] = Decimal('0')
            gl_account_totals[gl_account] += net_amount
        else:
            logger.debug(f"GL account {gl_account} not included in any category - skipping")

    # Process transactions
    for transaction in gl_data:
        gl_account = transaction.get('GL Account', '')
        period = transaction.get('PERIOD', '')
        net_amount = to_decimal(transaction.get('Net Amount', Decimal('0')))
        # Use GL Description, fall back to Line Description if GL Description is empty
        description = transaction.get('GL Description', '').strip()
        if not description:
            description = transaction.get('Line Description', '').strip()

        # Skip invalid transactions or outside recon periods
        if not gl_account or not period or net_amount == 0 or str(period) not in recon_periods:
            continue

        # Check if this GL account would be included somewhere and has negative total
        if gl_account in gl_account_totals and gl_account_totals[gl_account] < 0:
            if gl_account not in negative_balance_gl_accounts:
                # Track which categories this account was included in
                included_categories = []
                for category in categories:
                    if check_account_inclusion(gl_account, inclusions.get(category, [])):
                        included_categories.append(category)
                        
                negative_balance_gl_accounts[gl_account] = {
                    'description': description,
                    'total_amount': gl_account_totals[gl_account],
                    'periods': {},
                    'included_in_categories': included_categories
                }
            negative_balance_gl_accounts[gl_account]['periods'][period] = net_amount
            continue  # Skip this transaction from all calculations

        # Store GL account description
        if gl_account not in gl_account_names and description:
            gl_account_names[gl_account] = description

        # Initialize GL line detail if needed
        if gl_account not in gl_line_details:
            gl_line_details[gl_account] = {
                'description': description,
                'periods': {},  # Track by period for accurate calculations
                'gross': {cat: Decimal('0') for cat in categories + ['base', 'cap', 'admin_fee']},
                'exclusions': {cat: Decimal('0') for cat in categories + ['base', 'cap', 'admin_fee']},
                'net': {cat: Decimal('0') for cat in categories + ['base', 'cap', 'admin_fee']},
                'exclusion_levels': {cat: set() for cat in categories + ['base', 'cap', 'admin_fee']},
                # Track which level excluded
                'inclusion_rules': {cat: [] for cat in categories + ['base', 'cap']},  # Track which rules included
                'exclusion_rules': {cat: [] for cat in categories + ['base', 'cap', 'admin_fee']},
                # Track which rules excluded
                'categories': set()
            }

        # Initialize period tracking
        if period not in gl_line_details[gl_account]['periods']:
            gl_line_details[gl_account]['periods'][period] = {
                'amount': Decimal('0'),
                'categories': set()
            }

        gl_line_details[gl_account]['periods'][period]['amount'] += net_amount

        # Make a copy of the transaction
        processed_transaction = transaction.copy()
        processed_transaction['Net Amount'] = net_amount

        # Process each category
        for category in categories:
            category_inclusions = inclusions.get(category, [])
            category_exclusions = exclusions.get(category, [])

            # Step 1: Check if account matches ANY inclusion rule
            is_gross_included = check_account_inclusion(gl_account, category_inclusions)

            if not is_gross_included:
                # Skip if not included in this category
                continue

            # At this point, the account is included in GROSS for this category
            gross_entries[category].append(processed_transaction)
            gross_amounts[category] += net_amount
            included_accounts[category].add(gl_account)

            # Track in GL line details
            gl_line_details[gl_account]['gross'][category] += net_amount
            gl_line_details[gl_account]['categories'].add(category)
            gl_line_details[gl_account]['periods'][period]['categories'].add(category)

            # Track which inclusion rules matched - but only keep the highest priority one
            # If we haven't added any rules yet for this account/category, set them now
            if not gl_line_details[gl_account]['inclusion_rules'][category]:
                for rule in category_inclusions:
                    if check_account_inclusion(gl_account, [rule]):
                        # Store only the first matching rule (highest priority based on hierarchy)
                        gl_line_details[gl_account]['inclusion_rules'][category] = [rule]
                        break

            # Step 2: Check if it should be excluded
            is_excluded = check_account_exclusion(gl_account, category_exclusions)

            if is_excluded:
                # Account is included in GROSS but also excluded
                exclusion_entries[category].append(processed_transaction)
                exclusion_amounts[category] += net_amount
                excluded_accounts[category].add(gl_account)
                gl_line_details[gl_account]['exclusions'][category] += net_amount

                # Track which exclusion rules matched
                for rule in category_exclusions:
                    if check_account_exclusion(gl_account, [rule]):
                        # Store the rule, duplicates will be removed when displaying
                        gl_line_details[gl_account]['exclusion_rules'][category].append(rule)
                        gl_line_details[gl_account]['exclusion_levels'][category].add('merged')  # From merged settings

                logger.debug(f"GL account {gl_account} excluded from {category} - Amount: {float(net_amount):.2f}")
            else:
                # Account is included in GROSS and not excluded - add to NET
                net_entries[category].append(processed_transaction)
                gl_line_details[gl_account]['net'][category] += net_amount

            # Add to base category for both CAM and RET
            if category in ['cam', 'ret']:
                # Always add to base GROSS
                gross_entries['base'].append(processed_transaction)
                gross_amounts['base'] += net_amount
                included_accounts['base'].add(gl_account)
                gl_line_details[gl_account]['gross']['base'] += net_amount
                gl_line_details[gl_account]['categories'].add('base')

                # Check base exclusions
                base_exclusions = exclusions.get('base', [])
                is_base_excluded = check_account_exclusion(gl_account, base_exclusions)

                if is_base_excluded:
                    exclusion_entries['base'].append(processed_transaction)
                    exclusion_amounts['base'] += net_amount
                    excluded_accounts['base'].add(gl_account)
                    gl_line_details[gl_account]['exclusions']['base'] += net_amount

                    # Track base exclusion rules
                    for rule in base_exclusions:
                        if check_account_exclusion(gl_account, [rule]):
                            # Store the rule, duplicates will be removed when displaying
                            if 'exclusion_rules' not in gl_line_details[gl_account]:
                                gl_line_details[gl_account]['exclusion_rules'] = {}
                            if 'base' not in gl_line_details[gl_account]['exclusion_rules']:
                                gl_line_details[gl_account]['exclusion_rules']['base'] = []
                            gl_line_details[gl_account]['exclusion_rules']['base'].append(rule)
                else:
                    net_entries['base'].append(processed_transaction)
                    gl_line_details[gl_account]['net']['base'] += net_amount

            # Add to cap category ONLY for CAM (not RET)
            if category == 'cam':
                # Add to cap GROSS
                gross_entries['cap'].append(processed_transaction)
                gross_amounts['cap'] += net_amount
                included_accounts['cap'].add(gl_account)
                gl_line_details[gl_account]['gross']['cap'] += net_amount
                gl_line_details[gl_account]['categories'].add('cap')

                # Check cap exclusions
                cap_exclusions = exclusions.get('cap', [])
                is_cap_excluded = check_account_exclusion(gl_account, cap_exclusions)

                if is_cap_excluded:
                    exclusion_entries['cap'].append(processed_transaction)
                    exclusion_amounts['cap'] += net_amount
                    excluded_accounts['cap'].add(gl_account)
                    gl_line_details[gl_account]['exclusions']['cap'] += net_amount

                    # Track cap exclusion rules
                    for rule in cap_exclusions:
                        if check_account_exclusion(gl_account, [rule]):
                            # Store the rule, duplicates will be removed when displaying
                            if 'exclusion_rules' not in gl_line_details[gl_account]:
                                gl_line_details[gl_account]['exclusion_rules'] = {}
                            if 'cap' not in gl_line_details[gl_account]['exclusion_rules']:
                                gl_line_details[gl_account]['exclusion_rules']['cap'] = []
                            gl_line_details[gl_account]['exclusion_rules']['cap'].append(rule)
                else:
                    net_entries['cap'].append(processed_transaction)
                    gl_line_details[gl_account]['net']['cap'] += net_amount

    # Calculate net amounts
    net_amounts = {cat: gross_amounts[cat] - exclusion_amounts[cat] for cat in gross_amounts}

    # Log detailed breakdown
    for category in categories + ['base', 'cap']:
        logger.info(f"Category {category}:")
        logger.info(f"  Gross amount: {float(gross_amounts[category]):.2f}")
        logger.info(f"  Exclusions: {float(exclusion_amounts[category]):.2f}")
        logger.info(f"  Net amount: {float(net_amounts[category]):.2f}")

        if included_accounts[category]:
            logger.info(f"  Included accounts: {sorted(included_accounts[category])}")
        if excluded_accounts[category]:
            logger.info(f"  Excluded accounts: {sorted(excluded_accounts[category])}")

    # Log negative balance GL accounts if any
    if negative_balance_gl_accounts:
        logger.info(f"Found {len(negative_balance_gl_accounts)} included GL accounts with negative total balances (excluded from calculations):")
        for gl_account, detail in negative_balance_gl_accounts.items():
            logger.info(f"  GL {gl_account} ({detail['description']}): Total: {float(detail['total_amount']):.2f}")

    # Return comprehensive results with GL line details
    return {
        'gross_entries': gross_entries,
        'exclusion_entries': exclusion_entries,
        'net_entries': net_entries,
        'gross_amounts': gross_amounts,
        'exclusion_amounts': exclusion_amounts,
        'net_amounts': net_amounts,
        'included_accounts': included_accounts,
        'excluded_accounts': excluded_accounts,
        'gl_line_details': gl_line_details,  # Enhanced tracking
        'gl_account_names': gl_account_names,
        'negative_balance_gl_accounts': negative_balance_gl_accounts,  # Accounts excluded for negative balance
        'settings_used': settings  # Include settings for reference
    }


# Use the enhanced version for all GL filtering
filter_gl_accounts = filter_gl_accounts_with_detail


# ========== CAM, TAX, ADMIN FEE CALCULATIONS ==========

def calculate_admin_fee_percentage(settings: Dict[str, Any]) -> Decimal:
    """Calculate the admin fee percentage from settings with standardized handling."""
    # Get property ID to handle property-specific defaults
    property_id = settings.get('property_id', '').upper()
    
    # Get admin fee percentage from settings
    admin_fee_percentage_str = settings.get('settings', {}).get('admin_fee_percentage', '')

    # Handle empty strings with property-specific defaults
    if not admin_fee_percentage_str or admin_fee_percentage_str == "":
        # Default to 15% for WAT property, 0% otherwise
        if property_id == 'WAT':
            return Decimal('0.15')
        return Decimal('0')  # Default for other properties

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
        categories: List[str] = ['cam', 'ret'],
        capital_expenses_amount: Decimal = Decimal('0')
) -> Dict[str, Any]:
    """Calculate CAM, TAX, and admin fee amounts with detailed tracking."""
    # Get amounts from filtered data
    gross_amounts = gl_filtered_data['gross_amounts']
    exclusion_amounts = gl_filtered_data['exclusion_amounts']
    net_amounts = gl_filtered_data['net_amounts']
    gross_entries = gl_filtered_data.get('gross_entries', {})
    net_entries = gl_filtered_data.get('net_entries', {})

    # Get CAM and TAX amounts
    cam_gross = gross_amounts.get('cam', Decimal('0')) if 'cam' in categories else Decimal('0')
    cam_exclusions = exclusion_amounts.get('cam', Decimal('0')) if 'cam' in categories else Decimal('0')
    cam_net = net_amounts.get('cam', Decimal('0')) if 'cam' in categories else Decimal('0')

    ret_gross = gross_amounts.get('ret', Decimal('0')) if 'ret' in categories else Decimal('0')
    ret_exclusions = exclusion_amounts.get('ret', Decimal('0')) if 'ret' in categories else Decimal('0')
    ret_net = net_amounts.get('ret', Decimal('0')) if 'ret' in categories else Decimal('0')

    # Calculate admin fee
    admin_fee_percentage = calculate_admin_fee_percentage(settings)

    # Get admin_fee specific exclusions
    admin_fee_exclusions_list = settings.get('settings', {}).get('gl_exclusions', {}).get('admin_fee', [])

    # Calculate admin fee eligible CAM net by applying admin fee-specific exclusions upfront
    admin_fee_eligible_cam_net = cam_net
    admin_fee_specific_exclusion_amount = Decimal('0')
    
    # Apply admin_fee specific exclusions if they exist
    if admin_fee_exclusions_list:
        # Process CAM net entries to find additional admin_fee specific exclusions
        for entry in net_entries.get('cam', []):
            gl_account = entry.get('GL Account', '')
            if gl_account and check_account_exclusion(gl_account, admin_fee_exclusions_list):
                # This account passes CAM exclusions but is specifically excluded from admin_fee
                exclusion_amount = entry.get('Net Amount', Decimal('0'))
                admin_fee_specific_exclusion_amount += exclusion_amount
                admin_fee_eligible_cam_net -= exclusion_amount
    
    # Calculate admin fee gross on the CAM net before admin-specific exclusions
    admin_fee_gross_base = cam_net + capital_expenses_amount
    admin_fee_gross = admin_fee_gross_base * admin_fee_percentage
    
    # Calculate admin fee net after applying admin-specific exclusions
    admin_fee_base_amount = admin_fee_eligible_cam_net + capital_expenses_amount
    admin_fee_net = admin_fee_base_amount * admin_fee_percentage
    
    # Calculate the admin fee exclusions as the difference between gross and net
    admin_fee_exclusions = admin_fee_gross - admin_fee_net
    
    # DEBUG: Log admin fee calculation details
    logger.info(f"Admin fee calculation debug:")
    logger.info(f"  CAM Gross: {float(cam_gross):.2f}")
    logger.info(f"  CAM Net (after CAM exclusions): {float(cam_net):.2f}")
    logger.info(f"  Admin Fee-specific exclusions: {float(admin_fee_specific_exclusion_amount):.2f}")
    logger.info(f"  Admin Fee eligible CAM Net: {float(admin_fee_eligible_cam_net):.2f}")
    logger.info(f"  Capital Expenses Amount: {float(capital_expenses_amount):.2f}")
    logger.info(f"  Admin Fee Gross Base: {float(admin_fee_gross_base):.2f}")
    logger.info(f"  Admin Fee Net Base: {float(admin_fee_base_amount):.2f}")
    logger.info(f"  Admin Fee %: {float(admin_fee_percentage * 100):.2f}%")
    logger.info(f"  Admin Fee Gross: {float(admin_fee_gross):.2f}")
    logger.info(f"  Admin Fee Exclusions: {float(admin_fee_exclusions):.2f}")
    logger.info(f"  Admin Fee Net: {float(admin_fee_net):.2f}")
    
    if admin_fee_specific_exclusion_amount > 0:
        logger.info(f"Admin fee calculation details (with specific exclusions):")
        logger.info(f"  Gross Calculation:")
        logger.info(f"    CAM Net total: {float(cam_net):.2f}")
        logger.info(f"    Plus: Capital expenses: {float(capital_expenses_amount):.2f}")
        logger.info(f"    Admin Fee Gross Base: {float(admin_fee_gross_base):.2f}")
        logger.info(f"    Admin Fee Gross (Base × {float(admin_fee_percentage * 100):.2f}%): {float(admin_fee_gross):.2f}")
        logger.info(f"  Net Calculation:")
        logger.info(f"    CAM Net total: {float(cam_net):.2f}")
        logger.info(f"    Less: Admin fee-specific exclusions: {float(admin_fee_specific_exclusion_amount):.2f}")
        logger.info(f"    Admin Fee Eligible CAM Net: {float(admin_fee_eligible_cam_net):.2f}")
        logger.info(f"    Plus: Capital expenses: {float(capital_expenses_amount):.2f}")
        logger.info(f"    Admin Fee Net Base: {float(admin_fee_base_amount):.2f}")
        logger.info(f"    Admin Fee Net (Base × {float(admin_fee_percentage * 100):.2f}%): {float(admin_fee_net):.2f}")
        logger.info(f"  Admin Fee Exclusions (Gross - Net): {float(admin_fee_exclusions):.2f}")

    # Determine if admin fee is included in cap and base year calculations
    include_in_cap = is_admin_fee_included_in(settings, 'cap')
    include_in_base = is_admin_fee_included_in(settings, 'base')

    # Calculate combined totals - ALWAYS using the appropriate gross/net values
    # First calculate without admin fee
    combined_gross_total = cam_gross + ret_gross
    combined_exclusions = cam_exclusions + ret_exclusions

    # Add admin fee to combined totals if needed
    # Note: admin fee is an additional calculation, not a GL account group like CAM and RET
    # So we need to add it to combined totals separately
    combined_gross_with_admin = combined_gross_total + admin_fee_gross
    combined_exclusions_with_admin = combined_exclusions + admin_fee_exclusions
    combined_net_with_admin = combined_gross_with_admin - combined_exclusions_with_admin

    # Choose the appropriate totals based on whether we want to include admin fee
    # For reporting purposes, admin fee is considered part of the total
    combined_gross_total = combined_gross_with_admin
    combined_exclusions = combined_exclusions_with_admin
    combined_net_total = combined_net_with_admin

    # For cap calculation - use appropriate values based on settings
    if include_in_cap:
        cap_gross_total = combined_gross_with_admin
        cap_exclusions_total = combined_exclusions_with_admin
        cap_admin_fee = admin_fee_net
    else:
        cap_gross_total = combined_gross_total - admin_fee_gross
        cap_exclusions_total = combined_exclusions - admin_fee_exclusions
        cap_admin_fee = Decimal('0')

    cap_net_total = cap_gross_total - cap_exclusions_total

    # For base year calculation - use appropriate values based on settings
    if include_in_base:
        base_gross_total = combined_gross_with_admin
        base_exclusions_total = combined_exclusions_with_admin
        base_admin_fee = admin_fee_net
    else:
        base_gross_total = combined_gross_total - admin_fee_gross
        base_exclusions_total = combined_exclusions - admin_fee_exclusions
        base_admin_fee = Decimal('0')

    base_net_total = base_gross_total - base_exclusions_total

    # Log detailed calculations
    logger.info(f"CAM calculations:")
    logger.info(f"  Gross: {float(cam_gross):.2f}")
    logger.info(f"  Exclusions: {float(cam_exclusions):.2f}")
    logger.info(f"  Net: {float(cam_net):.2f}")

    logger.info(f"RET calculations:")
    logger.info(f"  Gross: {float(ret_gross):.2f}")
    logger.info(f"  Exclusions: {float(ret_exclusions):.2f}")
    logger.info(f"  Net: {float(ret_net):.2f}")

    logger.info(f"Admin fee calculations:")
    logger.info(f"  Percentage: {float(admin_fee_percentage) * 100:.2f}%")
    logger.info(f"  Gross base amount (CAM + Capital): {float(admin_fee_gross_base):.2f}")
    logger.info(f"    CAM net: {float(cam_net):.2f}")
    logger.info(f"    Capital expenses: {float(capital_expenses_amount):.2f}")
    logger.info(f"  Gross admin fee: {float(admin_fee_gross):.2f}")
    logger.info(f"  Admin fee exclusions: {float(admin_fee_exclusions):.2f}")
    logger.info(f"  Net base amount (Eligible CAM + Capital): {float(admin_fee_base_amount):.2f}")
    logger.info(f"  Net admin fee: {float(admin_fee_net):.2f}")
    logger.info(f"  In cap: {include_in_cap}, in base: {include_in_base}")

    # Return comprehensive results
    return {
        'cam_gross': cam_gross,
        'cam_exclusions': cam_exclusions,
        'cam_net': cam_net,

        'ret_gross': ret_gross,
        'ret_exclusions': ret_exclusions,
        'ret_net': ret_net,

        'admin_fee_percentage': admin_fee_percentage,
        'admin_fee_gross': admin_fee_gross,
        'admin_fee_exclusions': admin_fee_exclusions,
        'admin_fee_net': admin_fee_net,
        'admin_fee_exclusions_list': admin_fee_exclusions_list,  # Added to pass specific admin fee exclusion list
        'admin_fee_base_amount': admin_fee_base_amount,  # CAM + Capital expenses
        'capital_expenses_in_admin': capital_expenses_amount,  # Amount of capital expenses included in admin fee

        'combined_gross_total': combined_gross_total,
        'combined_exclusions': combined_exclusions,
        'combined_net_total': combined_net_total,

        'cap_gross_total': cap_gross_total,
        'cap_exclusions_total': cap_exclusions_total,
        'cap_admin_fee': cap_admin_fee,
        'cap_net_total': cap_net_total,

        'base_gross_total': base_gross_total,
        'base_exclusions_total': base_exclusions_total,
        'base_admin_fee': base_admin_fee,
        'base_net_total': base_net_total,

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

    # If base year doesn't apply, no adjustment needed
    if not applies:
        logger.info("Base year adjustment does not apply")
        return {
            'base_year_applies': False,
            'base_year_has_effect': False,  # NEW
            'base_year': None,
            'base_year_amount': Decimal('0'),
            'base_year_adjustment': Decimal('0'),
            'total_before_adjustment': base_year_total,
            'after_base_adjustment': base_year_total
        }

    # Get base year amount
    base_year_amount_str = settings.get('settings', {}).get('base_year_amount', '0')
    base_amount = to_decimal(base_year_amount_str)

    # Calculate the base year adjustment (never deduct more than the base amount or what's available)
    base_year_adjustment = min(base_amount, base_year_total)

    # Calculate amount after base year adjustment
    after_base = base_year_total - base_year_adjustment

    # Log the calculation
    logger.info(
        f"Base year adjustment: {float(base_year_total):.2f} - {float(base_year_adjustment):.2f} = {float(after_base):.2f}")

    return {
        'base_year_applies': True,
        'base_year_has_effect': base_year_adjustment > 0,  # NEW - True only if actually applied
        'base_year': base_year_setting,
        'base_year_amount': base_amount,
        'base_year_adjustment': base_year_adjustment,
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
    # Make sure to handle case where cap_percentage might be a non-string/non-number
    cap_percentage = to_decimal(cap_percentage_str)
    
    # Check if we need to convert from percentage to decimal format
    if cap_percentage >= Decimal('1'):
        cap_percentage = cap_percentage / Decimal('100')
    
    logger.info(f"Using cap percentage: {float(cap_percentage) * 100:.4f}%")

    # Get cap type
    cap_type = cap_settings.get('cap_type', 'previous_year')

    # Get min/max increase
    min_increase_str = settings.get('settings', {}).get('min_increase', '')
    max_increase_str = settings.get('settings', {}).get('max_increase', '')

    # Convert min increase with proper percentage handling
    min_increase = None
    if min_increase_str:
        min_increase = to_decimal(min_increase_str)
        # Check if we need to convert from percentage to decimal format
        if min_increase >= Decimal('1'):
            min_increase = min_increase / Decimal('100')
            logger.info(f"Using min increase: {float(min_increase) * 100:.4f}%")
        else:
            logger.info(f"Using min increase (already in decimal): {float(min_increase) * 100:.4f}%")
    
    # Convert max increase with proper percentage handling
    max_increase = None
    if max_increase_str:
        max_increase = to_decimal(max_increase_str)
        # Check if we need to convert from percentage to decimal format
        if max_increase >= Decimal('1'):
            max_increase = max_increase / Decimal('100')
            logger.info(f"Using max increase: {float(max_increase) * 100:.4f}%")
        else:
            logger.info(f"Using max increase (already in decimal): {float(max_increase) * 100:.4f}%")

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


def determine_cap_eligible_amount(
        gl_filtered_data: Dict[str, Any],
        tenant_cam_tax_admin: Dict[str, Any]
) -> Decimal:
    """Determine the amount that is eligible for cap calculations."""
    # The cap-eligible amount is the net amount for all GL accounts included in cap
    cap_eligible_net = gl_filtered_data['net_amounts'].get('cap', Decimal('0'))

    # Add admin fee if it's included in cap
    if tenant_cam_tax_admin.get('include_admin_in_cap', False):
        cap_eligible_net += tenant_cam_tax_admin.get('admin_fee_net', Decimal('0'))

    logger.info(f"Cap eligible amount: {float(cap_eligible_net):.2f}")
    return cap_eligible_net


def calculate_cap_deduction(
        tenant_id: str,
        recon_year: int,
        cap_eligible_amount: Decimal,
        settings: Dict[str, Any],
        cap_history: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """Calculate cap deduction amount (if any)."""
    # Get cap limit
    cap_limit_results = calculate_cap_limit(tenant_id, recon_year, settings, cap_history)

    # Determine if cap applies
    cap_applies = cap_limit_results.get('reference_amount', Decimal('0')) > 0

    if not cap_applies:
        logger.info(f"Cap does not apply for tenant {tenant_id}")
        return {
            'cap_applies': False,
            'cap_has_effect': False,  # NEW
            'cap_limit': Decimal('0'),
            'cap_eligible_amount': cap_eligible_amount,
            'cap_deduction': Decimal('0'),
            'net_after_cap': cap_eligible_amount,
            'cap_limit_results': cap_limit_results
        }

    cap_limit = cap_limit_results.get('effective_cap_limit', Decimal('0'))

    # Calculate deduction (only if eligible amount exceeds cap)
    cap_deduction = Decimal('0')
    if cap_eligible_amount > cap_limit:
        cap_deduction = cap_eligible_amount - cap_limit
        logger.info(f"Cap limit applied: {float(cap_eligible_amount):.2f} exceeds cap of {float(cap_limit):.2f}")
        logger.info(f"Cap deduction: {float(cap_deduction):.2f}")

    # Calculate net amount after cap
    net_after_cap = cap_eligible_amount - cap_deduction

    return {
        'cap_applies': cap_applies,
        'cap_has_effect': cap_deduction > 0,  # NEW - True only if deduction actually applied
        'cap_limit': cap_limit,
        'cap_eligible_amount': cap_eligible_amount,
        'cap_deduction': cap_deduction,
        'net_after_cap': net_after_cap,
        'cap_limit_results': cap_limit_results
    }


def update_cap_history(
        tenant_id: str,
        recon_year: int,
        cap_eligible_amount: Decimal,
        cap_history: Dict[str, Dict[str, float]] = None
) -> Dict[str, Dict[str, float]]:
    """Update cap history with the cap-eligible amount for the current reconciliation."""
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()

    # Convert recon_year to string
    recon_year_str = str(recon_year)

    # Initialize tenant entry if it doesn't exist
    tenant_id_str = str(tenant_id)
    if tenant_id_str not in cap_history:
        cap_history[tenant_id_str] = {}

    # Update the entry with the cap-eligible amount (not the final billing amount)
    # This ensures caps are based on what would have been charged without the cap
    cap_history[tenant_id_str][recon_year_str] = float(cap_eligible_amount)
    logger.info(f"Updated cap history for tenant {tenant_id}, year {recon_year}: {float(cap_eligible_amount):.2f}")

    # Save the updated cap history
    save_cap_history(cap_history)

    return cap_history


# ========== CAPITAL EXPENSES CALCULATION ==========

def calculate_capital_expenses(
        settings: Dict[str, Any],
        recon_year: int,
        periods: List[str],
        tenant_share_percentage: Optional[Decimal] = None
) -> Dict[str, Any]:
    """Calculate amortized capital expenses for the reconciliation with detailed reporting."""
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
    total_property_expense = Decimal('0')  # Track property-level total
    expense_count = 0

    for expense_id, expense in merged_expenses.items():
        # Extract expense details
        expense_year = to_decimal(expense.get('year', '0'), '0')
        expense_amount = to_decimal(expense.get('amount', '0'), '0')
        amort_years = to_decimal(expense.get('amort_years', '1'), '1')
        description = expense.get('description', '')

        # Ensure amortization period is at least 1 year
        if amort_years < 1:
            amort_years = Decimal('1')

        # Check if expense applies to current year
        expense_year_int = int(expense_year)
        start_year = expense_year_int
        end_year = expense_year_int + int(amort_years) - 1

        if expense_year_int > recon_year or end_year < recon_year:
            continue

        # Calculate annual amortized amount
        annual_amount = expense_amount / amort_years

        # Get tenant share percentage if applicable
        if tenant_share_percentage is not None:
            # Use the provided tenant share percentage (e.g., 1.74% = 0.0174)
            tenant_allocation_percentage = tenant_share_percentage
        elif 'tenant_id' in settings:
            # Fallback to square footage calculation if percentage not provided
            property_sf = to_decimal(settings.get('total_rsf', '0'))
            tenant_sf = to_decimal(settings.get('settings', {}).get('square_footage', '0'))
            
            if property_sf > 0 and tenant_sf > 0:
                tenant_allocation_percentage = tenant_sf / property_sf
            else:
                tenant_allocation_percentage = Decimal('1')  # Default to 100%
        else:
            tenant_allocation_percentage = Decimal('1')  # Default to 100%

        # Calculate tenant's share
        tenant_annual_share = annual_amount * tenant_allocation_percentage
        
        # Apply proration based on occupancy if tenant settings are provided
        prorated_amount = tenant_annual_share  # Start with tenant's share, not full amount
        if 'tenant_id' in settings:
            lease_start = settings.get('lease_start')
            lease_end = settings.get('lease_end')

            if lease_start or lease_end:
                # Calculate occupancy factors
                occupancy_factors = calculate_occupancy_factors(periods, lease_start, lease_end)

                # Calculate average occupancy
                if occupancy_factors:
                    avg_occupancy = sum(occupancy_factors.values()) / Decimal(len(periods))
                    prorated_amount = tenant_annual_share * avg_occupancy  # Apply to tenant's share

        # Add to amortized expenses if there's an amount
        if prorated_amount > 0:
            amortized_expenses.append({
                'id': expense_id,
                'description': description,
                'year': expense_year_int,
                'amount': expense_amount,
                'amort_years': int(amort_years),
                'annual_amount': annual_amount,
                'prorated_amount': prorated_amount,
                'start_year': start_year,
                'end_year': end_year,
                'total_cost': expense_amount,
                'amortization_years': int(amort_years),
                'tenant_allocation_percentage': tenant_allocation_percentage,
                'tenant_annual_share': tenant_annual_share
            })

            total_capital_expense += prorated_amount  # Use prorated amount (after occupancy adjustment)
            total_property_expense += annual_amount  # Track property-level total
            expense_count += 1

    logger.info(
        f"Calculated capital expenses: {len(amortized_expenses)} items, total: {float(total_capital_expense):.2f}")

    return {
        'capital_expenses': amortized_expenses,
        'total_capital_expenses': total_capital_expense,
        'total_property_expenses': total_property_expense,  # Property-level total
        'expense_count': expense_count,
        'has_amortization': expense_count > 0  # NEW
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

            # Check if the value already appears to be a decimal (less than 1)
            # This handles cases where the value might be entered as 0.7 instead of 70
            if fixed_share < Decimal('1'):
                logger.info(f"Using fixed share percentage (already in decimal format): {float(fixed_share) * 100:.4f}%")
                return fixed_share
            else:
                # Convert from percentage (e.g., 5.138) to decimal (0.05138)
                fixed_share = fixed_share / Decimal('100')
                logger.info(f"Using fixed share percentage (converted from percentage): {float(fixed_share) * 100:.4f}%")
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
    """Get override information for a specific tenant and property.

    The override amount is treated as an adjustment that gets added to the calculated billing amount,
    not as a replacement for the entire calculated amount.
    
    IMPORTANT: The override amount is used exactly as provided in the custom_overrides.json file,
    with no scaling or adjustments based on the description, months, or reconciliation periods.
    The description field (e.g., "Jan-Apr 2024 payment") is for informational purposes only
    and does not affect calculations.
    """
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
    """Get the old monthly payment amount for a tenant.
    
    NOTE: This function is only used for payment tracking and has no effect on override amounts.
    Override amounts from custom_overrides.json are used exactly as-is with no adjustments.
    """
    # Load tenant CAM data
    tenant_cam_data = load_json(TENANT_CAM_DATA_PATH)

    # Convert tenant_id to string for comparison
    tenant_id_str = str(tenant_id)

    # Find the record for this tenant and property
    for record in tenant_cam_data:
        record_tenant_id = str(record.get('TenantID', ''))
        record_property_id = record.get('PropertyID', '')

        if record_tenant_id == tenant_id_str and (record_property_id or '').lower() == (property_id or '').lower():
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


def get_tenant_payments(
        tenant_id: str,
        property_id: str,
        periods: List[str],
        income_categories: List[str] = None
) -> Dict[str, Any]:
    """Get all payments made by a tenant during specific periods."""
    # Load tenant CAM data
    tenant_cam_data = load_json(TENANT_CAM_DATA_PATH)

    # Convert tenant_id to string for comparison
    tenant_id_str = str(tenant_id)

    # Initialize payments dictionary
    payments = {
        'total': Decimal('0'),
        'by_period': {},
        'by_category': {}
    }

    # Find payments for this tenant and property
    for record in tenant_cam_data:
        record_tenant_id = str(record.get('TenantID', ''))
        record_property_id = record.get('PropertyID', '')
        income_category = record.get('IncomeCategory', '')

        # Filter by income category if specified
        if income_categories and income_category not in income_categories:
            continue

        if record_tenant_id == tenant_id_str and (record_property_id or '').lower() == (property_id or '').lower():
            # Extract the period from BillingMonth (e.g., "2024-05" -> "202405")
            billing_month = record.get('BillingMonth', '')
            if billing_month:
                try:
                    # Convert from YYYY-MM to YYYYMM format
                    parts = billing_month.split('-')
                    if len(parts) == 2:
                        period = f"{parts[0]}{parts[1]}"

                        # Check if this period is in our list of periods
                        if period in periods:
                            # Get the MatchedEstimate value (what was billed)
                            matched_estimate = record.get('MatchedEstimate', '')

                            if matched_estimate and matched_estimate != '':
                                amount = to_decimal(matched_estimate)

                                # Add to total
                                payments['total'] += amount

                                # Add to by_period
                                if period not in payments['by_period']:
                                    payments['by_period'][period] = Decimal('0')
                                payments['by_period'][period] += amount

                                # Add to by_category
                                if income_category not in payments['by_category']:
                                    payments['by_category'][income_category] = Decimal('0')
                                payments['by_category'][income_category] += amount

                                logger.debug(
                                    f"Found payment for tenant {tenant_id}, period {period}, category {income_category}: {float(amount):.2f}")
                except Exception as e:
                    logger.warning(f"Error processing billing month {billing_month}: {str(e)}")

    logger.info(f"Total payments for tenant {tenant_id} over {len(periods)} periods: {float(payments['total']):.2f}")
    return payments


def calculate_new_monthly_payment(
        final_amount: Decimal,
        periods_count: int = 12
) -> Decimal:
    """Calculate the new monthly payment amount based on the reconciliation amount.

    Note: This should use the base_billing amount that does NOT include the override amount.
    The override amount is treated as a one-time adjustment and is not factored into monthly payments.
    """
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


# ========== GL DETAIL REPORTING ==========

def generate_gl_detail_report(
        tenant_result: Dict[str, Any],
        property_id: str,
        recon_year: int
) -> str:
    """Generate a detailed GL line item report for a single tenant that matches actual reconciliation."""
    tenant_id = tenant_result['tenant_id']
    tenant_name = tenant_result['tenant_name']

    # Create tenant-specific directory
    tenant_dir = os.path.join(GL_DETAILS_PATH, f"{property_id}_{recon_year}",
                              f"Tenant_{tenant_id}_{tenant_name.replace(' ', '_')}")
    os.makedirs(tenant_dir, exist_ok=True)

    # Create filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(tenant_dir, f"GL_detail_{tenant_id}_{recon_year}_{timestamp}.csv")

    # Extract needed data
    gl_filtered_data = tenant_result['gl_filtered_data']
    gl_line_details = gl_filtered_data.get('gl_line_details', {})

    # Get calculation parameters from actual reconciliation
    tenant_share_percentage = tenant_result['tenant_share_percentage']
    tenant_cam_tax_admin = tenant_result['tenant_cam_tax_admin']
    admin_fee_percentage = tenant_cam_tax_admin['admin_fee_percentage']

    # Get total amounts for proportion calculations
    total_cam_net = tenant_cam_tax_admin['cam_net']
    total_ret_net = tenant_cam_tax_admin['ret_net']
    total_base_net = tenant_cam_tax_admin['base_net_total']
    total_cap_net = tenant_cam_tax_admin['cap_net_total']

    # Get adjustments from actual reconciliation
    base_year_result = tenant_result['base_year_result']
    cap_result = tenant_result['cap_result']
    occupancy_factors = tenant_result['occupancy_factors']

    # Get override adjustment DIRECTLY from the custom_overrides.json file
    # NOT from tenant_result which might have already been modified
    # This ensures we always use the original override amount with no scaling or adjustments
    override_info = get_tenant_override(tenant_id, property_id)
    override_adjustment = override_info['override_amount']  # Use the raw value directly
    has_override = override_adjustment != 0

    # Calculate average occupancy
    avg_occupancy = Decimal('1')
    if occupancy_factors:
        avg_occupancy = sum(occupancy_factors.values()) / len(occupancy_factors)

    # Define columns for GL detail report
    columns = [
        'gl_account', 'description',
        'cam_gross', 'cam_exclusions', 'cam_net',
        'ret_gross', 'ret_exclusions', 'ret_net',
        'combined_gross', 'combined_exclusions', 'combined_net',
        'cam_inclusion_rules', 'cam_exclusion_rules',
        'ret_inclusion_rules', 'ret_exclusion_rules',
        'admin_fee_percentage', 'admin_fee_exclusion_rules', 'admin_fee_amount',
        'base_exclusion_rules', 'cap_exclusion_rules',
        'total_before_proration',
        'tenant_share_percentage', 'tenant_share_amount',
        'base_year_impact', 'cap_impact',
        'occupancy_factor', 'override_amount', 'override_description',
        'final_tenant_amount',
        'inclusion_categories', 'exclusion_categories'
    ]

    # Create report rows
    report_rows = []
    totals = {col: Decimal('0') if col not in ['gl_account', 'description', 'admin_fee_percentage',
                                               'tenant_share_percentage', 'occupancy_factor', 'cam_inclusion_rules',
                                               'cam_exclusion_rules', 'override_description',
                                               'admin_fee_exclusion_rules',
                                               'ret_inclusion_rules', 'ret_exclusion_rules', 'base_exclusion_rules',
                                               'cap_exclusion_rules', 'inclusion_categories',
                                               'exclusion_categories'] else '' for col in columns}

    # First pass: Calculate admin fee exclusions like in the property report
    admin_fee_excluded_accounts = set()
    admin_fee_specific_exclusion_amount = Decimal('0')

    # Get admin_fee specific exclusions from tenant settings
    admin_fee_exclusions_list = tenant_cam_tax_admin.get('admin_fee_exclusions_list', [])

    # Calculate admin fee eligible CAM net directly
    # Start with CAM net (after CAM exclusions) and apply admin fee-specific exclusions upfront
    admin_fee_eligible_cam_net = total_cam_net
    
    # Process accounts for admin fee-specific exclusions
    if admin_fee_exclusions_list:
        for gl_account, gl_detail in sorted(gl_line_details.items()):
            cam_net = gl_detail['net'].get('cam', Decimal('0'))
            if cam_net > 0 and check_account_exclusion(gl_account, admin_fee_exclusions_list):
                # This account is excluded from admin fee
                admin_fee_excluded_accounts.add(gl_account)
                admin_fee_specific_exclusion_amount += cam_net
                admin_fee_eligible_cam_net -= cam_net  # Deduct from eligible amount immediately
                
                # Track which admin fee exclusion rules matched for reporting
                for rule in admin_fee_exclusions_list:
                    if check_account_exclusion(gl_account, [rule]):
                        if 'exclusion_rules' not in gl_line_details[gl_account]:
                            gl_line_details[gl_account]['exclusion_rules'] = {}
                        if 'admin_fee' not in gl_line_details[gl_account]['exclusion_rules']:
                            gl_line_details[gl_account]['exclusion_rules']['admin_fee'] = []
                        gl_line_details[gl_account]['exclusion_rules']['admin_fee'].append(rule)
                logger.debug(f"GL account {gl_account} excluded from admin fee due to specific admin fee exclusions")
    
    # Calculate the total admin fee directly on the eligible CAM net
    total_admin_fee = admin_fee_eligible_cam_net * admin_fee_percentage
    
    # Calculate the admin fee exclusions value (for reporting consistency)
    # This represents the difference between admin fee calculated without exclusions and with exclusions
    admin_fee_exclusions = (total_cam_net * admin_fee_percentage) - total_admin_fee

    # Enhanced logging to debug admin fee calculations
    logger.info(f"Property report style admin fee calculation: ")
    logger.info(f"  CAM Net Total: {total_cam_net}")
    logger.info(f"  Admin Fee Specific Exclusions: {admin_fee_specific_exclusion_amount}")
    logger.info(f"  Admin Fee Eligible CAM Net: {admin_fee_eligible_cam_net}")
    logger.info(f"  Admin Fee Percentage: {admin_fee_percentage}")
    
    # Calculate both gross and net admin fee values
    total_admin_fee_gross = total_cam_net * admin_fee_percentage
    total_admin_fee_net = admin_fee_eligible_cam_net * admin_fee_percentage
    total_admin_fee_exclusions = total_admin_fee_gross - total_admin_fee_net
    
    logger.info(f"  Total Admin Fee Gross: {total_cam_net} × {admin_fee_percentage} = {total_admin_fee_gross}")
    logger.info(f"  Total Admin Fee Net: {admin_fee_eligible_cam_net} × {admin_fee_percentage} = {total_admin_fee_net}")
    logger.info(f"  Admin Fee Exclusions: {total_admin_fee_exclusions} (difference between admin fee with and without exclusions)")
    
    # Store the admin fee values in the tenant_cam_tax_admin dictionary for CSV reporting
    tenant_cam_tax_admin['admin_fee_gross'] = total_admin_fee_gross
    tenant_cam_tax_admin['admin_fee_net'] = total_admin_fee_net
    tenant_cam_tax_admin['admin_fee_exclusions'] = total_admin_fee_exclusions
    # Get capital expenses from the tenant result or use 0 if not available
    capital_expenses = tenant_cam_tax_admin.get('capital_expenses_in_admin', Decimal('0'))
    tenant_cam_tax_admin['admin_fee_base_amount'] = admin_fee_eligible_cam_net + capital_expenses  # Include capital expenses in base amount

    # Process each GL account
    for gl_account, gl_detail in sorted(gl_line_details.items()):
        # Get values from gl_detail
        cam_gross = gl_detail['gross'].get('cam', Decimal('0'))
        cam_exclusions = gl_detail['exclusions'].get('cam', Decimal('0'))
        cam_net = gl_detail['net'].get('cam', Decimal('0'))

        ret_gross = gl_detail['gross'].get('ret', Decimal('0'))
        ret_exclusions = gl_detail['exclusions'].get('ret', Decimal('0'))
        ret_net = gl_detail['net'].get('ret', Decimal('0'))

        combined_gross = cam_gross + ret_gross
        combined_exclusions = cam_exclusions + ret_exclusions
        combined_net = cam_net + ret_net

        # Calculate admin fee for this GL line using our pre-calculated total admin fee
        # Calculate admin fee for this GL line
        admin_fee_amount = Decimal('0')
        property_admin_fee_amount = Decimal('0')
        if admin_fee_eligible_cam_net > 0 and cam_net > 0 and gl_account not in admin_fee_excluded_accounts:
            # First calculate the property-level admin fee for this GL line
            property_admin_fee_amount = (cam_net / admin_fee_eligible_cam_net) * total_admin_fee
            # Then calculate the tenant's share of this admin fee
            admin_fee_amount = property_admin_fee_amount * tenant_share_percentage

        # Calculate tenant's share of the GL amount (without admin fee)
        tenant_share_amount = (combined_net * tenant_share_percentage).quantize(Decimal('0.000001'),
                                                                              rounding=ROUND_HALF_UP)
        
        # Total before proration (for later calculations, not for display)
        total_before_proration = combined_net + property_admin_fee_amount

        # Calculate proportional base year impact
        base_year_impact = Decimal('0')
        if base_year_result['base_year_has_effect'] and total_base_net > 0:
            base_net_for_gl = gl_detail['net'].get('base', Decimal('0'))
            if base_net_for_gl > 0:
                # Proportional share of base year adjustment with consistent rounding
                base_year_impact = ((base_net_for_gl / total_base_net) * base_year_result[
                    'base_year_adjustment'] * tenant_share_percentage).quantize(Decimal('0.000001'),
                                                                                rounding=ROUND_HALF_UP)

        # Calculate proportional cap impact
        cap_impact = Decimal('0')
        if cap_result['cap_has_effect'] and total_cap_net > 0:
            cap_net_for_gl = gl_detail['net'].get('cap', Decimal('0'))
            if cap_net_for_gl > 0:
                # Proportional share of cap deduction with consistent rounding
                cap_impact = ((cap_net_for_gl / total_cap_net) * cap_result[
                    'cap_deduction'] * tenant_share_percentage).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

        # Calculate override impact for this GL line
        # Distribute override proportionally across GL accounts based on tenant share amount
        override_impact = Decimal('0')
        if has_override:
            # First, calculate the total tenant share amount across all GL accounts if not already done
            # This is needed to properly proportion the override amount
            if 'total_tenant_share_calculated' not in totals or not totals['total_tenant_share_calculated']:
                # Reset and recalculate the total tenant share amount to ensure accuracy
                total_tenant_share = Decimal('0')
                # Loop through all GL accounts to sum up their tenant share amounts
                for gl_acct, gl_data in sorted(gl_line_details.items()):
                    # Calculate components for this GL account
                    gl_cam_net = gl_data['net'].get('cam', Decimal('0'))
                    gl_ret_net = gl_data['net'].get('ret', Decimal('0'))
                    gl_combined_net = gl_cam_net + gl_ret_net
                    
                    # Calculate admin fee for this account
                    gl_admin_fee = Decimal('0')
                    is_excluded = gl_acct in admin_fee_excluded_accounts
                    if not is_excluded and admin_fee_eligible_cam_net > 0 and gl_cam_net > 0:
                        gl_admin_fee = (gl_cam_net / admin_fee_eligible_cam_net) * total_admin_fee
                    
                    # Calculate total before proration
                    gl_before_proration = gl_combined_net + gl_admin_fee
                    
                    # Apply tenant share percentage to get tenant share amount
                    gl_tenant_share = gl_before_proration * tenant_share_percentage
                    
                    # Add to running total
                    total_tenant_share += gl_tenant_share
                
                # Store the total and mark as calculated
                totals['total_tenant_share_for_override'] = total_tenant_share
                totals['total_tenant_share_calculated'] = True
                logger.debug(f"Calculated total tenant share amount for override distribution: {total_tenant_share}")
            
            # Now calculate this GL account's proportional share of the override amount
            # IMPORTANT: Use the original override amount directly with no scaling or adjustments
            # The override_adjustment now comes directly from get_tenant_override() and not from tenant_result
            total_tenant_share = totals['total_tenant_share_for_override']
            if total_tenant_share > 0 and tenant_share_amount > 0:
                # Calculate the proportional override amount for this GL line
                # based on its percentage contribution to the total tenant share
                override_impact = (tenant_share_amount / total_tenant_share) * override_adjustment
                logger.debug(f"GL {gl_account}: Tenant share ${tenant_share_amount} / Total ${total_tenant_share} = " +
                           f"{tenant_share_amount / total_tenant_share:.4f} × Override ${override_adjustment} = ${override_impact}")

        # Apply base year and cap impacts first
        after_base_cap_adjustments = tenant_share_amount - base_year_impact - cap_impact

        # Apply occupancy adjustment
        # Round to 6 decimal places to match property report calculation
        after_occupancy = (after_base_cap_adjustments * avg_occupancy).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        
        # Apply override amount AFTER occupancy adjustment
        # Override is a fixed amount that doesn't get adjusted by occupancy
        final_tenant_amount = after_occupancy + override_impact

        # Get inclusion/exclusion rules
        # For inclusion rules, we already store only the highest priority rule
        cam_inclusion_rules = ', '.join(gl_detail.get('inclusion_rules', {}).get('cam', []))
        # For exclusion rules, remove duplicates since they might be added multiple times
        cam_exclusion_rules = ', '.join(sorted(set(gl_detail.get('exclusion_rules', {}).get('cam', []))))
        ret_inclusion_rules = ', '.join(gl_detail.get('inclusion_rules', {}).get('ret', []))
        ret_exclusion_rules = ', '.join(sorted(set(gl_detail.get('exclusion_rules', {}).get('ret', []))))
        admin_fee_exclusion_rules = ', '.join(sorted(set(gl_detail.get('exclusion_rules', {}).get('admin_fee', []))))
        base_exclusion_rules = ', '.join(sorted(set(gl_detail.get('exclusion_rules', {}).get('base', []))))
        cap_exclusion_rules = ', '.join(sorted(set(gl_detail.get('exclusion_rules', {}).get('cap', []))))

        # Get categories
        inclusion_categories = ', '.join(sorted(gl_detail.get('categories', set())))
        exclusion_categories = ', '.join(sorted(gl_detail.get('exclusion_levels', {}).keys()))

        # Create row
        # Prepare override description if needed
        override_desc = ''
        if has_override:
            if override_adjustment < 0:
                override_desc = 'Manual Reduction'
            else:
                override_desc = 'Manual Addition'

        # Get the GL description from the source data
        # First try to get it from gl_detail.get('description')
        # If not available, try gl_account_names.get(gl_account) which contains descriptions from the master GL data
        gl_description = gl_detail.get('description', '')
        if not gl_description and gl_account in gl_filtered_data.get('gl_account_names', {}):
            gl_description = gl_filtered_data.get('gl_account_names', {}).get(gl_account, '')
            
        row = {
            'gl_account': gl_account,
            'description': gl_description,
            'cam_gross': format_currency(cam_gross),
            'cam_exclusions': format_currency(cam_exclusions * -1) if cam_exclusions > 0 else '$0.00',
            'cam_net': format_currency(cam_net),
            'ret_gross': format_currency(ret_gross),
            'ret_exclusions': format_currency(ret_exclusions * -1) if ret_exclusions > 0 else '$0.00',
            'ret_net': format_currency(ret_net),
            'combined_gross': format_currency(combined_gross),
            'combined_exclusions': format_currency(combined_exclusions * -1) if combined_exclusions > 0 else '$0.00',
            'combined_net': format_currency(combined_net),
            'cam_inclusion_rules': cam_inclusion_rules,
            'cam_exclusion_rules': cam_exclusion_rules,
            'ret_inclusion_rules': ret_inclusion_rules,
            'ret_exclusion_rules': ret_exclusion_rules,
            'admin_fee_percentage': format_percentage(admin_fee_percentage * Decimal('100') if admin_fee_percentage < Decimal('1') else admin_fee_percentage, 2),
            'admin_fee_exclusion_rules': admin_fee_exclusion_rules,
            'admin_fee_amount': format_currency(admin_fee_amount),
            'base_exclusion_rules': base_exclusion_rules,
            'cap_exclusion_rules': cap_exclusion_rules,
            'total_before_proration': format_currency(total_before_proration),
            'tenant_share_percentage': format_percentage(tenant_share_percentage * Decimal('100') if tenant_share_percentage < Decimal('1') else tenant_share_percentage, 4),
            'tenant_share_amount': format_currency(tenant_share_amount),
            'base_year_impact': format_currency(base_year_impact * -1) if base_year_impact > 0 else '$0.00',
            'cap_impact': format_currency(cap_impact * -1) if cap_impact > 0 else '$0.00',
            'occupancy_factor': f"{float(avg_occupancy):.4f}",
            # For override amount, preserve the sign for proper display
            'override_amount': format_currency(override_impact),
            'override_description': override_desc,
            'final_tenant_amount': format_currency(final_tenant_amount),
            'inclusion_categories': inclusion_categories,
            'exclusion_categories': exclusion_categories
        }

        report_rows.append(row)

        # Update totals
        totals['cam_gross'] = totals.get('cam_gross', Decimal('0')) + cam_gross
        totals['cam_exclusions'] = totals.get('cam_exclusions', Decimal('0')) + cam_exclusions
        totals['cam_net'] = totals.get('cam_net', Decimal('0')) + cam_net
        totals['ret_gross'] = totals.get('ret_gross', Decimal('0')) + ret_gross
        totals['ret_exclusions'] = totals.get('ret_exclusions', Decimal('0')) + ret_exclusions
        totals['ret_net'] = totals.get('ret_net', Decimal('0')) + ret_net
        totals['combined_gross'] = totals.get('combined_gross', Decimal('0')) + combined_gross
        totals['combined_exclusions'] = totals.get('combined_exclusions', Decimal('0')) + combined_exclusions
        totals['combined_net'] = totals.get('combined_net', Decimal('0')) + combined_net
        totals['admin_fee_amount'] = totals.get('admin_fee_amount', Decimal('0')) + admin_fee_amount
        totals['total_before_proration'] = totals.get('total_before_proration', Decimal('0')) + total_before_proration
        totals['tenant_share_amount'] = totals.get('tenant_share_amount', Decimal('0')) + tenant_share_amount
        totals['base_year_impact'] = totals.get('base_year_impact', Decimal('0')) + base_year_impact
        totals['cap_impact'] = totals.get('cap_impact', Decimal('0')) + cap_impact
        
        # For override_amount, we track the sum of the individual override impacts
        # This is just for verification - the final total will be set to the original override amount
        # from custom_overrides.json
        if 'calculated_override_total' not in totals:
            totals['calculated_override_total'] = Decimal('0')
        totals['calculated_override_total'] += override_impact
        
        # We'll set totals['override_amount'] based on the original override amount later
        # (keep this here as a fallback, but it won't be used)
        totals['override_amount'] = totals.get('override_amount', Decimal('0')) + override_impact
        
        totals['final_tenant_amount'] = totals.get('final_tenant_amount', Decimal('0')) + final_tenant_amount

    # Format totals row
    totals['gl_account'] = 'TOTAL'
    totals['description'] = 'Total All GL Accounts'
    totals['cam_gross'] = format_currency(totals['cam_gross'])
    totals['cam_exclusions'] = format_currency(totals['cam_exclusions'] * -1) if totals[
                                                                                     'cam_exclusions'] > 0 else '$0.00'
    totals['cam_net'] = format_currency(totals['cam_net'])
    totals['ret_gross'] = format_currency(totals['ret_gross'])
    totals['ret_exclusions'] = format_currency(totals['ret_exclusions'] * -1) if totals[
                                                                                     'ret_exclusions'] > 0 else '$0.00'
    totals['ret_net'] = format_currency(totals['ret_net'])
    totals['combined_gross'] = format_currency(totals['combined_gross'])
    totals['combined_exclusions'] = format_currency(totals['combined_exclusions'] * -1) if totals[
                                                                                               'combined_exclusions'] > 0 else '$0.00'
    totals['combined_net'] = format_currency(totals['combined_net'])
    totals['admin_fee_percentage'] = format_percentage(admin_fee_percentage * Decimal('100') if admin_fee_percentage < Decimal('1') else admin_fee_percentage, 2)
    totals['admin_fee_amount'] = format_currency(totals['admin_fee_amount'])
    totals['total_before_proration'] = format_currency(totals['total_before_proration'])
    totals['tenant_share_percentage'] = format_percentage(tenant_share_percentage * Decimal('100') if tenant_share_percentage < Decimal('1') else tenant_share_percentage, 4)
    totals['tenant_share_amount'] = format_currency(totals['tenant_share_amount'])
    totals['base_year_impact'] = format_currency(totals['base_year_impact'] * -1) if totals[
                                                                                         'base_year_impact'] > 0 else '$0.00'
    totals['cap_impact'] = format_currency(totals['cap_impact'] * -1) if totals['cap_impact'] > 0 else '$0.00'
    # Ensure totals follow the same column order (occupancy first, then override)
    totals['override_amount'] = format_currency(totals['override_amount'])

    # Set total override description
    if has_override:
        # Get the actual override description from the custom overrides file
        override_info = get_tenant_override(tenant_id, property_id)
        
        # For verification, calculate the sum of all individual override impacts
        calculated_total_override = sum(
            to_decimal(row['override_amount'].replace('$', '').replace(',', '')) 
            for row in report_rows if row.get('override_amount')
        )
        logger.debug(f"Sum of individual override impacts: {calculated_total_override}")
        logger.debug(f"Original override amount: {override_info['override_amount']}")
        
        # The difference should be very small (rounding error only)
        difference = abs(calculated_total_override - override_info['override_amount'])
        if difference > Decimal('0.01'):
            logger.warning(f"Override distribution has a significant discrepancy: {difference}")
        
        if override_info['override_description']:
            totals['override_description'] = override_info['override_description']
            
            # IMPORTANT: There are two approaches here:
            # 1. Set the total to exactly match the original override amount (preferred)
            # 2. Use the sum of the individual override impacts (for verification)
            # We're using approach #1 to ensure the total matches exactly
            totals['override_amount'] = format_currency(override_info['override_amount'])
        else:
            # Fall back to generic description if no description available
            if override_adjustment < 0:
                totals['override_description'] = 'Manual Reduction (Total)'
            else:
                totals['override_description'] = 'Manual Addition (Total)'

    totals['occupancy_factor'] = f"{float(avg_occupancy):.4f}"
    totals['final_tenant_amount'] = format_currency(totals['final_tenant_amount'])
    totals['inclusion_categories'] = 'Multiple'
    totals['exclusion_categories'] = 'Multiple'

    # Add negative balance GL accounts section
    negative_balance_gl_accounts = gl_filtered_data.get('negative_balance_gl_accounts', {})
    if negative_balance_gl_accounts:
        # Add separator row
        separator_row = {col: '' for col in columns}
        separator_row['gl_account'] = '--- NEGATIVE BALANCE ACCOUNTS (EXCLUDED) ---'
        separator_row['description'] = 'These included GL accounts were excluded from calculations due to negative total balances'
        report_rows.append(separator_row)
        
        # Add each negative balance GL account
        for gl_account, detail in sorted(negative_balance_gl_accounts.items()):
            neg_row = {col: '' for col in columns}
            neg_row['gl_account'] = gl_account
            neg_row['description'] = detail['description']
            neg_row['combined_gross'] = format_currency(detail['total_amount'])
            neg_row['combined_net'] = format_currency(detail['total_amount'])
            included_cats = detail.get('included_in_categories', [])
            neg_row['inclusion_categories'] = ', '.join(included_cats) if included_cats else 'Unknown'
            neg_row['exclusion_categories'] = 'NEGATIVE BALANCE'
            neg_row['final_tenant_amount'] = '$0.00'
            report_rows.append(neg_row)

    # Add capital expenses row if applicable
    capital_expenses_total = tenant_result['capital_expenses_result']['total_capital_expenses']
    tenant_share_percentage = tenant_result['tenant_share_percentage']
    if capital_expenses_total > 0:
        capital_row = {col: '' for col in columns}
        capital_row['gl_account'] = 'CAPITAL'
        capital_row['description'] = 'Amortized Capital Expenses'
        capital_row['tenant_share_amount'] = format_currency(capital_expenses_total * tenant_share_percentage)
        capital_row['occupancy_factor'] = f"{float(avg_occupancy):.4f}"

        # Calculate capital expenses with consistent rounding to match property report
        capital_share = capital_expenses_total * tenant_share_percentage
        capital_final_amount = (capital_share * avg_occupancy).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

        capital_row['override_amount'] = "$0.00"
        capital_row['override_description'] = ""

        capital_row['final_tenant_amount'] = format_currency(capital_final_amount)
        report_rows.append(capital_row)

        # Update final totals
        totals['final_tenant_amount'] = format_currency(
            to_decimal(totals['final_tenant_amount'].replace('$', '')) + capital_final_amount)

    # Remove calculation-only fields before writing the CSV
    # These fields are used for internal calculations but shouldn't be in the final output
    calculation_fields = ['calculated_override_total', 'total_tenant_share_for_override', 'total_tenant_share_calculated']
    for field in calculation_fields:
        if field in totals:
            del totals[field]
    
    # Write CSV File
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        for row in report_rows:
            writer.writerow(row)
        writer.writerow(totals)
        
        # Add formula explanation row
        formula_row = {col: get_formula_for_field(col, totals) for col in columns}
        formula_row[columns[0]] = "FORMULA EXPLANATIONS:"  # Mark the first column
        writer.writerow(formula_row)

    return output_path


def get_formula_for_field(field: str, data: Dict) -> str:
    """
    Returns a plain English description of the formula used for the field.
    This provides transparency about how values were derived.
    """
    # Define common formula patterns
    if field.endswith('_net_total') and field.replace('_net_total', '_gross_total') in data and field.replace('_net_total', '_exclusions') in data:
        category = field.replace('_net_total', '')
        return f"{category} gross total minus {category} exclusions (eligible GL accounts minus excluded GL accounts)"
    
    elif field.endswith('_tenant_share') and 'share_percentage' in data:
        # For tenant share calculations
        base = field.replace('_tenant_share', '')
        return f"{base} net total multiplied by tenant's share percentage ({data.get('share_percentage', '')})"
    
    elif field.endswith('_final_amount') and field.replace('_final_amount', '_subtotal') in data:
        # For fields that have cap or other adjustments
        base = field.replace('_final_amount', '')
        adjustment = field.replace('_final_amount', '_adjustment')
        if adjustment in data:
            return f"{base} subtotal plus/minus {base} adjustments (such as overrides, caps, or other corrections)"
        else:
            return f"{base} subtotal amount (no adjustments applied)"
    
    # Admin fee calculations
    elif field == 'admin_fee_gross':
        return "CAM net × admin fee percentage (before admin-specific exclusions)"
    
    elif field == 'admin_fee_net':
        return "Admin fee eligible CAM net × admin fee percentage (after admin-specific exclusions)"
    
    elif field == 'admin_fee_exclusions':
        return "Admin fee gross - admin fee net (impact of admin-fee-specific exclusions)"
    
    elif field == 'admin_fee_base_amount':
        return "Admin fee eligible CAM net + capital expenses (base after all exclusions)"
    
    elif field == 'capital_expenses_in_admin':
        return "Capital expenses amount included in admin fee base calculation"
        
    elif field == 'combined_net_total':
        return "Combined gross total minus all exclusions (sum of CAM, RET, and other categories after exclusions)"
        
    elif field == 'combined_gross_total':
        return "Sum of all category gross totals (CAM + RET + other categories before exclusions)"
        
    elif field == 'combined_exclusions':
        return "Sum of all category exclusions (excluded GL accounts from CAM, RET, and other categories)"
        
    elif field == 'after_cap_adjustment':
        return "Amount after applying any applicable cap limits (final amount subject to cap if cap applies, or original amount if no cap)"
        
    elif field == 'subtotal_after_tenant_share':
        return "Tenant's share of expenses plus tenant's share of capital expenses (combined total the tenant is responsible for)"
        
    elif field == 'occupancy_adjusted_amount':
        return "Expense subtotal multiplied by tenant's occupancy factor (adjusts for partial occupancy periods)"
        
    elif field == 'final_billing':
        return "Base billing plus any manual override adjustments (final amount billed to tenant)"
        
    elif field == 'total_balance':
        return "Reconciliation balance plus catchup balance (total amount due combining current year and catch-up period)"
        
    elif field == 'reconciliation_balance':
        return "Reconciliation expected minus reconciliation paid (difference between expected and actual payments)"
    
    elif field == 'admin_fee_percentage':
        return "Admin fee percentage from lease terms (management fee percentage applied to eligible expenses)"
        
    elif field == 'cam_gross_total':
        return "Sum of all CAM expenses from GL accounts (before applying exclusions)"
        
    elif field == 'cam_exclusions':
        return "Sum of all excluded CAM expenses (GL accounts specifically excluded from CAM category)"
        
    elif field == 'ret_gross_total':
        return "Sum of all RET (Real Estate Tax) expenses from GL accounts (before applying exclusions)"
        
    elif field == 'ret_exclusions':
        return "Sum of all excluded RET expenses (GL accounts specifically excluded from RET category)"
    
    # Default case: no formula description available
    return "Direct value"


def generate_csv_report(
        report_rows: List[Dict[str, Any]],
        property_id: str,
        recon_year: int,
        categories: List[str] = ['cam', 'ret']
) -> str:
    """Generate a detailed CSV report with enhanced calculation transparency."""
    # Create output directory if it doesn't exist
    os.makedirs(REPORTS_PATH, exist_ok=True)

    # Create filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    category_str = "_".join(categories)
    output_path = os.path.join(REPORTS_PATH,
                               f"tenant_billing_{property_id}_{category_str}_{recon_year}_{timestamp}.csv")

    # Define columns for the report - enhanced with calculation detail columns
    columns = [
        # Basic tenant information
        'tenant_id', 'tenant_name', 'property_id', 'property_name', 'property_full_name', 'suite',
        'lease_start', 'lease_end', 'share_method', 'share_percentage',

        # Property totals
        'property_gl_total',

        # CAM breakdown (gross, exclusions, net)
        'cam_gross_total', 'cam_exclusions', 'cam_net_total',

        # RET breakdown (gross, exclusions, net)
        'ret_gross_total', 'ret_exclusions', 'ret_net_total',

        # Admin fee breakdown
        'admin_fee_percentage', 'admin_fee_gross', 'admin_fee_exclusions', 'admin_fee_net',
        'admin_fee_base_amount', 'capital_expenses_in_admin',

        # Combined totals
        'combined_gross_total', 'combined_exclusions', 'combined_net_total',

        # Base year details
        'base_year', 'base_year_amount',
        'total_before_base_adjustment', 'base_year_adjustment', 'after_base_adjustment',
        'base_year_applied',

        # Cap details
        'cap_applies', 'cap_type', 'cap_reference_amount', 'cap_percentage',
        'cap_limit', 'cap_eligible_amount', 'cap_deduction',
        'after_cap_adjustment',
        'cap_applied',

        # Property total before tenant prorations
        'property_total_before_prorations',

        # Capital expenses
        'capital_expenses_total',

        # Tenant share calculation (first proration)
        'tenant_share_amount', 'tenant_capital_expenses', 'subtotal_after_tenant_share',

        # Occupancy adjustment (second proration)
        'average_occupancy', 'occupied_months', 'full_months', 'partial_months',
        'subtotal_before_occupancy_adjustment', 'occupancy_adjusted_amount',

        # Final amounts
        'base_billing', 'override_amount', 'override_adjustment', 'override_description', 'final_billing',
        'has_override',

        # Payment tracking
        'old_monthly', 'new_monthly', 'new_monthly_excludes_override', 'monthly_difference',
        'percentage_change', 'change_type', 'is_significant',

        # Enhanced payment tracking and balance calculation
        'reconciliation_periods', 'reconciliation_expected', 'reconciliation_paid',
        'reconciliation_balance',
        'catchup_periods', 'catchup_monthly', 'catchup_expected', 'catchup_paid',
        'catchup_balance',
        'total_balance',
        'has_catchup_period',

        # Period dates
        'reconciliation_start_date', 'reconciliation_end_date',
        'catchup_start_date', 'catchup_end_date',

        # Effective dates
        'letter_generation_date', 'monthly_charge_effective_date', 'payment_due_date',

        # Amortization summary
        'amortization_exists', 'amortization_total_amount', 'amortization_items_count',
    ]
    
    # Define a template for amortization fields that we'll use dynamically
    # Instead of hardcoding 5 items, we'll add them based on actual data
    amortization_fields = [
        'description',
        'total_amount',
        'years',
        'annual_amount',
        'your_share'
    ]

    # First, determine the maximum number of amortization items across all rows
    max_amortization_items = 0
    for row in report_rows:
        # Get count from row or use expense count if available directly
        item_count = int(row.get('amortization_items_count', '0') or '0')
        max_amortization_items = max(max_amortization_items, item_count)
    
    # Dynamically add amortization item columns based on actual data
    dynamic_columns = columns.copy()
    for i in range(1, max_amortization_items + 1):
        for field in amortization_fields:
            dynamic_columns.append(f'amortization_{i}_{field}')
    
    # Write the CSV file
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=dynamic_columns)
            writer.writeheader()

            for row in report_rows:
                # Filter the row to include only the defined columns
                filtered_row = {col: row.get(col, '') for col in dynamic_columns}
                writer.writerow(filtered_row)
                
            # Add formula explanation row at the bottom
            if report_rows:
                formula_row = {col: get_formula_for_field(col, report_rows[-1]) for col in dynamic_columns}
                formula_row[dynamic_columns[0]] = "FORMULA EXPLANATIONS:"  # Mark the first column
                writer.writerow(formula_row)

        logger.info(f"Generated enhanced CSV report with {len(report_rows)} rows: {output_path}")
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

    # JSON encoder class to handle Decimal, Set and Date objects
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, set):
                return list(obj)  # Convert sets to lists for JSON serialization
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()  # Convert dates to ISO format string
            # Let the base class default method handle other types
            return super().default(obj)

    # Create a clean copy of the data for serialization
    def prepare_for_serialization(data):
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, set):
            return list(data)
        elif isinstance(data, (datetime.date, datetime.datetime)):
            return data.isoformat()  # Convert dates to ISO format string
        elif isinstance(data, dict):
            return {k: prepare_for_serialization(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [prepare_for_serialization(item) for item in data]
        elif hasattr(data, '__dict__'):
            return prepare_for_serialization(data.__dict__)
        else:
            return data

    # Apply the conversion to make the results JSON serializable
    serializable_results = prepare_for_serialization(billing_results)

    # Write the JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, cls=CustomEncoder)

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
    Calculate CAM reconciliation for a single tenant with a linear flow and detailed reporting.
    """
    logger.info(f"===== Starting reconciliation for tenant {tenant_id} in property {property_id} =====")
    logger.info(f"Categories: {categories}, Year: {recon_year}")

    # STEP 1: Load all settings with inheritance
    settings = merge_settings(property_id, tenant_id)
    property_settings = merge_settings(property_id)  # For property-level calculations

    # STEP 2: Load and filter GL data
    gl_data = load_gl_data(property_id)
    recon_periods = periods_dict['recon_periods']
    catchup_periods = periods_dict['catchup_periods']

    # Enhanced filtering with detailed tracking
    gl_filtered_data = filter_gl_accounts_with_detail(gl_data, settings, recon_periods, categories, catchup_periods)

    # STEP 3: Calculate tenant share percentage first (needed for capital expenses)
    tenant_share_percentage = calculate_tenant_share_percentage(settings, property_settings)

    # STEP 4: Calculate capital expenses first (needed for admin fee calculation)
    property_capital_result = calculate_capital_expenses(settings, recon_year, recon_periods, tenant_share_percentage)
    property_capital_expenses = property_capital_result['total_property_expenses']  # Use property-level total
    tenant_capital_expenses = property_capital_result['total_capital_expenses']  # Use tenant's share
    
    # DEBUG: Log to verify capital expense values
    logger.info(f"Capital Expense Debug for tenant {tenant_id}:")
    logger.info(f"  Property Capital Expenses: {float(property_capital_expenses):.2f}")
    logger.info(f"  Tenant Capital Expenses: {float(tenant_capital_expenses):.2f}")
    logger.info(f"  Tenant Share Percentage: {float(tenant_share_percentage):.4f}")
    expected_tenant_capital = property_capital_expenses * tenant_share_percentage
    logger.info(f"  Expected Tenant Capital: {float(expected_tenant_capital):.2f}")
    
    # Verify the calculation is correct
    if abs(tenant_capital_expenses - expected_tenant_capital) > Decimal('0.01'):
        logger.warning(f"Tenant capital expenses mismatch!")
        logger.warning(f"  Calculated: {float(tenant_capital_expenses):.2f}")
        logger.warning(f"  Expected: {float(expected_tenant_capital):.2f}")

    # STEP 5: Calculate CAM, TAX, admin fee - PROPERTY LEVEL with capital expenses
    property_cam_tax_admin = calculate_cam_tax_admin(gl_filtered_data, property_settings, categories, capital_expenses_amount=property_capital_expenses)

    # STEP 6: Calculate CAM, TAX, admin fee - TENANT SPECIFIC with capital expenses
    tenant_cam_tax_admin = calculate_cam_tax_admin(gl_filtered_data, settings, categories, capital_expenses_amount=tenant_capital_expenses)

    # STEP 7: Apply base year adjustment
    base_year_result = calculate_base_year_adjustment(
        recon_year,
        tenant_cam_tax_admin['base_net_total'],  # This already accounts for admin fee inclusion
        settings
    )

    # Store the amount before and after base year adjustment
    before_base_amount = tenant_cam_tax_admin['base_net_total']
    base_year_adjustment = base_year_result['base_year_adjustment']
    after_base_amount = base_year_result['after_base_adjustment']

    # STEP 8: Calculate cap-eligible amount
    cap_eligible_amount = determine_cap_eligible_amount(gl_filtered_data, tenant_cam_tax_admin)

    # STEP 9: Apply cap limits and calculate deduction
    cap_history = load_cap_history()

    cap_result = calculate_cap_deduction(
        tenant_id,
        recon_year,
        cap_eligible_amount,
        settings,
        cap_history
    )

    # Calculate the amount after cap adjustment (apply cap deduction)
    after_cap_amount = after_base_amount - cap_result['cap_deduction']
    logger.info(f"Amount after cap adjustment: {float(after_cap_amount):.2f}")

    # STEP 10: Calculate property-level total after all adjustments  
    property_total_after_adjustments = after_cap_amount + property_capital_expenses
    tenant_share = calculate_tenant_share(after_cap_amount, tenant_share_percentage)

    # Calculate subtotal after tenant share calculation
    subtotal_after_tenant_share = tenant_share + tenant_capital_expenses

    # STEP 11: Apply occupancy adjustment (PRORATION STEP)
    occupancy_factors = calculate_occupancy_factors(
        recon_periods,
        settings.get('lease_start'),
        settings.get('lease_end')
    )

    # Calculate average occupancy for reporting
    avg_occupancy = Decimal('1')
    if occupancy_factors:
        avg_occupancy = sum(occupancy_factors.values()) / len(occupancy_factors)

    # Apply occupancy adjustment
    occupancy_adjusted_amount = apply_occupancy_adjustment(subtotal_after_tenant_share, occupancy_factors)

    # STEP 12: Apply any tenant override
    # IMPORTANT: The override amount is used exactly as it appears in custom_overrides.json
    # with no scaling or adjustments based on the description or reconciliation periods
    override_info = get_tenant_override(tenant_id, property_id)
    override_amount = override_info['override_amount']  # Use the raw value directly

    # Calculate base billing (before override)
    base_billing = occupancy_adjusted_amount

    # Calculate final billing (with override if applicable)
    final_billing = base_billing
    if override_amount != 0:
        logger.info(f"Applying override amount: {float(override_amount):.2f} as an addition to the billing")
        final_billing = base_billing + override_amount

    # STEP 13: Update cap history unless skipped
    if not skip_cap_update:
        # Update with eligible amount (not final billing)
        # This is the correct approach for cap history
        cap_history = update_cap_history(tenant_id, recon_year, cap_eligible_amount)

    # STEP 14: Calculate payment tracking information
    old_monthly = get_old_monthly_payment(tenant_id, property_id)
    recon_period_count = len(recon_periods)

    # Calculate new monthly without the override amount
    new_monthly = calculate_new_monthly_payment(base_billing, recon_period_count)
    payment_change = calculate_payment_change(old_monthly, new_monthly)

    # STEP 15: ENHANCED PAYMENT TRACKING - Calculate actual payments and balances
    # Define relevant income categories for CAM charges
    # You may need to adjust these based on your data structure
    cam_income_categories = ['CAM', 'OPX', 'EXP', 'RNT', 'PRK']  # Example categories

    # Get tenant payments for reconciliation year
    recon_payments = get_tenant_payments(tenant_id, property_id, recon_periods, cam_income_categories)
    recon_paid = recon_payments['total']

    # Calculate reconciliation year balance
    recon_balance = final_billing - recon_paid
    logger.info(
        f"Reconciliation year balance: {float(final_billing):.2f} - {float(recon_paid):.2f} = {float(recon_balance):.2f}")

    # Calculate monthly amount from reconciliation for catch-up (without override)
    monthly_amount = Decimal('0')
    if recon_periods:
        monthly_amount = base_billing / Decimal(len(recon_periods))

    # Calculate expected catch-up payment
    catchup_expected = Decimal('0')
    if catchup_periods:
        catchup_expected = monthly_amount * Decimal(len(catchup_periods))
        logger.info(
            f"Catch-up expected: {float(monthly_amount):.2f} × {len(catchup_periods)} = {float(catchup_expected):.2f}")

    # Get actual catch-up payments
    catchup_paid = Decimal('0')
    catchup_payment_data = None
    if catchup_periods:
        catchup_payment_data = get_tenant_payments(tenant_id, property_id, catchup_periods, cam_income_categories)
        catchup_paid = catchup_payment_data['total']
        logger.info(f"Catch-up paid: {float(catchup_paid):.2f}")

    # Calculate catch-up balance
    catchup_balance = catchup_expected - catchup_paid
    logger.info(
        f"Catch-up balance: {float(catchup_expected):.2f} - {float(catchup_paid):.2f} = {float(catchup_balance):.2f}")

    # Calculate total balance
    total_balance = recon_balance + catchup_balance
    logger.info(
        f"Total balance: {float(recon_balance):.2f} + {float(catchup_balance):.2f} = {float(total_balance):.2f}")

    # STEP 16: Calculate period dates
    recon_start_date = None
    recon_end_date = None
    if recon_periods:
        first_period_info = get_period_info(recon_periods[0])
        last_period_info = get_period_info(recon_periods[-1])
        if first_period_info['valid']:
            recon_start_date = first_period_info['first_day']
        if last_period_info['valid']:
            recon_end_date = last_period_info['last_day']

    catchup_start_date = None
    catchup_end_date = None
    if catchup_periods:
        first_catchup_info = get_period_info(catchup_periods[0])
        last_catchup_info = get_period_info(catchup_periods[-1])
        if first_catchup_info['valid']:
            catchup_start_date = first_catchup_info['first_day']
        if last_catchup_info['valid']:
            catchup_end_date = last_catchup_info['last_day']

    # STEP 17: Calculate effective dates
    current_date = datetime.date.today()
    letter_generation_date = current_date

    # Monthly charge effective date - typically first of next month
    if current_date.month == 12:
        monthly_charge_effective_date = datetime.date(current_date.year + 1, 1, 1)
    else:
        monthly_charge_effective_date = datetime.date(current_date.year, current_date.month + 1, 1)

    # Payment due date - typically 30 days from letter generation
    payment_due_date = current_date + datetime.timedelta(days=30)

    # STEP 18: Get property full name from Properties.json
    property_name_mapping = load_property_name_mapping()
    property_full_name = property_name_mapping.get(property_id.upper(), property_settings.get('name', property_id))

    # STEP 19: Create a detailed report row with enhanced fields
    share_method = settings.get('settings', {}).get('prorate_share_method', 'RSF')

    # Count full/partial months
    occupied_months = sum(1 for f in occupancy_factors.values() if f > 0)
    full_months = sum(1 for f in occupancy_factors.values() if f >= Decimal('1'))
    partial_months = sum(1 for f in occupancy_factors.values() if Decimal('0') < f < Decimal('1'))

    # Format enhanced report row with detailed calculation steps
    report_row = {
        # Basic tenant information
        'tenant_id': tenant_id,
        'tenant_name': settings.get('tenant_name', ''),
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'property_full_name': property_full_name,
        'suite': settings.get('suite', ''),
        'lease_start': settings.get('lease_start', ''),
        'lease_end': settings.get('lease_end', ''),

        # Share method information
        'share_method': share_method,
        'share_percentage': format_percentage(tenant_share_percentage * Decimal('100') if tenant_share_percentage < Decimal('1') else tenant_share_percentage, 4),

        # Property gross total
        'property_gl_total': format_currency(property_cam_tax_admin['combined_gross_total']),

        # CAM breakdown (gross, exclusions, net)
        'cam_gross_total': format_currency(tenant_cam_tax_admin['cam_gross']),
        'cam_exclusions': format_currency(tenant_cam_tax_admin['cam_exclusions']),
        'cam_net_total': format_currency(tenant_cam_tax_admin['cam_net']),

        # RET breakdown (gross, exclusions, net)
        'ret_gross_total': format_currency(tenant_cam_tax_admin['ret_gross']),
        'ret_exclusions': format_currency(tenant_cam_tax_admin['ret_exclusions']),
        'ret_net_total': format_currency(tenant_cam_tax_admin['ret_net']),

        # Admin fee breakdown - showing tenant's prorated share
        'admin_fee_percentage': format_percentage(tenant_cam_tax_admin['admin_fee_percentage'] * Decimal('100') if tenant_cam_tax_admin['admin_fee_percentage'] < Decimal('1') else tenant_cam_tax_admin['admin_fee_percentage'], 2),
        'admin_fee_gross': format_currency(tenant_cam_tax_admin['admin_fee_gross'] * tenant_share_percentage),
        'admin_fee_exclusions': format_currency(tenant_cam_tax_admin['admin_fee_exclusions'] * tenant_share_percentage),
        'admin_fee_net': format_currency(tenant_cam_tax_admin['admin_fee_net'] * tenant_share_percentage),
        'admin_fee_base_amount': format_currency(tenant_cam_tax_admin.get('admin_fee_base_amount', Decimal('0')) * tenant_share_percentage),
        'capital_expenses_in_admin': format_currency(tenant_cam_tax_admin.get('capital_expenses_in_admin', Decimal('0')) * tenant_share_percentage),

        # Combined totals
        'combined_gross_total': format_currency(tenant_cam_tax_admin['combined_gross_total']),
        'combined_exclusions': format_currency(tenant_cam_tax_admin['combined_exclusions']),
        'combined_net_total': format_currency(tenant_cam_tax_admin['combined_net_total']),

        # Base year details
        'base_year': base_year_result['base_year'],
        'base_year_amount': format_currency(base_year_result['base_year_amount']),
        'total_before_base_adjustment': format_currency(before_base_amount),
        'base_year_adjustment': format_currency(base_year_adjustment),
        'after_base_adjustment': format_currency(after_base_amount),
        'base_year_applied': 'true' if base_year_result['base_year_has_effect'] else 'false',

        # Cap details
        'cap_applies': 'Yes' if cap_result['cap_applies'] else 'No',
        'cap_type': settings.get('settings', {}).get('cap_settings', {}).get('cap_type', 'previous_year'),
        'cap_reference_amount': format_currency(
            cap_result.get('cap_limit_results', {}).get('reference_amount', Decimal('0'))),
        'cap_percentage': format_percentage(
            to_decimal(settings.get('settings', {}).get('cap_settings', {}).get('cap_percentage', '0')),
            2),
        'cap_limit': format_currency(cap_result['cap_limit']),
        'cap_eligible_amount': format_currency(cap_result['cap_eligible_amount']),
        'cap_deduction': format_currency(cap_result['cap_deduction']),
        'after_cap_adjustment': format_currency(after_cap_amount),
        'cap_applied': 'true' if cap_result['cap_has_effect'] else 'false',

        # Property total before tenant prorations
        'property_total_before_prorations': format_currency(property_total_after_adjustments),

        # Capital expenses
        'capital_expenses_total': format_currency(property_capital_expenses),

        # Tenant share calculation (first proration)
        'tenant_share_amount': format_currency(tenant_share),
        'tenant_capital_expenses': format_currency(tenant_capital_expenses),
        'subtotal_after_tenant_share': format_currency(subtotal_after_tenant_share),

        # Occupancy adjustment (second proration)
        'average_occupancy': f"{float(avg_occupancy):.4f}",
        'occupied_months': occupied_months,
        'full_months': full_months,
        'partial_months': partial_months,
        'subtotal_before_occupancy_adjustment': format_currency(subtotal_after_tenant_share),
        'occupancy_adjusted_amount': format_currency(occupancy_adjusted_amount),

        # Final amounts
        'base_billing': format_currency(base_billing),
        'override_amount': format_currency(override_amount),
        'override_adjustment': 'Yes' if override_amount != 0 else 'No',
        'override_description': override_info['override_description'] if override_amount != 0 else '',
        'final_billing': format_currency(final_billing),
        'has_override': 'true' if override_amount != 0 else 'false',

        # Payment tracking
        'old_monthly': format_currency(old_monthly),
        'new_monthly': format_currency(new_monthly),
        'new_monthly_excludes_override': 'Yes',
        'monthly_difference': format_currency(payment_change['difference']),
        'percentage_change': format_percentage(payment_change['percentage_change'], 1),
        'change_type': payment_change['change_type'],
        'is_significant': 'Yes' if payment_change['is_significant'] else 'No',

        # ENHANCED - Payment and balance tracking fields
        'reconciliation_periods': len(recon_periods),
        'reconciliation_expected': format_currency(final_billing),
        'reconciliation_paid': format_currency(recon_paid),
        'reconciliation_balance': format_currency(recon_balance),

        'catchup_periods': len(catchup_periods) if catchup_periods else 0,
        'catchup_monthly': format_currency(monthly_amount),
        'catchup_expected': format_currency(catchup_expected),
        'catchup_paid': format_currency(catchup_paid),
        'catchup_balance': format_currency(catchup_balance),

        'total_balance': format_currency(total_balance),
        'has_catchup_period': 'true' if catchup_periods else 'false',

        # Period dates
        'reconciliation_start_date': recon_start_date.strftime('%Y-%m-%d') if recon_start_date else '',
        'reconciliation_end_date': recon_end_date.strftime('%Y-%m-%d') if recon_end_date else '',
        'catchup_start_date': catchup_start_date.strftime('%Y-%m-%d') if catchup_start_date else '',
        'catchup_end_date': catchup_end_date.strftime('%Y-%m-%d') if catchup_end_date else '',

        # Effective dates
        'letter_generation_date': letter_generation_date.strftime('%Y-%m-%d'),
        'monthly_charge_effective_date': monthly_charge_effective_date.strftime('%Y-%m-%d'),
        'payment_due_date': payment_due_date.strftime('%Y-%m-%d'),

        # Amortization summary
        'amortization_exists': 'true' if property_capital_result['has_amortization'] else 'false',
        'amortization_total_amount': format_currency(property_capital_result['total_property_expenses']),
        'amortization_items_count': str(property_capital_result['expense_count']),
    }

    # Add all amortization items dynamically (no arbitrary limit)
    for i, expense in enumerate(property_capital_result['capital_expenses'], 1):
        tenant_share_of_expense = expense.get('tenant_annual_share', Decimal('0'))
        report_row.update({
            f'amortization_{i}_description': expense.get('description', ''),
            f'amortization_{i}_total_amount': format_currency(expense.get('total_cost', 0)),
            f'amortization_{i}_years': str(expense.get('amortization_years', 0)),
            f'amortization_{i}_annual_amount': format_currency(expense.get('annual_amount', 0)),
            f'amortization_{i}_your_share': format_currency(tenant_share_of_expense)
        })

    # Return comprehensive results
    return {
        'tenant_id': tenant_id,
        'tenant_name': settings.get('tenant_name', ''),
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'recon_year': recon_year,
        'categories': categories,
        'periods': periods_dict,

        # Detailed calculation components
        'gl_filtered_data': gl_filtered_data,
        'property_cam_tax_admin': property_cam_tax_admin,
        'tenant_cam_tax_admin': tenant_cam_tax_admin,
        'base_year_result': base_year_result,
        'cap_result': cap_result,
        'capital_expenses_result': property_capital_result,
        'tenant_share_percentage': tenant_share_percentage,
        'tenant_share_amount': tenant_share,
        'property_total_after_adjustments': property_total_after_adjustments,
        'subtotal_after_tenant_share': subtotal_after_tenant_share,
        'subtotal_before_occupancy_adjustment': subtotal_after_tenant_share,
        'occupancy_factors': occupancy_factors,
        'average_occupancy': avg_occupancy,
        'occupancy_adjusted_amount': occupancy_adjusted_amount,
        'override_info': override_info,
        'override_adjustment': override_amount,
        'override_amount': override_amount,

        # Final amounts and payment tracking
        'base_billing': base_billing,
        'override_applied_as_adjustment': override_amount != 0,
        'final_billing': final_billing,
        'old_monthly': old_monthly,
        'new_monthly': new_monthly,
        'new_monthly_excludes_override': True,
        'payment_change': payment_change,

        # ENHANCED - Payment and balance tracking
        'payment_tracking': {
            'recon_paid': recon_paid,
            'recon_balance': recon_balance,
            'catchup_expected': catchup_expected,
            'catchup_paid': catchup_paid,
            'catchup_balance': catchup_balance,
            'total_balance': total_balance,
            'recon_payments_detail': recon_payments,
            'catchup_payments_detail': catchup_payment_data if catchup_periods else None
        },

        # Period information
        'period_dates': {
            'reconciliation_start': recon_start_date,
            'reconciliation_end': recon_end_date,
            'catchup_start': catchup_start_date,
            'catchup_end': catchup_end_date
        },

        # Effective dates
        'effective_dates': {
            'letter_generation': letter_generation_date,
            'monthly_charge_effective': monthly_charge_effective_date,
            'payment_due': payment_due_date
        },

        # Enhanced report row for CSV export
        'report_row': report_row
    }


def process_property_reconciliation(
        property_id: str,
        recon_year: int,
        last_bill: Optional[str] = None,
        tenant_id: Optional[str] = None,
        categories: List[str] = ['cam', 'ret'],
        skip_cap_update: bool = False,
        generate_letters: bool = True,
        auto_combine_pdf: bool = True
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
    gl_detail_reports = []

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

        # Generate GL detail report for each tenant
        gl_detail_path = generate_gl_detail_report(result, property_id, recon_year)
        if gl_detail_path:
            gl_detail_reports.append(gl_detail_path)

    # Generate reports
    csv_report_path = generate_csv_report(report_rows, property_id, recon_year, categories)
    json_report_path = generate_json_report(tenant_results, property_id, recon_year, categories)

    # Store results
    results = {
        'property_id': property_id,
        'recon_year': recon_year,
        'categories': categories,
        'periods': periods,
        'tenant_count': len(tenant_results),
        'tenant_results': tenant_results,
        'csv_report_path': csv_report_path,
        'json_report_path': json_report_path,
        'gl_detail_reports': gl_detail_reports,
        'gl_dir': os.path.join(GL_DETAILS_PATH, f"{property_id}_{recon_year}")  # Pass directory containing GL detail CSVs
    }
    
    # Always generate letters unless explicitly skipped
    if generate_letters and generate_letters_from_results is not None:
        try:
            # Add auto_combine_pdf flag to ensure combined PDF is created
            if auto_combine_pdf:
                results['auto_combine_pdf'] = True
            
            # Generate letters directly from the results
            letter_success, letter_total = generate_letters_from_results(results)
            
            # Add letter generation results to the return value
            results['letter_generation'] = {
                'successful': letter_success,
                'total': letter_total
            }
            
            print(f"Letter generation complete: {letter_success} of {letter_total} letters generated")
        except Exception as e:
            print(f"Error generating letters: {str(e)}")
    
    return results


# ========== MAIN FUNCTION ==========

def main():
    """Main entry point for the reconciliation process."""
    parser = argparse.ArgumentParser(description='Enhanced CAM Reconciliation Calculator')

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
    parser.add_argument(
        '--skip_letters',
        action='store_true',
        help='Skip generating tenant letters'
    )
    parser.add_argument(
        '--auto_combine_pdf',
        action='store_true',
        help='Automatically combine generated letters into a single PDF',
        default=True
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
            args.skip_cap_update,
            generate_letters=not args.skip_letters,  # Generate letters by default
            auto_combine_pdf=args.auto_combine_pdf  # Pass the auto_combine_pdf flag
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
        print(f"- CSV Summary: {results['csv_report_path']}")
        print(f"- JSON Detail: {results['json_report_path']}")

        if results.get('gl_detail_reports'):
            print(f"- GL Detail Reports: {len(results['gl_detail_reports'])} generated")
            for report in results['gl_detail_reports'][:3]:  # Show first 3 for brevity
                print(f"  > {report}")
            if len(results['gl_detail_reports']) > 3:
                print(f"  ... and {len(results['gl_detail_reports']) - 3} more")

        print("=" * 80 + "\n")

        return 0  # Success

    except Exception as e:
        logger.exception(f"Error during reconciliation: {str(e)}")
        print(f"\nERROR: {str(e)}")
        return 1  # Error


if __name__ == "__main__":
    sys.exit(main())