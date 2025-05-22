# Letter Generator Normalization Recommendations

This document outlines recommended normalizations for the enhanced letter generator to simplify the code and ensure all fields are directly sourced from the CSV output without additional calculations.

## CSV Reports Overview

The letter generator uses data from two main types of CSV reports:

1. **Tenant Billing CSV**: Main report with summary data for all tenants (filename pattern: `tenant_billing_{property_id}_cam_{year}_{timestamp}.csv`)
2. **GL Detail CSV**: Detailed GL account breakdown for a specific tenant (filename pattern: `GL_detail_{tenant_id}_{year}_{timestamp}.csv`)

## General Approach

The goal is to move all calculations to the New Full.py script and ensure the letter generator simply formats and displays values from the CSV without performing calculations. This will make the code easier to maintain and troubleshoot.

## Recommended Normalizations

### 1. Conditional Section Flags

Currently, the letter generator calculates whether certain sections should be displayed by checking if values are greater than zero (Lines 415-420):

```python
# Current approach:
has_base_year = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '') or 0) > 0
has_cap = float(tenant_data.get("cap_deduction", "0").strip('$').replace(',', '') or 0) > 0
has_amortization = float(tenant_data.get("amortization_total_amount", "0").strip('$').replace(',', '') or 0) > 0
has_admin_fee = float(tenant_data.get("admin_fee_net", "0").strip('$').replace(',', '') or 0) > 0
has_catchup = float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', '') or 0) != 0
```

**Recommendation**: Add explicit boolean flags in the Tenant Billing CSV for each section:
- has_base_year
- has_cap
- has_amortization
- has_admin_fee
- has_catchup

### 2. Date Formatting

Currently, the letter generator does date formatting with custom functions (Lines 61-106):

```python
# Current approach:
main_period_range = format_date_range(recon_start_date, recon_end_date)
catchup_period_range = format_date_range(catchup_start_date, catchup_end_date)
```

**Recommendation**: Include pre-formatted date ranges in the Tenant Billing CSV:
- reconciliation_period_formatted
- catchup_period_formatted

### 3. GL Detail File Path

Currently, the letter generator has complex logic to locate GL detail files (Lines 249-315):

```python
# Current approach:
gl_detail_file = find_gl_detail_file(tenant_id, gl_detail_dir)
if gl_detail_file:
    gl_details, gl_total_row = get_gl_details_for_tenant(gl_detail_file)
```

**Recommendation**: Include the full path to GL detail file in the Tenant Billing CSV:
- gl_detail_file_path

### 4. Amortization Item Handling

Currently, the letter generator dynamically accesses amortization items by index (Lines 721-734):

```python
# Current approach:
for i in range(1, amort_count + 1):
    # Get item details
    description = escape_latex(tenant_data.get(f"amortization_{i}_description", ""))
    total_amount = format_currency(tenant_data.get(f"amortization_{i}_total_amount", "0"))
    years = tenant_data.get(f"amortization_{i}_years", "")
    annual_amount = format_currency(tenant_data.get(f"amortization_{i}_annual_amount", "0"))
    tenant_share = format_currency(tenant_data.get(f"amortization_{i}_your_share", "0"))
```

**Recommendation**: Include a structured JSON string in the Tenant Billing CSV that can be parsed:
- amortization_items_json

### 5. Value Formatting

Currently, the letter generator has formatting functions for currency and percentages (Lines 34-59):

```python
# Current approach:
property_total = format_currency(tenant_data.get("property_gl_total", "0"))
tenant_pro_rata = format_percentage(tenant_data.get("share_percentage", "0"))
```

**Recommendation**: Keep these formatting functions as they provide consistent formatting, but add a consistent pattern for handling formatted values:

```python
# Recommended approach:
def get_formatted_currency(tenant_data, field_name, default="0"):
    return format_currency(tenant_data.get(field_name, default))

def get_formatted_percentage(tenant_data, field_name, default="0"):
    return format_percentage(tenant_data.get(field_name, default))
```

### 6. Conditional Override Handling

Currently, the letter generator uses separate checks for override formatting (Lines 496-499):

```python
# Current approach:
if override_amount.startswith('-'):
    override_value = override_amount[1:]  # Remove the negative sign
    document += f"{override_description} & -\\${override_value} \\\\\n"
else:
    document += f"{override_description} & \\${override_amount} \\\\\n"
```

