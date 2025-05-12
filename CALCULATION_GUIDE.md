# CAM Reconciliation Calculation Guide

This document explains the methodology and calculation process used in the LastRec CAM reconciliation system.

## Calculation Flow

The reconciliation process follows these steps in sequence:

1. **Load Settings**: Multi-level inheritance from portfolio → property → tenant
2. **Load and Filter GL Data**: Apply inclusion/exclusion rules to determine eligible expenses
3. **Calculate CAM, Tax, Admin Fee**: Calculate base amounts for each category
4. **Apply Base Year Adjustment**: Deduct base year amount if applicable
5. **Apply Cap Limit**: Calculate and apply cap deductions if applicable
6. **Calculate Capital Expenses**: Amortize capital expenses over their defined periods
7. **Apply Tenant Share**: Calculate tenant's proportional share using RSF or fixed percentage
8. **Apply Occupancy Adjustment**: Adjust for partial occupancy periods
9. **Apply Tenant Override**: Check for any manual override amounts
10. **Update Cap History**: Store calculated amounts for future year reference
11. **Calculate Payment Information**: Determine balances and new monthly amounts
12. **Generate Reports**: Create detailed CSV and JSON reports

## Key Calculation Components

### GL Account Filtering

GL accounts are filtered using inclusion and exclusion rules:

1. **Inclusion Rules**: Determine which GL accounts are included in gross expenses
2. **Exclusion Rules**: Determine which GL accounts are excluded from net calculations
3. **Special Exclusions**: Additional exclusions for base year and cap calculations

```
Gross Amount - Exclusions = Net Amount
```

### CAM and Tax Calculations

The system processes each expense category separately:

1. **CAM (Common Area Maintenance)**: Operating expenses shared among tenants
2. **RET (Real Estate Taxes)**: Property tax expenses shared among tenants

The process applies appropriate inclusions/exclusions for each category.

### Admin Fee Calculation

Admin fees are calculated as a percentage of CAM expenses:

```
Admin Fee = CAM Net Amount × Admin Fee Percentage
```

Admin fees can be included or excluded from base year and cap calculations based on settings.

### Base Year Adjustment

If a base year is defined, the system deducts the base amount from the tenant's share:

```
After Base Adjustment = Base Net Amount - Base Year Amount
```

The base year adjustment is never negative (never deducts more than the available amount).

### Cap Limit Calculation

Caps limit the year-over-year increase that can be charged to a tenant:

1. **Reference Amount**: Previous year's amount (or highest previous year based on settings)
2. **Cap Limit**: Reference Amount × (1 + Cap Percentage)
3. **Cap Deduction**: Applied if the calculated amount exceeds the cap limit

```
Cap Deduction = Max(0, Cap Eligible Amount - Cap Limit)
```

Additional cap controls include minimum/maximum increase percentages and stop amounts.

### Capital Expenses

Capital expenses are major expenditures amortized over multiple years:

```
Annual Amortized Amount = Expense Amount ÷ Amortization Years
```

For tenant calculations, this amount is prorated based on the tenant's share percentage.

### Tenant Share Calculation

Tenant share is calculated using one of two methods:

1. **RSF Method**: Based on square footage ratio
   ```
   Tenant Share = Tenant Square Footage ÷ Total Property Square Footage
   ```

2. **Fixed Method**: Using a predefined percentage from settings

### Occupancy Adjustment

For partial year occupancy, charges are prorated based on the tenant's lease period:

```
Adjusted Amount = Amount × (Days Occupied ÷ Total Days in Period)
```

### Payment Tracking

The system calculates:

1. **Reconciliation Year Balance**: Expected charges - Actual payments
2. **Catch-up Period Balance**: Expected charges for catch-up period - Actual payments
3. **Total Balance**: Reconciliation + Catch-up balance
4. **New Monthly Payment**: Total ÷ Number of months

## Reporting

The system generates comprehensive reports that include:

1. **Property-level Totals**: Gross, exclusions, and net amounts
2. **Detailed Calculation Steps**: All intermediate calculations
3. **Tenant-specific Values**: Share percentage, occupancy factors, etc.
4. **Financial Summaries**: Final billing amounts, balances, and monthly payments

## Example Calculation

For a typical tenant:

1. **Property CAM Total**: $100,000
2. **Base Year Deduction**: $40,000
3. **After Base**: $60,000
4. **Cap Limit**: $55,000 (based on previous year + cap %)
5. **Cap Deduction**: $5,000
6. **After Cap**: $55,000
7. **Tenant Share**: 10% of property
8. **Tenant Amount**: $5,500
9. **Occupancy Factor**: 100% (full year)
10. **Final Billing**: $5,500
11. **Old Monthly**: $400
12. **New Monthly**: $458.33
13. **Monthly Change**: +$58.33 (14.6% increase)

## Special Calculations

### Admin Fee Inclusion

Admin fees can be:
- Excluded from both base and cap calculations
- Included in cap calculations only
- Included in base calculations only
- Included in both cap and base calculations

### Multiple Exclusions

Exclusions are additive across levels. If an account is excluded at both portfolio and property level, it will be excluded.

### Inclusions Override

Inclusions completely override across levels. If a property defines inclusions for a category, they replace portfolio inclusions.