#\!/usr/bin/env python3
"""
Script to test LaTeX letter generation with actual reconciliation data.
"""

import os
import sys
import glob
from pathlib import Path

# Import the LaTeX letter generator
from latex_letter_generator import generate_letters_from_results

# Configuration
csv_report_path = "Output/Reports/tenant_billing_WAT_cam_2024_20250515_142513.csv"
gl_detail_pattern = "Output/Reports/GL_Details/WAT_2024/**/GL_detail_*_2024_*.csv"

# Create a results dictionary to pass to the generator
results = {
    'csv_report_path': csv_report_path,
    'gl_detail_reports': glob.glob(gl_detail_pattern, recursive=True)
}

# Print what we found
print(f"CSV Report: {csv_report_path}")
print(f"Found {len(results['gl_detail_reports'])} GL detail reports")

# Generate letters
success_count, total_count = generate_letters_from_results(results)

print(f"\nLetter generation complete: {success_count} of {total_count} letters generated")
print("Check Letters/CAM/WAT/2024/ for both LaTeX (.tex) and PDF (.pdf) files.")
