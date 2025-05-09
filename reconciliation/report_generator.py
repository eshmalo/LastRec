#!/usr/bin/env python3
"""
Report Generator Module

This module generates tenant billing reports based on reconciliation calculations.
It computes tenant-specific shares, applies occupancy factors, and generates
detailed reports with all calculation steps.
"""

import os
import json
import logging
import datetime
import csv
import uuid
import decimal
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union

from reconciliation.utils.helpers import format_currency
from reconciliation.occupancy_calculator import calculate_occupancy_factors
from reconciliation.manual_override_loader import get_override_amount

# Configure logging
logger = logging.getLogger(__name__)

# Path for output reports
REPORTS_PATH = os.path.join('Output', 'Reports')


def calculate_tenant_share(
    tenant_settings: Dict[str, Any],
    property_settings: Dict[str, Any],
    property_recoverable: Union[Decimal, Dict[str, Any]]
) -> Decimal:
    """
    Calculate tenant's share of property recoverable amount.
    
    Args:
        tenant_settings: Tenant settings dictionary
        property_settings: Property settings dictionary
        property_recoverable: Total property recoverable amount or dictionary with recoverable amount
        
    Returns:
        Tenant's share of recoverable amount
    """
    # Extract tenant's CAM/TAX/admin_fee from property_recoverable if it's a dictionary
    if isinstance(property_recoverable, dict) and 'cam_tax_admin_results' in property_recoverable:
        cam_tax_admin_results = property_recoverable.get('cam_tax_admin_results', {})
        if cam_tax_admin_results:
            # We have detailed CAM/TAX/admin results - calculate share directly
            cam_total = cam_tax_admin_results.get('cam_total', Decimal('0'))
            admin_fee_amount = cam_tax_admin_results.get('admin_fee_amount', Decimal('0'))
            
            # Get share percentage
            share_percentage = get_tenant_share_percentage(tenant_settings, property_settings)
            
            # Calculate tenant's share of CAM and admin fee
            tenant_cam_share = cam_total * share_percentage
            tenant_admin_share = admin_fee_amount * share_percentage
            
            # Combined total is the tenant's CAM share plus admin fee share
            tenant_share = tenant_cam_share + tenant_admin_share
            logger.info(f"Using detailed calculation: tenant_cam_share={tenant_cam_share}, tenant_admin_share={tenant_admin_share}, total={tenant_share}")
            
            return tenant_share
    
    # Fall back to simple calculation if we don't have detailed results
    # Extract the recoverable amount if property_recoverable is a dictionary
    if isinstance(property_recoverable, dict):
        recoverable_amount = property_recoverable.get('final_recoverable_amount', Decimal('0'))
        logger.info(f"Using recoverable amount from dictionary: {recoverable_amount}")
    else:
        recoverable_amount = property_recoverable
        logger.info(f"Using direct recoverable amount: {recoverable_amount}")
    
    # Calculate share percentage
    share_percentage = get_tenant_share_percentage(tenant_settings, property_settings)
    
    # Apply share percentage to recoverable amount
    tenant_share = recoverable_amount * share_percentage
    logger.info(f"Using simple calculation: share_percentage={share_percentage}, recoverable_amount={recoverable_amount}, tenant_share={tenant_share}")
    
    return tenant_share


def get_tenant_share_percentage(
    tenant_settings: Dict[str, Any],
    property_settings: Dict[str, Any]
) -> Decimal:
    """
    Calculate tenant's share percentage based on share method.
    
    Args:
        tenant_settings: Tenant settings dictionary
        property_settings: Property settings dictionary
        
    Returns:
        Tenant's share percentage as a decimal (e.g., 0.05 for 5%)
    """
    # Get tenant's share method
    share_method = tenant_settings.get('settings', {}).get('prorate_share_method', '')
    
    # Fixed share percentage
    if share_method == "Fixed":
        fixed_share_str = tenant_settings.get('settings', {}).get('fixed_pyc_share', '0')
        
        try:
            # Handle None, empty string, and other invalid values
            if fixed_share_str is None or fixed_share_str == '':
                fixed_share_str = '0'
                
            # Ensure we have a string for Decimal conversion
            if not isinstance(fixed_share_str, str):
                fixed_share_str = str(fixed_share_str)
                
            # Convert from percentage (e.g., 5.138) to decimal (0.05138)
            fixed_share = Decimal(fixed_share_str) / Decimal('100')
            logger.info(f"Using fixed share percentage: {fixed_share_str}% = {fixed_share}")
            return fixed_share
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            logger.error(f"Invalid fixed share percentage: {fixed_share_str}. Error: {str(e)}")
            # Fall back to RSF calculation below
    
    # RSF-based calculation (default)
    tenant_sf = tenant_settings.get('settings', {}).get('square_footage', '0')
    property_sf = property_settings.get('total_rsf', '0')
    
    try:
        tenant_sf = Decimal(str(tenant_sf or '0'))
        property_sf = Decimal(str(property_sf or '0'))
        
        if property_sf > 0:
            share_pct = tenant_sf / property_sf
            logger.info(f"Using RSF-based share: {tenant_sf}/{property_sf} = {share_pct}")
            return share_pct
        else:
            logger.error("Property square footage is zero or invalid")
            return Decimal('0')
    except (ValueError, TypeError):
        logger.error(f"Invalid square footage values: tenant={tenant_sf}, property={property_sf}")
        return Decimal('0')


