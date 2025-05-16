#!/usr/bin/env python3
"""
Diagnostic script to help identify why certain GL accounts might be appearing 
in the negative balance section when they shouldn't be.
"""

import json
from decimal import Decimal

def check_account_inclusion(gl_account, inclusion_rules):
    """Check if a GL account should be included based on inclusion rules."""
    if not inclusion_rules:
        return False
    
    # Normalize the account
    clean_account = gl_account.replace('MR', '')
    
    for rule in inclusion_rules:
        rule = str(rule).strip()
        if '-' in rule:  # It's a range
            parts = rule.split('-')
            if len(parts) == 2:
                start, end = parts
                start = start.strip().replace('MR', '')
                end = end.strip().replace('MR', '')
                if start <= clean_account <= end:
                    return True, f"Range {rule}"
        else:  # It's a single account
            clean_rule = rule.replace('MR', '')
            if clean_rule == clean_account:
                return True, f"Exact match {rule}"
    
    return False, None

def diagnose_gl_account(gl_account, inclusions, gl_transactions):
    """Diagnose why a GL account might be included/excluded."""
    print(f"\nDiagnosing GL Account: {gl_account}")
    print("-" * 50)
    
    # Check inclusion in each category
    included_in = []
    inclusion_reasons = {}
    
    for category, rules in inclusions.items():
        is_included, reason = check_account_inclusion(gl_account, rules)
        if is_included:
            included_in.append(category)
            inclusion_reasons[category] = reason
    
    if included_in:
        print(f"✓ Included in categories: {included_in}")
        for cat, reason in inclusion_reasons.items():
            print(f"  - {cat}: {reason}")
    else:
        print(f"✗ Not included in any category")
        print(f"  This account should NOT appear in negative balance section")
        return
    
    # Calculate total across periods
    total = Decimal('0')
    period_amounts = {}
    
    for transaction in gl_transactions:
        if transaction['GL Account'] == gl_account:
            period = transaction['PERIOD']
            amount = Decimal(str(transaction['Net Amount']))
            total += amount
            period_amounts[period] = amount
    
    print(f"\nPeriod breakdown:")
    for period, amount in sorted(period_amounts.items()):
        print(f"  {period}: ${amount:,.2f}")
    
    print(f"\nTotal across all periods: ${total:,.2f}")
    
    if total < 0:
        print(f"⚠️  NEGATIVE TOTAL - This account WILL be excluded")
    else:
        print(f"✓ Positive total - This account will NOT be excluded")

# Example usage
if __name__ == "__main__":
    # Example GL inclusion rules
    example_inclusions = {
        'cam': ['6000-6999', '7000-7999'],
        'ret': ['8000-8999'],
    }
    
    # Example GL transactions
    example_transactions = [
        {'GL Account': '4010', 'PERIOD': '202401', 'Net Amount': '-50000'},
        {'GL Account': '4010', 'PERIOD': '202402', 'Net Amount': '-50000'},
        {'GL Account': '6010', 'PERIOD': '202401', 'Net Amount': '10000'},
        {'GL Account': '6010', 'PERIOD': '202402', 'Net Amount': '-15000'},
    ]
    
    # Test specific accounts
    test_accounts = ['4010', '6010']
    
    print("GL Account Negative Balance Diagnostic Tool")
    print("=" * 50)
    
    for account in test_accounts:
        diagnose_gl_account(account, example_inclusions, example_transactions)
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("- Only accounts included in at least one category are checked for negative balances")
    print("- Accounts with negative totals across all periods are excluded")
    print("- Accounts not included in any category should never appear in negative balance section")