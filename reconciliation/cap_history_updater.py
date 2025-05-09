#!/usr/bin/env python3
"""
Cap History Updater Module

This module updates the cap history with new reconciliation amounts.
It is used to maintain the historical record of recoverable amounts for cap calculations.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union

from reconciliation.cap_override_handler import load_cap_history, save_cap_history

# Configure logging
logger = logging.getLogger(__name__)


def update_tenant_cap_history(
    tenant_id: Union[str, int],
    recon_year: Union[str, int],
    recoverable_amount: Decimal,
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Update the cap history for a specific tenant and year.
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        recoverable_amount: Recoverable amount to record
        cap_history: Optional cap history dictionary
        
    Returns:
        Updated cap history dictionary
    """
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()
    
    # Convert tenant_id to string
    tenant_id_str = str(tenant_id)
    
    # Convert recon_year to string
    recon_year_str = str(recon_year)
    
    # Initialize tenant entry if it doesn't exist
    if tenant_id_str not in cap_history:
        cap_history[tenant_id_str] = {}
    
    # Convert Decimal to float for storage (JSON compatibility)
    float_amount = float(recoverable_amount)
    
    # Update the cap history
    cap_history[tenant_id_str][recon_year_str] = float_amount
    
    logger.info(
        f"Updated cap history for tenant {tenant_id_str}, year {recon_year_str}: {float_amount}"
    )
    
    return cap_history


def batch_update_cap_history(
    tenant_billing_results: List[Dict[str, Any]],
    recon_year: Union[str, int]
) -> Dict[str, Dict[str, float]]:
    """
    Update cap history for multiple tenants from billing results.
    
    Args:
        tenant_billing_results: List of tenant billing calculation results
        recon_year: Reconciliation year
        
    Returns:
        Updated cap history dictionary
    """
    # Load current cap history
    cap_history = load_cap_history()
    
    # Track tenants updated
    updated_tenants = []
    
    # Update cap history for each tenant
    for billing_result in tenant_billing_results:
        tenant_id = billing_result.get('tenant_id')
        
        if tenant_id is None:
            logger.warning("Skipping record with missing tenant_id")
            continue
        
        # Get the amount for cap history (base_billing, not including overrides)
        if 'base_billing' in billing_result:
            recoverable_amount = billing_result.get('base_billing', Decimal('0'))
        else:
            # If base_billing not available, use final_billing
            recoverable_amount = billing_result.get('final_billing', Decimal('0'))
        
        # Update cap history for this tenant
        cap_history = update_tenant_cap_history(
            tenant_id,
            recon_year,
            recoverable_amount,
            cap_history
        )
        
        updated_tenants.append(tenant_id)
    
    # Save the updated cap history
    if updated_tenants:
        save_cap_history(cap_history)
        logger.info(f"Updated cap history for {len(updated_tenants)} tenants")
    else:
        logger.warning("No tenants updated in cap history")
    
    return cap_history


def update_cap_history(
    tenant_billing_results: List[Dict[str, Any]],
    recon_year: Union[str, int]
) -> Dict[str, Any]:
    """
    Main function to update cap history after reconciliation.
    
    Args:
        tenant_billing_results: List of tenant billing calculation results
        recon_year: Reconciliation year
        
    Returns:
        Dictionary with update results
    """
    # Update cap history
    updated_cap_history = batch_update_cap_history(tenant_billing_results, recon_year)
    
    # Count updated tenants
    updated_count = 0
    for tenant_id, years in updated_cap_history.items():
        if str(recon_year) in years:
            updated_count += 1
    
    # Return results
    return {
        'recon_year': recon_year,
        'updated_tenants': updated_count,
        'total_tenants': len(tenant_billing_results),
        'success': updated_count > 0
    }


if __name__ == "__main__":
    # Example usage
    import sys
    from decimal import Decimal
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock data for testing
    recon_year = 2024
    
    mock_tenant_billing = [
        {
            'tenant_id': '1001',
            'tenant_name': 'Tenant A',
            'base_billing': Decimal('6000.00'),
            'final_billing': Decimal('6000.00')  # No override
        },
        {
            'tenant_id': '1002',
            'tenant_name': 'Tenant B',
            'base_billing': Decimal('12600.00'),
            'override_amount': Decimal('1000.00'),
            'final_billing': Decimal('13600.00')  # Includes override
        }
    ]
    
    # Update cap history
    result = update_cap_history(mock_tenant_billing, recon_year)
    
    # Print results
    print("\nCap History Update Results:")
    print(f"Reconciliation Year: {result['recon_year']}")
    print(f"Tenants Updated: {result['updated_tenants']} of {result['total_tenants']}")
    print(f"Success: {result['success']}")
    
    # Show current cap history
    print("\nCurrent Cap History:")
    cap_history = load_cap_history()
    
    for tenant_id, years in cap_history.items():
        print(f"Tenant ID: {tenant_id}")
        for year, amount in sorted(years.items()):
            print(f"  {year}: ${amount:,.2f}")