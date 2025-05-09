# Payment Tracker Module

The Payment Tracker Module provides functionality for tracking and comparing monthly payment changes
for tenants in the CAM/TAX Reconciliation system. This document summarizes the implementation details
and usage instructions.

## Features

1. **Old Payment Tracking**
   - Retrieves old monthly payment amounts from the `MatchedEstimate` field in Tenant CAM data
   - Handles empty or invalid values gracefully

2. **New Payment Calculation**
   - Calculates new monthly payment by dividing final reconciliation amount by number of periods
   - Supports custom period counts (default: 12 months)

3. **Payment Comparison**
   - Calculates absolute dollar difference between old and new payments
   - Calculates percentage change with special handling for zero values
   - Classifies changes as "increase", "decrease", "no_change", or "first_billing"
   - Flags significant changes (>=20% difference)

4. **Reporting**
   - Generates detailed CSV reports with tenant payment information
   - Includes tenant names, property information, and change metrics
   - Logs significant payment changes with warnings

## Implementation

The implementation includes the following files:

1. **payment_tracker.py**
   - Core module for payment tracking functionality
   - Provides functions for getting old monthly payments, calculating new payments, and generating comparisons
   - Uses cached tenant data for efficient lookups

2. **test_payment_tracker.py**
   - Test script for running payment tracking on a property
   - Generates detailed output files and summary reports
   - Supports command line arguments for property, year, and more

3. **generate_tenant_report.py**
   - Standalone script for generating tenant payment reports with names
   - Uses Tenant CAM data to look up tenant names
   - Creates formatted CSV reports

## Integration Points

The payment tracker integrates with the reconciliation system at the following points:

1. **report_generator.py**
   - Uses payment tracker during report generation to include payment comparison metrics
   - Adds payment metrics to tenant billing reports

2. **reconciliation.py**
   - Provides final reconciliation amounts to the payment tracker
   - Passes period information for accurate calculations

## Usage

### In Python Code

```python
from reconciliation.payment_tracker import get_payment_comparison

# Get payment comparison for a tenant
comparison = get_payment_comparison(
    tenant_id='1001',
    property_id='ELW',
    final_amount=Decimal('36000.00'),
    periods_count=12
)

# Access metrics
old_monthly = comparison['old_monthly']
new_monthly = comparison['new_monthly']
percentage_change = comparison['percentage_change']
is_significant = comparison['is_significant']
```

### Command Line

Use the test script to analyze payment changes for a property:

```bash
python test_payment_tracker.py WAT 2024 202505
```

Generate a tenant report with names from payment changes:

```bash
python generate_tenant_report.py latest
python generate_tenant_report.py Output/payment_changes_WAT_2024.json
```

## Enhancements

1. **Tenant Name Lookup**
   - Tenant names are included in reports and log messages
   - Supports integration with tenant information systems

2. **CSV Report Generator**
   - Generates formatted reports with proper column headers
   - Includes all metrics in a single view

3. **Payment Significance Flagging**
   - Highlights large payment changes (>=20%)
   - Captures different change types for easy filtering