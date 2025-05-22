# Letter Field Mapping Document

This document maps all fields used in the enhanced letter generator to their source columns in the CSV outputs from the New Full.py script. This mapping will help ensure that all letter fields come directly from the CSV without additional calculations.

## CSV Report Types

The letter generator uses data from two main types of CSV reports:

1. **Tenant Billing CSV**: Main report with summary data for all tenants (filename pattern: `tenant_billing_{property_id}_cam_{year}_{timestamp}.csv`)
2. **GL Detail CSV**: Detailed GL account breakdown for a specific tenant (filename pattern: `GL_detail_{tenant_id}_{year}_{timestamp}.csv`)

## Basic Tenant Information

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| tenant_id | tenant_id | Tenant Billing | Tenant identifier |
| tenant_name | tenant_name | Tenant Billing | Tenant's name |
| property_id | property_id | Tenant Billing | Property identifier |
| property_full_name | property_full_name | Tenant Billing | Full property name |

## Date Information

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| reconciliation_start_date | reconciliation_start_date | Tenant Billing | Start date of reconciliation period |
| reconciliation_end_date | reconciliation_end_date | Tenant Billing | End date of reconciliation period |
| catchup_start_date | catchup_start_date | Tenant Billing | Start date of catchup period |
| catchup_end_date | catchup_end_date | Tenant Billing | End date of catchup period |
| monthly_charge_effective_date | monthly_charge_effective_date | Tenant Billing | Date when new monthly charge becomes effective |

## Main Financial Amounts

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| property_total | cam_net_total (with property_gl_total fallback) | Tenant Billing | Total property CAM expenses after exclusions |
| share_percentage | share_percentage | Tenant Billing | Tenant's pro-rata share percentage |
| tenant_share_amount | tenant_share_amount | Tenant Billing | Tenant's share of expenses |
| year_due_amount | subtotal_after_tenant_share | Tenant Billing | Year due amount after applying tenant share |
| base_year_adjustment | base_year_adjustment | Tenant Billing | Base year deduction amount |
| cap_deduction | cap_deduction | Tenant Billing | Cap reduction amount |
| admin_fee_net | admin_fee_net | Tenant Billing | Administrative fee amount |
| subtotal_after_tenant_share | subtotal_after_tenant_share | Tenant Billing | Year due amount after applying tenant share |

## Payment Information

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| reconciliation_paid | reconciliation_paid | Tenant Billing | Amount already paid during reconciliation period |
| reconciliation_balance | reconciliation_balance | Tenant Billing | Remaining balance for reconciliation period |
| catchup_balance | catchup_balance | Tenant Billing | Balance for catchup period |
| total_balance | total_balance | Tenant Billing | Final grand total amount due |
| old_monthly | old_monthly | Tenant Billing | Previous monthly charge amount |
| new_monthly | new_monthly | Tenant Billing | New monthly charge amount |
| monthly_difference | monthly_difference | Tenant Billing | Difference between old and new monthly charges |

## Override Information

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| has_override | has_override | Tenant Billing | Flag indicating if an override exists |
| override_amount | override_amount | Tenant Billing | Amount of the override |
| override_description | override_description | Tenant Billing | Description of the override |

## Amortization Information

| Letter Field | CSV Column | CSV Report Type | Description |
|--------------|------------|----------------|-------------|
| amortization_total_amount | amortization_total_amount | Tenant Billing | Total amortization amount |
| amortization_items_count | amortization_items_count | Tenant Billing | Number of amortization items |
| amortization_{i}_description | Dynamically defined in CSV | Tenant Billing | Description of amortization item |
| amortization_{i}_total_amount | Dynamically defined in CSV | Tenant Billing | Total amount of amortization item |
| amortization_{i}_years | Dynamically defined in CSV | Tenant Billing | Number of years for amortization |
| amortization_{i}_annual_amount | Dynamically defined in CSV | Tenant Billing | Annual amount for amortization item |
| amortization_{i}_your_share | Dynamically defined in CSV | Tenant Billing | Tenant's share of amortization item |

## GL Detail Information (from separate GL detail CSV files)

| Letter Field | GL Detail CSV Column | CSV Report Type | Description |
|--------------|----------------------|----------------|-------------|
| gl_account | gl_account | GL Detail | GL account number |
| description | description | GL Detail | GL account description |
| combined_gross | combined_gross | GL Detail | Total gross amount for GL account |
| tenant_share_percentage | tenant_share_percentage | GL Detail | Tenant's share percentage for this GL account |
| tenant_share_amount | tenant_share_amount | GL Detail | Tenant's share amount for this GL account |
| admin_fee_percentage | admin_fee_percentage | GL Detail | Admin fee percentage for this GL account |
| admin_fee_amount | admin_fee_amount | GL Detail | Admin fee amount for this GL account |
| admin_fee_exclusion_rules | admin_fee_exclusion_rules | GL Detail | Rules for admin fee exclusion |
| cap_exclusion_rules | cap_exclusion_rules | GL Detail | Rules for cap exclusion |
| cap_impact | cap_impact | GL Detail | Cap impact amount for this GL account |
**IMPORTANT**: The GL table totals should be calculated by summing the individual GL account rows in the letter generator, not taken directly from CSV outputs. This ensures accuracy when individual GL accounts may be excluded or have special handling.

## Implementation Notes

1. All monetary values should be formatted using the `format_currency()` function
2. All percentage values should be formatted using the `format_percentage()` function
3. All dates should be formatted using appropriate date formatting functions
4. No additional calculations should be performed in the letter generator - get all values directly from CSV
5. For conditional sections (e.g., base year, cap, amortization), use the corresponding flag values from CSV

## CSV File Locations

1. **Tenant Billing CSV**: Located in `Output/Reports/tenant_billing_{property_id}_cam_{year}_{timestamp}.csv`
2. **GL Detail CSV**: Located in `Output/Reports/GL_Details/{property_id}_{year}/Tenant_{tenant_id}_{tenant_name}/GL_detail_{tenant_id}_{year}_{timestamp}.csv`

## Sample Implementation Approach

```python
# Example for getting a field directly from CSV
tenant_id = tenant_data.get("tenant_id", "")

# Example for formatting a currency value with fallback
property_total = format_currency(tenant_data.get("cam_net_total", tenant_data.get("property_gl_total", "0")))

# Example for checking if a section should be included
has_base_year = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '') or 0) > 0
if has_base_year:
    # Include base year section in letter
    document += f"Base Year Deduction & -\\${base_year_amount} \\\\\n"
```

By following this mapping, we can ensure that all letter fields are directly sourced from the appropriate CSV outputs without additional calculations in the letter generator.