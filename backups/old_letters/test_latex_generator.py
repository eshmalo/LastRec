#!/usr/bin/env python3
"""
Test script for LaTeX letter generation
This script tests creating LaTeX and PDF files for reconciliation letters
"""

import os
import sys
import subprocess
from pathlib import Path
from letter_generator import generate_tenant_letter, escape_latex, format_currency, format_percentage

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

def generate_latex_letter(tenant_data, gl_detail_file, debug_mode=False):
    """
    Generate a LaTeX letter for a tenant.
    
    Args:
        tenant_data: Dictionary with tenant billing data
        gl_detail_file: Path to the GL detail file for this tenant
        debug_mode: Whether to print debug information
        
    Returns:
        The path to the generated LaTeX file
    """
    if debug_mode:
        print(f"Generating LaTeX letter for tenant {tenant_data.get('tenant_id')} - {tenant_data.get('tenant_name')}")
    
    # First generate the text letter to get the path
    text_file_path = generate_tenant_letter(tenant_data, gl_detail_file, debug_mode)
    text_path = Path(text_file_path)
    
    # Extract basic tenant info for output path
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = tenant_data.get("tenant_name", "")
    property_id = tenant_data.get("property_id", "")
    # Extract year from reconciliation_end_date properly
    from letter_generator import extract_year_from_date
    reconciliation_year = extract_year_from_date(tenant_data.get("reconciliation_end_date", ""))
    
    # Create LaTeX directory
    latex_dir = text_path.parent / "LaTeX"
    latex_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output file paths
    latex_file_path = latex_dir / f"{text_path.stem}.tex"
    pdf_dir = text_path.parent / "PDFs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_file_path = pdf_dir / f"{text_path.stem}.pdf"
    
    # Format all the data for LaTeX
    title = f"CAM RECONCILIATION - {tenant_data.get('property_full_name')}"
    
    # Extract all the financial values for display
    recon_start_date = tenant_data.get("reconciliation_start_date", "")
    recon_end_date = tenant_data.get("reconciliation_end_date", "")
    catchup_start_date = tenant_data.get("catchup_start_date", "")
    catchup_end_date = tenant_data.get("catchup_end_date", "")
    
    # Format dates for display
    from letter_generator import format_date_range
    main_period_range = format_date_range(recon_start_date, recon_end_date)
    catchup_period_range = format_date_range(catchup_start_date, catchup_end_date)
    
    if catchup_period_range:
        reconciliation_period = f"{main_period_range} and {catchup_period_range}"
    else:
        reconciliation_period = main_period_range
    
    # Generate LaTeX content
    latex_content = []
    latex_content.append(r"\documentclass[12pt]{article}")
    latex_content.append(r"\usepackage[margin=1in]{geometry}")
    latex_content.append(r"\usepackage{booktabs}")
    latex_content.append(r"\usepackage{graphicx}")
    latex_content.append(r"\usepackage{enumitem}")
    latex_content.append(r"\usepackage{titlesec}")
    latex_content.append(r"\usepackage{xcolor}")
    latex_content.append(r"\usepackage{fancyhdr}")
    latex_content.append(r"\usepackage{lastpage}")
    latex_content.append(r"\renewcommand{\familydefault}{\sfdefault}")
    latex_content.append(r"\pagestyle{fancy}")
    latex_content.append(r"\fancyhf{}")
    latex_content.append(r"\renewcommand{\headrulewidth}{0pt}")
    latex_content.append(r"\fancyfoot[C]{\small\thepage\ of \pageref{LastPage}}")
    latex_content.append(r"\setlength{\parindent}{0pt}")
    latex_content.append(r"\titleformat{\section}{\normalfont\bfseries\Large}{\thesection}{1em}{}")
    latex_content.append(r"\titleformat{\subsection}{\normalfont\bfseries\large}{\thesubsection}{1em}{}")
    latex_content.append(r"\begin{document}")
    
    # Header
    latex_content.append(r"\begin{center}")
    latex_content.append(r"\textbf{\Large " + escape_latex(title) + r"}")
    latex_content.append(r"\end{center}")
    
    latex_content.append(r"\vspace{0.5em}")
    latex_content.append(r"\textbf{Reconciliation Period:} " + escape_latex(reconciliation_period) + r"\\")
    latex_content.append(r"\textbf{Tenant:} " + escape_latex(tenant_data.get("tenant_name", "")) + r"\\")
    
    # Add a horizontal rule
    latex_content.append(r"\vspace{0.5em}\hrule\vspace{0.5em}")
    
    # Reconciliation Summary
    latex_content.append(r"\subsection*{RECONCILIATION SUMMARY}")
    latex_content.append(r"\begin{itemize}[leftmargin=*,label={}]")
    
    # Extract financial values for display
    property_total_expenses = tenant_data.get("property_gl_total", "$0.00")
    tenant_pro_rata = tenant_data.get("share_percentage", "0%")
    tenant_share = tenant_data.get("tenant_share_amount", "$0.00")
    base_year_amount = tenant_data.get("base_year_adjustment", "$0.00")
    cap_reduction = tenant_data.get("cap_deduction", "$0.00")
    admin_fee = tenant_data.get("admin_fee_net", "$0.00")
    amortization_amount = tenant_data.get("amortization_total_amount", "$0.00")
    
    # Build line items
    latex_content.append(r"\item Total Property CAM Expenses (" + reconciliation_year + r"): " + 
                        escape_latex(property_total_expenses))
    latex_content.append(r"\item Tenant's Pro-Rata Share (" + escape_latex(tenant_pro_rata) + r"): " + 
                        escape_latex(tenant_share))
    
    # Only include line items with non-zero values
    if float(base_year_amount.strip('$').replace(',', '') or 0) > 0:
        latex_content.append(r"\item Base Year Deduction: -" + escape_latex(base_year_amount))
    if float(cap_reduction.strip('$').replace(',', '') or 0) > 0:
        latex_content.append(r"\item Cap Reduction: -" + escape_latex(cap_reduction))
    if float(amortization_amount.strip('$').replace(',', '') or 0) > 0:
        latex_content.append(r"\item Amortization: " + escape_latex(amortization_amount))
    if float(admin_fee.strip('$').replace(',', '') or 0) > 0:
        latex_content.append(r"\item Admin Fee: " + escape_latex(admin_fee))
    
    # Calculate year due - this ensures the sum matches the line items
    year_due = float(tenant_share.strip('$').replace(',', '') or 0)
    if float(base_year_amount.strip('$').replace(',', '') or 0) > 0:
        year_due -= float(base_year_amount.strip('$').replace(',', ''))
    if float(cap_reduction.strip('$').replace(',', '') or 0) > 0:
        year_due -= float(cap_reduction.strip('$').replace(',', ''))
    if float(admin_fee.strip('$').replace(',', '') or 0) > 0:
        year_due += float(admin_fee.strip('$').replace(',', ''))
    if float(amortization_amount.strip('$').replace(',', '') or 0) > 0:
        year_due += float(amortization_amount.strip('$').replace(',', ''))
    
    latex_content.append(r"\item Total Due for Year: " + escape_latex(format_currency(year_due)))
    latex_content.append(r"\item Previously Billed (" + reconciliation_year + r"): " + 
                        escape_latex(tenant_data.get("reconciliation_paid", "$0.00")))
    latex_content.append(r"\item " + reconciliation_year + r" Reconciliation Amount: " + 
                        escape_latex(tenant_data.get("reconciliation_balance", "$0.00")))
    
    # Add catchup period if exists
    if catchup_period_range and float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', '') or 0) != 0:
        latex_content.append(r"\item " + escape_latex(catchup_period_range) + r" Catchup Period: " + 
                            escape_latex(tenant_data.get("catchup_balance", "$0.00")))
    
    # Add override if exists
    has_override = tenant_data.get("has_override", "false").lower() == "true"
    override_amount = tenant_data.get("override_amount", "$0.00")
    override_description = tenant_data.get("override_description", "Manual Adjustment")
    if has_override and float(override_amount.strip('$').replace(',', '') or 0) != 0:
        latex_content.append(r"\item " + escape_latex(override_description) + r": " + 
                            escape_latex(override_amount))
    
    # Add grand total
    latex_content.append(r"\item \textbf{ADDITIONAL AMOUNT DUE: " + 
                        escape_latex(tenant_data.get("total_balance", "$0.00")) + r"}")
    
    latex_content.append(r"\end{itemize}")
    
    # Add a horizontal rule
    latex_content.append(r"\vspace{0.5em}\hrule\vspace{0.5em}")
    
    # Monthly charge update
    latex_content.append(r"\subsection*{MONTHLY CHARGE UPDATE}")
    latex_content.append(r"\begin{itemize}[leftmargin=*,label={}]")
    latex_content.append(r"\item Current Monthly Charge: " + 
                        escape_latex(tenant_data.get("old_monthly", "$0.00")))
    latex_content.append(r"\item New Monthly Charge: " + 
                        escape_latex(tenant_data.get("new_monthly", "$0.00")))
    latex_content.append(r"\item Difference per Month: " + 
                        escape_latex(tenant_data.get("monthly_difference", "$0.00")))
    
    # Get effective date
    effective_date = tenant_data.get("monthly_charge_effective_date", "")
    if effective_date:
        import datetime
        try:
            # Convert YYYY-MM-DD to Mon DD, YYYY
            date_obj = datetime.datetime.strptime(effective_date, "%Y-%m-%d")
            effective_date = date_obj.strftime("%b %d, %Y")
        except ValueError:
            # If parse fails, use as is
            pass
    else:
        # Calculate next month
        today = datetime.datetime.now()
        next_month = today.replace(day=1)
        if today.month == 12:
            next_month = next_month.replace(year=today.year + 1, month=1)
        else:
            next_month = next_month.replace(month=today.month + 1)
        effective_date = next_month.strftime("%b %d, %Y")
    
    latex_content.append(r"\item The new monthly charge will be effective starting " + 
                        escape_latex(effective_date) + r".")
    latex_content.append(r"\end{itemize}")
    
    # Add a horizontal rule
    latex_content.append(r"\vspace{0.5em}\hrule\vspace{0.5em}")
    
    # Footer with contact info
    from letter_generator import CONTACT_INFO
    latex_content.append(CONTACT_INFO)
    
    # End document
    latex_content.append(r"\end{document}")
    
    # Write the LaTeX file
    with open(latex_file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(latex_content))
    
    if debug_mode:
        print(f"  LaTeX file generated at: {latex_file_path}")
    
    # Attempt to compile the LaTeX file to PDF
    try:
        # Run pdflatex twice to ensure references are resolved
        process = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory=' + str(pdf_dir), str(latex_file_path)],
            capture_output=True,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            print(f"  Warning: PDF generation encountered errors:")
            print(process.stderr)
            # Save the error log
            error_log_path = pdf_dir / f"{text_path.stem}_error.log"
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(process.stdout)
            print(f"  Error log saved to: {error_log_path}")
        else:
            # Run again for references
            subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-output-directory=' + str(pdf_dir), str(latex_file_path)],
                capture_output=True,
                check=False
            )
            print(f"  PDF generated successfully at: {pdf_file_path}")
    except FileNotFoundError:
        print("  Warning: pdflatex command not found. PDF generation skipped.")
        print("  You need to install LaTeX to generate PDFs (e.g., MacTeX on macOS)")
    
    return str(latex_file_path)

def main():
    print("Testing LaTeX letter generation with sample data...")
    
    try:
        # No GL detail file for this test
        gl_detail_file = ""
        
        # Generate the LaTeX letter
        latex_path = generate_latex_letter(sample_tenant_data, gl_detail_file, debug_mode=True)
        
        print(f"\nSuccess! LaTeX letter generated at: {latex_path}")
        
        # Check if PDF was generated
        pdf_path = Path(latex_path).parent.parent / "PDFs" / f"{Path(latex_path).stem}.pdf"
        if pdf_path.exists():
            print(f"PDF generated at: {pdf_path}")
        
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nError generating LaTeX letter: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()