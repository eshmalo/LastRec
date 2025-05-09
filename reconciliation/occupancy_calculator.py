#!/usr/bin/env python3
"""
Occupancy Calculator Module

This module calculates tenant occupancy factors for each period based on
lease start and end dates. It handles full and partial occupancy periods.
"""

import logging
import datetime
import calendar
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union

from reconciliation.utils.helpers import parse_date
from reconciliation.period_calculator import get_period_info

# Configure logging
logger = logging.getLogger(__name__)


def parse_lease_dates(
    lease_start: Optional[str], 
    lease_end: Optional[str]
) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
    """
    Parse lease start and end dates from string format.
    
    Args:
        lease_start: Lease start date string in MM/DD/YYYY or YYYY-MM-DD format
        lease_end: Lease end date string in MM/DD/YYYY or YYYY-MM-DD format
        
    Returns:
        Tuple of (start_date, end_date) as datetime.date objects or None
    """
    start_date = parse_date(lease_start) if lease_start else None
    end_date = parse_date(lease_end) if lease_end else None
    
    # Log warnings for invalid dates
    if lease_start and not start_date:
        logger.warning(f"Invalid lease start date format: {lease_start}")
    
    if lease_end and not end_date:
        logger.warning(f"Invalid lease end date format: {lease_end}")
    
    return start_date, end_date


def calculate_overlap_days(
    period: str,
    start_date: Optional[datetime.date],
    end_date: Optional[datetime.date]
) -> int:
    """
    Calculate the number of days in a period that overlap with lease dates.
    
    Args:
        period: Period in YYYYMM format
        start_date: Lease start date
        end_date: Lease end date
        
    Returns:
        Number of days that overlap with lease term
    """
    # Get period information
    period_info = get_period_info(period)
    
    if not period_info['valid']:
        logger.error(f"Invalid period format: {period}")
        return 0
    
    # Get first and last day of the period
    period_start = period_info['first_day']
    period_end = period_info['last_day']
    
    # If no lease dates provided, assume full occupancy
    if not start_date and not end_date:
        return period_info['days_in_month']
    
    # If only end date is provided, assume start before period
    if not start_date:
        start_date = datetime.date(1900, 1, 1)  # Use very early date
    
    # If only start date is provided, assume end after period
    if not end_date:
        end_date = datetime.date(2100, 12, 31)  # Use very future date
    
    # Check if lease period completely outside of period
    if end_date < period_start or start_date > period_end:
        return 0
    
    # Calculate actual first day of overlap
    overlap_start = max(start_date, period_start)
    
    # Calculate actual last day of overlap
    overlap_end = min(end_date, period_end)
    
    # Calculate number of days in overlap
    overlap_days = (overlap_end - overlap_start).days + 1
    
    return overlap_days


def calculate_occupancy_factor(
    period: str,
    start_date: Optional[datetime.date],
    end_date: Optional[datetime.date]
) -> Decimal:
    """
    Calculate occupancy factor for a single period.
    
    Args:
        period: Period in YYYYMM format
        start_date: Lease start date
        end_date: Lease end date
        
    Returns:
        Occupancy factor as Decimal (0.0 to 1.0)
    """
    # Get period information
    period_info = get_period_info(period)
    
    if not period_info['valid']:
        logger.error(f"Invalid period format: {period}")
        return Decimal('0')
    
    # Calculate days of overlap
    overlap_days = calculate_overlap_days(period, start_date, end_date)
    
    # Calculate occupancy factor
    days_in_month = period_info['days_in_month']
    factor = Decimal(overlap_days) / Decimal(days_in_month)
    
    return factor


