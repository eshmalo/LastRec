#!/usr/bin/env python3
"""
Manual Override Loader Module

This module loads custom manual overrides for tenant reconciliation amounts.
These overrides can be used to adjust the final recoverable amount.
"""

import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List, Union

from reconciliation.utils.helpers import load_json

# Configure logging
logger = logging.getLogger(__name__)

# Path to the custom overrides file
OVERRIDES_PATH = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides', 'custom_overrides.json')


def load_manual_overrides() -> List[Dict[str, Any]]:
    """
    Load manual overrides from the overrides file.
    
    Returns:
        List of override dictionaries
    """
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
    """
    Create a lookup dictionary for overrides by tenant_id and property_id.
    
    Args:
        overrides: List of override dictionaries
        
    Returns:
        Dictionary mapping "tenant_id_property_id" to override details
    """
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


def get_override_amount(
    tenant_id: Union[str, int],
    property_id: str,
    override_lookup: Optional[Dict[str, Dict[str, Any]]] = None
) -> Decimal:
    """
    Get the override amount for a specific tenant and property.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        override_lookup: Optional override lookup dictionary
        
    Returns:
        Override amount as Decimal, or 0 if no override exists
    """
    # Load overrides if not provided
    if override_lookup is None:
        overrides = load_manual_overrides()
        override_lookup = create_override_lookup(overrides)
    
    # Create the lookup key
    key = f"{tenant_id}_{property_id}"
    
    # Get the override entry
    override = override_lookup.get(key)
    
    if not override:
        return Decimal('0')
    
    # Get the override amount
    override_amount_str = override.get('override_amount', '0')
    
    # Handle empty string or None
    if not override_amount_str:
        return Decimal('0')
    
    try:
        override_amount = Decimal(str(override_amount_str))
        if override_amount != 0:
            logger.info(f"Found manual override for tenant {tenant_id}, property {property_id}: {override_amount}")
        return override_amount
    except (ValueError, TypeError):
        logger.error(f"Invalid override amount: {override_amount_str}")
        return Decimal('0')


def get_override_description(
    tenant_id: Union[str, int],
    property_id: str,
    override_lookup: Optional[Dict[str, Dict[str, Any]]] = None
) -> str:
    """
    Get the override description for a specific tenant and property.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        override_lookup: Optional override lookup dictionary
        
    Returns:
        Override description, or empty string if no override exists
    """
    # Load overrides if not provided
    if override_lookup is None:
        overrides = load_manual_overrides()
        override_lookup = create_override_lookup(overrides)
    
    # Create the lookup key
    key = f"{tenant_id}_{property_id}"
    
    # Get the override entry
    override = override_lookup.get(key)
    
    if not override:
        return ""
    
    # Get the override description
    return override.get('description', '')


def load_overrides_for_tenant(
    tenant_id: Union[str, int],
    property_id: str
) -> Dict[str, Any]:
    """
    Load all override information for a specific tenant and property.
    
    Args:
        tenant_id: Tenant identifier
        property_id: Property identifier
        
    Returns:
        Dictionary with override information
    """
    # Load all overrides
    overrides = load_manual_overrides()
    override_lookup = create_override_lookup(overrides)
    
    # Get the override amount and description
    amount = get_override_amount(tenant_id, property_id, override_lookup)
    description = get_override_description(tenant_id, property_id, override_lookup)
    
    return {
        'tenant_id': tenant_id,
        'property_id': property_id,
        'has_override': amount != 0,
        'override_amount': amount,
        'override_description': description
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Load all overrides
    overrides = load_manual_overrides()
    
    # Print summary
    print(f"\nLoaded {len(overrides)} manual overrides")
    
    # Print examples
    if overrides:
        print("\nExample overrides:")
        for i, override in enumerate(overrides[:5]):  # Show up to 5 examples
            tenant_id = override.get('tenant_id')
            tenant_name = override.get('tenant_name', '')
            property_id = override.get('property_id', '')
            property_name = override.get('property_name', '')
            amount = override.get('override_amount', '')
            description = override.get('description', '')
            
            print(f"{i+1}. Tenant: {tenant_name} (ID: {tenant_id})")
            print(f"   Property: {property_name} (ID: {property_id})")
            print(f"   Override Amount: {amount}")
            if description:
                print(f"   Description: {description}")
            print("")
    
    # Test lookup for a specific tenant (if command line arguments provided)
    if len(sys.argv) >= 3:
        tenant_id = sys.argv[1]
        property_id = sys.argv[2]
        
        override_info = load_overrides_for_tenant(tenant_id, property_id)
        
        print(f"\nOverride information for Tenant ID {tenant_id}, Property ID {property_id}:")
        print(f"Has Override: {override_info['has_override']}")
        
        if override_info['has_override']:
            print(f"Amount: {override_info['override_amount']}")
            if override_info['override_description']:
                print(f"Description: {override_info['override_description']}")