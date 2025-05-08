#!/usr/bin/env python3
"""
This script performs three main tasks:
1. Convert all CSV files in the Input folder to JSON format in the Output/JSON folder
2. Extract and categorize GL accounts with property and period data, updating the gl_categories_original.json file
3. Generate a hierarchical folder structure for recovery settings files (portfolio, property, and tenant levels)
"""

import os
import csv
import json
import re
import datetime
from collections import defaultdict
from decimal import Decimal

def is_in_range(gl_account, start_range, end_range):
    """Check if a GL account is within the specified range."""
    return start_range <= gl_account <= end_range

def convert_csv_to_json(input_folder, output_folder):
    """
    Convert all CSV files in the input folder to JSON files in the output folder.
    
    Args:
        input_folder (str): Path to the folder containing CSV files
        output_folder (str): Path to the folder where JSON files will be saved
    """
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Get all CSV files in the input folder
    csv_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"No CSV files found in {input_folder}")
        return False
    
    print(f"Found {len(csv_files)} CSV files to convert")
    
    for csv_file in csv_files:
        # Construct the full file paths
        csv_path = os.path.join(input_folder, csv_file)
        json_file = os.path.splitext(csv_file)[0] + '.json'
        json_path = os.path.join(output_folder, json_file)
        
        print(f"Converting {csv_file} to {json_file}...")
        
        try:
            # Read CSV using standard library
            with open(csv_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                # Use DictReader to automatically map each row to a dictionary
                csv_reader = csv.DictReader(csvfile)
                
                # Clean up column names (remove BOM characters and extra quotes)
                cleaned_fieldnames = []
                for name in csv_reader.fieldnames:
                    # Remove BOM character if present
                    name = name.replace('\ufeff', '')
                    # Remove extra quotes in field names
                    name = name.replace('"', '')
                    cleaned_fieldnames.append(name)
                
                # Create a new DictReader with cleaned fieldnames
                csvfile.seek(0)
                next(csvfile)  # Skip the header row
                csv_reader = csv.DictReader(csvfile, fieldnames=cleaned_fieldnames)
                
                records = []
                for row in csv_reader:
                    clean_row = {}
                    for key, value in row.items():
                        # Clean the key (remove BOM and quotes)
                        clean_key = key.replace('\ufeff', '').replace('"', '')
                        
                        # Try to convert to integer or float
                        if value and isinstance(value, str) and value.strip():
                            try:
                                if value.isdigit():
                                    clean_row[clean_key] = int(value)
                                elif value.replace('.', '', 1).isdigit() and value.count('.') == 1:
                                    clean_row[clean_key] = float(value)
                                else:
                                    clean_row[clean_key] = value
                            except (ValueError, AttributeError):
                                clean_row[clean_key] = value
                        else:
                            clean_row[clean_key] = value
                    
                    records.append(clean_row)
            
            # Write JSON file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=4)
            
            print(f"Successfully converted {csv_file} to {json_file}")
        
        except Exception as e:
            print(f"Error converting {csv_file}: {str(e)}")
            return False
    
    print("Conversion complete!")
    return True

def extract_gl_descriptions():
    """
    Extract GL descriptions from the GL Master file and update the gl_categories structure
    with property and period data.
    """
    # Load GL Master data directly from CSV
    gl_master_csv_path = os.path.join('Input', 'GL Master 3.csv')
    gl_csv_data = []
    
    print(f"Loading GL Master data from CSV: {gl_master_csv_path}")
    with open(gl_master_csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        gl_csv_data = list(reader)
    
    print(f"Loaded {len(gl_csv_data)} rows from CSV")
    
    # Load GL categories
    gl_categories_path = os.path.join('Input', 'gl_categories_original.json')
    output_path = os.path.join('Data', 'ManualInputs', 'gl_categories_with_property_and_periods.json')
    with open(gl_categories_path, 'r', encoding='utf-8') as f:
        gl_categories = json.load(f)
    
    # Create a nested dictionary to store GL accounts and their descriptions by property
    # Structure: {property_id: {gl_account: {"description": str, "count": int, "periods": {period: net_amount}}}}
    property_gl_dict = defaultdict(lambda: defaultdict(lambda: {
        "description": "", 
        "count": 0,
        "periods": defaultdict(Decimal)  # Using defaultdict to sum up amounts by period
    }))
    
    # Collect all GL accounts with their descriptions by property
    # Also collect financial data by period
    for entry in gl_csv_data:
        property_id = entry.get('Property ID')
        gl_account = entry.get('GL Account')
        gl_description = entry.get('GL Description')
        period = entry.get('PERIOD')
        
        # Handle net amount - convert to Decimal for accurate financial calculations
        try:
            net_amount = Decimal(entry.get('Net Amount', '0') or '0')
        except:
            print(f"Warning: Invalid Net Amount '{entry.get('Net Amount')}' for {property_id}, {gl_account}, {period}")
            net_amount = Decimal('0')
        
        if property_id and gl_account and gl_description and period:
            # If we've seen this account-property combo before
            if property_gl_dict[property_id][gl_account]["count"] > 0:
                # Check if the description is different
                existing_desc = property_gl_dict[property_id][gl_account]["description"]
                if existing_desc != gl_description:
                    print(f"WARNING: GL account {gl_account} for property {property_id} has multiple descriptions:")
                    print(f"  Existing: '{existing_desc}'")
                    print(f"  New: '{gl_description}'")
                    # We'll keep the first description we encountered
            else:
                # First time seeing this account-property combo
                property_gl_dict[property_id][gl_account]["description"] = gl_description
            
            # Increment the count
            property_gl_dict[property_id][gl_account]["count"] += 1
            
            # Add the net amount to the appropriate period
            property_gl_dict[property_id][gl_account]["periods"][period] += net_amount
    
    # Consolidate GL accounts across properties
    # For the same GL account across different properties, collect all unique descriptions
    consolidated_gl_dict = {}
    gl_with_multiple_descriptions = {}
    
    for property_id, accounts in property_gl_dict.items():
        for gl_account, details in accounts.items():
            if gl_account not in consolidated_gl_dict:
                consolidated_gl_dict[gl_account] = {
                    "description": details["description"],
                    "properties": [property_id],
                    "all_descriptions": {details["description"]},
                    "property_periods": {property_id: {
                        period: str(amount)  # Convert Decimal to string for JSON serialization
                        for period, amount in details["periods"].items()
                    }}
                }
            else:
                consolidated_gl_dict[gl_account]["properties"].append(property_id)
                consolidated_gl_dict[gl_account]["all_descriptions"].add(details["description"])
                consolidated_gl_dict[gl_account]["property_periods"][property_id] = {
                    period: str(amount)  # Convert Decimal to string for JSON serialization
                    for period, amount in details["periods"].items()
                }
                
                # If we have multiple descriptions for this GL account across properties
                if details["description"] != consolidated_gl_dict[gl_account]["description"]:
                    if gl_account not in gl_with_multiple_descriptions:
                        gl_with_multiple_descriptions[gl_account] = {
                            consolidated_gl_dict[gl_account]["description"],
                            details["description"]
                        }
                    else:
                        gl_with_multiple_descriptions[gl_account].add(details["description"])
    
    # Report any GL accounts with multiple descriptions across properties
    if gl_with_multiple_descriptions:
        print(f"\nFound {len(gl_with_multiple_descriptions)} GL accounts with different descriptions across properties:")
        for gl_account, descriptions in gl_with_multiple_descriptions.items():
            print(f"  GL Account {gl_account} has {len(descriptions)} different descriptions:")
            for desc in descriptions:
                print(f"    - '{desc}'")
    
    # Create the gl_categories structure with property information
    # Process each account range in gl_categories
    gl_account_details = defaultdict(list)
    
    # Find the category for each GL account
    for range_key, range_info in gl_categories['gl_account_lookup'].items():
        start, end = range_key.split('-')
        
        for gl_account, details in consolidated_gl_dict.items():
            if is_in_range(gl_account, start, end):
                gl_account_details[range_key].append({
                    'gl_account': gl_account,
                    'description': details["description"],
                    'properties': sorted(details["properties"]),
                    'property_periods': details["property_periods"],
                    'category': range_info['category'],
                    'parent_category': range_info.get('parent_category'),
                    'group': range_info['group']
                })
    
    # Helper function to find and update the right category in the nested structure
    def update_category_with_gl_accounts(categories_list):
        # First, get all categories flattened with their paths
        flat_categories = []
        
        def flatten_categories(category_list, parent_path=None):
            for category in category_list:
                current_path = []
                
                if 'group' in category:
                    # This is the top-level "Recoveries" group
                    current_path = [category['group']]
                    
                    if 'subcategories' in category:
                        for subcategory in category['subcategories']:
                            subcategory_path = current_path.copy()
                            if 'name' in subcategory:
                                subcategory_path.append(subcategory['name'])
                                
                                # Add this category
                                flat_categories.append({
                                    'path': subcategory_path,
                                    'category': subcategory
                                })
                                
                                # Process any further subcategories
                                if 'subcategories' in subcategory:
                                    flatten_categories(subcategory['subcategories'], subcategory_path)
                
        flatten_categories(categories_list)
        
        # Now update each category with its GL accounts
        for gl_range, accounts in gl_account_details.items():
            if not accounts:
                continue
                
            # All accounts in this range have the same category info
            category_name = accounts[0]['category']
            parent_category = accounts[0].get('parent_category')
            
            # Find the matching category by path
            for flat_category in flat_categories:
                path = flat_category['path']
                category = flat_category['category']
                
                # Check if this is the right category
                if category['name'] == category_name:
                    # For subcategories of CAM, we need to check the parent
                    if parent_category and len(path) > 1 and path[-2] == parent_category:
                        # This is a match (e.g. CAM -> Property Insurance)
                        if 'gl_accounts' not in category:
                            category['gl_accounts'] = []
                            
                        # Add detailed GL accounts to this category
                        for account in accounts:
                            category['gl_accounts'].append({
                                'gl_account': account['gl_account'],
                                'description': account['description'],
                                'properties': account['properties'],
                                'property_periods': account['property_periods']
                            })
                        break
                    elif not parent_category and path[-1] == category_name:
                        # This is a direct match (e.g. Real Estate Taxes)
                        if 'gl_accounts' not in category:
                            category['gl_accounts'] = []
                            
                        # Add detailed GL accounts to this category
                        for account in accounts:
                            category['gl_accounts'].append({
                                'gl_account': account['gl_account'],
                                'description': account['description'],
                                'properties': account['properties'],
                                'property_periods': account['property_periods']
                            })
                        break
    
    # Update the categories with GL accounts
    update_category_with_gl_accounts(gl_categories['categories'])
    
    # Add detailed GL accounts to a new section in the JSON
    gl_categories['gl_accounts_detail'] = {}
    for gl_account, details in consolidated_gl_dict.items():
        gl_category = None
        parent_category = None
        
        # Find which category this GL account belongs to
        for range_key, range_info in gl_categories['gl_account_lookup'].items():
            start, end = range_key.split('-')
            if is_in_range(gl_account, start, end):
                gl_category = range_info['category']
                parent_category = range_info.get('parent_category')
                break
        
        if gl_category:
            gl_categories['gl_accounts_detail'][gl_account] = {
                'description': details['description'],
                'properties': sorted(details['properties']),
                'property_periods': details['property_periods'],
                'category': gl_category,
                'parent_category': parent_category,
                'group': 'Recoveries'  # All our categories are under Recoveries
            }
    
    # Save the updated GL categories to a new file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(gl_categories, f, indent=2)
    
    # Print statistics
    property_count = len(property_gl_dict)
    account_count = len(consolidated_gl_dict)
    multiprops_accounts = sum(1 for details in consolidated_gl_dict.values() if len(details['properties']) > 1)
    
    # Calculate period statistics
    all_periods = set()
    for gl_account, details in consolidated_gl_dict.items():
        for property_id, periods in details['property_periods'].items():
            all_periods.update(periods.keys())
    
    total_period_entries = sum(
        len(periods) 
        for gl_account, details in consolidated_gl_dict.items()
        for property_id, periods in details['property_periods'].items()
    )
    
    print(f"\nCreated {output_path} with detailed GL account information including period data.")
    print(f"Found {account_count} unique GL accounts across {property_count} properties.")
    print(f"{multiprops_accounts} GL accounts are used by multiple properties.")
    print(f"Processed {len(all_periods)} unique accounting periods with {total_period_entries} total period entries.")
    
    return output_path

def load_json_file(file_path):
    """Load a JSON file and return its contents"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_custom_overrides(tenants, properties):
    """Generate a custom overrides file template with all tenant IDs and names, preserving existing override values"""
    # Define output directory
    overrides_dir = os.path.join('Data', 'ProcessedOutput', 'CustomOverrides')
    
    # Create directory if it doesn't exist
    if not os.path.exists(overrides_dir):
        os.makedirs(overrides_dir)
    
    # Create a lookup for property names
    property_names = {p.get('Property ID'): p.get('Property Name', '') for p in properties if p.get('Property ID')}
    
    # Path to the existing overrides file
    overrides_file = os.path.join(overrides_dir, 'custom_overrides.json')
    
    # Load existing overrides if file exists
    existing_overrides = {}
    if os.path.exists(overrides_file):
        try:
            with open(overrides_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                # Create lookup by tenant_id and property_id
                for override in existing_data:
                    tenant_id = override.get('tenant_id')
                    property_id = override.get('property_id')
                    if tenant_id is not None and property_id is not None:
                        key = f"{tenant_id}_{property_id}"
                        existing_overrides[key] = override
                print(f"Loaded {len(existing_overrides)} existing tenant override settings")
        except Exception as e:
            print(f"Error loading existing overrides: {e}")
    
    # Create lookup of all tenants we need to process to avoid duplicates
    tenant_property_pairs = set()
    tenant_overrides = []
    new_tenant_count = 0
    preserved_count = 0
    
    # First, build a unique set of tenant_id and property_id combinations
    for tenant in tenants:
        tenant_id = tenant.get('Tenant ID')
        property_id = tenant.get('Property ID', '')
        
        if tenant_id is not None:
            # Add this combination to our set to track uniqueness
            tenant_property_pairs.add(f"{tenant_id}_{property_id}")
    
    print(f"Found {len(tenant_property_pairs)} unique tenant-property combinations")
    
    # Now process each unique tenant+property combination exactly once
    for key in tenant_property_pairs:
        tenant_id, property_id = key.split('_', 1)
        
        # Find the tenant data for this combination
        tenant_data = None
        for tenant in tenants:
            if str(tenant.get('Tenant ID')) == tenant_id and tenant.get('Property ID', '') == property_id:
                tenant_data = tenant
                break
        
        if not tenant_data:
            print(f"Warning: Could not find tenant data for ID {tenant_id} in property {property_id}")
            continue
            
        tenant_name = tenant_data.get('Tenant Name', '')
        property_name = property_names.get(property_id, '')
        
        # Check if this tenant already has override settings
        if key in existing_overrides:
            # Preserve existing override value and description
            tenant_override = existing_overrides[key].copy()
            # Update name in case it changed
            tenant_override['tenant_name'] = tenant_name
            tenant_override['property_name'] = property_name
            preserved_count += 1
        else:
            # Create new entry with empty string for override_amount
            tenant_override = {
                'tenant_id': int(tenant_id),  # Convert to int to match original format
                'tenant_name': tenant_name,
                'property_id': property_id,
                'property_name': property_name,
                'override_amount': "",
                'description': '',
                'format_notes': {
                    'number_format': 'All monetary values should be entered as numbers without currency symbols',
                    'override_purpose': 'This overrides the calculated tenant CAM amount with a fixed amount'
                }
            }
            new_tenant_count += 1
        
        tenant_overrides.append(tenant_override)
    
    # Sort by property ID and tenant name for easier navigation
    tenant_overrides.sort(key=lambda x: (x['property_id'], x['tenant_name']))
    
    # Save the overrides file
    with open(overrides_file, 'w', encoding='utf-8') as f:
        json.dump(tenant_overrides, f, indent=2)
    
    print(f"Updated custom overrides template: preserved {preserved_count} existing entries, added {new_tenant_count} new tenants")
    return len(tenant_overrides)

def generate_settings_files():
    """Generate separate JSON files for portfolio, properties, and tenants in a folder structure,
    preserving existing values for specified fields"""
    # Define paths
    data_dir = os.path.join('Data', 'ProcessedOutput')
    portfolio_dir = os.path.join(data_dir, 'PortfolioSettings')
    property_dir = os.path.join(data_dir, 'PropertySettings')
    
    # Create directories if they don't exist
    for directory in [data_dir, portfolio_dir, property_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    # Output file for portfolio
    portfolio_file = os.path.join(portfolio_dir, 'portfolio_settings.json')
    
    # Load property and tenant data
    properties_path = os.path.join('Output', 'JSON', '1. Properties.json')
    tenants_path = os.path.join('Output', 'JSON', '2. Tenants.json')
    tenant_cam_path = os.path.join('Output', 'JSON', 'Tenant CAM data1.json')
    
    properties = load_json_file(properties_path)
    tenants = load_json_file(tenants_path)
    tenant_cam_data = load_json_file(tenant_cam_path)
    
    # Create a lookup for tenant CAM data by tenant ID
    tenant_cam_lookup = {}
    for cam_entry in tenant_cam_data:
        tenant_id = cam_entry.get('TenantID')
        if tenant_id:
            if tenant_id not in tenant_cam_lookup:
                tenant_cam_lookup[tenant_id] = {
                    'TenantGLA': cam_entry.get('TenantGLA'),
                    'ProRataShare': cam_entry.get('ProRataShare'),
                    'FixedProRataPYC': cam_entry.get('FixedProRataPYC'),
                    'STOP': cam_entry.get('STOP'),
                    'MININCR': cam_entry.get('MININCR'),
                    'MAXINCR': cam_entry.get('MAXINCR')
                }
    print(f"Loaded CAM data for {len(tenant_cam_lookup)} tenants")
    
    # Default portfolio settings template with examples and explanations
    default_portfolio_settings = {
        "name": "Main Portfolio",
        "metadata": {
            "created_at": datetime.datetime.now().isoformat(),
            "description": "Portfolio-wide recovery settings",
            "format_notes": {
                "number_format": "Percentages are stored differently depending on the field: Most percentage values are stored as decimals (5% as 0.05), except fixed_pyc_share which is stored as the actual percentage value (5.138% as 5.138)",
                "date_format": "Dates should be in MM/DD/YYYY or YYYY-MM-DD format",
                "gl_account_format": "GL accounts can be specified with or without the MR prefix",
                "admin_fee_in_cap_base": "Controls admin fee inclusion: \"\" (exclude from both), \"cap\" (include in cap only), \"base\" (include in base only), \"cap,base\" (include in both)",
                "capital_expenses": "Capital expenses are major expenditures that can be amortized over multiple years. The system calculates the amortized amount by dividing the total cost by the amortization period. Each expense needs an ID, description, year incurred, total amount, and amortization period in years."
            }
        },
        "settings": {
            # GL Account Inclusions/Exclusions
            "gl_inclusions": {
                # Example: ["5010", "5020", "5030"] - Include these GL accounts in calculations
                "ret": [],  # GL accounts to include specifically for Real Estate Tax calculations
                "cam": [],  # GL accounts to include specifically for CAM calculations
                "admin_fee": []  # GL accounts to include specifically for admin fee calculations
            },
            "gl_exclusions": {
                # Example: ["6010", "6020", "6030"] - Exclude these GL accounts from calculations
                "ret": [],  # GL accounts to exclude from Real Estate Tax calculations
                "cam": [],  # GL accounts to exclude from CAM calculations 
                "admin_fee": [],  # GL accounts to exclude from admin fee calculations
                "base": [],  # Additional GL accounts to exclude when calculating base year expenses
                "cap": []  # Additional GL accounts to exclude when calculating cap limits
            },
            
            # Property Information
            "square_footage": "",  # Example: 100000 - Total property square footage
            
            # Pro-rata Share Method
            # Options: "RSF" (calculated based on square footage), "Fixed" (fixed percentage), "Custom" (tenant-specific)
            "prorate_share_method": "",
            
            # Admin Fee Settings
            # Example: 0.15 for 15% - Percentage charged as administrative fee on CAM expenses
            "admin_fee_percentage": "",
            
            # Base Year Settings - Controls tenant charges based on expenses exceeding base year
            "base_year": "",  # Example: "2020" - The reference year for base year calculations
            "base_year_amount": "",  # Example: 100000 - Optional fixed base amount (property total, not tenant share)
            
            # Increase Limit Settings - Alternative to cap percentage
            "min_increase": "",  # Example: 0.03 for 3% - Minimum annual increase (from MININCR field)
            "max_increase": "",  # Example: 0.05 for 5% - Maximum annual increase (from MAXINCR field)
            
            # Stop Amount Settings
            "stop_amount": "",  # Example: 5.75 - Stop amount per square foot (from STOP field)
            
            # Cap Settings - Limits year-over-year expense increases
            "cap_settings": {
                # Example: 0.05 for 5% - Maximum percentage increase allowed per year
                "cap_percentage": "",
                
                # Options: "previous_year" (compares to prior year) or "highest_previous_year" (compares to highest historical)
                "cap_type": "",
                
                # Override cap year and amount - for manual specification of reference year
                "override_cap_year": "",  # Example: "2023" - Year to use as reference
                "override_cap_amount": ""  # Example: 150000 - Amount to use for that year
            },
            
            # Admin Fee Inclusion in Cap/Base Calculations
            # Options: null (exclude from both), "cap" (include in cap only), 
            # "base" (include in base only), or "cap,base" (include in both)
            "admin_fee_in_cap_base": "",
        }
    }
    
    # Fields to preserve in portfolio settings
    portfolio_preserve_fields = [
        "settings.gl_inclusions", 
        "settings.gl_exclusions",
        "settings.admin_fee_percentage",
        "settings.prorate_share_method",
        "settings.base_year",
        "settings.base_year_amount",
        "settings.min_increase",
        "settings.max_increase",
        "settings.stop_amount",
        "settings.cap_settings",
        "settings.admin_fee_in_cap_base"
    ]
    
    # Load existing portfolio settings if they exist
    existing_portfolio = {}
    if os.path.exists(portfolio_file):
        try:
            with open(portfolio_file, 'r', encoding='utf-8') as f:
                existing_portfolio = json.load(f)
            print(f"Loaded existing portfolio settings")
        except Exception as e:
            print(f"Error loading existing portfolio settings: {e}")
    
    # Helper function to get nested dictionary values using dot notation
    def get_nested(obj, path):
        parts = path.split('.')
        current = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
        
    # Helper function to set nested dictionary values using dot notation
    def set_nested(obj, path, value):
        parts = path.split('.')
        current = obj
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    # Create the portfolio settings, preserving specified fields
    portfolio_settings = default_portfolio_settings.copy()
    
    # Preserve specified fields from existing settings
    if existing_portfolio:
            
        # Preserve specified fields
        for field in portfolio_preserve_fields:
            value = get_nested(existing_portfolio, field)
            if value is not None:
                # Replace any null values in dictionaries with empty strings
                if isinstance(value, dict):
                    for k, v in value.items():
                        if v is None:
                            value[k] = ""
                # Replace any null values in lists with empty strings
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            for k, v in item.items():
                                if v is None:
                                    item[k] = ""
                set_nested(portfolio_settings, field, value)
    
    # Update metadata timestamp
    portfolio_settings["metadata"]["created_at"] = datetime.datetime.now().isoformat()
    
    # Save portfolio settings
    with open(portfolio_file, 'w', encoding='utf-8') as f:
        json.dump(portfolio_settings, f, indent=2)
    
    print(f"Updated portfolio settings file: {portfolio_file}")
    
    # Group tenants by property
    tenants_by_property = defaultdict(list)
    for tenant in tenants:
        property_id = tenant.get('Property ID')
        if property_id:
            tenants_by_property[property_id].append(tenant)
    
    # Fields to preserve in property settings
    property_preserve_fields = [
        "settings.gl_inclusions", 
        "settings.gl_exclusions",
        "settings.prorate_share_method",
        "settings.admin_fee_percentage",
        "settings.base_year",
        "settings.base_year_amount",
        "settings.min_increase",
        "settings.max_increase",
        "settings.stop_amount",
        "settings.cap_settings",
        "settings.admin_fee_in_cap_base",
        "capital_expenses"  # Preserve capital expenses that can be amortized over time
    ]
    
    # Fields to preserve in tenant settings
    tenant_preserve_fields = [
        "settings.prorate_share_method",
        "settings.fixed_pyc_share",
        "settings.gl_inclusions",
        "settings.gl_exclusions",
        "settings.admin_fee_percentage",
        "settings.base_year",
        "settings.base_year_amount",
        "settings.min_increase",
        "settings.max_increase",
        "settings.stop_amount",
        "settings.cap_settings",
        "settings.admin_fee_in_cap_base",
        "capital_expenses"  # Preserve capital expenses that can be amortized over time
    ]
    
    # Create/update property and tenant files
    property_count = 0
    tenant_count = 0
    new_property_count = 0
    updated_property_count = 0
    new_tenant_count = 0
    updated_tenant_count = 0
    
    for property_data in properties:
        property_id = property_data.get('Property ID')
        if not property_id:
            continue
            
        # Create property directory and tenant directory
        property_specific_dir = os.path.join(property_dir, property_id)
        tenant_dir = os.path.join(property_specific_dir, 'TenantSettings')
        
        for directory in [property_specific_dir, tenant_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
        # Default property settings template with examples and explanations
        default_property_settings = {
            "property_id": property_id,
            "name": property_data.get('Property Name', ''),
            "total_rsf": property_data.get('Total RSF', 0),
            "metadata": {
                "created_at": datetime.datetime.now().isoformat(),
                "description": f"Recovery settings for property {property_id}",
                "format_notes": {
                    "number_format": "Percentages are stored differently depending on the field: Most percentage values are stored as decimals (5% as 0.05), except fixed_pyc_share which is stored as the actual percentage value (5.138% as 5.138)",
                    "date_format": "Dates should be in MM/DD/YYYY or YYYY-MM-DD format",
                    "gl_account_format": "GL accounts can be specified with or without the MR prefix",
                    "admin_fee_in_cap_base": "Controls admin fee inclusion: \"\" (exclude from both), \"cap\" (include in cap only), \"base\" (include in base only), \"cap,base\" (include in both)",
                    "capital_expenses": "Capital expenses are major expenditures that can be amortized over multiple years. The system calculates the amortized amount by dividing the total cost by the amortization period. Each expense needs an ID, description, year incurred, total amount, and amortization period in years."
                }
            },
            # Capital expenses that can be amortized over time
            "capital_expenses": [
                {
                    "id": "",
                    "description": "",
                    "year": "",
                    "amount": "",
                    "amort_years": ""
                }
            ],
            "settings": {
                # GL Account Inclusions/Exclusions - Property-specific overrides
                "gl_inclusions": {
                    # Example: ["5010", "5020", "5030"] - Include these GL accounts at property level
                    "ret": [],  # Property-specific GL accounts to include for Real Estate Tax
                    "cam": [],  # Property-specific GL accounts to include for CAM
                    "admin_fee": []  # Property-specific GL accounts to include for admin fee
                },
                "gl_exclusions": {
                    # Example: ["6010", "6020", "6030"] - Exclude these GL accounts at property level
                    "ret": [],  # Property-specific GL accounts to exclude from Real Estate Tax
                    "cam": [],  # Property-specific GL accounts to exclude from CAM
                    "admin_fee": [],  # Property-specific GL accounts to exclude from admin fee
                    "base": [],  # Property-specific GL accounts to exclude from base year calculations
                    "cap": []  # Property-specific GL accounts to exclude from cap calculations
                },
                
                # Property Information
                "square_footage": property_data.get('Total RSF') or "",  # Example: 100000 - Property's total square footage
                
                # Pro-rata Share Method at Property Level
                # Options: "RSF" (based on square footage), "Fixed" (fixed percentage), "Custom" (tenant-specific)
                "prorate_share_method": "",
                
                # Admin Fee Settings - Property-specific
                # Example: 0.15 for 15% - Overrides portfolio setting for this property only
                "admin_fee_percentage": "",
                
                # Base Year Settings - Property-specific defaults
                "base_year": "",  # Example: "2020" - Base year for all tenants in this property
                "base_year_amount": "",  # Example: 100000 - Fixed base amount for property (not tenant share)
                
                # Increase Limit Settings - Property-specific defaults
                "min_increase": "",  # Example: 0.03 for 3% - Minimum annual increase for all tenants
                "max_increase": "",  # Example: 0.05 for 5% - Maximum annual increase for all tenants
                "stop_amount": "",   # Example: 5.75 - Stop amount per square foot for property
                
                # Cap Settings - Property-specific defaults
                "cap_settings": {
                    # Example: 0.05 for 5% - Maximum percentage increase allowed per year
                    "cap_percentage": "",
                    
                    # Options: "previous_year" (compares to immediate prior year only)
                    # or "highest_previous_year" (compares to highest of all prior years)
                    "cap_type": "",
                    
                    # Override cap year and amount - for manual specification of reference year
                    "override_cap_year": "",  # Example: "2023" - Year to use as reference
                    "override_cap_amount": ""  # Example: 150000 - Amount to use for that year
                },
                
                # Admin Fee in Cap/Base - Property-specific setting
                # Options: null (exclude from both), "cap" (include in cap only), 
                # "base" (include in base only), or "cap,base" (include in both)
                "admin_fee_in_cap_base": ""  
            }
        }
        
        # Path to existing property settings file
        property_settings_file = os.path.join(property_specific_dir, 'property_settings.json')
        
        # Load existing property settings if they exist
        existing_property = {}
        if os.path.exists(property_settings_file):
            try:
                with open(property_settings_file, 'r', encoding='utf-8') as f:
                    existing_property = json.load(f)
                # Ensure capital_expenses exists even in older files
                if "capital_expenses" not in existing_property or not existing_property["capital_expenses"]:
                    existing_property["capital_expenses"] = [
                        {
                            "id": "",
                            "description": "",
                            "year": "",
                            "amount": "",
                            "amort_years": ""
                        }
                    ]
                updated_property_count += 1
            except Exception as e:
                print(f"Error loading existing property settings for {property_id}: {e}")
        else:
            new_property_count += 1
        
        # Create property settings, preserving specified fields
        property_settings = default_property_settings.copy()
        
        # Preserve specified fields from existing settings
        if existing_property:
            # Helper functions defined earlier in the portfolio section
            
            # Preserve specified fields
            for field in property_preserve_fields:
                value = get_nested(existing_property, field)
                if value is not None:
                    # Replace any null values in dictionaries with empty strings
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if v is None:
                                value[k] = ""
                    # Replace any null values in lists with empty strings
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                for k, v in item.items():
                                    if v is None:
                                        item[k] = ""
                    set_nested(property_settings, field, value)
        
        # Update metadata timestamp
        property_settings["metadata"]["created_at"] = datetime.datetime.now().isoformat()
        
        # Save property settings
        with open(property_settings_file, 'w', encoding='utf-8') as f:
            json.dump(property_settings, f, indent=2)
            
        property_count += 1
        
        # Create/update tenant settings files for this property
        for tenant in tenants_by_property.get(property_id, []):
            tenant_id = tenant.get('Tenant ID')
            if tenant_id is None:  # Skip if tenant_id is None
                continue
            
            # Get CAM data if available - but we'll only use it for new tenants
            # or when specific fields aren't already set in existing tenant settings
            cam_data = tenant_cam_lookup.get(tenant_id, {})
            tenant_gla = cam_data.get('TenantGLA', 0)
            pro_rata_share = cam_data.get('ProRataShare', tenant.get('Share %', 0))
            fixed_pyc_share = cam_data.get('FixedProRataPYC', '')  # Keep as empty string if not present
            stop_amount = cam_data.get('STOP', '')
            min_increase = cam_data.get('MININCR', '')
            max_increase = cam_data.get('MAXINCR', '')
                
            # Get property total RSF
            property_total_rsf = property_data.get('Total RSF', 0)
            
            # Default tenant settings template with examples and explanations
            default_tenant_settings = {
                "tenant_id": tenant_id,
                "name": tenant.get('Tenant Name', ''),
                "property_id": property_id,
                "suite": tenant.get('Suite', ''),
                "lease_start": tenant.get('Lease Start', ''),  # Format: "MM/DD/YYYY" or "YYYY-MM-DD"
                "lease_end": tenant.get('Lease End', ''),      # Format: "MM/DD/YYYY" or "YYYY-MM-DD"
                "metadata": {
                    "created_at": datetime.datetime.now().isoformat(),
                    "description": f"Recovery settings for tenant {tenant_id} in property {property_id}",
                    "format_notes": {
                        "number_format": "Percentages are stored differently depending on the field: Most percentage values are stored as decimals (5% as 0.05), except fixed_pyc_share which is stored as the actual percentage value (5.138% as 5.138)",
                        "date_format": "Dates should be in MM/DD/YYYY or YYYY-MM-DD format",
                        "gl_account_format": "GL accounts can be specified with or without the MR prefix",
                        "admin_fee_in_cap_base": "Controls admin fee inclusion: \"\" (exclude from both), \"cap\" (include in cap only), \"base\" (include in base only), \"cap,base\" (include in both)",
                        "capital_expenses": "Capital expenses are major expenditures that can be amortized over multiple years. The system calculates the amortized amount by dividing the total cost by the amortization period. Each expense needs an ID, description, year incurred, total amount, and amortization period in years. For tenant-level capital expenses, the amount is applied only to this tenant."
                    }
                },
                # Capital expenses that can be amortized over time
                "capital_expenses": [
                    {
                        "id": "",
                        "description": "",
                        "year": "",
                        "amount": "",
                        "amort_years": ""
                    }
                ],
                "settings": {
                    # GL Account Inclusions/Exclusions - Tenant-specific overrides
                    "gl_inclusions": {
                        # Example: ["5010", "5020", "5030"] - Include these GL accounts for this tenant only
                        "ret": [],  # Tenant-specific GL accounts to include for Real Estate Tax
                        "cam": [],  # Tenant-specific GL accounts to include for CAM
                        "admin_fee": []  # Tenant-specific GL accounts to include for admin fee
                    },
                    "gl_exclusions": {
                        # Example: ["6010", "6020", "6030"] - Exclude these GL accounts for this tenant only
                        "ret": [],  # Tenant-specific GL accounts to exclude from Real Estate Tax
                        "cam": [],  # Tenant-specific GL accounts to exclude from CAM
                        "admin_fee": [],  # Tenant-specific GL accounts to exclude from admin fee
                        "base": [],  # Tenant-specific GL accounts to exclude from base year calculations
                                    # These exclusions are IN ADDITION TO regular CAM exclusions
                        "cap": []  # Tenant-specific GL accounts to exclude from cap calculations
                                  # These exclusions are IN ADDITION TO regular CAM exclusions
                    },
                    
                    # Tenant Information
                    "square_footage": tenant_gla or tenant.get('TenantGLA') or "",  # Example: 5000 - Tenant's leased area
                    
                    # Pro-rata Share Information - Tenant-specific
                    "prorate_share_method": "Fixed" if fixed_pyc_share else "",  # "RSF", "Fixed", or "Custom"
                    "fixed_pyc_share": fixed_pyc_share or "",  # Example: 0.0525 for 5.25% - Fixed prior year charge share
                    
                    # Admin Fee Settings - Tenant-specific override
                    # Example: 0.15 for 15% - Overrides property and portfolio admin fee settings
                    "admin_fee_percentage": "",
                    
                    # Base Year Settings - Tenant-specific
                    "base_year": tenant.get('Base Year') or "",  # Example: "2020" - Tenant's specific base year
                    "base_year_amount": tenant.get('Initial CAM Floor') or "",  # Example: 5000 - Fixed base amount for tenant
                                                                               # Unlike property level, this IS tenant's share
                    
                    # Increase Limit Settings - Tenant-specific
                    "min_increase": min_increase or "",  # Example: 0.03 for 3% - Minimum annual increase for this tenant
                    "max_increase": max_increase or "",  # Example: 0.05 for 5% - Maximum annual increase for this tenant
                    "stop_amount": stop_amount or "",   # Example: 5.75 - Stop amount per square foot for this tenant
                    
                    # Cap Settings - Tenant-specific
                    "cap_settings": {
                        # Example: 0.05 for 5% - Maximum percentage increase allowed for this tenant
                        "cap_percentage": "",
                        
                        # Options: "previous_year" (cap based on prior year only) 
                        # or "highest_previous_year" (cap based on highest previous year)
                        "cap_type": "",
                        
                        # Override cap year and amount - for manual specification of reference year
                        "override_cap_year": "",  # Example: "2023" - Year to use as reference
                        "override_cap_amount": ""  # Example: 150000 - Amount to use for that year (total property amount)
                    },
                    
                    # Admin Fee in Cap/Base - Tenant-specific setting
                    # Options: null (exclude admin fee from both cap and base calculations)
                    # "cap" (include admin fee in cap calculations only)
                    # "base" (include admin fee in base calculations only)
                    # "cap,base" (include admin fee in both cap and base calculations)
                    "admin_fee_in_cap_base": ""
                }
            }
            
            # Save tenant settings with tenant name in filename
            tenant_name = tenant.get('Tenant Name', '').strip()
            # Replace invalid filename characters with underscores
            safe_tenant_name = ''.join(c if c.isalnum() or c in ' .-' else '_' for c in tenant_name)
            # Limit length and add tenant ID
            safe_tenant_name = safe_tenant_name[:50]  # Limit length to avoid too long filenames
            filename = f"{safe_tenant_name} - {tenant_id}.json" if safe_tenant_name else f"{tenant_id}.json"
            
            tenant_settings_file = os.path.join(tenant_dir, filename)
            
            # Load existing tenant settings if they exist
            existing_tenant = {}
            if os.path.exists(tenant_settings_file):
                try:
                    with open(tenant_settings_file, 'r', encoding='utf-8') as f:
                        existing_tenant = json.load(f)
                    # Ensure capital_expenses exists even in older files
                    if "capital_expenses" not in existing_tenant or not existing_tenant["capital_expenses"]:
                        existing_tenant["capital_expenses"] = [
                            {
                                "id": "",
                                "description": "",
                                "year": "",
                                "amount": "",
                                "amort_years": ""
                            }
                        ]
                    updated_tenant_count += 1
                except Exception as e:
                    print(f"Error loading existing tenant settings for {tenant_id}: {e}")
            else:
                new_tenant_count += 1
            
            # Create tenant settings, preserving specified fields
            tenant_settings = default_tenant_settings.copy()
            
            # Preserve specified fields from existing settings
            if existing_tenant:
                # IMPORTANT: Preserve all specified fields - this ensures manually edited values
                # in existing files always take precedence over source data values
                for field in tenant_preserve_fields:
                    value = get_nested(existing_tenant, field)
                    if value is not None:
                        # Replace any null values in dictionaries with empty strings
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if v is None:
                                    value[k] = ""
                        # Replace any null values in lists with empty strings
                        elif isinstance(value, list):
                            for i, item in enumerate(value):
                                if isinstance(item, dict):
                                    for k, v in item.items():
                                        if v is None:
                                            item[k] = ""
                        # Always use the value from the existing file for critical fields
                        set_nested(tenant_settings, field, value)
                        
                        # Print a debug message when we find a manually edited critical field
                        # that differs from source data (like fixed pyc share)
                        if field == "settings.fixed_pyc_share" and value != fixed_pyc_share and fixed_pyc_share is not None:
                            # Use a set to track which tenant messages we've already printed to avoid duplicates
                            if not hasattr(generate_settings_files, 'tenant_debug_messages'):
                                generate_settings_files.tenant_debug_messages = set()
                            
                            message_key = f"{tenant_id}_{field}_{value}_{fixed_pyc_share}"
                            if message_key not in generate_settings_files.tenant_debug_messages:
                                print(f"Preserving manually edited value for Tenant {tenant_id}: {field}={value} (differs from source data {fixed_pyc_share})")
                                generate_settings_files.tenant_debug_messages.add(message_key)
            
            # Update metadata timestamp and non-preserved fields
            tenant_settings["metadata"]["created_at"] = datetime.datetime.now().isoformat()
            tenant_settings["name"] = tenant.get('Tenant Name', '')
            tenant_settings["suite"] = tenant.get('Suite', '')
            tenant_settings["lease_start"] = tenant.get('Lease Start', '')
            tenant_settings["lease_end"] = tenant.get('Lease End', '')
            
            # Special handling for cap_settings to ensure new fields get added
            if existing_tenant and "settings" in existing_tenant and "cap_settings" in existing_tenant["settings"]:
                # Start with the new template
                updated_cap_settings = tenant_settings["settings"]["cap_settings"].copy()
                
                # Get existing cap settings
                existing_cap_settings = existing_tenant["settings"]["cap_settings"]
                
                # Copy all existing values 
                for key, value in existing_cap_settings.items():
                    if value is not None:  # Only copy non-null values
                        updated_cap_settings[key] = value
                    else:
                        updated_cap_settings[key] = ""
                
                # Ensure override fields exist
                if "override_cap_year" not in updated_cap_settings:
                    updated_cap_settings["override_cap_year"] = ""
                if "override_cap_amount" not in updated_cap_settings:
                    updated_cap_settings["override_cap_amount"] = ""
                
                # Update the tenant settings with merged cap_settings
                tenant_settings["settings"]["cap_settings"] = updated_cap_settings
            
            # Ensure override fields exist in all cases
            if "cap_settings" in tenant_settings["settings"]:
                if "override_cap_year" not in tenant_settings["settings"]["cap_settings"]:
                    tenant_settings["settings"]["cap_settings"]["override_cap_year"] = ""
                if "override_cap_amount" not in tenant_settings["settings"]["cap_settings"]:
                    tenant_settings["settings"]["cap_settings"]["override_cap_amount"] = ""
            
            # For square footage, check if we should preserve existing value
            if existing_tenant and "settings" in existing_tenant and "square_footage" in existing_tenant["settings"]:
                # Keep existing square footage if it exists, but replace null with empty string
                sf_value = existing_tenant["settings"]["square_footage"]
                tenant_settings["settings"]["square_footage"] = "" if sf_value is None else sf_value
            else:
                # Otherwise use the source data
                tenant_settings["settings"]["square_footage"] = tenant_gla or tenant.get('TenantGLA') or ""
            
            # Save tenant settings
            with open(tenant_settings_file, 'w', encoding='utf-8') as f:
                json.dump(tenant_settings, f, indent=2)
                
            tenant_count += 1
    
    print(f"Property settings: {new_property_count} new, {updated_property_count} updated")
    print(f"Tenant settings: {new_tenant_count} new, {updated_tenant_count} updated")
    
    # Return counts for reporting
    return property_count, tenant_count

def main():
    """Main function to process data: convert CSV to JSON, extract GL information, and generate settings files"""
    print("STEP 1: Converting CSV files to JSON format")
    input_folder = "Input"
    output_folder = "Output/JSON"
    
    # First, convert CSV files to JSON
    csv_to_json_success = convert_csv_to_json(input_folder, output_folder)
    if not csv_to_json_success:
        print("Error converting CSV files. Aborting process.")
        return
    
    print("\nSTEP 2: Extracting GL account information with property and period data")
    # Next, extract GL descriptions and update categories
    gl_output_file = extract_gl_descriptions()
    
    print("\nSTEP 3: Generating settings files for portfolio, properties, and tenants")
    # Clean up old files first if they exist
    old_files = [
        os.path.join('Data', 'ProcessedOutput', 'portfolio_settings.json'),
        os.path.join('Data', 'ProcessedOutput', 'property_settings.json'),
        os.path.join('Data', 'ProcessedOutput', 'tenant_settings.json')
    ]
    
    for old_file in old_files:
        if os.path.exists(old_file):
            os.remove(old_file)
            print(f"Removed old file: {old_file}")
            
    # Create a README file with guidance on settings format
    readme_path = os.path.join('Data', 'ProcessedOutput', 'SETTINGS_FORMAT_GUIDE.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write("""# CAM Reconciliation Settings Format Guide

## Overview
This guide explains the format and options for all settings used in the CAM reconciliation system.

## Hierarchy
Settings follow a hierarchy where more specific levels override more general levels:
1. **Portfolio Level** - Global default settings
2. **Property Level** - Settings for each property that override portfolio defaults
3. **Tenant Level** - Tenant-specific settings that override property settings

## Common Settings Format

### Capital Expenses
Capital expenses are major expenditures that can be amortized over multiple years. These are defined at both property and tenant levels.

```json
"capital_expenses": [
  {
    "id": "CAP001",                 // Unique identifier for the capital expense
    "description": "Roof repair",   // Description of the capital expense
    "year": 2024,                   // Year in which the expense was incurred
    "amount": 50000,                // Total cost of the capital expense
    "amort_years": 5                // Number of years over which to amortize the expense
  },
  {
    "id": "CAP002",
    "description": "Parking lot resurfacing",
    "year": 2023,
    "amount": 30000,
    "amort_years": 3
  }
]
```

The system will calculate the amortized amount per year by dividing the total cost by the amortization period. For expenses at the property level, tenant shares will be calculated based on their pro-rata percentages. Tenant-level capital expenses apply only to that specific tenant.

### GL Account Inclusions/Exclusions
```json
"gl_inclusions": {
  "ret": ["5010", "5020"],   // Include these GL accounts in RET calculations
  "cam": ["6010", "6020"],   // Include these GL accounts in CAM calculations
  "admin_fee": ["7010"]      // Include these GL accounts in admin fee calculations
},
"gl_exclusions": {
  "ret": ["5030", "5040"],   // Exclude these GL accounts from RET calculations
  "cam": ["6030", "6040"],   // Exclude these GL accounts from CAM calculations
  "admin_fee": ["7020"],     // Exclude these GL accounts from admin fee calculations
  "base": ["8010", "8020"],  // Exclude these accounts from base year calculations
  "cap": ["9010", "9020"]    // Exclude these accounts from cap calculations
}
```

### Pro-rata Share Method
```json
"prorate_share_method": "Fixed",              // Options: "RSF", "Fixed", "Custom"
"fixed_pyc_share": 5.138                      // Example: 5.138 means 5.138% - Fixed prior year charge share
```

### Admin Fee Settings
```json
"admin_fee_percentage": 0.15,                 // Example: 0.15 for 15%
"admin_fee_in_cap_base": "cap,base"           // Options: "", "cap", "base", "cap,base"
```

### Base Year Settings
```json
"base_year": "2020",                          // The reference year for calculations
"base_year_amount": 100000                    // Fixed amount override (property level)
                                              // or tenant share (tenant level)
```

### Cap Settings
```json
"cap_settings": {
  "cap_percentage": 0.05,                     // Example: 0.05 for 5% maximum increase
  "cap_type": "previous_year",                // Options: "previous_year" or "highest_previous_year"
  "override_cap_year": "2023",                // Example: "2023" - Manual override for reference year
  "override_cap_amount": 150000               // Example: 150000 - Amount to use for that year
},
"min_increase": 0.03,                         // Example: 0.03 for 3% minimum
"max_increase": 0.05                          // Example: 0.05 for 5% maximum
```

## Special Format Notes

### Number Format
Percentages are stored differently depending on the field:
- Most percentage values are stored as decimals: 5% is stored as `0.05`, 15% is stored as `0.15`
- Exception: `fixed_pyc_share` is stored as the actual percentage value: 5.138% is stored as `5.138`

### Date Format
Dates should be in one of these formats:
- `MM/DD/YYYY` (e.g., "01/15/2022")
- `YYYY-MM-DD` (e.g., "2022-01-15")

### GL Account Format
GL accounts can be specified with or without the "MR" prefix. The system will handle both formats.

### Admin Fee in Cap and Base
The `admin_fee_in_cap_base` field controls whether admin fees are included in cap and base calculations:
- `""` - Admin fees excluded from both cap and base calculations
- `"cap"` - Admin fees included in cap calculations only
- `"base"` - Admin fees included in base calculations only
- `"cap,base"` - Admin fees included in both cap and base calculations
""")
        print(f"Created settings format guide: {readme_path}")
    
    # Generate settings files
    property_count, tenant_count = generate_settings_files()
    
    # Load property and tenant data for custom overrides
    properties_path = os.path.join('Output', 'JSON', '1. Properties.json')
    tenants_path = os.path.join('Output', 'JSON', '2. Tenants.json')
    
    properties = load_json_file(properties_path)
    tenants = load_json_file(tenants_path)
    
    print("\nSTEP 4: Creating custom overrides template")
    # Generate custom overrides template
    override_count = generate_custom_overrides(tenants, properties)
    
    print(f"\nProcess completed successfully!")
    print(f"Final outputs:")
    print(f"1. JSON files in {output_folder}")
    print(f"2. GL account data: {gl_output_file}")
    print(f"3. Recovery settings: {property_count} property files and {tenant_count} tenant files")
    print(f"4. Custom overrides template with {override_count} tenants")

if __name__ == "__main__":
    main()