def calculate_occupancy_factors(
    periods: List[str],
    lease_start: Optional[str] = None,
    lease_end: Optional[str] = None
) -> Dict[str, Decimal]:
    """
    Calculate occupancy factors for a list of periods.
    
    Args:
        periods: List of periods in YYYYMM format
        lease_start: Lease start date string
        lease_end: Lease end date string
        
    Returns:
        Dictionary mapping periods to occupancy factors
    """
    # Parse lease dates
    start_date, end_date = parse_lease_dates(lease_start, lease_end)
    
    # Calculate factors for each period
    factors = {}
    
    for period in periods:
        factor = calculate_occupancy_factor(period, start_date, end_date)
        factors[period] = factor
    
    # Log summary
    occupied_months = sum(1 for f in factors.values() if f > 0)
    full_months = sum(1 for f in factors.values() if f >= Decimal('1'))
    partial_months = sum(1 for f in factors.values() if Decimal('0') < f < Decimal('1'))
    
    logger.info(
        f"Calculated occupancy factors: {len(periods)} periods, "
        f"{occupied_months} occupied, {full_months} full, {partial_months} partial"
    )
    
    return factors


def calculate_weighted_factor(
    factors: Dict[str, Decimal],
    weights: Optional[Dict[str, Decimal]] = None
) -> Decimal:
    """
    Calculate weighted average occupancy factor.
    
    Args:
        factors: Dictionary mapping periods to occupancy factors
        weights: Optional dictionary mapping periods to weights
        
    Returns:
        Weighted average factor as Decimal
    """
    if not factors:
        return Decimal('0')
    
    # If no weights provided, use equal weights
    if not weights:
        weights = {period: Decimal('1') for period in factors}
    
    # Calculate weighted sum
    weighted_sum = sum(factors.get(period, Decimal('0')) * weights.get(period, Decimal('0')) 
                       for period in set(factors) & set(weights))
    
    # Calculate sum of weights
    total_weight = sum(weights.get(period, Decimal('0')) for period in set(factors) & set(weights))
    
    # Avoid division by zero
    if total_weight == 0:
        return Decimal('0')
    
    return weighted_sum / total_weight


def calculate_occupancy(
    tenant_settings: Dict[str, Any],
    periods: List[str]
) -> Dict[str, Any]:
    """
    Main function to calculate tenant occupancy.
    
    Args:
        tenant_settings: Settings dictionary with lease dates
        periods: List of periods in YYYYMM format
        
    Returns:
        Dictionary with occupancy calculation results
    """
    # Get lease dates from tenant settings
    lease_start = tenant_settings.get('lease_start')
    lease_end = tenant_settings.get('lease_end')
    
    # Calculate occupancy factors
    factors = calculate_occupancy_factors(periods, lease_start, lease_end)
    
    # Calculate weighted average factor (equal weights)
    avg_factor = calculate_weighted_factor(factors)
    
    # Return comprehensive results
    return {
        'tenant_id': tenant_settings.get('tenant_id'),
        'tenant_name': tenant_settings.get('tenant_name', ''),
        'lease_start': lease_start,
        'lease_end': lease_end,
        'periods': periods,
        'occupancy_factors': factors,
        'average_factor': avg_factor
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    mock_tenant = {
        'tenant_id': '1234',
        'tenant_name': 'Example Tenant',
        'lease_start': '04/15/2024',  # Mid-April 2024
        'lease_end': '06/20/2025'     # Mid-June 2025
    }
    
    # Example periods (Jan 2024 through Dec 2025)
    example_periods = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            example_periods.append(f"{year}{month:02d}")
    
    # Calculate occupancy
    result = calculate_occupancy(mock_tenant, example_periods)
    
    # Print results
    print("\nOccupancy Calculation Results:")
    print(f"Tenant: {result['tenant_name']} (ID: {result['tenant_id']})")
    print(f"Lease Period: {result['lease_start']} to {result['lease_end']}")
    print(f"Average Occupancy Factor: {float(result['average_factor']):.4f}")
    
    print("\nMonthly Occupancy Factors:")
    for period in result['periods']:
        factor = result['occupancy_factors'].get(period, Decimal('0'))
        period_info = get_period_info(period)
        
        if period_info['valid']:
            print(f"- {period_info['month_name']} {period_info['year']}: {float(factor):.2f}")
    
    print("\nOccupancy Summary:")
    print(f"Full Months: {sum(1 for f in result['occupancy_factors'].values() if f >= Decimal('1'))}")
    print(f"Partial Months: {sum(1 for f in result['occupancy_factors'].values() if Decimal('0') < f < Decimal('1'))}")
    print(f"Unoccupied Months: {sum(1 for f in result['occupancy_factors'].values() if f == Decimal('0'))}")