# CAM/TAX Reconciliation Engine

A comprehensive system for calculating Common Area Maintenance (CAM) and Real Estate Tax (RET) reconciliations for commercial properties.

## Overview

The CAM/TAX Reconciliation Engine processes general ledger data, applies various adjustments (base year, caps, occupancy factors), and generates detailed tenant billing reports. It supports a hierarchical settings model where tenant-specific settings override property settings, which in turn override portfolio-level defaults.

## Features

- **Hierarchical Settings**: Portfolio → Property → Tenant configuration inheritance
- **GL Processing**: Filter and categorize general ledger transactions
- **CAM/TAX/Admin Fee Calculations**: Calculate expenses with proper inclusions/exclusions
- **Base Year Adjustments**: Apply base year thresholds to expenses
- **Cap Enforcement**: Apply year-over-year increase limits
- **Occupancy Calculation**: Pro-rate expenses based on lease periods
- **Manual Overrides**: Support for custom tenant adjustments
- **Comprehensive Reporting**: Generate detailed CSV and JSON reports
- **Cap History Tracking**: Maintain historical expense records for future reconciliations

## Installation

1. Clone this repository
2. Ensure the proper directory structure is in place:
   - `Data/` - Settings and input data
   - `Input/` - Raw input files
   - `Output/` - Generated outputs and reports

## Usage

```bash
python reconciliation.py --property_id PROPERTY_ID --recon_year YEAR [--last_bill YYYYMM] [--tenant_id TENANT_ID]
```

### Arguments

- `--property_id`: Property identifier (e.g., ELW)
- `--recon_year`: Reconciliation year (e.g., 2024)
- `--last_bill`: Optional last billing date in YYYYMM format (for catch-up periods)
- `--tenant_id`: Optional tenant ID to process only one tenant
- `--output_dir`: Directory for output reports (default: Output/Reports)
- `--skip_cap_update`: Skip updating cap history (for testing)
- `--verbose`: Enable verbose logging

### Examples

```bash
# Process entire property
python reconciliation.py --property_id ELW --recon_year 2024

# Process property with catch-up period through May 2025
python reconciliation.py --property_id ELW --recon_year 2024 --last_bill 202505

# Process a single tenant
python reconciliation.py --property_id ELW --recon_year 2024 --tenant_id 1330
```

## Data Structure

### Settings Files Hierarchy

The system uses a three-level settings hierarchy:

1. **Portfolio Settings**: `Data/ProcessedOutput/PortfolioSettings/portfolio_settings.json`
2. **Property Settings**: `Data/ProcessedOutput/PropertySettings/{PROPERTY_ID}/property_settings.json`
3. **Tenant Settings**: `Data/ProcessedOutput/PropertySettings/{PROPERTY_ID}/TenantSettings/{TENANT_NAME} - {TENANT_ID}.json`

### GL Data

GL data is expected in: `Output/JSON/GL Master 3.json`

### Cap History

Cap history is stored in: `Data/cap_history.json`

### Manual Overrides

Custom overrides are stored in: `Data/ProcessedOutput/CustomOverrides/custom_overrides.json`

## Configuration Fields

### Key Settings

| Setting | Description | Format |
|---------|-------------|--------|
| `prorate_share_method` | Method for calculating tenant's share (`RSF` or `Fixed`) | String |
| `fixed_pyc_share` | Fixed percentage share (used when `prorate_share_method` is `Fixed`) | Number as percentage (e.g., `5.138` for 5.138%) |
| `admin_fee_percentage` | Percentage for admin fee calculation | Decimal (e.g., `0.15` for 15%) |
| `base_year` | Base year for expense comparison | Year (e.g., `2022`) |
| `base_year_amount` | Base year amount threshold | Number |
| `cap_settings.cap_percentage` | Maximum allowed annual increase percentage | Decimal (e.g., `0.05` for 5%) |
| `cap_settings.cap_type` | Type of cap calculation (`previous_year` or `highest_previous_year`) | String |
| `min_increase` | Minimum annual increase percentage | Decimal (e.g., `0.03` for 3%) |
| `max_increase` | Maximum annual increase percentage | Decimal (e.g., `0.05` for 5%) |
| `stop_amount` | Stop amount per square foot | Number |
| `admin_fee_in_cap_base` | Controls admin fee inclusion in cap and base calculations | String: `""`, `"cap"`, `"base"`, or `"cap,base"` |

### GL Inclusion/Exclusion

GL accounts can be included or excluded from different calculation categories:

```json
"gl_inclusions": {
  "ret": ["5010", "5020"],   // Include in Real Estate Tax
  "cam": ["6010", "6020"],   // Include in CAM
  "admin_fee": ["7010"]      // Include in admin fee base
},
"gl_exclusions": {
  "ret": ["5030", "5040"],   // Exclude from Real Estate Tax
  "cam": ["6030", "6040"],   // Exclude from CAM
  "admin_fee": ["7020"],     // Exclude from admin fee base
  "base": ["8010", "8020"],  // Exclude from base year calculations
  "cap": ["9010", "9020"]    // Exclude from cap calculations
}
```

### Capital Expenses

Capital expenses are defined as:

```json
"capital_expenses": [
  {
    "id": "CAP001",                 // Unique identifier
    "description": "Roof repair",   // Description
    "year": 2024,                   // Year incurred
    "amount": 50000,                // Total amount
    "amort_years": 5                // Amortization period
  }
]
```

## Module Structure

- `reconciliation.py`: Main CLI entrypoint
- `settings_loader.py`: Loads and merges settings
- `cap_override_handler.py`: Manages cap history
- `gl_loader.py`: Filters and groups GL entries
- `calculations/`:
  - `cam_tax_admin.py`: CAM/TAX/Admin fee calculations
  - `base_year.py`: Base year adjustments
  - `caps.py`: Cap limit enforcement
  - `capital_expenses.py`: Capital expense amortization
- `period_calculator.py`: Period calculation
- `occupancy_calculator.py`: Tenant occupancy factors
- `manual_override_loader.py`: Loads custom overrides
- `report_generator.py`: Generates tenant reports
- `cap_history_updater.py`: Updates cap history

## Output Reports

The system generates two types of reports:

1. **CSV Report**: Summary report with one row per tenant, including all key calculations
2. **JSON Report**: Detailed report with complete calculation breakdowns for each tenant

## Calculation Flow

1. Load settings from all levels (portfolio, property, tenant)
2. Apply cap overrides if specified
3. Load and filter GL data based on settings
4. Calculate CAM, TAX, and admin fee amounts
5. Apply base year adjustments
6. Enforce cap limits
7. Calculate tenant shares with occupancy factors
8. Apply any manual overrides
9. Generate reports
10. Update cap history for future reconciliations

## Example Calculation

For a tenant with:
- 5% share of property
- Base year threshold of $10,000
- 5% cap on annual increases
- 75% occupancy (9 of 12 months)

The calculation would be:

1. Property CAM/TAX total: $120,000
2. After base year: $110,000 ($120,000 - $10,000)
3. After cap: $105,000 (assuming last year was $100,000)
4. Tenant's share: $5,250 ($105,000 × 5%)
5. Occupancy adjusted: $3,937.50 ($5,250 × 75%)
6. Final billing: $3,937.50 (+ any manual override)