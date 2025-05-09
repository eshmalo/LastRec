#!/usr/bin/env python3
"""
Capital Expenses Calculation Module (Stub)

This module is a stub for future implementation of capital expense amortization.
It provides placeholder functions that will be fully implemented in the future.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


def merge_capital_expenses(
    property_capital_expenses: List[Dict[str, Any]],
    tenant_capital_expenses: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge property and tenant capital expenses.
    
    This function merges two lists of capital expenses, with tenant-specific
    expenses taking precedence if there are duplicates (by id).
    
    Args:
        property_capital_expenses: List of property-level capital expenses
        tenant_capital_expenses: List of tenant-specific capital expenses
        
    Returns:
        Merged list of capital expenses
    """
    # Create a dictionary of property expenses by id
    property_expenses_dict = {
        expense.get('id'): expense 
        for expense in property_capital_expenses 
        if expense.get('id')
    }
    
    # Create a dictionary of tenant expenses by id
    tenant_expenses_dict = {
        expense.get('id'): expense 
        for expense in tenant_capital_expenses 
        if expense.get('id')
    }
    
    # Merge the dictionaries, with tenant expenses taking precedence
    merged_dict = {**property_expenses_dict, **tenant_expenses_dict}
    
    # Convert back to a list
    merged_expenses = list(merged_dict.values())
    
    # Filter out any items with empty id, description, or amount
    filtered_expenses = [
        expense for expense in merged_expenses
        if expense.get('id') and expense.get('description') and expense.get('amount')
    ]
    
    logger.info(f"Merged capital expenses: {len(filtered_expenses)} items")
    
    return filtered_expenses


