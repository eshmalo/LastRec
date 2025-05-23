#!/usr/bin/env python3
"""
CAM Reconciliation Letter Generator

This module provides letter generation functionality for CAM reconciliation results.
It's designed to be imported by New Full.py to automatically generate letters after reconciliation.
"""

import os
import csv
import re
import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# ========== CONFIGURATION ==========

# Output directory structure
LETTERS_DIR = Path("Letters")

# Property name mapping
PROPERTY_NAMES = {
    "WAT": "Watchung",
    "CTR": "Plainview Center",
    "BOO": "Cinemark Boonton",
    "HYL": "Hylan Plaza",
    "ELW": "East Northport",
    "UKA": "Union City"
}

# Contact information for footer
CONTACT_INFO = "For questions, please contact Evelyn Diaz at (201) 871-8800 x210 or ediaz@treecocenters.com"

# ========== UTILITY FUNCTIONS ==========

def format_currency(amount: Any, include_dollar_sign: bool = True) -> str:
    """Format value as currency with $ sign and commas."""
    try:
        # Convert to float to handle various input types
        value = float(amount)
        if include_dollar_sign:
            return f"${value:,.2f}"
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        if include_dollar_sign:
            return "$0.00"
        return "0.00"


def format_percentage(value: Any, precision: int = 2) -> str:
    """Format value as percentage with specified precision."""
    try:
        # Convert to float and handle percentage conversion
        value = float(value)
        # If value is already in decimal form (e.g. 0.0514 for 5.14%)
        if value < 1:
            value = value * 100
        return f"{value:.{precision}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in text."""
    if not text:
        return ""
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}'
    }
    return ''.join(replacements.get(c, c) for c in str(text))


def format_date_range(start_date: str, end_date: str) -> str:
    """Format date range (e.g., Jan-Dec 2024)."""
    if not start_date or not end_date:
        return ""
    
    try:
        # Try to parse dates in YYYY-MM-DD format
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        
        # Get month abbreviations
        start_month = start.strftime("%b")
        end_month = end.strftime("%b")
        
        # If range is full year
        if (start.month == 1 and start.day == 1 and 
            end.month == 12 and end.day == 31 and 
            start.year == end.year):
            return f"Jan-Dec {start.year}"
        
        # If same year but not full year
        if start.year == end.year:
            return f"{start_month}-{end_month} {start.year}"
        
        # Different years
        return f"{start_month} {start.year}-{end_month} {end.year}"
    except ValueError:
        # Fallback to original strings
        return f"{start_date} to {end_date}"


def extract_year_from_date(date_str: str) -> str:
    """Extract year from date string."""
    if not date_str:
        return ""
    
    # Try to parse YYYY-MM-DD
    match = re.search(r'(\d{4})-\d{2}-\d{2}', date_str)
    if match:
        return match.group(1)
    
    # Check if year is already in string
    year_match = re.search(r'\b(20\d{2})\b', date_str)
    if year_match:
        return year_match.group(1)
    
    return ""

# ========== DATA READING FUNCTIONS ==========

