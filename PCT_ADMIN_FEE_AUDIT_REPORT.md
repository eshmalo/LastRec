# PCT Letters Admin Fee Audit Report
**Date**: 2025-05-24  
**Property**: Palisade Court (PCT)  
**Year**: 2024  
**Total Letters Reviewed**: 19

## Executive Summary

**Critical Finding**: 18 out of 19 PCT letters (94.7%) contained incorrect property-level admin fee reporting due to a calculation methodology bug that has been fixed.

**Impact**: All incorrect letters understated the property admin fee, with errors ranging from $1,015 to $64,428 per letter.

## Technical Issue

### Root Cause
Letters were displaying tenant-specific admin fee calculations instead of the correct property-level total:
- **Incorrect Method**: Used individual tenant's capital share in admin fee calculation
- **Correct Method**: Should use total property capital expenses for admin fee base

### Calculation Details
- **CAM Net**: $1,065,679.05
- **Property Capital Expenses**: $75,179.49
- **Admin Fee Rate**: 15%
- **Correct Property Admin Fee**: **$171,128.78**

**Formula**: 15% × ($1,065,679.05 + $75,179.49) = $171,128.78

## Detailed Findings

### Letters by Accuracy Status

#### ✅ CORRECT (1 letter)
| Tenant | Admin Fee Shown | Status |
|---------|----------------|---------|
| TS_Mobility_of_NJ_LLC_1447 | $171,128.78 | ✅ CORRECT |

#### ❌ INCORRECT (18 letters)
| Tenant | Admin Fee Shown | Error Amount | Error % |
|---------|----------------|--------------|---------|
| Apple_Bank_for_Savings_1455 | $106,768.63 | -$64,360.15 | -37.6% |
| CHIPOTLE_MEXICAN_GRILL_OF_COLORADO_1483 | $106,700.85 | -$64,427.93 | -37.7% |
| IVYREHAB_Network,_Inc._1454 | $106,706.46 | -$64,422.32 | -37.7% |
| PC_Beauty_Corp._1457 | $128,080.86 | -$43,047.92 | -25.2% |
| THE_HABIT_RESTAURANTS,_LLC_1530 | $159,851.86 | -$11,276.92 | -6.6% |
| Victor_(Vittorio)_Capparelli_1463 | $159,986.05 | -$11,142.73 | -6.5% |
| Subprize,_LLC_1459 | $159,972.52 | -$11,156.26 | -6.5% |
| Lulu_Lounge,_LLC_1449 | $160,025.52 | -$11,103.26 | -6.5% |
| Jaclyn_Taylor,_LLC_1451 | $160,079.65 | -$11,049.13 | -6.5% |
| Floris_International,_Inc._1462 | $160,106.72 | -$11,022.06 | -6.4% |
| Englewood_Health_1465 | $160,123.63 | -$11,005.15 | -6.4% |
| Diamond_Braces_of_Hackensack._LLC_1461 | $160,093.75 | -$11,035.03 | -6.4% |
| ShopRite_of_Englewood_Associates,_Inc._1464 | $160,312.48 | -$10,816.30 | -6.3% |
| CAJUN_RESTAUREANT_ENGLEWOOD,_LLC_1458 | $160,464.19 | -$10,664.59 | -6.2% |
| SHOPRITE_OF_ENGLEWOOD_ASSOCIATES_INC_1467 | $164,631.19 | -$6,497.59 | -3.8% |
| TSAOCAA_ENGLEWOOD_LLC_1453 | $166,166.93 | -$4,961.85 | -2.9% |
| Wok_Oriental_Rest.,_Inc._1460 | $167,745.70 | -$3,383.08 | -2.0% |
| PCNJ_Englewood,_LLC_1466 | $170,113.86 | -$1,014.92 | -0.6% |

## Error Pattern Analysis

### Primary Error Categories
1. **~$160K Range** (11 letters): -$10,664 to -$11,276 error
2. **~$107K Range** (3 letters): -$64,360 to -$64,428 error  
3. **Outliers** (4 letters): Various errors between -$1,015 to -$43,048

### Statistical Summary
- **Average Error**: -$20,132.62
- **Total Cumulative Understatement**: $362,387.19
- **Error Range**: $1,015 to $64,428
- **All Errors**: Understatements (property admin fee shown too low)

## Business Impact

### Transparency Issues
- Property owners and tenants received misleading property-level financial information
- Audit trails showed inconsistent property totals across tenant letters
- Letters failed to accurately represent true property admin fee costs

### Billing Impact
- **No change to individual tenant billing amounts** - tenant calculations were mathematically correct
- Only property-level reporting was affected

## Resolution

### Fix Implemented
- **Date**: 2025-05-24
- **Solution**: Added `property_admin_fee_total` field to display correct property-level admin fee
- **Verification**: TS_Mobility_of_NJ_LLC_1447 letter shows correct amount ($171,128.78)

### Technical Changes
1. Added property admin fee field to reconciliation results
2. Updated letter generator to use property total instead of tenant calculation
3. Included new field in CSV exports for transparency
4. Added field descriptions for reporting

## Recommendations

1. **Immediate**: Regenerate letters for affected tenants if property-level transparency is required
2. **Process**: Implement validation checks to ensure property totals are consistent across all tenant letters
3. **Monitoring**: Add automated verification that property admin fee totals are identical across all tenant letters for same property/year

## Conclusion

The admin fee reporting bug has been successfully identified and fixed. While individual tenant billing amounts were mathematically correct, property-level reporting accuracy has been significantly improved. Future letters will display the correct property admin fee total of $171,128.78.