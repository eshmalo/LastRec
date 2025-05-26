# GL-Specific Admin Fee Percentage Override Feature - Scope of Work

## Executive Summary

This document outlines the comprehensive scope of work for implementing GL-specific admin fee percentage overrides in the CAM reconciliation system. This feature will allow different admin fee percentages to be applied to specific GL accounts, overriding the default hierarchy of portfolio → property → tenant admin fee percentages.

## Current Admin Fee Structure Analysis

### Existing Admin Fee Calculation Logic
- **Location**: `New Full.py:1000-1023` - `calculate_admin_fee_percentage()`
- **Current hierarchy**: Portfolio → Property → Tenant (tenant-level overrides property-level, which overrides portfolio-level)
- **Default percentages**: WAT property defaults to 15%, others default to 0%
- **Calculation**: Applied uniformly to all CAM Net + Capital Expenses

### Current Settings Structure
- **Portfolio Level**: `/Data/ProcessedOutput/PortfolioSettings/portfolio_settings.json`
- **Property Level**: `/Data/ProcessedOutput/PropertySettings/[PROPERTY]/property_settings.json`
- **Tenant Level**: `/Data/ProcessedOutput/PropertySettings/[PROPERTY]/TenantSettings/[TENANT].json`

### Current GL Processing Logic
- **Location**: `New Full.py:652-701` - `check_account_inclusion()` and `check_account_exclusion()`
- **Filter function**: `New Full.py:704-800+` - `filter_gl_accounts_with_detail()`
- **GL exclusions**: Currently supports CAM, RET, admin_fee, base, cap exclusions
- **Admin fee exclusions**: Applied to remove specific GLs from admin fee calculation base

## Proposed Feature Design

### 1. New Settings Structure: `admin_fee_gl_overrides`

#### Portfolio Level (portfolio_settings.json)
```json
{
  "settings": {
    "admin_fee_gl_overrides": [
      {
        "id": "insurance_override",
        "description": "Lower admin fee for insurance accounts",
        "admin_fee_percentage": 0.10,
        "gl_accounts": ["MR510000", "MR510100", "MR510200"],
        "gl_ranges": ["MR510000-MR510400"],
        "priority": 1
      },
      {
        "id": "maintenance_override", 
        "description": "Higher admin fee for maintenance",
        "admin_fee_percentage": 0.20,
        "gl_accounts": ["MR520000", "MR521000"],
        "priority": 2
      }
    ]
  }
}
```

#### Property Level (property_settings.json)
```json
{
  "settings": {
    "admin_fee_gl_overrides": [
      {
        "id": "property_specific_override",
        "description": "Property-specific GL override",
        "admin_fee_percentage": 0.12,
        "gl_accounts": ["MR530000"],
        "priority": 1
      }
    ]
  }
}
```

#### Tenant Level (tenant_settings.json)
```json
{
  "settings": {
    "admin_fee_gl_overrides": [
      {
        "id": "tenant_specific_override",
        "description": "Tenant-specific GL override", 
        "admin_fee_percentage": 0.05,
        "gl_accounts": ["MR540000"],
        "priority": 1
      }
    ]
  }
}
```

### 2. Override Priority and Hierarchy

**Priority Resolution**:
1. **Tenant-level overrides** (highest priority)
2. **Property-level overrides** 
3. **Portfolio-level overrides**
4. **Default admin fee percentage** (lowest priority)

**Within each level**: Priority field determines order (lower number = higher priority)

### 3. New Configuration Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `id` | String | Unique identifier for the override | Yes |
| `description` | String | Human-readable description | Yes |
| `admin_fee_percentage` | Decimal | Override percentage (0.15 = 15%) | Yes |
| `gl_accounts` | Array[String] | Specific GL accounts to override | No* |
| `gl_ranges` | Array[String] | GL account ranges (e.g., "MR510000-MR510400") | No* |
| `priority` | Integer | Priority within the same level (1 = highest) | No (default: 999) |

*Either `gl_accounts` or `gl_ranges` must be provided

## Code Changes Required

### 1. New Functions (New Full.py)

#### `get_admin_fee_gl_overrides(settings: Dict[str, Any]) -> List[Dict[str, Any]]`
- **Location**: After `calculate_admin_fee_percentage()` (~line 1025)
- **Purpose**: Extract and validate GL override settings from hierarchy
- **Returns**: Merged list of overrides with priority resolution

#### `calculate_gl_specific_admin_fee_percentage(gl_account: str, overrides: List[Dict], default_percentage: Decimal) -> Decimal`
- **Location**: After `get_admin_fee_gl_overrides()` (~line 1050)
- **Purpose**: Determine admin fee percentage for specific GL account
- **Logic**: Check overrides by priority, return first match or default

#### `calculate_cam_tax_admin_with_gl_overrides()` 
- **Location**: Replace/enhance existing `calculate_cam_tax_admin()` (~line 1032)
- **Purpose**: Enhanced version that applies GL-specific admin fees
- **Logic**: Process each GL account with its specific admin fee percentage

### 2. Enhanced GL Processing Logic

#### Modify `filter_gl_accounts_with_detail()`
- **Location**: ~line 704
- **Enhancement**: Track admin fee percentage per GL account in `gl_line_details`
- **New field**: `admin_fee_percentage_applied` in GL details

### 3. Settings Validation Functions

#### `validate_admin_fee_gl_overrides(overrides: List[Dict]) -> Tuple[bool, List[str]]`
- **Location**: New utility function (~line 600)
- **Purpose**: Validate override configuration format and logic
- **Checks**: Required fields, percentage ranges, GL account format, duplicate GLs

