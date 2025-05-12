# LastRec - CAM Reconciliation System

## Overview

LastRec is a comprehensive CAM (Common Area Maintenance) reconciliation calculator system designed to streamline the process of calculating tenant charges for commercial real estate properties. The system handles complex calculations including:

- CAM and Real Estate Tax reconciliations
- Administrative fee calculations
- Base year adjustments
- Cap limits and caps history tracking
- Capital expense amortization
- Tenant occupancy adjustment
- Payment tracking and monthly charge calculations

## Project Structure

- `New Full.py` - Core reconciliation calculator script
- `process_data.py` - Data preparation utility for input files
- `/Data/` - Contains processed output and settings
- `/Input/` - Place for input CSV files
- `/Output/` - Generated reports and JSON data

## Getting Started

### Prerequisites

- Python 3.6+
- Required Python packages: (standard library)

### Installation

1. Clone or download this repository
2. Make sure your input files are in the `/Input/` directory

### Running the Data Processor

The data processor converts CSV input files to JSON and prepares the settings structure:

```
python process_data.py
```

This will:
1. Convert all CSV files in the Input folder to JSON format
2. Extract and categorize GL accounts with property and period data
3. Generate a hierarchical folder structure for settings files
4. Create a custom overrides template

### Running the Reconciliation Calculator

The main reconciliation calculator can be run with:

```
python "New Full.py" --property_id PROPERTY_ID --recon_year YEAR [--tenant_id TENANT_ID] [--last_bill YYYYMM]
```

Parameters:
- `--property_id`: Property identifier (e.g., ELW)
- `--recon_year`: Reconciliation year (e.g., 2024)
- `--tenant_id`: (Optional) Process only one specific tenant
- `--last_bill`: (Optional) Last billing date in YYYYMM format for catch-up calculations
- `--categories`: (Optional) Comma-separated list of expense categories (default: cam,ret)
- `--skip_cap_update`: (Optional) Skip updating the cap history (for testing)
- `--verbose`: (Optional) Enable verbose logging

## Features

### Input Data Processing

The `process_data.py` script:
- Converts CSV files to JSON format
- Extracts GL account information with property and period data
- Generates a hierarchical settings structure for portfolio, properties, and tenants
- Creates a custom overrides template

### Enhanced Reconciliation Calculation

The `New Full.py` script:
- Performs multi-level settings inheritance (portfolio → property → tenant)
- Filters GL accounts based on inclusion/exclusion rules
- Calculates CAM, tax, and admin fee amounts
- Applies base year adjustments and cap limits
- Handles capital expense amortization
- Calculates tenant proration share and occupancy adjustments
- Tracks tenant payments and balances
- Generates detailed CSV and JSON reports

### Settings Hierarchy

The system uses a three-tiered settings approach:
1. **Portfolio Level** - Global default settings
2. **Property Level** - Settings for each property that override portfolio defaults
3. **Tenant Level** - Tenant-specific settings that override property settings

## File Formats

### Input Files

The system expects these CSV files in the Input directory:
- `GL Master 3.csv` - General ledger data with property, GL account, and period information
- `1. Properties.csv` - Property information including ID, name, and total square footage
- `2. Tenants.csv` - Tenant information including ID, property, lease dates, etc.
- `Tenant CAM data1.csv` - CAM-specific data for tenants including proration and billing information
- `gl_categories_original.json` - GL account categorization information

### Output Files

The system generates:
- Hierarchical settings files in JSON format
- Enhanced CAM reconciliation calculations in CSV and JSON formats
- Cap history tracking in JSON format
- Detailed logs of the reconciliation process

## Settings Structure

See the `Data/ProcessedOutput/SETTINGS_FORMAT_GUIDE.md` file for detailed information on the available settings and their formats.

## License

Proprietary and confidential. Unauthorized copying or use is prohibited.