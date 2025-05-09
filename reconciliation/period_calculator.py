#!/usr/bin/env python3
"""
Period Calculator Module

This module calculates the reconciliation periods for a given year and last billing date.
It handles both reconciliation periods and catch-up periods.
"""

import logging
import datetime
from typing import List, Optional, Dict, Any, Union
from dateutil.relativedelta import relativedelta

from reconciliation.utils.helpers import parse_period

# Configure logging
logger = logging.getLogger(__name__)


def generate_recon_periods(recon_year: Union[str, int]) -> List[str]:
    """
    Generate reconciliation periods for a given year (January through December).
    
    Args:
        recon_year: Reconciliation year
        
    Returns:
        List of periods in YYYYMM format
    """
    # Convert recon_year to int if it's a string
    try:
        year = int(recon_year)
    except (ValueError, TypeError):
        logger.error(f"Invalid reconciliation year: {recon_year}")
        return []
    
    # Generate periods for all months in the reconciliation year
    periods = []
    for month in range(1, 13):
        periods.append(f"{year}{month:02d}")
    
    logger.info(f"Generated {len(periods)} reconciliation periods for year {year}")
    return periods


def generate_catchup_periods(
    recon_year: Union[str, int], 
    last_bill_date: str
) -> List[str]:
    """
    Generate catch-up periods from January of the year after reconciliation
    through the last billing date.
    
    Args:
        recon_year: Reconciliation year
        last_bill_date: Last billing date in YYYYMM format
        
    Returns:
        List of periods in YYYYMM format
    """
    # Parse the inputs
    try:
        year = int(recon_year)
        last_date = parse_period(last_bill_date)
        
        if not last_date:
            logger.error(f"Invalid last billing date format: {last_bill_date}")
            return []
        
        # If last_bill_date is within or before the reconciliation year, 
        # there are no catch-up periods
        if last_date.year <= year:
            logger.info("Last billing date is within or before reconciliation year, no catch-up periods")
            return []
    except (ValueError, TypeError):
        logger.error(f"Invalid input: recon_year={recon_year}, last_bill_date={last_bill_date}")
        return []
    
    # Start from January of the year after reconciliation
    start_date = datetime.date(year + 1, 1, 1)
    
    # Generate periods from start_date through last_date
    periods = []
    current_date = start_date
    
    while current_date <= last_date:
        periods.append(current_date.strftime("%Y%m"))
        
        # Move to next month
        current_date += relativedelta(months=1)
    
    logger.info(f"Generated {len(periods)} catch-up periods from {start_date.strftime('%Y%m')} to {last_bill_date}")
    return periods


def calculate_periods(
    recon_year: Union[str, int], 
    last_bill_date: Optional[str] = None
) -> Dict[str, List[str]]:
    """
    Calculate reconciliation and catch-up periods.
    
    Args:
        recon_year: Reconciliation year
        last_bill_date: Optional last billing date in YYYYMM format
        
    Returns:
        Dictionary with 'recon_periods', 'catchup_periods', and 'full_period'
    """
    # Generate reconciliation periods
    recon_periods = generate_recon_periods(recon_year)
    
    # Generate catch-up periods if last_bill_date is provided
    catchup_periods = []
    if last_bill_date:
        catchup_periods = generate_catchup_periods(recon_year, last_bill_date)
    
    # Combine recon and catch-up periods for the full period
    full_period = recon_periods + [p for p in catchup_periods if p not in recon_periods]
    
    return {
        'recon_periods': recon_periods,
        'catchup_periods': catchup_periods,
        'full_period': full_period
    }


def get_period_info(period: str) -> Dict[str, Any]:
    """
    Get detailed information about a period.
    
    Args:
        period: Period in YYYYMM format
        
    Returns:
        Dictionary with period information (year, month, days, etc.)
    """
    period_date = parse_period(period)
    
    if not period_date:
        return {
            'valid': False,
            'period': period
        }
    
    # Calculate the last day of the month
    next_month = period_date.replace(day=28) + datetime.timedelta(days=4)
    last_day = next_month - datetime.timedelta(days=next_month.day)
    
    # Get month name
    month_name = period_date.strftime("%B")
    
    return {
        'valid': True,
        'period': period,
        'year': period_date.year,
        'month': period_date.month,
        'month_name': month_name,
        'days_in_month': last_day.day,
        'first_day': period_date,
        'last_day': last_day
    }


def get_detailed_periods(periods: List[str]) -> List[Dict[str, Any]]:
    """
    Get detailed information for a list of periods.
    
    Args:
        periods: List of periods in YYYYMM format
        
    Returns:
        List of dictionaries with period information
    """
    return [get_period_info(period) for period in periods]


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Get command line arguments
    recon_year = 2024
    last_bill_date = "202505"  # May 2025
    
    if len(sys.argv) > 1:
        recon_year = sys.argv[1]
    
    if len(sys.argv) > 2:
        last_bill_date = sys.argv[2]
    
    # Calculate periods
    periods = calculate_periods(recon_year, last_bill_date)
    
    # Print results
    print("\nPeriod Calculation Results:")
    print(f"Reconciliation Year: {recon_year}")
    print(f"Last Bill Date: {last_bill_date}")
    
    print("\nReconciliation Periods:")
    for period in periods['recon_periods']:
        info = get_period_info(period)
        if info['valid']:
            print(f"- {info['month_name']} {info['year']} ({info['days_in_month']} days)")
    
    print("\nCatch-up Periods:")
    if periods['catchup_periods']:
        for period in periods['catchup_periods']:
            info = get_period_info(period)
            if info['valid']:
                print(f"- {info['month_name']} {info['year']} ({info['days_in_month']} days)")
    else:
        print("- None")
    
    print(f"\nTotal periods: {len(periods['full_period'])}")