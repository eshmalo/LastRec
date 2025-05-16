#!/usr/bin/env python3
"""
Test script to verify the negative balance exclusion logic
"""

from decimal import Decimal

# Mock data to test the logic
def test_negative_balance_logic():
    # Mock GL data with Base Rents (which should not be included in CAM)
    gl_data = [
        {'GL Account': '4010', 'GL Description': 'Base Rents', 'PERIOD': '202401', 'Net Amount': '-50000'},
        {'GL Account': '4010', 'GL Description': 'Base Rents', 'PERIOD': '202402', 'Net Amount': '-50000'},
        {'GL Account': '6010', 'GL Description': 'Utilities', 'PERIOD': '202401', 'Net Amount': '10000'},
        {'GL Account': '6010', 'GL Description': 'Utilities', 'PERIOD': '202402', 'Net Amount': '-15000'},  # Negative total
        {'GL Account': '6020', 'GL Description': 'Maintenance', 'PERIOD': '202401', 'Net Amount': '5000'},
        {'GL Account': '6020', 'GL Description': 'Maintenance', 'PERIOD': '202402', 'Net Amount': '3000'},
    ]
    
    # Mock inclusion rules (Base Rents 4010 not included in CAM)
    inclusions = {
        'cam': ['6000-6999'],  # Only utilities and maintenance included
        'ret': [],
    }
    
    recon_periods = ['202401', '202402']
    categories = ['cam', 'ret']
    
    # Simulate the logic
    gl_account_totals = {}
    negative_balance_accounts = {}
    
    # First pass: Calculate totals for included accounts only
    for transaction in gl_data:
        gl_account = transaction['GL Account']
        period = transaction['PERIOD']
        net_amount = Decimal(transaction['Net Amount'])
        
        if not gl_account or not period or str(period) not in recon_periods:
            continue
            
        # Check if included in ANY category
        is_included_anywhere = False
        for category in categories:
            category_inclusions = inclusions.get(category, [])
            if category_inclusions:
                # Simple check - would need full implementation for ranges
                for rule in category_inclusions:
                    if '-' in rule:  # Range
                        start, end = rule.split('-')
                        if start <= gl_account <= end:
                            is_included_anywhere = True
                            break
                    elif gl_account == rule:
                        is_included_anywhere = True
                        break
            if is_included_anywhere:
                break
        
        # Only accumulate totals for included accounts
        if is_included_anywhere:
            if gl_account not in gl_account_totals:
                gl_account_totals[gl_account] = Decimal('0')
            gl_account_totals[gl_account] += net_amount
            print(f"Account {gl_account} ({transaction['GL Description']}) included, adding {net_amount}")
    
    print("\nGL Account Totals (included accounts only):")
    for account, total in gl_account_totals.items():
        print(f"  {account}: {total}")
    
    # Identify negative balance accounts
    for account, total in gl_account_totals.items():
        if total < 0:
            negative_balance_accounts[account] = total
            print(f"\nAccount {account} has negative balance: {total}")
    
    print(f"\nNegative balance accounts: {negative_balance_accounts}")
    print(f"Base Rents (4010) in negative balance list: {'4010' in negative_balance_accounts}")

if __name__ == '__main__':
    test_negative_balance_logic()