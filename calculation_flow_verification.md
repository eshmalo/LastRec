# CAM Reconciliation Calculation Flow Verification

## Current Implementation (After Capital Expenses in Admin Fee Update)

### Step-by-Step Flow:

1. **Load Settings and GL Data**
   - Merge tenant/property settings
   - Load and filter GL transactions

2. **Calculate Tenant Share Percentage** (STEP 3)
   - Needed for capital expense calculations

3. **Calculate Capital Expenses** (STEP 4)
   - Property level: `property_capital_expenses`
   - Tenant level: `tenant_capital_expenses`

4. **Calculate CAM/TAX/Admin Fee** (STEPS 5-6)
   - Admin fee base = CAM gross + Capital expenses
   - Admin fee = base × 15%
   - Returns `tenant_cam_tax_admin` with combined totals

5. **Apply Base Year Adjustment** (STEP 7)
   - Applied to: `tenant_cam_tax_admin['base_net_total']`
   - This total already includes CAM + TAX + Admin fee
   - Returns: `after_base_amount`

6. **Calculate Cap-Eligible Amount** (STEP 8)
   - Uses: GL filtered data + admin fee (if cap-eligible)
   - The admin fee already includes capital expenses in its calculation

7. **Apply Cap Limits** (STEP 9)
   - Applied to: `cap_eligible_amount`
   - Calculates deduction if amount exceeds cap
   - Returns: `after_cap_amount`

8. **Add Capital Expenses Back** (STEP 10)
   - `property_total_after_adjustments = after_cap_amount + property_capital_expenses`
   - Capital expenses are added AFTER base year and cap adjustments

9. **Calculate Tenant Share** (STEP 10)
   - Applied to the adjusted amount
   - Add tenant's capital expenses

10. **Apply Occupancy Adjustment** (STEP 11)
    - Final proration

## Key Points:

✅ **Admin Fee Calculation**:
- Now includes capital expenses in the base amount
- Calculated as: (CAM gross + Capital expenses) × 15%

✅ **Base Year Adjustment**:
- Applied to combined total that includes admin fee
- Admin fee already has capital expenses factored in
- No changes needed to base year function

✅ **Cap Limits**:
- Applied to eligible amount which includes admin fee (if eligible)
- Admin fee already has capital expenses factored in
- No changes needed to cap function

✅ **Capital Expenses**:
- Added AFTER base year and cap adjustments
- This is the correct approach as capital expenses are not subject to these adjustments

## Conclusion:

The current implementation is correct. Base year and cap functions do not need any modifications because:

1. They operate on totals that already include the admin fee
2. The admin fee now includes capital expenses in its calculation
3. The actual capital expense line items are added after these adjustments, which is the correct treatment

# Percentage Handling Fix Verification (May 21, 2025)

## Admin Fee Calculation Flow

The admin fee calculation follows this sequence:

1. **Load Tenant Settings**
   - Read `fixed_pyc_share` from tenant settings JSON file
   - This represents the tenant's percentage share of property expenses

2. **Convert Share to Decimal**
   - Process through `calculate_tenant_share_percentage` function
   - Now correctly handles both formats:
     - Values ≥1: Divided by 100 (e.g., 5.138 → 0.05138 for 5.138%)
     - Values <1: Used as-is (e.g., 0.007 → 0.007 for 0.7%)

3. **Calculate Tenant Share Amount**
   - Multiply share percentage by the total eligible amount
   - For admin fees: `tenant_share_percentage * admin_fee_base_amount`

4. **Apply Additional Rules**
   - Handle caps, floors, and other tenant-specific adjustments
   - Apply inclusions/exclusions based on tenant lease terms

## Verification Steps for Admin Fee Calculation

For tenant 1334 (Chip East Northporf LLC):

### 1. Initial Investigation
- **Problem**: Letter showed admin fee of $60,945.37 but billing data showed $609.45
- **Discrepancy ratio**: ~100x difference (indicating a percentage interpretation issue)
- **Tenant setting value**: 0.7 (intended as 0.7% but interpreted as 70%)

### 2. Code Logic Verification
- **Original logic**: All percentages divided by 100
- **Problem**: 0.7 → 0.007 (reduced by factor of 100 when should remain 0.7%)
- **Fix**: Added check for values <1 to handle them appropriately

### 3. Testing with Original Setting (0.7)
- Run with code fix but keep tenant setting at 0.7
- **Expected result**: 0.7% admin fee (since code now interprets 0.7 correctly as 0.7%)
- **Actual result**: 0.7% admin fee (~$609.45)

### 4. Testing with Updated Setting (0.007)
- Changed tenant setting to 0.007 to explicitly represent 0.7%
- **Expected result**: 0.7% admin fee (~$609.45)
- **Actual result**: 0.7% admin fee (~$609.45)

### 5. Validation Across Documents
- **CSV Data**: Admin fee column shows ~$609.45
- **LaTeX Letter Source**: Shows admin fee value of ~$609.45
- **Final PDF Letter**: Displays admin fee value of ~$609.45

## Admin Fee Base Amount Calculation

The admin fee is calculated as a percentage of eligible expenses:

1. **Total Property Expenses**
   - Sum of all eligible GL line items for the property
   - Defined in property settings under eligible expense categories

2. **Apply Global Exclusions**
   - Remove any globally excluded GL codes
   - Remove items explicitly marked as excluded in property settings

3. **Calculate Base Amount for Admin Fee**
   - Apply property-specific admin fee calculation rules
   - Typically 15% of eligible expenses after exclusions

4. **Apply Tenant Share**
   - Multiply base admin fee by tenant's share percentage
   - For Chip East: 0.7% × admin_fee_base_amount

## Common Percentage Calculation Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Decimal/percentage confusion | Values off by factor of 100 | Check if value is <1 before dividing |
| Mixed format data sources | Inconsistent calculations | Standardize on one format or handle both |
| Rounding errors | Small discrepancies in final values | Use Decimal type throughout calculations |
| Unit display issues | Correct values but wrong display | Ensure formatting functions use correct multipliers |

## Testing with Other Tenant Settings

Verified that the fix works correctly for:
1. Tenants with percentages >1% (e.g., 5.2%)
2. Tenants with percentages <1% (e.g., 0.7%)
3. Tenants with fixed dollar amounts instead of percentages