def calculate_monthly_amounts(
    property_recoverable: Decimal,
    periods: List[str]
) -> Dict[str, Decimal]:
    """
    Calculate monthly amounts by dividing property recoverable by number of periods.
    
    Args:
        property_recoverable: Total property recoverable amount
        periods: List of periods to distribute across
        
    Returns:
        Dictionary mapping periods to monthly amounts
    """
    if not periods:
        logger.warning("No periods provided for monthly calculation")
        return {}
    
    # Calculate monthly amount (divide total by number of periods)
    monthly_amount = property_recoverable / Decimal(len(periods))
    
    # Create dictionary mapping each period to its amount
    monthly_amounts = {period: monthly_amount for period in periods}
    
    logger.info(f"Calculated monthly amounts: {monthly_amount} per month for {len(periods)} months")
    
    return monthly_amounts


def apply_occupancy_factors(
    monthly_amounts: Dict[str, Decimal],
    occupancy_factors: Dict[str, Decimal]
) -> Dict[str, Decimal]:
    """
    Apply occupancy factors to monthly amounts.
    
    Args:
        monthly_amounts: Dictionary mapping periods to monthly amounts
        occupancy_factors: Dictionary mapping periods to occupancy factors
        
    Returns:
        Dictionary mapping periods to adjusted amounts
    """
    adjusted_amounts = {}
    
    for period in monthly_amounts:
        base_amount = monthly_amounts.get(period, Decimal('0'))
        factor = occupancy_factors.get(period, Decimal('0'))
        
        adjusted_amount = base_amount * factor
        adjusted_amounts[period] = adjusted_amount
    
    total_adjusted = sum(adjusted_amounts.values())
    logger.info(f"Applied occupancy factors: total adjusted amount = {total_adjusted}")
    
    return adjusted_amounts