def calculate_amortized_amount(
    expense: Dict[str, Any],
    current_year: int,
    periods: Optional[List[str]] = None,
    tenant_settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate the amortized amount for a capital expense in the current year.
    
    Args:
        expense: Capital expense dictionary
        current_year: Current reconciliation year
        periods: Optional list of periods (months) for proration
        tenant_settings: Optional tenant settings for occupancy calculation
        
    Returns:
        Dictionary with amortized amount information
    """
    try:
        expense_year = int(expense.get('year', 0))
        expense_amount = Decimal(str(expense.get('amount', 0)))
        amort_years = int(expense.get('amort_years', 1))
        
        # If amortization period is invalid, default to 1 year
        if amort_years < 1:
            amort_years = 1
        
        # Check if expense applies to current year
        if expense_year > current_year or expense_year + amort_years <= current_year:
            return {
                'description': expense.get('description', ''),
                'annual_amount': Decimal('0'),
                'prorated_amount': Decimal('0'),
                'applicable': False
            }
        
        # Calculate the annual amortized amount
        annual_amount = expense_amount / Decimal(amort_years)
        prorated_amount = annual_amount
        
        # If periods and tenant settings provided, calculate occupancy-adjusted amount
        if periods and tenant_settings and len(periods) > 0:
            lease_start = tenant_settings.get('lease_start')
            lease_end = tenant_settings.get('lease_end')
            
            # Import here to avoid circular imports
            from reconciliation.occupancy_calculator import calculate_occupancy_factors
            
            # Calculate occupancy factors
            occupancy_factors = calculate_occupancy_factors(periods, lease_start, lease_end)
            
            # Calculate average occupancy factor
            if occupancy_factors:
                avg_occupancy = sum(occupancy_factors.values()) / Decimal(len(periods))
                prorated_amount = annual_amount * avg_occupancy
                logger.info(f"Prorated capital expense '{expense.get('description')}' by occupancy factor {float(avg_occupancy):.4f}: "
                          f"{float(annual_amount)} → {float(prorated_amount)}")
        
        return {
            'id': expense.get('id', ''),
            'description': expense.get('description', ''),
            'year': expense_year,
            'amount': expense_amount,
            'amort_years': amort_years,
            'annual_amount': annual_amount,
            'prorated_amount': prorated_amount,
            'applicable': True
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid capital expense data: {expense} - {str(e)}")
        return {
            'description': expense.get('description', ''),
            'annual_amount': Decimal('0'),
            'prorated_amount': Decimal('0'),
            'applicable': False,
            'error': str(e)
        }


def calculate_capital_expenses(
    settings: Dict[str, Any],
    recon_year: Union[str, int],
    periods: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Calculate amortized capital expenses for the reconciliation.
    
    Args:
        settings: Settings dictionary with capital expenses data
        recon_year: Current reconciliation year
        periods: Optional list of periods for occupancy proration
        
    Returns:
        Dictionary with capital expense calculation results
    """
    # Convert recon_year to int if it's a string
    try:
        recon_year_int = int(recon_year)
    except (ValueError, TypeError):
        logger.error(f"Invalid reconciliation year: {recon_year}")
        return {
            'capital_expenses': [],
            'total_capital_expenses': Decimal('0')
        }
    
    # Get capital expenses from settings
    # First try tenant-specific capital_expenses, then fall back to property_capital_expenses if no tenant-specific ones exist
    property_expenses = settings.get('property_capital_expenses', [])
    
    # Check for tenant capital expenses (supporting both field names)
    tenant_expenses = settings.get('capital_expenses', [])
    if not tenant_expenses and 'property_capital_expenses' in settings:
        # If tenant JSON uses property_capital_expenses field instead of capital_expenses, use that
        tenant_expenses = settings.get('property_capital_expenses', [])
    
    # Log the expenses found
    logger.info(f"Found {len(property_expenses)} property capital expenses and {len(tenant_expenses)} tenant capital expenses")
    
    # Merge property and tenant expenses
    merged_expenses = merge_capital_expenses(property_expenses, tenant_expenses)
    
    # Calculate amortized amount for each expense
    amortized_expenses = []
    total_amount = Decimal('0')
    
    for expense in merged_expenses:
        # Calculate amortized amount with proration if periods are provided
        amortization_result = calculate_amortized_amount(
            expense, 
            recon_year_int,
            periods,
            settings if 'tenant_id' in settings else None  # Only pass tenant settings if this is a tenant
        )
        
        if amortization_result.get('applicable', False):
            # Get the prorated amount if it exists, otherwise use the annual amount
            amortized_amount = amortization_result.get('prorated_amount', Decimal('0'))
            
            # Add to the list if there's an actual amount
            if amortized_amount > 0:
                amortized_expenses.append(amortization_result)
                total_amount += amortized_amount
    
    logger.info(f"Calculated capital expenses: {len(amortized_expenses)} items, total: {total_amount}")
    
    return {
        'capital_expenses': amortized_expenses,
        'total_capital_expenses': total_amount
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    recon_year = 2024
    
    mock_settings = {
        'property_capital_expenses': [
            {
                'id': 'CAP001',
                'description': 'Roof repair',
                'year': 2022,
                'amount': 50000,
                'amort_years': 5
            },
            {
                'id': 'CAP002',
                'description': 'Parking lot resurfacing',
                'year': 2023,
                'amount': 30000,
                'amort_years': 3
            }
        ],
        'capital_expenses': [
            {
                'id': 'CAP003',
                'description': 'Tenant-specific improvement',
                'year': 2023,
                'amount': 10000,
                'amort_years': 2
            },
            {
                'id': 'CAP001',  # Same ID as property expense, should override
                'description': 'Roof repair (tenant override)',
                'year': 2022,
                'amount': 5000,  # Tenant's share only
                'amort_years': 5
            }
        ]
    }
    
    # Calculate capital expenses
    result = calculate_capital_expenses(mock_settings, recon_year)
    
    # Print results
    print("\nCapital Expense Calculation Results:")
    print(f"Total Capital Expenses: ${float(result.get('total_capital_expenses', 0)):,.2f}")
    print("\nAmortized Expenses:")
    
    for expense in result.get('capital_expenses', []):
        print(f"- {expense.get('description')}: ${float(expense.get('amortized_amount', 0)):,.2f}/year "
              f"(${float(expense.get('amount', 0)):,.2f} over {expense.get('amort_years')} years, "
              f"started in {expense.get('year')})")