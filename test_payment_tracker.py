#!/usr/bin/env python3
"""
Payment Tracker Test Script

This script tests the payment tracker functionality by running a reconciliation
for a specific property and tenant, then analyzing the payment comparison results.
"""

import os
import sys
import json
import csv
import logging
import datetime
from decimal import Decimal

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import reconciliation modules
from reconciliation.reconciliation import process_property
from reconciliation.payment_tracker import get_payment_comparison, clear_cache, generate_payment_change_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('Output', 'payment_tracker_test.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_payment_tracker_test(property_id, recon_year, tenant_id=None, last_bill=None):
    """
    Run a test reconciliation and analyze payment tracking results.
    
    Args:
        property_id: Property identifier
        recon_year: Reconciliation year
        tenant_id: Optional tenant ID to test a specific tenant
        last_bill: Optional last bill date in YYYYMM format
    """
    logger.info(f"Testing payment tracker for property {property_id}, year {recon_year}")
    
    # Ensure cache is clear for accurate test
    clear_cache()
    
    # Run reconciliation
    results = process_property(
        property_id,
        recon_year,
        last_bill,
        tenant_id,
        skip_cap_update=True  # Skip cap history update for testing
    )
    
    logger.info(f"Reconciliation complete, analyzing tenant results ({results['tenant_count']} tenants)")
    
    # Analyze payment tracking results
    significant_changes = []
    tenant_summary = []
    
    for tenant_result in results['tenant_results']:
        tenant_id = tenant_result['tenant_id']
        property_id = tenant_result['property_id']
        final_amount = tenant_result['final_recoverable_amount']
        periods_count = len(tenant_result['periods']['full_period'])
        
        # Get payment comparison
        payment_comparison = get_payment_comparison(
            tenant_id,
            property_id,
            final_amount,
            periods_count
        )
        
        # Build summary
        summary = {
            "tenant_id": tenant_id,
            "old_monthly": float(payment_comparison['old_monthly']),
            "new_monthly": float(payment_comparison['new_monthly']),
            "difference": float(payment_comparison['difference']),
            "percentage_change": float(payment_comparison['percentage_change']),
            "change_type": payment_comparison['change_type'],
            "is_significant": payment_comparison['is_significant']
        }
        
        tenant_summary.append(summary)
        
        # Track significant changes
        if payment_comparison['is_significant']:
            significant_changes.append(summary)
    
    # Print payment tracking summary
    print("\n=== Payment Tracking Summary ===")
    print(f"Property: {property_id}")
    print(f"Tenants analyzed: {len(tenant_summary)}")
    print(f"Significant changes: {len(significant_changes)}")
    
    # Print details for all tenants
    print("\nAll Tenant Payment Changes:")
    for summary in tenant_summary:
        print(f"- Tenant {summary['tenant_id']}: ${summary['old_monthly']:.2f} → ${summary['new_monthly']:.2f} " +
              f"(${summary['difference']:.2f}, {summary['percentage_change']:.1f}%) - " +
              f"{'⚠️ SIGNIFICANT' if summary['is_significant'] else 'Normal'}")
    
    # Print significant changes section
    if significant_changes:
        print("\nSignificant Payment Changes (≥20%):")
        for change in significant_changes:
            print(f"- Tenant {change['tenant_id']}: ${change['old_monthly']:.2f} → ${change['new_monthly']:.2f} " +
                  f"(${change['difference']:.2f}, {change['percentage_change']:.1f}%)")
    
    # Save results to file
    output_path = os.path.join('Output', f"payment_changes_{property_id}_{recon_year}.json")
    with open(output_path, 'w') as f:
        json.dump(tenant_summary, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_path}")
    
    # Generate formatted report
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = generate_payment_change_report(
        [
            # Convert float values back to Decimal for report generation
            {k: Decimal(str(v)) if isinstance(v, float) else v for k, v in summary.items()}
            for summary in tenant_summary
        ],
        os.path.join('Output', 'Reports', f"payment_changes_{property_id}_{recon_year}_{timestamp}.csv")
    )
    
    if report_path:
        print(f"Formatted CSV report saved to: {report_path}")
    
    return tenant_summary


if __name__ == "__main__":
    # Default test parameters
    test_property_id = "WAT"  # Property to test
    test_recon_year = 2024    # Reconciliation year
    test_last_bill = "202505" # Last bill date
    test_tenant_id = None     # All tenants
    
    # Check if command-line parameters provided
    if len(sys.argv) > 1:
        test_property_id = sys.argv[1]
    if len(sys.argv) > 2:
        test_recon_year = int(sys.argv[2])
    if len(sys.argv) > 3:
        test_last_bill = sys.argv[3]
    if len(sys.argv) > 4:
        test_tenant_id = sys.argv[4]
    
    # Run the test
    run_payment_tracker_test(
        test_property_id,
        test_recon_year,
        test_tenant_id,
        test_last_bill
    )