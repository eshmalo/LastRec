#!/usr/bin/env python3
"""
Test script for verifying GL detail processing functionality in the enhanced_letter_generator.py

This script helps verify that the GL detail processing handles special cases correctly:
- FORMULA EXPLANATIONS row
- NEGATIVE BALANCE sections
- Direct value entries
- Various non-numeric values

Usage:
    python test_gl_processing.py
    
It will create a test GL detail CSV and verify the processing works as expected.
"""

import os
import csv
import tempfile
import sys
from pathlib import Path

# Import functions from the enhanced letter generator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from enhanced_letter_generator import get_gl_details_for_tenant, read_csv_file
except ImportError:
    print("Error: Could not import from enhanced_letter_generator.py")
    sys.exit(1)

def create_test_gl_detail_file():
    """Create a test GL detail file with various edge cases."""
    print("Creating test GL detail file...")
    
    # Create a temporary file
    fd, temp_path = tempfile.mkstemp(suffix='.csv')
    os.close(fd)
    
    # Define the GL detail data
    fieldnames = [
        'gl_account', 'description', 'combined_gross', 'combined_exclusions', 'combined_net',
        'tenant_share_percentage', 'tenant_share_amount', 'admin_fee_percentage', 
        'admin_fee_exclusion_rules', 'admin_fee_amount', 'exclusion_categories', 'cap_impact'
    ]
    
    rows = [
        # Regular rows (should be included)
        {
            'gl_account': 'MR100000', 
            'description': 'Cash', 
            'combined_gross': '$100.00', 
            'combined_exclusions': '$0.00', 
            'combined_net': '$100.00',
            'tenant_share_percentage': '5.00%', 
            'tenant_share_amount': '$5.00', 
            'admin_fee_percentage': '15.00%',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '$0.75',
            'exclusion_categories': '',
            'cap_impact': '$0.00'
        },
        {
            'gl_account': 'MR200000', 
            'description': 'Building', 
            'combined_gross': '$200.00', 
            'combined_exclusions': '$0.00', 
            'combined_net': '$200.00',
            'tenant_share_percentage': '5.00%', 
            'tenant_share_amount': '$10.00', 
            'admin_fee_percentage': '15.00%',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '$1.50',
            'exclusion_categories': '',
            'cap_impact': '$0.00'
        },
        
        # Zero amount row (should be filtered out)
        {
            'gl_account': 'MR300000', 
            'description': 'Zero Amount', 
            'combined_gross': '$0.00', 
            'combined_exclusions': '$0.00', 
            'combined_net': '$0.00',
            'tenant_share_percentage': '5.00%', 
            'tenant_share_amount': '$0.00', 
            'admin_fee_percentage': '15.00%',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '$0.00',
            'exclusion_categories': '',
            'cap_impact': '$0.00'
        },
        
        # NEGATIVE BALANCE header (should be filtered out)
        {
            'gl_account': '--- NEGATIVE BALANCE ACCOUNTS (EXCLUDED) ---', 
            'description': 'These included GL accounts were excluded from calculations due to negative total balances', 
            'combined_gross': '', 
            'combined_exclusions': '', 
            'combined_net': '',
            'tenant_share_percentage': '', 
            'tenant_share_amount': '', 
            'admin_fee_percentage': '',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '',
            'exclusion_categories': '',
            'cap_impact': ''
        },
        
        # Negative balance account (should be filtered out)
        {
            'gl_account': 'MR400000', 
            'description': 'Negative Account', 
            'combined_gross': '$-100.00', 
            'combined_exclusions': '$0.00', 
            'combined_net': '$-100.00',
            'tenant_share_percentage': '5.00%', 
            'tenant_share_amount': '$-5.00', 
            'admin_fee_percentage': '15.00%',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '$-0.75',
            'exclusion_categories': 'NEGATIVE BALANCE',
            'cap_impact': '$0.00'
        },
        
        # TOTAL row (should be captured separately)
        {
            'gl_account': 'TOTAL', 
            'description': 'Total All GL Accounts', 
            'combined_gross': '$300.00', 
            'combined_exclusions': '$0.00', 
            'combined_net': '$300.00',
            'tenant_share_percentage': '5.00%', 
            'tenant_share_amount': '$15.00', 
            'admin_fee_percentage': '15.00%',
            'admin_fee_exclusion_rules': '', 
            'admin_fee_amount': '$2.25',
            'exclusion_categories': 'Multiple',
            'cap_impact': '$0.00'
        },
        
        # FORMULA EXPLANATIONS row (should be filtered out)
        {
            'gl_account': 'FORMULA EXPLANATIONS:', 
            'description': 'Direct value', 
            'combined_gross': 'Direct value', 
            'combined_exclusions': 'Direct value', 
            'combined_net': 'Direct value',
            'tenant_share_percentage': 'Direct value', 
            'tenant_share_amount': 'Direct value', 
            'admin_fee_percentage': 'Direct value',
            'admin_fee_exclusion_rules': 'Direct value', 
            'admin_fee_amount': 'Direct value',
            'exclusion_categories': 'Direct value',
            'cap_impact': 'Direct value'
        }
    ]
    
    # Write the data to the file
    with open(temp_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Test GL detail file created at: {temp_path}")
    return temp_path

def run_test():
    """Run the test for GL detail processing."""
    # Create the test file
    test_file_path = create_test_gl_detail_file()
    
    # Process the file using the get_gl_details_for_tenant function
    print("\nProcessing test GL detail file...")
    try:
        gl_details, total_row = get_gl_details_for_tenant(test_file_path)
        
        # Verify the results
        print("\nTEST RESULTS:")
        print(f"1. Found {len(gl_details)} GL detail rows (expected: 2)")
        if len(gl_details) == 2:
            print("✅ PASS: Correct number of GL detail rows")
        else:
            print("❌ FAIL: Incorrect number of GL detail rows")
            
        print(f"2. Total row found: {bool(total_row)} (expected: True)")
        if bool(total_row):
            print("✅ PASS: Total row was correctly identified")
        else:
            print("❌ FAIL: Total row was not found")
        
        print("\nFiltered GL accounts:")
        for row in gl_details:
            print(f"  - {row.get('gl_account', 'UNKNOWN')}: {row.get('description', 'UNKNOWN')} = {row.get('combined_gross', '$0.00')}")
            
        print("\nTotal row:")
        if total_row:
            print(f"  - {total_row.get('gl_account', 'UNKNOWN')}: {total_row.get('description', 'UNKNOWN')} = {total_row.get('combined_gross', '$0.00')}")
        
        # Clean up
        os.unlink(test_file_path)
        
        # Final result
        if len(gl_details) == 2 and bool(total_row):
            print("\n✅ TEST PASSED: GL detail processing is working correctly!")
            return True
        else:
            print("\n❌ TEST FAILED: GL detail processing is not working as expected!")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up
        os.unlink(test_file_path)
        return False

if __name__ == "__main__":
    print("=== GL Detail Processing Test ===")
    success = run_test()
    sys.exit(0 if success else 1)