### 4. Report and Output Enhancements

#### Enhanced CSV Output Columns
- **New columns**:
  - `admin_fee_percentage_applied`: Actual percentage used for each GL
  - `admin_fee_override_id`: Which override rule was applied
  - `admin_fee_override_description`: Description of applied override

#### Enhanced Letter Generation
- **Location**: `enhanced_letter_generator.py`
- **Enhancement**: Show GL-specific admin fee breakdowns in letters
- **New section**: "Admin Fee Calculation Details" table

#### Enhanced GL Detail Reports
- **Location**: `generate_gl_detail_report()` (~line 2101)
- **Enhancement**: Include override information in GL detail reports

## Implementation Phases

### Phase 1: Core Framework (Week 1)
1. **Settings structure design and validation**
   - Create validation functions
   - Update settings format guide
   - Add example configurations

2. **Basic GL override resolution logic**
   - Implement `get_admin_fee_gl_overrides()`
   - Implement `calculate_gl_specific_admin_fee_percentage()`
   - Add unit tests for priority resolution

### Phase 2: Calculation Engine (Week 2)
1. **Enhanced admin fee calculation**
   - Modify `calculate_cam_tax_admin()` to use GL-specific percentages
   - Update GL processing to track per-GL admin fees
   - Enhance `filter_gl_accounts_with_detail()` for override tracking

2. **Integration with existing logic**
   - Ensure compatibility with admin fee exclusions
   - Maintain backward compatibility with existing settings
   - Test with capital expenses integration

### Phase 3: Reporting and Output (Week 3)
1. **Enhanced CSV reports**
   - Add new columns for GL-specific admin fee tracking
   - Update column descriptions and documentation
   - Modify report generation functions

2. **Enhanced letter generation**
   - Add GL-specific admin fee breakdown tables
   - Update letter templates for override information
   - Test letter formatting and accuracy

### Phase 4: Testing and Documentation (Week 4)
1. **Comprehensive testing**
   - Unit tests for all new functions
   - Integration tests with existing reconciliation logic
   - Test with multiple properties and complex override scenarios

2. **Documentation updates**
   - Update `SETTINGS_FORMAT_GUIDE.md`
   - Create configuration examples
   - Update user documentation

## Data Migration Considerations

### Backward Compatibility
- **Existing settings**: Continue to work without modification
- **Default behavior**: When no overrides specified, use existing admin fee percentage
- **Migration script**: Not required - feature is additive

### Rollout Strategy
1. **Pilot testing**: Test with single property (PCT recommended)
2. **Gradual rollout**: Property by property implementation
3. **Validation**: Compare results with current calculations

## Testing Strategy

### Unit Tests
- GL override resolution logic
- Priority handling within and across levels
- Percentage calculation accuracy
- Settings validation

### Integration Tests
- Full reconciliation with GL overrides
- Multi-tenant, multi-property scenarios
- Edge cases (overlapping ranges, complex hierarchies)

### Validation Tests
- Compare override results with manual calculations
- Ensure mathematical consistency in letters
- Verify CSV report accuracy

## File Changes Summary

### New Files
- `GL_ADMIN_FEE_OVERRIDE_SCOPE.md` (this document)
- Test files for new functionality

### Modified Files
1. **New Full.py**
   - Add ~150 lines of new functions
   - Modify ~50 lines of existing functions
   - Enhance calculation and reporting logic

2. **enhanced_letter_generator.py** 
   - Add GL-specific admin fee breakdown section
   - Modify admin fee display logic

3. **SETTINGS_FORMAT_GUIDE.md**
   - Add documentation for new override settings
   - Include configuration examples

### Configuration Files
- All existing settings files (optional enhancement)
- New example configurations for testing

## Risk Assessment

### Low Risk
- **Backward compatibility**: Feature is purely additive
- **Testing approach**: Comprehensive validation strategy
- **Rollback capability**: Can disable by removing override settings

### Medium Risk
- **Complexity of priority resolution**: Requires careful testing
- **Performance impact**: Additional processing per GL account
- **User configuration errors**: Mitigated by validation functions

### Mitigation Strategies
- **Extensive unit testing**: Cover all edge cases
- **Configuration validation**: Prevent invalid settings
- **Documentation**: Clear examples and guidelines
- **Phased rollout**: Start with simple scenarios

## Success Criteria

1. **Functional Requirements**
   - GL-specific admin fee percentages correctly applied
   - Priority hierarchy properly respected
   - Accurate calculations in all reports and letters

2. **Performance Requirements**
   - No significant performance degradation (< 10% increase in processing time)
   - Memory usage remains within acceptable limits

3. **Quality Requirements**
   - 100% backward compatibility maintained
   - All existing tests continue to pass
   - New functionality has >95% test coverage

4. **User Experience**
   - Clear configuration format and documentation
   - Helpful error messages for invalid configurations
   - Enhanced reporting provides useful override information

## Estimated Effort

- **Development**: 3-4 weeks (1 developer)
- **Testing**: 1 week 
- **Documentation**: 0.5 weeks
- **Total**: 4.5-5.5 weeks

## Dependencies

- **Existing codebase**: Stable version of current reconciliation system
- **Testing data**: Representative property data for validation
- **User requirements**: Finalized list of required GL override scenarios

## Next Steps

1. **Requirements validation**: Review proposed design with stakeholders
2. **Technical approval**: Confirm approach with development team  
3. **Implementation kickoff**: Begin Phase 1 development
4. **Progress tracking**: Weekly status updates and milestone reviews