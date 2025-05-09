#!/usr/bin/env python3
"""
Settings Loader Module

This module loads and merges settings from different hierarchical levels:
1. Portfolio settings (global defaults)
2. Property settings (override portfolio defaults)
3. Tenant settings (override property settings)

The merged settings are used for CAM/TAX reconciliation calculations.
"""

import os
import json
import logging
from copy import deepcopy
from typing import Dict, Any, Optional, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
PORTFOLIO_SETTINGS_PATH = os.path.join('Data', 'ProcessedOutput', 'PortfolioSettings', 'portfolio_settings.json')
PROPERTY_SETTINGS_BASE_PATH = os.path.join('Data', 'ProcessedOutput', 'PropertySettings')


def load_json(file_path: str) -> Dict[str, Any]:
    """Load a JSON file and return its contents as a dictionary.
    
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


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with dict2 values overriding dict1 values when both exist.
    
    Args:
        dict1: Base dictionary
        dict2: Dictionary to merge on top of dict1
        
    Returns:
        New dictionary with merged values
    """
    result = deepcopy(dict1)
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # For non-dict values or keys not in dict1, use dict2's value
            # Only override if the value is not empty/None
            if value is not None and value != "":
                result[key] = deepcopy(value)
    
    return result


def load_portfolio_settings() -> Dict[str, Any]:
    """Load the portfolio-level settings.
    
    Returns:
        Dictionary containing portfolio settings
    """
    try:
        return load_json(PORTFOLIO_SETTINGS_PATH)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Could not load portfolio settings. Using empty default.")
        return {
            "name": "Default Portfolio",
            "settings": {
                "gl_inclusions": {"ret": [], "cam": [], "admin_fee": []},
                "gl_exclusions": {"ret": [], "cam": [], "admin_fee": [], "base": [], "cap": []},
                "prorate_share_method": "",
                "admin_fee_percentage": "",
                "base_year": "",
                "base_year_amount": "",
                "min_increase": "",
                "max_increase": "",
                "stop_amount": "",
                "cap_settings": {
                    "cap_percentage": "",
                    "cap_type": "",
                    "override_cap_year": "",
                    "override_cap_amount": ""
                },
                "admin_fee_in_cap_base": ""
            }
        }


def load_property_settings(property_id: str) -> Dict[str, Any]:
    """Load property-level settings.
    
    Args:
        property_id: Property identifier
        
    Returns:
        Dictionary containing property settings
    """
    property_settings_path = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'property_settings.json')
    
    try:
        return load_json(property_settings_path)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Could not load property settings for {property_id}. Using empty default.")
        return {
            "property_id": property_id,
            "name": f"Property {property_id}",
            "total_rsf": 0,
            "capital_expenses": [],
            "settings": {
                "gl_inclusions": {"ret": [], "cam": [], "admin_fee": []},
                "gl_exclusions": {"ret": [], "cam": [], "admin_fee": [], "base": [], "cap": []},
                "square_footage": "",
                "prorate_share_method": "",
                "admin_fee_percentage": "",
                "base_year": "",
                "base_year_amount": "",
                "min_increase": "",
                "max_increase": "",
                "stop_amount": "",
                "cap_settings": {
                    "cap_percentage": "",
                    "cap_type": "",
                    "override_cap_year": "",
                    "override_cap_amount": ""
                },
                "admin_fee_in_cap_base": ""
            }
        }


def load_tenant_settings(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """Load tenant-level settings.
    
    Args:
        property_id: Property identifier
        tenant_id: Tenant identifier
        
    Returns:
        Dictionary containing tenant settings or empty dict if not found
    """
    # Tenant settings directory
    tenant_settings_dir = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'TenantSettings')
    
    # If tenant directory doesn't exist, return empty settings
    if not os.path.exists(tenant_settings_dir):
        logger.warning(f"Tenant settings directory not found for property {property_id}")
        return {}
    
    # Find the tenant file by looking for a file that contains the tenant ID
    tenant_files = [f for f in os.listdir(tenant_settings_dir) if f.endswith(f"{tenant_id}.json")]
    
    if not tenant_files:
        logger.warning(f"No tenant settings file found for tenant ID {tenant_id} in property {property_id}")
        return {}
    
    tenant_file_path = os.path.join(tenant_settings_dir, tenant_files[0])
    
    try:
        return load_json(tenant_file_path)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Could not load tenant settings for tenant {tenant_id} in property {property_id}")
        return {}


def find_all_tenants_for_property(property_id: str) -> List[Tuple[str, str]]:
    """Find all tenants for a given property.
    
    Args:
        property_id: Property identifier
        
    Returns:
        List of tuples containing (tenant_id, tenant_name)
    """
    tenant_settings_dir = os.path.join(PROPERTY_SETTINGS_BASE_PATH, property_id, 'TenantSettings')
    
    if not os.path.exists(tenant_settings_dir):
        logger.warning(f"Tenant settings directory not found for property {property_id}")
        return []
    
    tenants = []
    
    for filename in os.listdir(tenant_settings_dir):
        if filename.endswith('.json'):
            try:
                file_path = os.path.join(tenant_settings_dir, filename)
                tenant_data = load_json(file_path)
                tenant_id = tenant_data.get('tenant_id')
                tenant_name = tenant_data.get('name', '')
                
                if tenant_id:
                    tenants.append((str(tenant_id), tenant_name))
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning(f"Could not process tenant file: {filename}")
    
    return tenants