def calculate_tenant_billing(
    tenant_settings: Dict[str, Any],
    property_settings: Dict[str, Any],
    property_recoverable: Union[Decimal, Dict[str, Any]],
    periods: List[str],
    override_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    periods_dict: Optional[Dict[str, List[str]]] = None  # Add periods_dict parameter
) -> Dict[str, Any]:
    """
    Calculate tenant billing amount with all adjustments.
    
    Args:
        tenant_settings: Tenant settings dictionary
        property_settings: Property settings dictionary
        property_recoverable: Total property recoverable amount
        periods: List of periods for calculation
        override_lookup: Optional override lookup dictionary
        periods_dict: Dictionary with recon_periods and catchup_periods
        
    Returns:
        Dictionary with tenant billing calculation results
    """
    tenant_id = tenant_settings.get('tenant_id')
    property_id = property_settings.get('property_id')
    
    # Calculate tenant's share of property recoverable
    tenant_share = calculate_tenant_share(tenant_settings, property_settings, property_recoverable)
    logger.info(f"DEBUG: Tenant {tenant_id} share: {tenant_share}")
    
    # If we have periods_dict, we need to separate recon and catchup periods
    recon_periods = []
    catchup_periods = []
    if periods_dict:
        recon_periods = periods_dict.get('recon_periods', [])
        catchup_periods = periods_dict.get('catchup_periods', [])
        logger.info(f"Using periods_dict: {len(recon_periods)} recon periods, {len(catchup_periods)} catchup periods")
        
        # For the monthly_amounts, we should only use the recon_periods 
        # This ensures tenant_share is allocated to recon year only
        if recon_periods:
            periods = recon_periods
            logger.info(f"Using ONLY recon periods for monthly amounts calculation: {len(periods)} periods")
    
    # Calculate monthly amounts - only using recon periods
    monthly_amounts = calculate_monthly_amounts(tenant_share, periods)
    logger.info(f"DEBUG: Tenant {tenant_id} monthly_amounts: {monthly_amounts}")
    
    # Calculate occupancy factors based on lease dates
    lease_start = tenant_settings.get('lease_start')
    lease_end = tenant_settings.get('lease_end')
    occupancy_factors = calculate_occupancy_factors(periods, lease_start, lease_end)
    logger.info(f"DEBUG: Tenant {tenant_id} occupancy_factors: {occupancy_factors}")
    
    # Apply occupancy factors to monthly amounts
    adjusted_amounts = apply_occupancy_factors(monthly_amounts, occupancy_factors)
    logger.info(f"DEBUG: Tenant {tenant_id} adjusted_amounts: {adjusted_amounts}")
    
    # Get manual override amount
    override_amount = get_override_amount(tenant_id, property_id, override_lookup)
    
    # Calculate final billing amount
    base_billing = sum(adjusted_amounts.values())
    final_billing = base_billing + override_amount
    
    # Account for tenant payments and separate recon year from catchup period
    recon_period_paid = Decimal('0')
    catchup_period_paid = Decimal('0')
    total_tenant_paid = Decimal('0')
    
    # Calculate separate amounts for recon year and catchup period
    recon_base_billing = Decimal('0')
    catchup_base_billing = Decimal('0')
    
    # Get previous monthly payment from MatchedEstimate if available
    try:
        from reconciliation.payment_tracker import get_old_monthly_payment
        old_monthly_payment = get_old_monthly_payment(tenant_id, property_id)
        
        # If we have periods_dict, calculate separate amounts for recon and catchup
        if periods_dict:
            recon_periods = periods_dict.get('recon_periods', [])
            catchup_periods = periods_dict.get('catchup_periods', [])
            recon_period_count = len(recon_periods)
            catchup_period_count = len(catchup_periods)
            
            # Calculate what tenant has already paid based on old monthly payment
            recon_period_paid = old_monthly_payment * Decimal(str(recon_period_count))
            catchup_period_paid = old_monthly_payment * Decimal(str(catchup_period_count))
            total_tenant_paid = recon_period_paid + catchup_period_paid
            
            # Since we've limited periods to only recon_periods when calculating monthly_amounts,
            # all adjusted_amounts are already for the reconciliation year
            recon_base_billing = base_billing
            
            # For catchup periods, we need to use the calculated new monthly payment
            # Calculated from the recon year's final amount
            try:
                from reconciliation.payment_tracker import calculate_new_monthly_payment
                new_monthly = calculate_new_monthly_payment(
                    final_billing,  # Use the total annual reconciliation amount
                    recon_period_count  # Divide by number of reconciliation periods
                )
            except Exception as e:
                logger.error(f"Error calculating new_monthly: {str(e)}")
                new_monthly = final_billing / Decimal(str(recon_period_count)) if recon_period_count > 0 else Decimal('0')
            
            # Catchup billing is simply the new monthly amount times the number of catchup periods
            if catchup_period_count > 0:
                catchup_base_billing = new_monthly * Decimal(str(catchup_period_count))
                logger.info(f"DEBUG: Calculating catchup_base_billing = {new_monthly} * {catchup_period_count} = {catchup_base_billing}")
            else:
                catchup_base_billing = Decimal('0')
                logger.info(f"DEBUG: No catchup periods, setting catchup_base_billing to 0")
            
            logger.info(f"DEBUG: Tenant {tenant_id} base_billing={base_billing}, recon_base_billing={recon_base_billing}")
            logger.info(f"DEBUG: Tenant {tenant_id} new_monthly={new_monthly}, catchup_base_billing={catchup_base_billing}")
            
            # Divide the override amount proportionally based on number of periods
            # This is a simplification; you might need a different logic based on your business rules
            total_periods = recon_period_count + catchup_period_count
            if total_periods > 0:
                recon_override = override_amount * (Decimal(str(recon_period_count)) / Decimal(str(total_periods)))
                catchup_override = override_amount * (Decimal(str(catchup_period_count)) / Decimal(str(total_periods)))
            else:
                recon_override = override_amount
                catchup_override = Decimal('0')
            
            # Calculate final billing for recon year and catchup period
            recon_final_billing = recon_base_billing + recon_override
            catchup_final_billing = catchup_base_billing + catchup_override
            
            # Calculate outstanding amounts separately for recon year and catchup period
            recon_outstanding = recon_final_billing - recon_period_paid
            catchup_outstanding = catchup_final_billing - catchup_period_paid
            total_outstanding = recon_outstanding + catchup_outstanding
            
            logger.info(
                f"Tenant payment tracking: old_monthly={old_monthly_payment}, "
                f"recon_paid={recon_period_paid}, catchup_paid={catchup_period_paid}, "
                f"recon_billing={recon_final_billing}, catchup_billing={catchup_final_billing}, "
                f"recon_outstanding={recon_outstanding}, catchup_outstanding={catchup_outstanding}"
            )
        else:
            # If no periods_dict, assume all billing is for recon year
            recon_base_billing = base_billing
            recon_final_billing = final_billing
            recon_outstanding = final_billing - recon_period_paid
            total_outstanding = recon_outstanding
    except Exception as e:
        logger.error(f"Error calculating tenant payments: {str(e)}")
        # Set default values in case of error
        recon_base_billing = base_billing
        recon_final_billing = final_billing
        catchup_base_billing = Decimal('0')
        catchup_final_billing = Decimal('0')
        recon_outstanding = final_billing
        catchup_outstanding = Decimal('0')
        total_outstanding = recon_outstanding
    
    logger.info(
        f"Calculated tenant billing: base={base_billing}, "
        f"override={override_amount}, final={final_billing}, "
        f"recon_final={recon_final_billing}, catchup_final={catchup_final_billing}, "
        f"recon_outstanding={recon_outstanding}, catchup_outstanding={catchup_outstanding}"
    )
    
    # Get share information for reporting
    share_method = tenant_settings.get('settings', {}).get('prorate_share_method', 'RSF')
    share_percentage = Decimal('0')
    
    if share_method == "Fixed":
        fixed_share_str = tenant_settings.get('settings', {}).get('fixed_pyc_share', '0')
        try:
            # Handle None, empty string, and other invalid values
            if fixed_share_str is None or fixed_share_str == '':
                fixed_share_str = '0'
                
            # Ensure we have a string for Decimal conversion
            if not isinstance(fixed_share_str, str):
                fixed_share_str = str(fixed_share_str)
                
            share_percentage = Decimal(fixed_share_str) / Decimal('100')
        except (ValueError, TypeError, decimal.InvalidOperation) as e:
            logger.error(f"Error converting share percentage: {fixed_share_str}. Error: {str(e)}")
            share_percentage = Decimal('0')
    else:
        tenant_sf = Decimal(str(tenant_settings.get('settings', {}).get('square_footage', '0') or '0'))
        property_sf = Decimal(str(property_settings.get('total_rsf', '0') or '0'))
        if property_sf > 0:
            share_percentage = tenant_sf / property_sf
    
    # Get categories from property_recoverable if available
    categories = []
    if isinstance(property_recoverable, dict) and 'categories' in property_recoverable:
        categories = property_recoverable.get('categories', [])
    
    # If property_recoverable is a dict, extract the actual amount and GL totals
    if isinstance(property_recoverable, dict):
        property_recoverable_amount = property_recoverable.get('final_recoverable_amount', Decimal('0'))
        # Get property GL totals if provided
        property_gl_totals = property_recoverable.get('property_gl_totals', {})
    else:
        property_recoverable_amount = property_recoverable
        property_gl_totals = {}
    
    # Extract any tenant-specific CAM/TAX/admin results from property_recoverable
    cam_tax_admin_results = {}
    if isinstance(property_recoverable, dict) and 'cam_tax_admin_results' in property_recoverable:
        cam_tax_admin_results = property_recoverable.get('cam_tax_admin_results', {})
        logger.info(f"Found cam_tax_admin_results in property_recoverable: {cam_tax_admin_results}")
        
    # Extract any tenant-specific cap results from property_recoverable
    cap_results = {}
    if isinstance(property_recoverable, dict) and 'cap_results' in property_recoverable:
        cap_results = property_recoverable.get('cap_results', {})
        cap_type = cap_results.get('cap_limit_results', {}).get('cap_type', 'None')
        cap_percentage = cap_results.get('cap_limit_results', {}).get('cap_percentage', 'None')
        logger.info(f"Found cap_results in property_recoverable: cap_type={cap_type}, cap_percentage={cap_percentage}")
    
    # Return comprehensive results with all necessary data for reporting
    result = {
        'tenant_id': tenant_id,
        'tenant_name': tenant_settings.get('tenant_name', ''),
        'property_id': property_id,
        'property_name': property_settings.get('name', ''),
        'lease_start': lease_start,
        'lease_end': lease_end,
        'suite': tenant_settings.get('suite', ''),
        'share_method': share_method,
        'share_percentage': share_percentage,
        'property_recoverable': property_recoverable_amount,
        'tenant_share_base': tenant_share,
        'periods': periods,
        'monthly_amounts': monthly_amounts,
        'occupancy_factors': occupancy_factors,
        'adjusted_amounts': adjusted_amounts,
        'has_override': override_amount != 0,
        'override_amount': override_amount,
        'base_billing': base_billing,
        'final_billing': final_billing,
        'categories': categories,  # Include categories in the result
        'property_gl_totals': property_gl_totals,
        'cam_tax_admin_results': cam_tax_admin_results,  # Include admin fee data
        'cap_results': cap_results,  # Include cap data
        
        # Add tenant payment tracking fields with separate recon and catchup values
        'periods_dict': periods_dict,
        
        # Reconciliation year amounts
        'recon_base_billing': recon_base_billing,
        'recon_final_billing': recon_final_billing,
        'recon_period_paid': recon_period_paid,
        'recon_outstanding': recon_outstanding,
        
        # Catchup period amounts
        'catchup_base_billing': catchup_base_billing,
        'catchup_final_billing': catchup_final_billing,
        'catchup_period_paid': catchup_period_paid,
        'catchup_outstanding': catchup_outstanding,
        
        # Total amounts
        'total_tenant_paid': total_tenant_paid,
        'total_outstanding': total_outstanding
    }
    
    logger.info(f"Tenant billing result includes cam_tax_admin_results: {cam_tax_admin_results != {}}")
    
    return result


