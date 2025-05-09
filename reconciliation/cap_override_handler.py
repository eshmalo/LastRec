#!/usr/bin/env python3
"""
Cap Override Handler Module

This module manages cap history and applies overrides based on settings.
It provides functions to load, save, and update the cap history database.
"""

import os
import json
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Union

from reconciliation.utils.helpers import load_json, save_json

# Configure logging
logger = logging.getLogger(__name__)

# Path to the cap history file
CAP_HISTORY_PATH = os.path.join('Data', 'cap_history.json')


def load_cap_history() -> Dict[str, Dict[str, float]]:
    """
    Load cap history from file.
    
    The cap history structure is:
    {
        "tenant_id": {
            "year": amount,
            ...
        },
        ...
    }
    
    Returns:
        Dictionary containing cap history data
    """
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
    """
    Save cap history to file.
    
    Args:
        cap_history: Dictionary containing cap history data
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(CAP_HISTORY_PATH), exist_ok=True)
        
        # Save the file
        with open(CAP_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(cap_history, f, indent=2)
        
        logger.info(f"Saved cap history to {CAP_HISTORY_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error saving cap history: {str(e)}")
        return False


def apply_cap_override(
    tenant_id: str, 
    override_year: str, 
    override_amount: float, 
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Apply a cap override for a specific tenant and year.
    
    Args:
        tenant_id: Tenant identifier
        override_year: Year to override
        override_amount: Amount to set for the year
        cap_history: Optional cap history dictionary, if None will be loaded from file
        
    Returns:
        Updated cap history dictionary
    """
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()
    
    # Initialize tenant entry if it doesn't exist
    if tenant_id not in cap_history:
        cap_history[tenant_id] = {}
    
    # Apply the override
    cap_history[tenant_id][override_year] = float(override_amount)
    logger.info(f"Applied cap override for tenant {tenant_id}, year {override_year}: {override_amount}")
    
    # Save the updated cap history
    save_cap_history(cap_history)
    
    return cap_history


def handle_cap_overrides(settings: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    Handle cap overrides based on settings.
    
    Args:
        settings: Settings dictionary containing tenant and cap settings
        
    Returns:
        Updated cap history dictionary
    """
    tenant_id = str(settings.get("tenant_id", ""))
    
    if not tenant_id:
        logger.warning("No tenant_id in settings, skipping cap overrides")
        return load_cap_history()
    
    # Get cap override settings
    cap_settings = settings.get("settings", {}).get("cap_settings", {})
    override_year = cap_settings.get("override_cap_year")
    override_amount = cap_settings.get("override_cap_amount")
    
    # Log the override settings
    logger.info(f"Cap override settings for tenant {tenant_id}:")
    logger.info(f"  Override year: {override_year}")
    logger.info(f"  Override amount: {override_amount}")
    
    # Skip if either override setting is missing
    if not override_year or override_amount is None or override_amount == "":
        logger.info(f"No valid cap override for tenant {tenant_id}")
        return load_cap_history()
    
    # Apply the override
    logger.info(f"Applying cap override for tenant {tenant_id}: year={override_year}, amount={override_amount}")
    
    # Handle whitespace in override_amount
    if isinstance(override_amount, str):
        override_amount = override_amount.strip()
        logger.info(f"Cleaned override amount: '{override_amount}'")
    
    return apply_cap_override(tenant_id, override_year, float(override_amount))


def get_reference_amount(
    tenant_id: str, 
    recon_year: Union[str, int], 
    cap_type: str, 
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Decimal:
    """
    Get the reference amount for cap calculations.
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        cap_type: Type of cap ('previous_year' or 'highest_previous_year')
        cap_history: Optional cap history dictionary, if None will be loaded from file
        
    Returns:
        Reference amount for cap calculations
    """
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()
    
    # Convert recon_year to string if needed
    recon_year = str(recon_year)
    
    # Get tenant's cap history
    tenant_history = cap_history.get(tenant_id, {})
    
    # Log the cap history for debugging
    logger.info(f"Cap history for tenant {tenant_id}: {tenant_history}")
    
    if not tenant_history:
        logger.warning(f"No cap history found for tenant {tenant_id}")
        return Decimal('0')
    
    # Calculate previous year
    prev_year = str(int(recon_year) - 1)
    
    # Log cap type
    logger.info(f"Cap type for tenant {tenant_id}: {cap_type}")
    
    if cap_type == "previous_year":
        # Use previous year's amount
        amount = tenant_history.get(prev_year, 0.0)
        logger.info(f"Using previous year cap for tenant {tenant_id}: {amount}")
        return Decimal(str(amount))
    elif cap_type == "highest_previous_year":
        # Find the highest amount from all previous years
        highest_amount = 0.0
        
        for year, amount in tenant_history.items():
            # Only consider years before recon_year
            if year < recon_year and amount > highest_amount:
                highest_amount = amount
                logger.info(f"New highest cap found for tenant {tenant_id} in year {year}: {amount}")
        
        logger.info(f"Using highest previous year cap for tenant {tenant_id}: {highest_amount}")
        return Decimal(str(highest_amount))
    else:
        logger.error(f"Unknown cap type: {cap_type}")
        return Decimal('0')


def update_cap_history(
    tenant_id: str, 
    recon_year: Union[str, int], 
    amount: float,
    cap_history: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Update cap history with the new amount for the current reconciliation.
    
    Args:
        tenant_id: Tenant identifier
        recon_year: Reconciliation year
        amount: Amount to save for the year
        cap_history: Optional cap history dictionary, if None will be loaded from file
        
    Returns:
        Updated cap history dictionary
    """
    # Load cap history if not provided
    if cap_history is None:
        cap_history = load_cap_history()
    
    # Convert recon_year to string if needed
    recon_year = str(recon_year)
    
    # Initialize tenant entry if it doesn't exist
    if tenant_id not in cap_history:
        cap_history[tenant_id] = {}
    
    # Update the entry
    cap_history[tenant_id][recon_year] = float(amount)
    logger.info(f"Updated cap history for tenant {tenant_id}, year {recon_year}: {amount}")
    
    # Save the updated cap history
    save_cap_history(cap_history)
    
    return cap_history


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) < 4:
        print("Usage: python cap_override_handler.py <tenant_id> <year> <amount>")
        sys.exit(1)
    
    tenant_id = sys.argv[1]
    year = sys.argv[2]
    amount = float(sys.argv[3])
    
    # Apply override
    updated_history = apply_cap_override(tenant_id, year, amount)
    
    # Display result
    tenant_history = updated_history.get(tenant_id, {})
    print(f"Cap history for tenant {tenant_id}:")
    for year, amount in sorted(tenant_history.items()):
        print(f"  {year}: ${amount:,.2f}")