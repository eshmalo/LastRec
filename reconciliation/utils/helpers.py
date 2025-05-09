#!/usr/bin/env python3
"""
Helper utilities for the CAM/TAX reconciliation system.

This module contains common utility functions used throughout the reconciliation process.
"""

import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dictionary containing the JSON file contents
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file isn't valid JSON
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        raise


def save_json(file_path: str, data: Any, indent: int = 2) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        file_path: Path where to save the JSON file
        data: Data to save (must be JSON serializable)
        indent: Number of spaces for indentation (default: 2)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False


def is_in_range(gl_account: str, account_range: str) -> bool:
    """
    Check if a GL account is within the specified range using numeric comparison.
    
    Args:
        gl_account: GL account number to check
        account_range: Range in format 'start-end'
        
    Returns:
        True if in range, False otherwise
    """
    try:
        start, end = account_range.split('-')
        
        # Remove any 'MR' prefix from all values for consistent comparison
        clean_account = gl_account.replace('MR', '')
        clean_start = start.replace('MR', '')
        clean_end = end.replace('MR', '')
        
        # Convert to integers for numeric comparison
        # Handle case where account might contain non-numeric characters
        try:
            numeric_account = int(clean_account)
            numeric_start = int(clean_start)
            numeric_end = int(clean_end)
            
            return numeric_start <= numeric_account <= numeric_end
        except ValueError:
            # If conversion fails, fall back to string comparison with warning
            logger.warning(f"Non-numeric GL account detected: {gl_account}. Using string comparison as fallback.")
            return clean_start <= clean_account <= clean_end
            
    except (ValueError, AttributeError):
        logger.error(f"Invalid account range format: {account_range}")
        return False


def parse_date(date_str: str) -> Optional[datetime.date]:
    """
    Parse a date string in various formats.
    
    Args:
        date_str: Date string in MM/DD/YYYY or YYYY-MM-DD format
        
    Returns:
        datetime.date object or None if parsing fails
    """
    if not date_str or date_str == "":
        return None
        
    formats = [
        "%m/%d/%Y",             # MM/DD/YYYY
        "%Y-%m-%d",             # YYYY-MM-DD
        "%m/%d/%Y %H:%M:%S %p"  # MM/DD/YYYY HH:MM:SS AM/PM
    ]
    
    for fmt in formats:
        try:
            # Try to parse with current format
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.date()
        except ValueError:
            continue
    
    logger.error(f"Could not parse date: {date_str}")
    return None


def format_currency(amount: Union[float, int, str]) -> str:
    """
    Format a number as currency.
    
    Args:
        amount: Amount to format
        
    Returns:
        Formatted currency string
    """
    try:
        # Convert to float if it's a string
        if isinstance(amount, str) and amount.strip():
            amount = float(amount)
        elif amount == "" or amount is None:
            return "$0.00"
            
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        logger.error(f"Invalid currency amount: {amount}")
        return "$0.00"


def get_month_name(month: int) -> str:
    """
    Get month name from month number.
    
    Args:
        month: Month number (1-12)
        
    Returns:
        Month name
    """
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    if 1 <= month <= 12:
        return months[month - 1]
    else:
        logger.error(f"Invalid month number: {month}")
        return ""


def parse_period(period_str: str) -> Optional[datetime.date]:
    """
    Parse a period string in YYYYMM format.
    
    Args:
        period_str: Period string in YYYYMM format
        
    Returns:
        datetime.date object with day set to 1, or None if parsing fails
    """
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


def generate_period_list(start_period: str, end_period: str) -> List[str]:
    """
    Generate a list of periods between start and end.
    
    Args:
        start_period: Start period in YYYYMM format
        end_period: End period in YYYYMM format
        
    Returns:
        List of periods in YYYYMM format
    """
    start_date = parse_period(start_period)
    end_date = parse_period(end_period)
    
    if not start_date or not end_date:
        return []
    
    if start_date > end_date:
        logger.error(f"Start period {start_period} is after end period {end_period}")
        return []
    
    periods = []
    current_date = start_date
    
    while current_date <= end_date:
        periods.append(current_date.strftime("%Y%m"))
        
        # Move to next month
        month = current_date.month
        year = current_date.year
        
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
            
        current_date = datetime.date(year, month, 1)
    
    return periods