def read_csv_file(file_path: str) -> List[Dict[str, str]]:
    """Read a CSV file and return a list of dictionaries."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading CSV file {file_path}: {str(e)}")
        return []


def get_gl_details_for_tenant(gl_detail_file: str) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """Read GL details from a specific GL detail file."""
    try:
        gl_details = read_csv_file(gl_detail_file)
        # Filter to remove the TOTAL row for processing individual rows
        tenant_gl_details = [row for row in gl_details if row.get('gl_account') != 'TOTAL']
        
        # Separately get the TOTAL row
        total_row = next((row for row in gl_details if row.get('gl_account') == 'TOTAL'), {})
        
        return tenant_gl_details, total_row
    except Exception as e:
        print(f"Error getting GL details from file {gl_detail_file}: {str(e)}")
        return [], {}

# ========== LETTER GENERATION ==========

def generate_tenant_letter(tenant_data: Dict[str, str], gl_detail_file: str, debug_mode: bool = False) -> str:
    """
    Generate a simple text letter for a tenant.
    
    Args:
        tenant_data: Dictionary with tenant billing data
        gl_detail_file: Path to the GL detail file for this tenant
        debug_mode: Whether to print debug information
        
    Returns:
        The path to the generated text file
    """
    if debug_mode:
        print(f"Generating letter for tenant {tenant_data.get('tenant_id')} - {tenant_data.get('tenant_name')}")
    
    # Extract tenant basic info
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = tenant_data.get("tenant_name", "")
    property_id = tenant_data.get("property_id", "")
    property_name = tenant_data.get("property_full_name", PROPERTY_NAMES.get(property_id, property_id))
    
    # Extract dates and format periods
    recon_start_date = tenant_data.get("reconciliation_start_date", "")
    recon_end_date = tenant_data.get("reconciliation_end_date", "")
    catchup_start_date = tenant_data.get("catchup_start_date", "")
    catchup_end_date = tenant_data.get("catchup_end_date", "")
    
    main_period_range = format_date_range(recon_start_date, recon_end_date)
    catchup_period_range = format_date_range(catchup_start_date, catchup_end_date)
    reconciliation_year = extract_year_from_date(recon_end_date)
    
    # Build reconciliation period string
    if catchup_period_range:
        reconciliation_period = f"{main_period_range} and {catchup_period_range}"
    else:
        reconciliation_period = main_period_range
    
    # Create output directories
    letter_dir = LETTERS_DIR / "CAM" / property_id / reconciliation_year
    letter_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output file path
    safe_tenant_name = tenant_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    output_path = letter_dir / f"{safe_tenant_name}_{tenant_id}.txt"
    
    # Extract financial values - only keep non-zero values
    property_total_expenses = float(tenant_data.get("property_gl_total", "0").strip('$').replace(',', ''))
    tenant_pro_rata = float(tenant_data.get("share_percentage", "0").strip('%'))
    tenant_share = float(tenant_data.get("tenant_share_amount", "0").strip('$').replace(',', ''))
    base_year_amount = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', ''))
    cap_reduction = float(tenant_data.get("cap_deduction", "0").strip('$').replace(',', ''))
    admin_fee = float(tenant_data.get("admin_fee_net", "0").strip('$').replace(',', ''))
    amortization_amount = float(tenant_data.get("amortization_total_amount", "0").strip('$').replace(',', ''))
    
    # Get billing details
    main_period_paid = float(tenant_data.get("reconciliation_paid", "0").strip('$').replace(',', ''))
    main_period_balance = float(tenant_data.get("reconciliation_balance", "0").strip('$').replace(',', ''))
    catchup_balance = float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', ''))
    
    # Get override info
    has_override = tenant_data.get("has_override", "false").lower() == "true"
    override_amount = float(tenant_data.get("override_amount", "0").strip('$').replace(',', ''))
    override_description = tenant_data.get("override_description", "Manual Adjustment")
    
    # Get total final amount
    grand_total = float(tenant_data.get("total_balance", "0").strip('$').replace(',', ''))
    
    # Calculate year due (main_period_total) - this ensures the sum matches the line items
    # Start with tenant share
    year_due = tenant_share
    # Deduct base year adjustment if present
    if base_year_amount > 0:
        year_due -= base_year_amount
    # Deduct cap reduction if present
    if cap_reduction > 0:
        year_due -= cap_reduction
    # Add admin fee if present
    if admin_fee > 0:
        year_due += admin_fee
    # Add amortization if present
    if amortization_amount > 0:
        year_due += amortization_amount
    
    # Get monthly charge info
    current_monthly_charge = float(tenant_data.get("old_monthly", "0").strip('$').replace(',', ''))
    new_monthly_charge = float(tenant_data.get("new_monthly", "0").strip('$').replace(',', ''))
    monthly_diff = float(tenant_data.get("monthly_difference", "0").strip('$').replace(',', ''))
    
    # Get effective date from tenant data or calculate it
    effective_date = tenant_data.get("monthly_charge_effective_date", "")
    if effective_date:
        try:
            # Convert YYYY-MM-DD to Mon DD, YYYY
            date_obj = datetime.datetime.strptime(effective_date, "%Y-%m-%d")
            effective_date = date_obj.strftime("%b %d, %Y")
        except ValueError:
            # If parse fails, use as is
            pass
    else:
        # Calculate next month
        today = datetime.datetime.now()
        next_month = today.replace(day=1)
        if today.month == 12:
            next_month = next_month.replace(year=today.year + 1, month=1)
        else:
            next_month = next_month.replace(month=today.month + 1)
        effective_date = next_month.strftime("%b %d, %Y")
    
    # Build the text letter content
    letter_content = []
    letter_content.append(f"CAM RECONCILIATION - {property_name}")
    letter_content.append(f"Reconciliation Period: {reconciliation_period}")
    letter_content.append(f"Tenant: {tenant_name}")
    letter_content.append("-" * 50)
    letter_content.append("RECONCILIATION SUMMARY")
    letter_content.append("-" * 50)
    letter_content.append(f"Total Property CAM Expenses ({reconciliation_year}): {format_currency(property_total_expenses)}")
    letter_content.append(f"Tenant's Pro-Rata Share ({format_percentage(tenant_pro_rata)}): {format_currency(tenant_share)}")
    
    if base_year_amount > 0:
        letter_content.append(f"Base Year Deduction: -{format_currency(base_year_amount)}")
    if cap_reduction > 0:
        letter_content.append(f"Cap Reduction: -{format_currency(cap_reduction)}")
    if amortization_amount > 0:
        letter_content.append(f"Amortization: {format_currency(amortization_amount)}")
    if admin_fee > 0:
        letter_content.append(f"Admin Fee: {format_currency(admin_fee)}")
    
    letter_content.append(f"Total Due for Year: {format_currency(year_due)}")
    letter_content.append(f"Previously Billed ({reconciliation_year}): {format_currency(main_period_paid)}")
    letter_content.append(f"{reconciliation_year} Reconciliation Amount: {format_currency(main_period_balance)}")
    
    if catchup_balance != 0:
        letter_content.append(f"{catchup_period_range} Catchup Period: {format_currency(catchup_balance)}")
    if has_override and override_amount != 0:
        letter_content.append(f"{override_description}: {format_currency(override_amount)}")
    
    letter_content.append(f"ADDITIONAL AMOUNT DUE: {format_currency(grand_total)}")
    letter_content.append("-" * 50)
    letter_content.append("MONTHLY CHARGE UPDATE")
    letter_content.append("-" * 50)
    letter_content.append(f"Current Monthly Charge: {format_currency(current_monthly_charge)}")
    letter_content.append(f"New Monthly Charge: {format_currency(new_monthly_charge)}")
    letter_content.append(f"Difference per Month: {format_currency(monthly_diff)}")
    letter_content.append(f"The new monthly charge will be effective starting {effective_date}.")
    letter_content.append("-" * 50)
    letter_content.append(f"{CONTACT_INFO}")
    
    # Write the letter to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(letter_content))
    
    print(f"  Letter generated successfully for tenant {tenant_id}: {output_path}")
    return str(output_path)


def generate_letters_from_results(results_dict: Dict[str, Any]) -> Tuple[int, int]:
    """
    Generate letters directly from reconciliation results dictionary.
    This is the function that will be called from New Full.py.
    
    Args:
        results_dict: Dictionary with reconciliation results
        
    Returns:
        Tuple of (success_count, total_count)
    """
    print("\nGenerating tenant letters from reconciliation results...")

    # Extract the necessary paths
    csv_report_path = results_dict.get('csv_report_path', '')
    gl_detail_reports = results_dict.get('gl_detail_reports', [])
    
    # Create a map of tenant IDs to their GL detail reports
    tenant_gl_map = {}
    for gl_path in gl_detail_reports:
        # Extract tenant ID from the filename
        filename = os.path.basename(gl_path)
        match = re.search(r'GL_detail_(\d+)_', filename)
        if match:
            tenant_id = match.group(1)
            tenant_gl_map[tenant_id] = gl_path
    
    # Read the tenant data from the CSV
    tenant_data = read_csv_file(csv_report_path)
    
    if not tenant_data:
        print(f"Error: No tenant data found in {csv_report_path}")
        return 0, 0
    
    print(f"Generating letters for {len(tenant_data)} tenants...")
    
    # Create letters directory
    LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track results
    successful = 0
    total = len(tenant_data)
    
    # Generate a letter for each tenant
    for tenant in tenant_data:
        tenant_id = tenant.get("tenant_id")
        tenant_name = tenant.get("tenant_name", "")
        
        print(f"Processing tenant {tenant_id} ({tenant_name})...")
        
        # Get the GL detail file for this tenant
        gl_detail_file = tenant_gl_map.get(tenant_id)
        
        try:
            # Generate letter
            output_path = generate_tenant_letter(tenant, gl_detail_file, debug_mode=True)
            successful += 1
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
    
    print(f"\nLetter generation complete: {successful} of {total} letters generated successfully")
    print(f"Letters are saved in: {LETTERS_DIR}")
    
    return successful, total


# For standalone script usage
def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CAM reconciliation letters for tenants')
    parser.add_argument('--billing', type=str, required=True, help='Path to tenant billing CSV file')
    parser.add_argument('--gl_dir', type=str, required=True, help='Directory containing GL detail CSV files')
    
    args = parser.parse_args()
    
    # For standalone use, read CSV and find GL files
    tenant_data = read_csv_file(args.billing)
    
    # Create a map of tenant IDs to GL detail files
    tenant_gl_map = {}
    for filename in os.listdir(args.gl_dir):
        match = re.search(r'GL_detail_(\d+)_', filename)
        if match:
            tenant_id = match.group(1)
            tenant_gl_map[tenant_id] = os.path.join(args.gl_dir, filename)
    
    # Track results
    successful = 0
    total = len(tenant_data)
    
    # Generate letters
    for tenant in tenant_data:
        tenant_id = tenant.get("tenant_id")
        gl_file = tenant_gl_map.get(tenant_id)
        
        try:
            output_path = generate_tenant_letter(tenant, gl_file, debug_mode=True)
            successful += 1
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
    
    print(f"Letter generation complete: {successful} of {total} letters generated successfully")
    return successful, total


if __name__ == "__main__":
    main()