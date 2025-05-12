# LastRec Setup Guide

This guide will help you prepare your data and set up the LastRec system for CAM reconciliation calculations.

## Input Data Requirements

To use the LastRec system, you'll need to prepare the following CSV files in the `Input` folder:

### 1. GL Master Data (GL Master 3.csv)

This file should contain general ledger transaction data with the following columns:
- `Property ID`: Property identifier
- `PERIOD`: Accounting period in YYYYMM format
- `Journal Ref`: Reference number
- `GL Account`: GL account code (with or without MR prefix)
- `GL Description`: Description of the GL account
- `Net Amount`: Transaction amount

### 2. Properties Data (1. Properties.csv)

This file should contain property information with the following columns:
- `Property ID`: Unique identifier for the property
- `Property Name`: Name of the property
- `Total RSF`: Total rentable square footage
- `Notes`: Additional property information
- `Last Rentup Date`: Date of last rent update

### 3. Tenants Data (2. Tenants.csv)

This file should contain tenant information with the following columns:
- `Tenant ID`: Unique identifier for the tenant
- `Property ID`: Property where the tenant is located
- `Tenant Name`: Name of the tenant
- `Suite`: Suite number or identifier
- `Lease Start`: Lease start date
- `Lease End`: Lease end date
- `Income Category`: Category for income tracking
- `Share %`: Tenant's share percentage (if fixed)
- `Base Year`: Base year for CAM calculations
- `Initial CAM Floor`: Initial CAM floor amount

### 4. Tenant CAM Data (Tenant CAM data1.csv)

This file should contain tenant CAM-specific data with the following columns:
- `TenantID`: Tenant identifier
- `TenantName`: Tenant name
- `PropertyID`: Property identifier
- `TenantGLA`: Tenant gross leasable area (square footage)
- `ProRataShare`: Pro-rata share decimal value
- `FixedProRataPYC`: Fixed prior year charge percentage
- `BASEYEAR`: Base year for calculations
- `STOP`: Stop amount per square foot
- `MININCR`: Minimum increase percentage
- `MAXINCR`: Maximum increase percentage
- `BillingMonth`: Billing month in YYYY-MM format
- `TotalBilledAmount`: Total amount billed
- `MatchedEstimate`: Monthly estimate amount

### 5. GL Categories (gl_categories_original.json)

This JSON file should define GL account categories with the following structure:
```json
{
  "gl_account_lookup": {
    "5000-5999": {
      "category": "Operating Expenses",
      "group": "Recoveries"
    },
    "6000-6999": {
      "category": "Real Estate Taxes",
      "group": "Recoveries"
    }
  },
  "categories": [
    {
      "group": "Recoveries",
      "subcategories": [
        {
          "name": "Operating Expenses",
          "subcategories": [
            {
              "name": "Property Maintenance"
            },
            {
              "name": "Utilities"
            }
          ]
        },
        {
          "name": "Real Estate Taxes"
        }
      ]
    }
  ]
}
```

## Data Processing Steps

After placing your CSV files in the `Input` folder, follow these steps:

1. **Process Data**: Run `python process_data.py` to:
   - Convert CSV files to JSON format
   - Extract GL account information
   - Generate settings files hierarchy

2. **Review Settings Files**: Check the generated settings files in:
   - `Data/ProcessedOutput/PortfolioSettings/`
   - `Data/ProcessedOutput/PropertySettings/`
   - `Data/ProcessedOutput/CustomOverrides/`

3. **Update Settings**: Customize settings for your specific needs:
   - GL account inclusions and exclusions
   - Admin fee percentages
   - Cap settings
   - Base year values
   - Capital expenses

## Settings Configuration

### Portfolio-Level Settings

Edit `Data/ProcessedOutput/PortfolioSettings/portfolio_settings.json` to adjust:
- Default GL account inclusions/exclusions
- Default admin fee percentage
- Default cap and base year settings
- Default pro-rata share method

### Property-Level Settings

For each property, edit the corresponding settings file in `Data/ProcessedOutput/PropertySettings/[PROPERTY_ID]/property_settings.json` to set:
- Property-specific GL inclusions/exclusions
- Property-specific admin fee percentage
- Property capital expenses
- Property-specific cap and base year settings

### Tenant-Level Settings

For each tenant, edit the corresponding settings file in `Data/ProcessedOutput/PropertySettings/[PROPERTY_ID]/TenantSettings/[TENANT_NAME] - [TENANT_ID].json` to:
- Set tenant-specific square footage
- Configure fixed pro-rata share if applicable
- Specify tenant-specific cap, base year settings
- Add tenant-specific capital expenses

### Custom Overrides

To override calculated amounts for specific tenants, edit `Data/ProcessedOutput/CustomOverrides/custom_overrides.json`.

## Running Reconciliation Calculations

After configuring your settings, run the reconciliation calculator:

```
python "New Full.py" --property_id PROPERTY_ID --recon_year YEAR [--tenant_id TENANT_ID] [--last_bill YYYYMM]
```

Replace:
- `PROPERTY_ID` with your property's identifier
- `YEAR` with the reconciliation year
- `TENANT_ID` (optional) with a specific tenant ID
- `YYYYMM` (optional) with the last billing period

## Output Reports

After running the calculation, check the Output folder for:
- `Output/Reports/tenant_billing_*.csv`: CSV format report with all tenant calculations
- `Output/Reports/tenant_billing_detail_*.json`: Detailed JSON report
- `Output/enhanced_cam_reconciliation.log`: Log file with calculation details

## Troubleshooting

If you encounter issues:

1. **Missing Data**: Ensure all required CSV files are in the Input folder
2. **Format Errors**: Verify your CSV files follow the expected format
3. **Calculation Issues**: Check the log file for error messages
4. **GL Account Problems**: Verify GL account inclusions/exclusions settings