**Recommendation**: Add a pre-formatted override field in the Tenant Billing CSV:
- override_amount_formatted

### 7. GL Detail Integration

Currently, the code has to find and parse GL detail files separately. It would be more efficient if:

1. **New Field in Tenant Billing CSV**: Add a field `gl_details_json` containing a JSON string with all GL details
2. **Alternative**: Ensure GL detail file path is correctly formatted and included in the Tenant Billing CSV

This would simplify the GL detail handling logic significantly.

## Proposed New Fields for Tenant Billing CSV

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| has_base_year | Boolean | Whether tenant has base year adjustment |
| has_cap | Boolean | Whether tenant has cap adjustment |
| has_amortization | Boolean | Whether tenant has amortization |
| has_admin_fee | Boolean | Whether tenant has admin fee |
| has_catchup | Boolean | Whether tenant has catchup period |
| reconciliation_period_formatted | String | Formatted reconciliation period (e.g., "Jan-Dec 2024") |
| catchup_period_formatted | String | Formatted catchup period (e.g., "Jan-Apr 2025") |
| gl_detail_file_path | String | Full path to GL detail CSV file |
| amortization_items_json | JSON String | JSON array of amortization items |
| override_amount_formatted | String | Pre-formatted override amount (with sign handling) |
| property_gl_total_formatted | String | Formatted property GL total |
| share_percentage_formatted | String | Formatted share percentage |
| reconciliation_year_formatted | String | Formatted reconciliation year |

## Simplified Implementation Example

With these normalizations, the letter generator could be much simpler:

```python
def generate_tenant_letter(tenant_data, debug_mode=False):
    """Generate a LaTeX letter for a tenant using simplified field access."""
    
    # Extract basic tenant info
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = escape_latex(tenant_data.get("tenant_name", ""))
    property_id = tenant_data.get("property_id", "")
    property_name = escape_latex(tenant_data.get("property_full_name", PROPERTY_NAMES.get(property_id, property_id)))
    
    # Get formatted periods
    reconciliation_period = tenant_data.get("reconciliation_period_formatted", "")
    catchup_period = tenant_data.get("catchup_period_formatted", "")
    
    # Extract financial values (already formatted in CSV)
    property_total = tenant_data.get("property_gl_total_formatted", "0.00")
    tenant_pro_rata = tenant_data.get("share_percentage_formatted", "0.00")
    tenant_share = tenant_data.get("tenant_share_amount_formatted", "0.00")
    
    # Get conditional section flags directly from CSV
    has_base_year = tenant_data.get("has_base_year", "false").lower() == "true"
    has_cap = tenant_data.get("has_cap", "false").lower() == "true"
    has_amortization = tenant_data.get("has_amortization", "false").lower() == "true"
    has_admin_fee = tenant_data.get("has_admin_fee", "false").lower() == "true"
    has_catchup = tenant_data.get("has_catchup", "false").lower() == "true"
    
    # Build the LaTeX document (simplified)
    document = f"""\\documentclass{{article}}
    ... [LaTeX headers] ...
    
    \\begin{{center}}
    \\Large\\textbf{{CAM Reconciliation - {property_name}}}
    
    \\normalsize
    \\textbf{{Reconciliation Period: {reconciliation_period}}}
    \\end{{center}}
    ... [rest of document] ...
    """
    
    # Get GL details if needed
    if tenant_data.get("gl_detail_file_path"):
        gl_detail_file = tenant_data.get("gl_detail_file_path")
        gl_details, gl_total_row = get_gl_details_for_tenant(gl_detail_file)
        # Add GL details to document...
    
    # Compile to PDF
    compile_success = compile_to_pdf(document, pdf_path, tex_path)
    
    return compile_success, pdf_path, tex_path
```

## Implementation Plan

1. Update New Full.py to include all normalized fields in the Tenant Billing CSV output
2. Modify enhanced_letter_generator.py to use these normalized fields
3. Test with sample data to ensure output matches
4. Create unit tests to verify that letters generate correctly

## Impact on CSV Files

### Tenant Billing CSV

Add new fields:
- Boolean flags for conditional sections
- Pre-formatted date ranges and values
- GL detail file paths
- JSON-structured amortization items

### GL Detail CSV

No changes needed, but ensure paths to these files are correctly included in the Tenant Billing CSV.

By making these normalizations, the letter generator will be more maintainable, easier to troubleshoot, and less prone to calculation errors.