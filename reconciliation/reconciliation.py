#!/usr/bin/env python3
"""
CAM/TAX Reconciliation Engine - Main CLI Entrypoint

This script orchestrates the entire reconciliation process:
1. Loads settings from portfolio, property, and tenant levels
2. Processes GL data for CAM and TAX expenses
3. Applies base year adjustments and cap limits
4. Calculates tenant-specific shares with occupancy factors
5. Generates detailed reports
6. Updates cap history for future reconciliations

Usage:
  python reconciliation.py [--property_id PROPERTY_ID] [--recon_year YEAR] [--last_bill YYYYMM] [--tenant_id TENANT_ID]
  
Examples:
  python reconciliation.py --property_id ELW --recon_year 2024
  python reconciliation.py --property_id ELW --recon_year 2024 --last_bill 202504 --tenant_id 1330
  python reconciliation.py  # Run with interactive prompts
"""

import os
import sys
import argparse
import logging
import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union

# Import reconciliation modules
from reconciliation.settings_loader import load_settings, find_all_tenants_for_property
from reconciliation.cap_override_handler import load_cap_history, handle_cap_overrides
from reconciliation.gl_loader import load_and_filter_gl
from reconciliation.calculations.cam_tax_admin import calculate_cam_tax_admin
from reconciliation.calculations.base_year import calculate_base_year
from reconciliation.calculations.caps import calculate_caps
from reconciliation.calculations.capital_expenses import calculate_capital_expenses
from reconciliation.period_calculator import calculate_periods
from reconciliation.report_generator import generate_reports
from reconciliation.cap_history_updater import update_cap_history

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('Output', 'reconciliation.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def prompt_for_property_id() -> str:
    """
    Interactively prompt for property ID.
    
    Returns:
        Property ID string
    """
    # Get all property directories
    property_dir = os.path.join('Data', 'ProcessedOutput', 'PropertySettings')
    available_properties = []
    
    if os.path.exists(property_dir):
        available_properties = [
            d for d in os.listdir(property_dir) 
            if os.path.isdir(os.path.join(property_dir, d))
        ]
    
    # Display available properties
    if available_properties:
        print("\nAvailable properties:")
        for i, prop_id in enumerate(available_properties, 1):
            prop_settings_path = os.path.join(property_dir, prop_id, 'property_settings.json')
            prop_name = prop_id
            
            # Try to get property name from settings
            try:
                if os.path.exists(prop_settings_path):
                    with open(prop_settings_path, 'r') as f:
                        import json
                        prop_data = json.load(f)
                        if 'name' in prop_data:
                            prop_name = prop_data['name']
            except:
                pass
            
            print(f"  {i}. {prop_id} - {prop_name}")
    
    # Prompt for property ID
    while True:
        if available_properties:
            prop_input = input("\nEnter property ID or number from the list: ")
            
            # Check if input is a number
            try:
                idx = int(prop_input) - 1
                if 0 <= idx < len(available_properties):
                    return available_properties[idx]
            except ValueError:
                pass
            
            # Check if input matches a property ID
            if prop_input in available_properties:
                return prop_input
                
            print("Invalid property ID or number. Please try again.")
        else:
            prop_input = input("\nEnter property ID: ")
            if prop_input.strip():
                return prop_input
            print("Property ID cannot be empty. Please try again.")


def prompt_for_recon_year() -> int:
    """
    Interactively prompt for reconciliation year.
    
    Returns:
        Reconciliation year as integer
    """
    current_year = datetime.datetime.now().year
    suggested_years = [current_year - 1, current_year]
    
    # Prompt for year
    while True:
        year_input = input(f"\nEnter reconciliation year [{', '.join(map(str, suggested_years))}]: ")
        
        # Use current year - 1 as default if empty
        if not year_input.strip():
            return current_year - 1
            
        try:
            year = int(year_input)
            if 2000 <= year <= 2100:  # Reasonable range
                return year
            else:
                print("Year must be between 2000 and 2100. Please try again.")
        except ValueError:
            print("Invalid year format. Please enter a valid year (e.g., 2024).")


def prompt_for_last_bill() -> Optional[str]:
    """
    Interactively prompt for last bill date.
    
    Returns:
        Last bill date in YYYYMM format or None if skipped
    """
    # Prompt for last bill date
    while True:
        last_bill_input = input("\nEnter last bill date in YYYYMM format (e.g., 202505) or press Enter to skip: ")
        
        # Skip if empty
        if not last_bill_input.strip():
            return None
            
        # Validate format
        if len(last_bill_input) != 6:
            print("Invalid format. Please use YYYYMM format (e.g., 202505).")
            continue
            
        try:
            year = int(last_bill_input[:4])
            month = int(last_bill_input[4:6])
            
            if 2000 <= year <= 2100 and 1 <= month <= 12:
                return last_bill_input
            else:
                print("Invalid year or month. Please try again.")
        except ValueError:
            print("Invalid format. Please use YYYYMM format (e.g., 202505).")


def prompt_for_tenant_id(property_id: str) -> Optional[str]:
    """
    Interactively prompt for tenant ID.
    
    Args:
        property_id: Property identifier
        
    Returns:
        Tenant ID or None if all tenants should be processed
    """
    # Find all tenants for this property
    tenants = find_all_tenants_for_property(property_id)
    
    # Display available tenants
    if tenants:
        print(f"\nAvailable tenants for property {property_id}:")
        print("  0. Process all tenants")
        
        for i, (tenant_id, tenant_name) in enumerate(tenants, 1):
            print(f"  {i}. {tenant_name} (ID: {tenant_id})")
    
    # Prompt for tenant ID
    while True:
        if tenants:
            tenant_input = input("\nEnter tenant number from the list (or 0 for all tenants): ")
            
            # Process all tenants
            if tenant_input == "0":
                return None
                
            # Check if input is a number
            try:
                idx = int(tenant_input) - 1
                if 0 <= idx < len(tenants):
                    return tenants[idx][0]  # Return tenant ID
            except ValueError:
                pass
            
            # Check if input matches a tenant ID
            for tenant_id, _ in tenants:
                if tenant_input == tenant_id:
                    return tenant_input
                    
            print("Invalid tenant number or ID. Please try again.")
        else:
            tenant_input = input("\nNo tenants found for this property. Enter tenant ID or press Enter to process all: ")
            
            if not tenant_input.strip():
                return None
                
            return tenant_input


def parse_arguments():
    """Parse command line arguments with interactive prompts for missing arguments."""
    parser = argparse.ArgumentParser(description='CAM/TAX Reconciliation Engine')
    
    parser.add_argument(
        '--property_id', 
        type=str,
        help='Property identifier (e.g., ELW)'
    )
    parser.add_argument(
        '--recon_year', 
        type=int,
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
        '--output_dir', 
        type=str, 
        default=os.path.join('Output', 'Reports'),
        help='Directory for output reports'
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
        '--interactive',
        action='store_true',
        help='Force interactive mode even if all required arguments are provided'
    )
    
    args = parser.parse_args()
    
    # Check if interactive mode is needed (missing required arguments or forced)
    if args.interactive or args.property_id is None or args.recon_year is None:
        print("\n=== CAM/TAX Reconciliation Engine ===")
        
        # Prompt for missing arguments
        if args.property_id is None:
            args.property_id = prompt_for_property_id()
            
        if args.recon_year is None:
            args.recon_year = prompt_for_recon_year()
            
        if args.last_bill is None:
            args.last_bill = prompt_for_last_bill()
            
        if args.tenant_id is None:
            args.tenant_id = prompt_for_tenant_id(args.property_id)
            
        # Prompt for categories
        if args.interactive:
            categories_input = input("\nEnter expense categories to include (comma-separated, e.g., cam,ret) [cam,ret]: ")
            if categories_input.strip():
                args.categories = categories_input
        
        # Confirm settings
        print("\nReconciliation Settings:")
        print(f"  Property ID: {args.property_id}")
        print(f"  Reconciliation Year: {args.recon_year}")
        print(f"  Last Bill Date: {args.last_bill or 'None'}")
        print(f"  Tenant ID: {args.tenant_id or 'All tenants'}")
        print(f"  Categories: {args.categories}")
        
        confirm = input("\nProceed with these settings? [Y/n]: ")
        if confirm.lower() == 'n':
            print("Reconciliation cancelled.")
            sys.exit(0)
    
    return args


def process_tenant(
    tenant_id: str,
    property_id: str,
    recon_year: int,
    periods: Dict[str, List[str]],
    property_settings: Dict[str, Any],
    cap_history: Dict[str, Dict[str, float]],
    categories: List[str] = ['cam', 'ret']
) -> Dict[str, Any]:
    """Process reconciliation for a single tenant."""
    logger.info(f"Processing tenant {tenant_id} in property {property_id} for categories: {categories}")
    
    # Load tenant settings
    tenant_settings = load_settings(property_id, tenant_id)
    
    # Apply cap overrides if present
    cap_history = handle_cap_overrides(tenant_settings)
    
    # Load and filter GL data - only use reconciliation year periods, not catch-up
    gl_data = load_and_filter_gl(
        property_id, 
        tenant_settings,
        periods['recon_periods']
    )
    
    # Filter GL data to only include the requested categories
    filtered_gl = gl_data['filtered_gl']
    for category in list(filtered_gl.keys()):
        if category.lower() not in categories and category not in ['base', 'cap', 'other']:
            # Set the category to empty if it's not in the requested categories
            # (preserve base, cap, and other categories for calculations)
            logger.info(f"Excluding category '{category}' from reconciliation as requested")
            filtered_gl[category] = []
    
    # Update the gl_data with the filtered categories
    gl_data['filtered_gl'] = filtered_gl
    
    # Recalculate totals based on filtered categories
    for cat in ['cam', 'ret']:
        if cat not in categories:
            # Zero out the totals for excluded categories
            gl_data['totals'][f'{cat}_total'] = Decimal('0')
    
    # Calculate CAM, TAX, and admin fee - pass the requested categories
    cam_tax_admin_results = calculate_cam_tax_admin(
        gl_data['filtered_gl'],
        tenant_settings,
        categories  # Pass the requested categories
    )
    
    # Calculate base year adjustment
    base_year_results = calculate_base_year(
        recon_year,
        cam_tax_admin_results,
        tenant_settings
    )
    
    # Apply caps
    # Make sure we pass the categories to cap calculations for proper cap exclusion handling
    gl_data['categories'] = categories
    cap_results = calculate_caps(
        tenant_id,
        recon_year,
        base_year_results,
        gl_data,
        tenant_settings
    )
    
    # Calculate capital expenses with occupancy proration - only use reconciliation year periods
    capital_expenses_results = calculate_capital_expenses(
        tenant_settings,
        recon_year,
        periods['recon_periods']  # Pass only recon_periods for occupancy proration
    )
    
    # Calculate total capital expense amount
    capital_expense_amount = capital_expenses_results.get('total_capital_expenses', Decimal('0'))
    
    # Calculate final recoverable amount including capital expenses
    final_amount = cap_results.get('final_recoverable_amount', Decimal('0')) + capital_expense_amount
    
    # Debug the final_amount for this tenant
    logger.info(f"Tenant {tenant_id} final_amount: {final_amount} = {cap_results.get('final_recoverable_amount', Decimal('0'))} (cap_results) + {capital_expense_amount} (capital_expenses)")
    
    # Combine results - ensure all data needed for reporting is included
    results = {
        'tenant_id': tenant_id,
        'property_id': property_id,
        'recon_year': recon_year,
        'periods': periods,
        'gl_data': gl_data,
        'cam_tax_admin_results': cam_tax_admin_results,  # Admin fee data is here
        'base_year_results': base_year_results,
        'cap_results': cap_results,
        'capital_expenses_results': capital_expenses_results,
        'final_recoverable_amount': final_amount,
        'categories': categories  # Include categories used in this reconciliation
    }
    
    # Log admin fee data to help with debugging
    logger.info(f"Tenant {tenant_id} admin fee data: base={cam_tax_admin_results.get('admin_fee_base', Decimal('0'))}, amount={cam_tax_admin_results.get('admin_fee_amount', Decimal('0'))}")
    
    logger.info(
        f"Tenant {tenant_id} reconciliation complete: "
        f"{results['final_recoverable_amount']}"
    )
    
    return results


def process_property(
    property_id: str,
    recon_year: int,
    last_bill: Optional[str] = None,
    tenant_id: Optional[str] = None,
    categories: List[str] = ['cam', 'ret'],
    skip_cap_update: bool = False
) -> Dict[str, Any]:
    """Process reconciliation for a property (all tenants or one tenant)."""
    logger.info(f"Starting reconciliation for property {property_id}, year {recon_year}, categories: {categories}")
    
    # Load property settings
    property_settings = load_settings(property_id)
    
    # Calculate periods for reconciliation
    periods = calculate_periods(recon_year, last_bill)
    
    # Load cap history
    cap_history = load_cap_history()
    
    # If tenant_id provided, process only that tenant
    if tenant_id:
        tenants_to_process = [(tenant_id, "")]
    else:
        # Find all tenants for this property
        tenants_to_process = find_all_tenants_for_property(property_id)
    
    logger.info(f"Processing {len(tenants_to_process)} tenants")
    
    # Process each tenant
    tenant_results = []
    tenant_settings_list = []
    
    for tenant_id, _ in tenants_to_process:
        # Load tenant settings for reporting
        tenant_settings = load_settings(property_id, tenant_id)
        tenant_settings_list.append(tenant_settings)
        
        # Process tenant
        result = process_tenant(
            tenant_id,
            property_id,
            recon_year,
            periods,
            property_settings,
            cap_history,
            categories
        )
        
        tenant_results.append(result)
    
    # Load property-level CAM, RET totals (without tenant-specific exclusions)
    # These should represent the total property expenses before tenant exclusions
    # But we need to respect the categories parameter
    property_gl_data = load_and_filter_gl(
        property_id,
        property_settings,  # Use property settings instead of tenant settings
        periods['recon_periods']
    )
    
    # Filter to include only requested categories
    filtered_gl = property_gl_data['filtered_gl'].copy()
    for category in list(filtered_gl.keys()):
        if category.lower() not in categories and category not in ['base', 'cap', 'other']:
            # Keep the category but zero it out for property totals
            logger.info(f"Excluding property-level category '{category}' as it's not in requested categories: {categories}")
            filtered_gl[category] = []
    
    # Recalculate property totals based on filtered categories
    cam_total = Decimal('0')
    if 'cam' in categories:
        cam_total = sum(tx.get('Net Amount', Decimal('0')) for tx in filtered_gl.get('cam', []))
    
    ret_total = Decimal('0')  
    if 'ret' in categories:
        ret_total = sum(tx.get('Net Amount', Decimal('0')) for tx in filtered_gl.get('ret', []))
    
    # Set property totals from filtered GL data
    property_totals = {
        'cam_total': cam_total,
        'ret_total': ret_total
    }
    
    logger.info(f"Filtered property totals based on categories ({categories}): CAM={cam_total}, RET={ret_total}")
    
    # Debug property GL totals
    logger.info(f"Property GL data - CAM total: {property_totals['cam_total']}, RET total: {property_totals['ret_total']}")
    
    # Store the property totals in each tenant result for reporting
    for tenant_result in tenant_results:
        if 'property_gl_totals' not in tenant_result:
            tenant_result['property_gl_totals'] = property_totals.copy()
        
        # Calculate admin fee at the property level (only if the property has admin_fee_percentage set)
        admin_fee_amount = Decimal('0')
        admin_fee_percentage_str = property_settings.get('settings', {}).get('admin_fee_percentage', '')
        
        # Only calculate admin fee if property has a percentage set
        if admin_fee_percentage_str and admin_fee_percentage_str.strip():
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
                
                # Calculate admin fee based on CAM total
                admin_fee_amount = property_totals.get('cam_total', Decimal('0')) * admin_fee_percentage
                logger.info(f"Property-level admin fee calculated: {admin_fee_amount} ({admin_fee_percentage * 100}% of {property_totals.get('cam_total')})")
            except (ValueError, decimal.InvalidOperation) as e:
                logger.error(f"Invalid property admin fee percentage: {admin_fee_percentage_str}, error: {str(e)}, using 0")
        else:
            logger.info("Property has no admin_fee_percentage set, not adding admin fee to property_recoverable")
        
        # Add admin fee to property_totals
        property_totals['admin_fee_amount'] = admin_fee_amount
        
        # Sum these up for the total property recoverable amount
        property_recoverable_amount = sum([
            property_totals.get('cam_total', Decimal('0')),
            property_totals.get('ret_total', Decimal('0')),
            property_totals.get('admin_fee_amount', Decimal('0'))
        ])
        
        # Create a property_recoverable dictionary with complete data
        property_recoverable = property_recoverable_amount
        logger.info(f"Total property recoverable amount: {property_recoverable_amount}")
    else:
        property_recoverable = Decimal('0')
    
    # Debug property totals right before passing to generate_reports
    logger.info(f"Property totals being passed to reports: CAM={property_totals.get('cam_total')}, RET={property_totals.get('ret_total')}")
    
    # Set property GL totals directly on the generate_report_row function for access in the reports
    from reconciliation.report_generator import generate_report_row
    generate_report_row.property_gl_totals = {
        'cam_total': property_totals.get('cam_total', Decimal('0')),
        'ret_total': property_totals.get('ret_total', Decimal('0'))
    }
    
    # Generate reports with complete data
    report_results = generate_reports(
        property_settings,
        tenant_settings_list,
        {
            'final_recoverable_amount': property_recoverable,
            'categories': categories,  # Pass categories to reports
            'property_gl_totals': property_totals,  # Pass property totals 
            'tenant_results': tenant_results  # Pass all tenant-specific results
        },
        periods['full_period']
    )
    
    # Update cap history unless skipped
    cap_update_results = None
    if not skip_cap_update:
        cap_update_results = update_cap_history(
            report_results['billing_results'],
            recon_year
        )
    
    # Return consolidated results
    return {
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'recon_year': recon_year,
        'periods': periods,
        'tenant_count': len(tenant_results),
        'tenant_results': tenant_results,
        'report_results': report_results,
        'cap_update_results': cap_update_results
    }


def main():
    """Main entry point for the reconciliation process."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Parse categories from command line argument
    categories = [cat.strip().lower() for cat in args.categories.split(',') if cat.strip()]
    
    try:
        # Process property reconciliation
        start_time = datetime.datetime.now()
        
        logger.info(f"Starting reconciliation: property={args.property_id}, year={args.recon_year}, categories={categories}")
        
        results = process_property(
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
        print("\n" + "="*80)
        print(f"RECONCILIATION COMPLETE - {elapsed_time:.2f}s")
        print("="*80)
        print(f"Property: {results['property_name']} ({results['property_id']})")
        print(f"Year: {results['recon_year']}")
        print(f"Tenants Processed: {results['tenant_count']}")
        
        if results['report_results']:
            print(f"\nReports Generated:")
            print(f"- CSV: {results['report_results']['csv_report_path']}")
            print(f"- JSON: {results['report_results']['json_report_path']}")
        
        if results['cap_update_results']:
            print(f"\nCap History Updated:")
            print(f"- Tenants Updated: {results['cap_update_results']['updated_tenants']}")
        
        print("="*80 + "\n")
        
        return 0  # Success
    
    except Exception as e:
        logger.exception(f"Error during reconciliation: {str(e)}")
        print(f"\nERROR: {str(e)}")
        return 1  # Error


if __name__ == "__main__":
    sys.exit(main())