def merge_settings(property_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Load and merge settings from portfolio, property, and tenant levels.
    
    Args:
        property_id: Property identifier
        tenant_id: Optional tenant identifier. If provided, tenant settings will be merged.
        
    Returns:
        Dictionary with merged settings
    """
    # Load portfolio settings (base level)
    portfolio_settings = load_portfolio_settings()
    
    # Load property settings
    property_data = load_property_settings(property_id)
    
    # Create a new deep copy of the portfolio settings
    result = deepcopy(portfolio_settings)
    result["property_id"] = property_id
    result["property_name"] = property_data.get("name", f"Property {property_id}")
    result["total_rsf"] = property_data.get("total_rsf", 0)
    result["property_capital_expenses"] = property_data.get("capital_expenses", [])
    
    # Special handling for GL inclusions
    # For each category (ret, cam, admin_fee)
    for category in ["ret", "cam", "admin_fee"]:
        # Get property level inclusions
        property_inclusions = property_data.get("settings", {}).get("gl_inclusions", {}).get(category, [])
        
        # Only replace portfolio inclusions if property has explicitly set non-empty inclusions
        if property_inclusions:
            result["settings"]["gl_inclusions"][category] = property_inclusions
    
    # Merge remaining property settings with portfolio settings
    for key, value in property_data.get("settings", {}).items():
        # Skip gl_inclusions as we handled it specially above
        if key == "gl_inclusions":
            continue
            
        if key in result["settings"]:
            # For nested dictionaries, do a deep merge
            if isinstance(value, dict) and isinstance(result["settings"][key], dict):
                result["settings"][key] = deep_merge(result["settings"][key], value)
            # For non-dict values or keys not in portfolio settings, use property's value if not empty
            elif value is not None and value != "":
                result["settings"][key] = deepcopy(value)
        else:
            # If key doesn't exist in portfolio settings, add it
            result["settings"][key] = deepcopy(value)
    
    # If tenant_id is provided, merge tenant settings
    if tenant_id:
        tenant_data = load_tenant_settings(property_id, tenant_id)
        
        # Merge tenant settings into the result
        for key, value in tenant_data.get("settings", {}).items():
            if key in result["settings"]:
                # Special handling for gl_inclusions and gl_exclusions
                # Allow tenant settings to override even with empty lists (to explicitly exclude all)
                if key == "gl_inclusions" or key == "gl_exclusions":
                    # For each category, override if the category exists in tenant settings
                    categories = ["ret", "cam", "admin_fee", "base", "cap"]
                    for category in categories:
                        if category in value:  # Override if category exists in tenant settings
                            result["settings"][key][category] = value[category]
                            logger.info(f"Tenant setting override: {key}.{category} has been set to {value[category]}")
                        else:
                            logger.debug(f"Tenant setting not provided for {key}.{category}, keeping inherited value")
                # For nested dictionaries, do a deep merge
                elif isinstance(value, dict) and isinstance(result["settings"][key], dict):
                    result["settings"][key] = deep_merge(result["settings"][key], value)
                # For non-dict values, use tenant's value if not empty
                elif value is not None and value != "":
                    result["settings"][key] = deepcopy(value)
            else:
                # If key doesn't exist in result settings, add it
                result["settings"][key] = deepcopy(value)
        
        # Include tenant-specific attributes in the result
        tenant_specific = {
            "tenant_id": tenant_data.get("tenant_id"),
            "tenant_name": tenant_data.get("name", ""),
            "lease_start": tenant_data.get("lease_start", ""),
            "lease_end": tenant_data.get("lease_end", ""),
            "suite": tenant_data.get("suite", ""),
            "capital_expenses": tenant_data.get("capital_expenses", [])
        }
        result.update(tenant_specific)
    
    # Set default values for essential settings if they're empty
    if not result["settings"].get("prorate_share_method"):
        result["settings"]["prorate_share_method"] = "RSF"  # Default to RSF method
        
    if not result["settings"]["cap_settings"].get("cap_type"):
        result["settings"]["cap_settings"]["cap_type"] = "previous_year"  # Default cap type
    
    return result


def apply_cap_overrides(settings: Dict[str, Any], cap_history: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Apply any cap override settings to the cap history.
    
    Args:
        settings: Merged settings dictionary
        cap_history: Dictionary containing cap history data
        
    Returns:
        Updated cap history with any overrides applied
    """
    tenant_id = str(settings.get("tenant_id", ""))
    
    if not tenant_id:
        logger.warning("No tenant_id in settings, skipping cap overrides")
        return cap_history
    
    # Get cap override settings
    cap_settings = settings.get("settings", {}).get("cap_settings", {})
    override_year = cap_settings.get("override_cap_year")
    override_amount = cap_settings.get("override_cap_amount")
    
    # Skip if either override setting is missing
    if not override_year or override_amount is None or override_amount == "":
        return cap_history
    
    # Initialize tenant entry if it doesn't exist
    if tenant_id not in cap_history:
        cap_history[tenant_id] = {}
    
    # Apply the override
    cap_history[tenant_id][override_year] = float(override_amount)
    logger.info(f"Applied cap override for tenant {tenant_id}, year {override_year}: {override_amount}")
    
    return cap_history


def load_settings(property_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Main function to load settings for reconciliation.
    
    Args:
        property_id: Property identifier
        tenant_id: Optional tenant identifier
        
    Returns:
        Merged settings dictionary with all required values
    """
    merged_settings = merge_settings(property_id, tenant_id)
    
    # For debugging
    logger.debug(f"Loaded settings for property {property_id}, tenant {tenant_id}: {merged_settings}")
    
    return merged_settings


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python settings_loader.py <property_id> [<tenant_id>]")
        sys.exit(1)
    
    property_id = sys.argv[1]
    tenant_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    settings = load_settings(property_id, tenant_id)
    print(json.dumps(settings, indent=2))