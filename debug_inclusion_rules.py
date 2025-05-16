#!/usr/bin/env python3
"""
Debug script to check which GL accounts are being included based on inclusion rules
"""

import json

def check_account_inclusion(gl_account, inclusion_rules):
    """Check if a GL account should be included based on inclusion rules."""
    if not inclusion_rules:
        return False
    
    # Normalize the account
    clean_account = gl_account.replace('MR', '')
    
    for rule in inclusion_rules:
        rule = rule.strip()
        if '-' in rule:  # It's a range
            start, end = rule.split('-')
            start = start.strip().replace('MR', '')
            end = end.strip().replace('MR', '')
            if start <= clean_account <= end:
                return True
        else:  # It's a single account
            clean_rule = rule.replace('MR', '')
            if clean_rule == clean_account:
                return True
    
    return False

# Test with common GL accounts
test_accounts = [
    '4010',  # Base Rents
    '4020',  # Other rental income
    '6010',  # Utilities
    '6020',  # Maintenance
    '7010',  # Insurance
    '8010',  # Admin costs
]

# Test inclusion rules
test_inclusions = {
    'cam': ['6000-6999', '7000-7999'],  # Common CAM inclusions
    'ret': ['8000-8999'],  # Common RET inclusions
}

print("GL Account Inclusion Test:")
print("-" * 50)
for account in test_accounts:
    included_in = []
    for category, rules in test_inclusions.items():
        if check_account_inclusion(account, rules):
            included_in.append(category)
    
    if included_in:
        print(f"GL {account}: Included in {included_in}")
    else:
        print(f"GL {account}: Not included in any category")

print("\nNote: Only GL accounts that are included in at least one category")
print("will be checked for negative balance exclusion.")