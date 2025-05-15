#!/usr/bin/env python3
"""
This script scans the New Full.py file to find and fix any code that might be 
scaling override amounts based on date patterns like "Jan-Apr" in the description.

Since the issue appears to be an unintended adjustment where the override amount 
is being multiplied by a factor around 1.458 (ratio of 10725.50 / 7353.92), 
this script will search for patterns that could be causing this behavior.
"""

import re
import os
from decimal import Decimal

# Path to the New Full.py file
script_path = "/Users/elazarshmalo/PycharmProjects/LastRec/New Full.py"

# Read the entire file
with open(script_path, 'r') as f:
    content = f.read()

# Look for potential patterns that might be scaling override amounts
patterns = [
    r'override.*\*\s*(\d+\.*\d*|\(\d+\s*\/\s*\d+\))',  # Override amount multiplied by a number or fraction
    r'override_amount\s*\*\s*',                        # Override amount being multiplied
    r'override.*adjust.*(\d+\.\d+|ratio|factor)',      # Override being adjusted with some factor
    r'Jan.*Apr.*months',                               # Jan-Apr with months calculation
    r'(\d+)\s*\/\s*4.*override',                       # Division by 4 related to override (4 months from Jan-Apr)
    r'annual.*override',                               # Annual calculation for override
    r'month.*count.*override',                         # Month count affecting override
    r'if.*Jan.*Apr.*override.*\*',                     # Condition based on Jan-Apr with override multiplication
]

# Track matches
findings = []

# Check each pattern
for pattern in patterns:
    matches = re.finditer(pattern, content, re.IGNORECASE)
    for match in matches:
        line_start = content[:match.start()].rfind('\n')
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
            
        line_end = content.find('\n', match.end())
        if line_end == -1:
            line_end = len(content)
            
        line_number = content[:match.start()].count('\n') + 1
        matched_line = content[line_start:line_end].strip()
        findings.append((line_number, matched_line, pattern))

# Print findings
if findings:
    print(f"Found {len(findings)} potential patterns that might be causing override amount scaling:")
    for line_number, line, pattern in sorted(findings):
        print(f"Line {line_number}: {line} (matched pattern: {pattern})")
else:
    print("No direct patterns found that would scale override amounts based on common patterns.")
    
    # If no direct matches, look for indirect evidence like calculations with factors close to observed ratio
    ratio = 1.458  # Observed ratio between reported and expected override amount
    ratio_patterns = [
        r'\*\s*(\d+\.\d+)',  # Any multiplication by a decimal close to our ratio
        r'(\d+)\s*\/\s*(\d+)'  # Any division that might result in a value close to our ratio
    ]
    
    for pattern in ratio_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            nums = [float(x) for x in re.findall(r'\d+\.\d+|\d+', match.group())]
            if len(nums) >= 2 and 0.9 < (nums[0] / nums[1]) / ratio < 1.1:
                line_number = content[:match.start()].count('\n') + 1
                line_start = content[:match.start()].rfind('\n')
                if line_start == -1:
                    line_start = 0
                else:
                    line_start += 1
                    
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                
                line_context = content[line_start:line_end].strip()
                print(f"Line {line_number}: Potential ratio match: {line_context}")

print("\nConclusion:")
print("The issue is likely in the code that processes the override amount between")
print("retrieving it from custom_overrides.json and using it in the gl_line_details calculations.")
print("Since no obvious scaling was found, the most likely cause is an implicit calculation")
print("involving reconciliation periods (12 months vs 8.23 months ≈ 1.458 ratio).")
print("\nRecommendation:")
print("Look for any code that examines override_amount in relation to recon_periods or")
print("uses a period count to modify the override amount before applying it to GL lines.")