def generate_report_row(billing_result: Dict[str, Any], tenant_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate a report row for a tenant billing calculation.
    
    Args:
        billing_result: Tenant billing calculation result
        tenant_settings: Optional tenant settings for additional details
        
    Returns:
        Dictionary with formatted report row including detailed calculation breakdowns
    """
    # Extract data from billing result
    tenant_id = billing_result.get('tenant_id')
    tenant_name = billing_result.get('tenant_name', '')
    property_id = billing_result.get('property_id')
    property_name = billing_result.get('property_name', '')
    share_method = billing_result.get('share_method', '')
    share_percentage = billing_result.get('share_percentage', Decimal('0'))
    base_billing = billing_result.get('base_billing', Decimal('0'))
    override_amount = billing_result.get('override_amount', Decimal('0'))
    final_billing = billing_result.get('final_billing', Decimal('0'))
    
    # Calculate occupancy statistics
    occupancy_factors = billing_result.get('occupancy_factors', {})
    periods = billing_result.get('periods', [])
    
    if periods:
        avg_occupancy = sum(occupancy_factors.values()) / Decimal(len(periods))
    else:
        avg_occupancy = Decimal('0')
    
    occupied_months = sum(1 for f in occupancy_factors.values() if f > 0)
    full_months = sum(1 for f in occupancy_factors.values() if f >= Decimal('1'))
    partial_months = sum(1 for f in occupancy_factors.values() if Decimal('0') < f < Decimal('1'))
    
    # Extract calculation details from nested results
    # Get CAM/TAX/Admin Fee details
    cam_tax_admin_results = {}
    if 'tenant_results' in billing_result:
        # If this is in the property-level results, get the first tenant's results
        if billing_result.get('tenant_results') and len(billing_result.get('tenant_results', [])) > 0:
            first_tenant = billing_result['tenant_results'][0]
            cam_tax_admin_results = first_tenant.get('cam_tax_admin_results', {})
    else:
        # Direct tenant result
        cam_tax_admin_results = billing_result.get('cam_tax_admin_results', {})
    
    logger.info(f"CAM/TAX/Admin results for report: {cam_tax_admin_results}")
    
    # Get base year details
    base_year_results = {}
    if 'base_year_results' in billing_result:
        base_year_results = billing_result.get('base_year_results', {})
        if 'base_year_results' in base_year_results:
            # Handle nested structure
            base_year_results = base_year_results.get('base_year_results', {})
    
    # Get cap details - properly traverse the nested structure
    cap_results = {}
    cap_limit_results = {}
    
    # Check if cap_results is directly in billing_result
    if 'cap_results' in billing_result:
        cap_results = billing_result.get('cap_results', {})
        # Check if cap_results has cap_limit_results directly
        if 'cap_limit_results' in cap_results:
            cap_limit_results = cap_results.get('cap_limit_results', {})
        # Otherwise check if it's under a nested 'cap_results'
        elif 'cap_results' in cap_results:
            nested_cap_results = cap_results.get('cap_results', {})
            cap_limit_results = nested_cap_results.get('cap_limit_results', {})
        else:
            cap_limit_results = {}
        
        logger.info(f"Found cap_results directly in billing_result: {cap_results.keys()}")
        
    # Otherwise, check if it's nested in 'base_year_results' (this is how it's structured)
    elif 'base_year_results' in billing_result and 'cap_results' in billing_result.get('base_year_results', {}):
        cap_results = billing_result['base_year_results'].get('cap_results', {})
        cap_limit_results = cap_results.get('cap_limit_results', {})
        logger.info(f"Found cap_results in base_year_results: {cap_results.keys() if cap_results else 'None'}")
    else:
        cap_limit_results = {}
        
    # Debug the cap_limit_results structure
    if cap_limit_results:
        logger.info(f"cap_limit_results: {cap_limit_results.keys()}")
    
    # Handle extra nested cap_results level
    if not cap_limit_results and 'cap_results' in cap_results:
        nested_results = cap_results.get('cap_results', {})
        if isinstance(nested_results, dict) and 'cap_limit_results' in nested_results:
            cap_limit_results = nested_results.get('cap_limit_results', {})
            logger.info(f"Found cap_limit_results in nested structure: {cap_limit_results.keys() if cap_limit_results else 'None'}")
        
    logger.info(f"Cap data for report: cap_type={cap_limit_results.get('cap_type', 'None')}, cap_percentage={cap_limit_results.get('cap_percentage', 'None')}")
        
    # Get tenant settings
    settings = tenant_settings if tenant_settings else {}
    
    # Get payment comparison data (old vs new monthly amounts)
    payment_data = {}
    try:
        from reconciliation.payment_tracker import get_payment_comparison
        
        payment_data = get_payment_comparison(
            tenant_id,
            property_id,
            final_billing,
            len(periods) if periods else 12,
            tenant_name=tenant_name
        )
    except Exception as e:
        logger.error(f"Error getting payment comparison for tenant {tenant_id}: {str(e)}")
    
    # Use the property totals passed from reconciliation.py
    property_gl_total = Decimal('0')
    
    # First check if there's a global property_gl_totals from reconciliation_results
    if hasattr(generate_report_row, 'property_gl_totals'):
        # Use the global property_gl_totals
        cam_total = generate_report_row.property_gl_totals.get('cam_total', Decimal('0'))
        ret_total = generate_report_row.property_gl_totals.get('ret_total', Decimal('0'))
        admin_fee_base = generate_report_row.property_gl_totals.get('admin_fee_base', Decimal('0'))
        property_gl_total = cam_total + ret_total
        logger.info(f"Using global property_gl_totals: CAM={cam_total}, RET={ret_total}, admin_fee_base={admin_fee_base}, Total={property_gl_total}")
    # Otherwise fall back to GL data
    elif 'gl_data' in billing_result and 'totals' in billing_result.get('gl_data', {}):
        # Fallback to gl_data (for backward compatibility)
        cam_total = billing_result['gl_data']['totals'].get('cam_total', Decimal('0'))
        ret_total = billing_result['gl_data']['totals'].get('ret_total', Decimal('0'))
        property_gl_total = cam_total + ret_total
        logger.info(f"Using gl_data: CAM={cam_total}, RET={ret_total}, Total={property_gl_total}")
    
    # Get admin fee percentage in decimal format (e.g., 0.15 for 15%)
    admin_fee_percentage = billing_result.get('cam_tax_admin_results', {}).get('admin_fee_percentage', Decimal('0'))
    if not admin_fee_percentage:
        admin_fee_percentage = Decimal(str(settings.get('settings', {}).get('admin_fee_percentage', '0') or '0'))
        # Convert from percentage to decimal if needed
        if admin_fee_percentage > Decimal('1'):
            admin_fee_percentage = admin_fee_percentage / Decimal('100')
    
    # Format row data with comprehensive breakdown focusing on tenant-specific values
    result = {
        # Basic tenant information
        'tenant_id': tenant_id,
        'tenant_name': tenant_name,
        'property_id': property_id,
        'property_name': property_name,
        'suite': billing_result.get('suite', ''),
        'lease_start': billing_result.get('lease_start', ''),
        'lease_end': billing_result.get('lease_end', ''),
        
        # Share method information
        'share_method': share_method,
        'share_percentage': f"{float(share_percentage) * 100:.4f}%",
        
        # Property grand total (all GL accounts before tenant share)
        'property_gl_total': format_currency(property_gl_total),
        
        # Tenant expense breakdown
        'cam_total': format_currency(billing_result.get('tenant_share_base', Decimal('0'))),
        'ret_total': format_currency(Decimal('0')),  # Zero for CAM-only reconciliation
        'admin_fee_base': format_currency(
            property_gl_total  # This is the total property GL amount
        ),
        'admin_fee': format_currency(
            property_gl_total * admin_fee_percentage  # Property total × admin fee %
        ),
        'tenant_admin_fee': format_currency(
            property_gl_total * admin_fee_percentage * share_percentage  # Tenant's share of property admin fee
        ),
        'admin_fee_percentage': (
            f"{float(billing_result.get('cam_tax_admin_results', {}).get('admin_fee_percentage', Decimal('0'))) * 100:.1f}%" 
            if billing_result.get('cam_tax_admin_results', {}).get('admin_fee_percentage') 
            else f"{Decimal(str(settings.get('settings', {}).get('admin_fee_percentage', '0') or '0')) * 100:.1f}%" 
            if settings.get('settings', {}).get('admin_fee_percentage') 
            else "0.0%"
        ),
        'recoverable_subtotal': format_currency(billing_result.get('tenant_share_base', Decimal('0'))),
        
        # Base year adjustment details
        'base_year': base_year_results.get('base_year', ''),
        'base_year_amount': format_currency(base_year_results.get('base_year_amount', 0)),
        'total_before_base_adjustment': format_currency(base_year_results.get('total_before_adjustment', 0)),
        'amount_after_base': format_currency(base_year_results.get('after_base_adjustment', 0)),
        
        # Cap limit details - now with improved cap breakdown
        'cap_type': cap_limit_results.get('cap_type', ''),
        'cap_percentage': f"{Decimal(str(cap_limit_results.get('cap_percentage', '0'))) * 100:.2f}%" if cap_limit_results.get('cap_percentage') else '',
        'cap_reference_amount': format_currency(cap_limit_results.get('reference_amount', Decimal('0'))),
        'cap_limit': format_currency(cap_limit_results.get('effective_cap_limit', Decimal('0'))),
        'cap_limited': "Yes" if cap_results.get('cap_limited') else "No",
        'amount_subject_to_cap': format_currency(cap_results.get('amount_subject_to_cap', Decimal('0'))),
        'capped_subject_amount': format_currency(cap_results.get('capped_subject_amount', Decimal('0'))),
        'excluded_amount': format_currency(cap_results.get('excluded_amount', Decimal('0'))),
        'amount_before_cap': format_currency(cap_results.get('amount_subject_to_cap', Decimal('0')) + cap_results.get('excluded_amount', Decimal('0'))),
        'amount_after_cap': format_currency(cap_results.get('final_capped_amount', Decimal('0'))),
        'cap_override_year': settings.get('settings', {}).get('cap_settings', {}).get('override_cap_year', ''),
        'cap_override_amount': format_currency(Decimal(str(settings.get('settings', {}).get('cap_settings', {}).get('override_cap_amount', '0') or '0'))),
        
        # Occupancy statistics
        'occupied_months': occupied_months,
        'full_months': full_months,
        'partial_months': partial_months,
        'average_occupancy': f"{float(avg_occupancy):.4f}",
        'occupancy_adjusted': format_currency(base_billing),
        
        # Override and final amounts
        'has_override': "Yes" if billing_result.get('has_override') else "No",
        'override_amount': format_currency(override_amount),
        'final_billing': format_currency(final_billing),
        
        # Reconciliation year detail 
        'recon_base_billing': format_currency(billing_result.get('recon_base_billing', Decimal('0'))),
        'recon_final_billing': format_currency(billing_result.get('recon_final_billing', Decimal('0'))),
        'recon_period_paid': format_currency(billing_result.get('recon_period_paid', Decimal('0'))),
        'recon_outstanding': format_currency(billing_result.get('recon_outstanding', Decimal('0'))),
        
        # Catchup period detail
        'catchup_base_billing': format_currency(billing_result.get('catchup_base_billing', Decimal('0'))),
        'catchup_final_billing': format_currency(billing_result.get('catchup_final_billing', Decimal('0'))),
        'catchup_period_paid': format_currency(billing_result.get('catchup_period_paid', Decimal('0'))),
        'catchup_outstanding': format_currency(billing_result.get('catchup_outstanding', Decimal('0'))),
        
        # Total amounts
        'total_tenant_paid': format_currency(billing_result.get('total_tenant_paid', Decimal('0'))),
        'total_outstanding': format_currency(billing_result.get('total_outstanding', Decimal('0')))
    }
    
    # Add payment comparison data if available
    if payment_data:
        result.update({
            'old_monthly': format_currency(payment_data.get('old_monthly', 0)),
            'new_monthly': format_currency(payment_data.get('new_monthly', 0)),
            'monthly_difference': format_currency(payment_data.get('difference', 0)),
            'percentage_change': f"{float(payment_data.get('percentage_change', 0)):.1f}%",
            'change_type': payment_data.get('change_type', ''),
            'significant_change': "Yes" if payment_data.get('is_significant', False) else "No"
        })
    
    return result


def generate_csv_report(
    report_rows: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> str:
    """
    Generate a CSV report from tenant billing results.
    
    Args:
        report_rows: List of report rows
        output_path: Optional output path for CSV file
        
    Returns:
        Path to the generated CSV file
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(REPORTS_PATH):
        os.makedirs(REPORTS_PATH)
    
    # Generate default output path if not provided
    if not output_path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(REPORTS_PATH, f"tenant_billing_report_{timestamp}.csv")
    
    # Define columns for the report - now focusing on tenant-specific details
    columns = [
        # Basic tenant information
        'tenant_id', 'tenant_name', 'property_id', 'property_name', 'suite',
        'lease_start', 'lease_end', 'share_method', 'share_percentage',
        
        # Property totals before tenant share
        'property_gl_total',
        
        # Tenant expense breakdown
        'cam_total', 'ret_total', 'admin_fee_base', 'admin_fee',
        'tenant_admin_fee', 'admin_fee_percentage', 'recoverable_subtotal',
        
        # Base year details
        'base_year', 'base_year_amount', 
        'total_before_base_adjustment', 'amount_after_base',
        
        # Cap limit details - with detailed breakdown
        'cap_type', 'cap_percentage', 'cap_reference_amount', 
        'cap_limit', 'cap_limited', 'amount_subject_to_cap', 'capped_subject_amount',
        'excluded_amount', 'amount_before_cap', 'amount_after_cap',
        'cap_override_year', 'cap_override_amount',
        
        # Occupancy adjustments
        'occupied_months', 'full_months', 'partial_months', 'average_occupancy',
        'occupancy_adjusted',
        
        # Final calculation
        'has_override', 'override_amount', 'final_billing',
        
        # Reconciliation year details
        'recon_base_billing', 'recon_final_billing', 'recon_period_paid', 'recon_outstanding',
        
        # Catchup period details
        'catchup_base_billing', 'catchup_final_billing', 'catchup_period_paid', 'catchup_outstanding',
        
        # Total tenant payments and outstanding amounts
        'total_tenant_paid', 'total_outstanding',
        
        # Payment comparison columns
        'old_monthly', 'new_monthly', 'monthly_difference', 'percentage_change',
        'change_type', 'significant_change'
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
    output_path: Optional[str] = None
) -> str:
    """
    Generate a detailed JSON report from tenant billing results.
    
    Args:
        billing_results: List of tenant billing calculation results
        output_path: Optional output path for JSON file
        
    Returns:
        Path to the generated JSON file
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(REPORTS_PATH):
        os.makedirs(REPORTS_PATH)
    
    # Generate default output path if not provided
    if not output_path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(REPORTS_PATH, f"tenant_billing_detail_{timestamp}.json")
    
    # Prepare data for serialization
    # Convert all Decimal values to strings to ensure proper JSON serialization
    serializable_results = []
    
    for result in billing_results:
        serializable_result = {}
        
        for key, value in result.items():
            if isinstance(value, Decimal):
                serializable_result[key] = str(value)
            elif isinstance(value, dict) and any(isinstance(v, Decimal) for v in value.values()):
                # Handle nested dictionaries with Decimal values
                serializable_result[key] = {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in value.items()
                }
            else:
                serializable_result[key] = value
        
        serializable_results.append(serializable_result)
    
    # Write the JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Generated detailed JSON report with {len(billing_results)} entries: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating JSON report: {str(e)}")
        return ""


def generate_reports(
    property_settings: Dict[str, Any],
    tenant_settings_list: List[Dict[str, Any]],
    reconciliation_results: Dict[str, Any],
    periods: List[str]
) -> Dict[str, Any]:
    """
    Generate tenant billing reports for a property.
    
    Args:
        property_settings: Property settings dictionary
        tenant_settings_list: List of tenant settings dictionaries
        reconciliation_results: Reconciliation calculation results
        periods: List of periods for the report
        
    Returns:
        Dictionary with report generation results
    """
    # Get property recoverable amount and categories from reconciliation results
    property_recoverable = reconciliation_results.get('final_recoverable_amount', Decimal('0'))
    
    # Get categories if present in reconciliation_results
    categories = reconciliation_results.get('categories', [])
    
    # Get tenant-specific results if they exist 
    tenant_results = reconciliation_results.get('tenant_results', [])
    logger.info(f"Found {len(tenant_results)} tenant-specific results in reconciliation_results")
    
    # Calculate tenant billing for each tenant
    billing_results = []
    
    for i, tenant_settings in enumerate(tenant_settings_list):
        # Create a property_recoverable dictionary if it's not already one
        if not isinstance(property_recoverable, dict):
            prop_recoverable_dict = {
                'final_recoverable_amount': property_recoverable,
                'categories': categories
            }
        else:
            prop_recoverable_dict = property_recoverable
            if 'categories' not in prop_recoverable_dict:
                prop_recoverable_dict['categories'] = categories
                
        # Get property GL totals if available
        if 'property_gl_totals' in prop_recoverable_dict:
            property_gl_totals = prop_recoverable_dict.get('property_gl_totals', {})
        else:
            property_gl_totals = {}
        
        # If we have tenant-specific results, use the tenant's data
        tenant_specific_amount = None
        if 'tenant_results' in reconciliation_results and len(reconciliation_results.get('tenant_results', [])) > i:
            tenant_result = reconciliation_results['tenant_results'][i]
            
            # Extract tenant's CAM/TAX/Admin results
            tenant_cam_tax_admin_results = tenant_result.get('cam_tax_admin_results', {})
            
            # Extract tenant's final recoverable amount
            tenant_specific_amount = tenant_result.get('final_recoverable_amount')
            
            # Extract tenant's cap results
            tenant_cap_results = tenant_result.get('cap_results', {})
            
            # Only use tenant-specific amount if it's not zero
            if tenant_specific_amount and tenant_specific_amount > 0:
                logger.info(f"Using tenant-specific recoverable amount: {tenant_specific_amount}")
                prop_recoverable_dict['final_recoverable_amount'] = tenant_specific_amount
            
            # Add all tenant-specific data to prop_recoverable_dict
            prop_recoverable_dict['cam_tax_admin_results'] = tenant_cam_tax_admin_results
            prop_recoverable_dict['cap_results'] = tenant_cap_results
            
            # Log the data we're passing
            logger.info(f"Adding tenant-specific cam_tax_admin_results to billing data: {tenant_cam_tax_admin_results}")
            if tenant_cap_results:
                cap_type = tenant_cap_results.get('cap_limit_results', {}).get('cap_type', 'None')
                cap_percentage = tenant_cap_results.get('cap_limit_results', {}).get('cap_percentage', 'None')
                logger.info(f"Adding tenant-specific cap_results: cap_type={cap_type}, cap_percentage={cap_percentage}")
            
        # Get periods_dict from tenant_result if available
        periods_dict = None
        if 'tenant_results' in reconciliation_results and len(reconciliation_results.get('tenant_results', [])) > i:
            periods_dict = reconciliation_results['tenant_results'][i].get('periods')
            logger.info(f"Found periods data: {len(periods_dict.get('recon_periods', []))} recon periods, {len(periods_dict.get('catchup_periods', []))} catchup periods")
        
        billing_result = calculate_tenant_billing(
            tenant_settings,
            property_settings,
            prop_recoverable_dict,
            periods,
            periods_dict=periods_dict
        )
        
        # Add property GL totals to the billing result
        property_gl_totals_dict = {
            'cam_total': prop_recoverable_dict.get('property_gl_totals', {}).get('cam_total', Decimal('0')), 
            'ret_total': prop_recoverable_dict.get('property_gl_totals', {}).get('ret_total', Decimal('0')),
            'admin_fee_base': prop_recoverable_dict.get('property_gl_totals', {}).get('admin_fee_base', Decimal('0'))
        }
        
        # Log what we're actually storing
        logger.info(f"Property GL totals from property_recoverable: CAM={property_gl_totals_dict['cam_total']}, RET={property_gl_totals_dict['ret_total']}, admin_fee_base={property_gl_totals_dict['admin_fee_base']}")
        
        billing_result['property_gl_totals'] = property_gl_totals_dict
        
        # Debug property GL totals
        logger.info(f"Property GL totals being added to billing result: CAM={property_gl_totals_dict['cam_total']}, RET={property_gl_totals_dict['ret_total']}")
        billing_results.append(billing_result)
    
    # Generate report rows from billing results, matching with tenant settings
    report_rows = []
    for i, result in enumerate(billing_results):
        # Get corresponding tenant settings if available
        tenant_setting = tenant_settings_list[i] if i < len(tenant_settings_list) else None
        report_rows.append(generate_report_row(result, tenant_setting))
    
    # Generate CSV report
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    property_id = property_settings.get('property_id', '')
    
    # Use categories from reconciliation_results directly
    # If not in reconciliation_results, try to get them from billing results
    if not categories:
        for result in billing_results:
            if 'categories' in result:
                categories = result.get('categories', [])
                break
    
    # Create category string for filename
    category_str = "_".join(categories) if categories else "all"
    
    csv_path = os.path.join(
        REPORTS_PATH, 
        f"tenant_billing_{property_id}_{category_str}_{timestamp}.csv"
    )
    csv_output = generate_csv_report(report_rows, csv_path)
    
    # Generate detailed JSON report
    json_path = os.path.join(
        REPORTS_PATH, 
        f"tenant_billing_detail_{property_id}_{category_str}_{timestamp}.json"
    )
    json_output = generate_json_report(billing_results, json_path)
    
    # Return report generation results
    return {
        'property_id': property_id,
        'tenant_count': len(billing_results),
        'total_billed': sum(result.get('final_billing', Decimal('0')) for result in billing_results),
        'billing_results': billing_results,
        'csv_report_path': csv_output,
        'json_report_path': json_output
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    mock_property_settings = {
        'property_id': 'PROP123',
        'name': 'Example Property',
        'total_rsf': 100000
    }
    
    mock_tenant_settings_list = [
        {
            'tenant_id': '1001',
            'tenant_name': 'Tenant A',
            'lease_start': '01/01/2023',
            'lease_end': '12/31/2025',
            'suite': 'A-100',
            'settings': {
                'prorate_share_method': 'RSF',
                'square_footage': 5000  # 5% of property
            }
        },
        {
            'tenant_id': '1002',
            'tenant_name': 'Tenant B',
            'lease_start': '03/15/2024',
            'lease_end': '03/14/2026',
            'suite': 'B-200',
            'settings': {
                'prorate_share_method': 'Fixed',
                'fixed_pyc_share': '10.5'  # 10.5%
            }
        }
    ]
    
    mock_reconciliation_results = {
        'final_recoverable_amount': Decimal('120000.00')
    }
    
    # Example periods (2024 full year)
    example_periods = []
    for month in range(1, 13):
        example_periods.append(f"2024{month:02d}")
    
    # Generate reports
    result = generate_reports(
        mock_property_settings,
        mock_tenant_settings_list,
        mock_reconciliation_results,
        example_periods
    )
    
    # Print summary
    print("\nReport Generation Results:")
    print(f"Property: {mock_property_settings['name']} (ID: {mock_property_settings['property_id']})")
    print(f"Tenants: {result['tenant_count']}")
    print(f"Total Billed: {format_currency(result['total_billed'])}")
    print(f"CSV Report: {result['csv_report_path']}")
    print(f"JSON Report: {result['json_report_path']}")
    
    # Print tenant billing summary
    print("\nTenant Billing Summary:")
    for i, billing_result in enumerate(result['billing_results']):
        print(f"{i+1}. {billing_result['tenant_name']} (ID: {billing_result['tenant_id']})")
        print(f"   Share: {float(billing_result['share_percentage'])*100:.2f}% ({billing_result['share_method']})")
        print(f"   Lease: {billing_result['lease_start']} to {billing_result['lease_end']}")
        print(f"   Base Amount: {format_currency(billing_result['base_billing'])}")
        
        if billing_result['has_override']:
            print(f"   Override: {format_currency(billing_result['override_amount'])}")
            
        print(f"   Final Billing: {format_currency(billing_result['final_billing'])}")