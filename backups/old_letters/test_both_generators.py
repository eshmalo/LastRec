#!/usr/bin/env python3
"""
Integration test for both letter generators
Shows how to use both the text and LaTeX letter generators together
"""

import os
import sys
from letter_generator import generate_tenant_letter, generate_letters_from_results
from latex_letter_generator import generate_latex_letter, generate_latex_letters_from_results

# Sample tenant data for testing
sample_tenant_data = {
    "tenant_id": "1234",
    "tenant_name": "Test Tenant, LLC",
    "property_id": "WAT",
    "property_full_name": "Watchung",
    "reconciliation_start_date": "2024-01-01",
    "reconciliation_end_date": "2024-12-31",
    "catchup_start_date": "2025-01-01",
    "catchup_end_date": "2025-04-30",
    "property_gl_total": "$150,000.00",
    "share_percentage": "5.25%",
    "tenant_share_amount": "$7,875.00",
    "base_year_adjustment": "$0.00",
    "cap_deduction": "$0.00",
    "admin_fee_net": "$150.00",
    "amortization_total_amount": "$0.00",
    "reconciliation_paid": "$5,000.00",
    "reconciliation_balance": "$2,875.00",
    "catchup_balance": "$525.00",
    "has_override": "false",
    "override_amount": "$0.00",
    "override_description": "",
    "total_balance": "$3,400.00",
    "old_monthly": "$600.00",
    "new_monthly": "$700.00",
    "monthly_difference": "$100.00",
    "monthly_charge_effective_date": "2025-06-01"
}

# Sample results dictionary that mimics the output from the main reconciliation process
sample_results = {
    'csv_report_path': 'test_data.csv',  # This file doesn't need to exist for the test
    'gl_detail_reports': []  # No GL detail reports for this test
}

def test_individual_generator():
    """Test generating letters for a single tenant"""
    print("\n=== Testing Individual Letter Generation ===")
    
    # No GL detail file for this test
    gl_detail_file = ""
    
    try:
        # Generate text letter
        print("\nGenerating text letter...")
        text_path = generate_tenant_letter(sample_tenant_data, gl_detail_file, debug_mode=True)
        print(f"Text letter generated at: {text_path}")
        
        # Generate LaTeX letter
        print("\nGenerating LaTeX letter...")
        latex_path = generate_latex_letter(sample_tenant_data, gl_detail_file, debug_mode=True)
        print(f"LaTeX letter generated at: {latex_path}")
        
        print("\nIndividual letter generation tests passed!")
        return True
    except Exception as e:
        print(f"Error in individual letter generation: {str(e)}")
        return False

def test_batch_integration():
    """Test how the letter generators would be integrated with the main script"""
    print("\n=== Testing Batch Integration ===")
    
    try:
        # In a real scenario, the results_dict would be populated from the reconciliation process
        # For this test, we'll use the sample_results with our tenant data
        
        # Mock populating the results with our sample tenant data
        # In reality, this would happen during the reconciliation process
        import csv
        import os
        from pathlib import Path
        
        # Create a temporary CSV with our sample data
        os.makedirs('Output', exist_ok=True)
        csv_path = os.path.join('Output', 'test_reconciliation_results.csv')
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sample_tenant_data.keys())
            writer.writeheader()
            writer.writerow(sample_tenant_data)
        
        # Create test results dictionary
        test_results = {
            'csv_report_path': csv_path,
            'gl_detail_reports': []  # No GL detail reports for this test
        }
        
        # Generate text letters
        print("\nGenerating text letters from results...")
        text_success, text_total = generate_letters_from_results(test_results)
        print(f"Text letters generated: {text_success} of {text_total}")
        
        # Generate LaTeX letters
        print("\nGenerating LaTeX letters from results...")
        latex_success, latex_total = generate_latex_letters_from_results(test_results, debug_mode=True)
        print(f"LaTeX letters generated: {latex_success} of {latex_total}")
        
        # Clean up test file
        if os.path.exists(csv_path):
            os.remove(csv_path)
        
        print("\nBatch integration tests passed!")
        return True
    except Exception as e:
        print(f"Error in batch integration test: {str(e)}")
        return False

def main():
    """Main entry point for the test script"""
    print("Testing letter generator integration...")
    
    # Run individual generator test
    individual_test_passed = test_individual_generator()
    
    # Run batch integration test
    batch_test_passed = test_batch_integration()
    
    # Report overall results
    if individual_test_passed and batch_test_passed:
        print("\n✅ All tests passed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())