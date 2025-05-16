#!/usr/bin/env python3
"""
Test script for latex_letter_generator.py.
This directly tests the LaTeX letter generation functionality.
"""

import os
from pathlib import Path
from latex_letter_generator import generate_tenant_letter, compile_to_pdf

# Create a sample tenant data dictionary
sample_tenant = {
    "tenant_id": "1401",
    "tenant_name": "Mexico Grill, LLC",
    "property_id": "WAT",
    "property_name": "Main Portfolio",
    "property_full_name": "Watchung",
    "share_percentage": "6.7300%",
    "property_gl_total": "$173,638.08",
    "cam_net_total": "$173,028.49",
    "admin_fee_percentage": "0.00%",
    "admin_fee_net": "$0.00",
    "base_year_adjustment": "$0.00",
    "cap_deduction": "$0.00",
    "tenant_share_amount": "$11,644.82",
    "amortization_total_amount": "$0.00",
    "reconciliation_paid": "$6,526.56",
    "reconciliation_balance": "$1,854.98",
    "catchup_balance": "$618.33",
    "total_balance": "$2,473.30",
    "override_amount": "$-3,263.28",
    "override_description": "Jan-Apr 2024 payment",
    "has_override": "true",
    "old_monthly": "$815.82",
    "new_monthly": "$970.40",
    "monthly_difference": "$154.58",
    "reconciliation_start_date": "2024-01-01",
    "reconciliation_end_date": "2024-12-31",
    "catchup_start_date": "2025-01-01",
    "catchup_end_date": "2025-04-30",
    "monthly_charge_effective_date": "2025-06-01",
    "amortization_exists": "false"
}

# No GL detail file for this test
gl_detail_file = None

def main():
    print("Testing LaTeX letter generator...")
    
    # Clear out existing test files if they exist
    test_dir = Path("Letters/Test")
    if test_dir.exists():
        for file in test_dir.glob("**/*"):
            if file.is_file():
                file.unlink()
    
    # Temporarily modify the LETTERS_DIR
    import latex_letter_generator
    old_letters_dir = latex_letter_generator.LETTERS_DIR
    latex_letter_generator.LETTERS_DIR = Path("Letters/Test")
    
    try:
        print("\nGenerating sample letter...")
        
        latex_content, pdf_path, tex_path = generate_tenant_letter(
            sample_tenant, gl_detail_file, debug_mode=True
        )
        
        # Create directories and save LaTeX file
        os.makedirs(os.path.dirname(tex_path), exist_ok=True)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
        print(f"LaTeX file written to: {tex_path}")
        
        # Try to compile to PDF
        if compile_to_pdf(latex_content, pdf_path):
            print(f"PDF compiled successfully to: {pdf_path}")
        else:
            print(f"Failed to compile PDF. Check curl output and LaTeX errors.")
    finally:
        # Restore original LETTERS_DIR
        latex_letter_generator.LETTERS_DIR = old_letters_dir
    
    print("\nTest complete.")

if __name__ == "__main__":
    main()