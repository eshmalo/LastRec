# Property ID Case Sensitivity Fix

## Issue
The `get_tenant_payments` function was failing to find billing records because of case-sensitive property ID matching:
- Billing JSON has PropertyID as "ELW" (uppercase)
- Reconciliation runs with property_id as "elw" (lowercase)
- The comparison was case-sensitive, resulting in 0 matches

## Solution
Modified the property ID comparison in `New Full.py` to be case-insensitive:

### Changes Made
**File:** New Full.py  
**Lines:** 1858 and 1906

**Before:**
```python
if record_tenant_id == tenant_id_str and record_property_id == property_id:
```

**After:**
```python
if record_tenant_id == tenant_id_str and (record_property_id or '').lower() == (property_id or '').lower():
```

## Benefits
1. Property IDs now match regardless of case ('elw' matches 'ELW')
2. Handles potential None values safely
3. Billing records are now properly found during reconciliation

## Test Results
Created test scripts that verify:
- 'elw' (lowercase) matches billing records with PropertyID='ELW'
- 'ELW' (uppercase) matches correctly
- 'Elw' (mixed case) matches correctly

All test cases now successfully find the expected billing records.

## Files Created/Modified
1. `New Full.py` - Modified property ID comparison in get_tenant_payments function
2. `debug_property_matching.py` - Debug script to identify the issue
3. `fix_property_matching.py` - Documentation of the fix
4. `test_property_fix.py` - Test script to verify the fix works

The fix ensures that the reconciliation process can now properly find billing records regardless of the case used for property IDs.

# Percentage Handling Fix (May 21, 2025)

## Problem
Inconsistent handling of percentage values in tenant settings files caused calculation errors in the reconciliation system. Specifically:

1. Tenant share percentages were inconsistently stored:
   - Some as regular percentages (e.g., 5.138 for 5.138%)
   - Some as decimals (e.g., 0.7 for 70% or 0.7%, leading to ambiguity)

2. These inconsistencies led to calculation errors:
   - Values ≥1 were correctly divided by 100 to convert to decimal form
   - Values <1 were also divided by 100, incorrectly reducing them by a factor of 100

3. For Chip East Northporf LLC (tenant ID 1334):
   - Setting was 0.7, intended to mean 0.7%
   - System interpreted it as 70%, then divided by 100 to get 0.7%
   - Actual tenant share should have been 0.7%, not 70%

## Fixed Logic in Code
The following change was made to `calculate_tenant_share_percentage` in `New Full.py`:

```python
# Original code: 
# fixed_share = fixed_share / Decimal('100')

# New code:
# Check if the value already appears to be a decimal (less than 1)
if fixed_share < Decimal('1'):
    logger.info(f"Using fixed share percentage (already in decimal format): {float(fixed_share) * 100:.4f}%")
    return fixed_share
else:
    # Convert from percentage (e.g., 5.138) to decimal (0.05138)
    fixed_share = fixed_share / Decimal('100')
    logger.info(f"Using fixed share percentage (converted from percentage): {float(fixed_share) * 100:.4f}%")
    return fixed_share
```

Similar updates were made to other percentage handling functions:
- `calculate_cap_limit`
- Functions for `min_increase` and `max_increase`

## Recommended Format Standards
To avoid future confusion, use the following standards for percentage values in tenant settings:

| Percentage Value | Format | Example | Notes |
|------------------|--------|---------|-------|
| Less than 1% | Decimal | 0.007 | For 0.7% |
| 1% or greater | Regular | 2.21 | For 2.21% |
| Any value | String with % sign | "0.7%" | Clear but requires extra parsing |

## Verification Process
1. Update code to handle both percentage formats correctly
2. For Chip East's specific case:
   - Update tenant settings from 0.7 to 0.007 to correctly represent 0.7%
3. Run CAM reconciliation for ELW property
4. Verify admin fee calculation in:
   - CSV billing data output
   - LaTeX letter source
   - PDF generated letter

## Long-term Solution
Consider standardizing percentage handling:
1. Validate percentage inputs when tenant settings are created
2. Add clear type annotations/comments in tenant settings files
3. Consider requiring explicit % sign in JSON values for clarity
4. Add unit tests specifically for percentage handling edge cases