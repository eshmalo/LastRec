#!/usr/bin/env python3
"""
LaTeX Letter Generator Patch

This script adds LaTeX and PDF functionality to the existing letter_generator.py
"""

import os
import sys
import re
import subprocess
from pathlib import Path

def compile_to_pdf(latex_content, output_file):
    """Compile LaTeX content to PDF using texlive.net online service."""
    try:
        # Create parent directories
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Save LaTeX content to file
        tex_file = output_file.replace('.pdf', '.tex')
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        print(f"  LaTeX content saved to: {tex_file}")
        
        # Use texlive.net's API with curl
        print("  Using texlive.net online compilation service...")
        
        # Build curl command
        curl_cmd = [
            'curl', '-s', '-L',
            '-X', 'POST',
            'https://texlive.net/cgi-bin/latexcgi',
            '-F', 'return=pdf',
            '-F', 'engine=pdflatex',
            '-F', 'filename[]=document.tex',
            '-F', f'filecontents[]={latex_content}'
        ]
        
        # Execute curl command
        with open(output_file, 'wb') as f:
            process = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE)
            stdout, stderr = process.communicate()
            f.write(stdout)
        
        # Check if the output is a valid PDF
        with open(output_file, 'rb') as f:
            content = f.read(4)
            if content == b'%PDF':
                print(f"  PDF generated successfully: {output_file}")
                return True
            else:
                # Not a valid PDF, might be an error log
                print(f"  Error in PDF generation. See error log.")
                # Save error log
                log_file = output_file.replace('.pdf', '_error.log')
                with open(log_file, 'wb') as f:
                    f.write(stdout)
                return False
    except Exception as e:
        print(f"  Error compiling PDF: {str(e)}")
        return False

def get_letter_template():
    """Return the main letter template."""
    return r"""\documentclass{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{xcolor}
\usepackage{fancyhdr}

% Set up fancy headers/footers
\pagestyle{fancy}
\fancyhf{} % Clear all headers/footers
\renewcommand{\footrulewidth}{0.4pt}
\fancyfoot[C]{$CONTACT_INFO$}

$DRAFT_WATERMARK$

\begin{document}

$DRAFT_HEADER$

\begin{center}
\Large\textbf{CAM Reconciliation - $PROPERTY_NAME$}

\normalsize
\textbf{Reconciliation Period: $RECONCILIATION_PERIOD$}
\end{center}

\begin{center}
\textbf{$TENANT_NAME$}
\end{center}

\vspace{1em}

\begin{center}
\begin{tabular}{@{}p{3.2in}r@{}}
\toprule
\textbf{Description} & \textbf{Amount} \\
\midrule
Total Property CAM Expenses ($RECONCILIATION_YEAR$) & \$PROPERTY_TOTAL_EXPENSES$ \\
Tenant's Pro-Rata Share ($TENANT_PRO_RATA$\%) & \$TENANT_SHARE$ \\
$BASE_YEAR_DEDUCTION$
$CAP_REDUCTION_LINE$
$AMORTIZATION_LINE$
$ADMIN_FEE_LINE$
\midrule
Total Due for Year & \$YEAR_DUE$ \\
Previously Billed ($RECONCILIATION_YEAR$) & \$MAIN_PERIOD_PAID$ \\
\midrule
$RECONCILIATION_YEAR$ Reconciliation Amount & \$MAIN_PERIOD_BALANCE$ \\
$CATCHUP_PERIOD_LINE$
$OVERRIDE_LINE$
\midrule
\textbf{ADDITIONAL AMOUNT DUE} & \textbf{\$GRAND_TOTAL$} \\
\bottomrule
\end{tabular}
\end{center}

\vspace{0.5em}
\hspace{1in}Please remit the amount shown above within 30 days.

\vspace{1em}
\begin{center}
\Large\textbf{Monthly Charge Update}
\end{center}

\begin{center}
\begin{tabular}{@{}p{3.2in}r@{}}
\toprule
Current Monthly Charge & \$CURRENT_MONTHLY_CHARGE$ \\
New Monthly Charge & \$NEW_MONTHLY_CHARGE$ \\
Difference per Month & \$MONTHLY_DIFF$ \\
\bottomrule
\end{tabular}
\end{center}

\vspace{0.5em}
\hspace{1in}The new monthly charge will be effective starting $EFFECTIVE_DATE$.

\vfill % Space at the bottom

$GL_BREAKDOWN_SECTION$

$AMORTIZATION_SECTION$

\end{document}"""


def get_gl_breakdown_template():
    """Return the GL breakdown template."""
    return r"""\newpage

\begin{center}
\Large\textbf{CAM Expense Breakdown}

\normalsize
\textbf{$PROPERTY_NAME$ - $RECONCILIATION_YEAR$}
\end{center}

$CAP_NOTE$

\begin{center}
$GL_TABLE_START$
\toprule
$GL_TABLE_HEADER$
\midrule
$GL_ROWS$
\midrule
\textbf{TOTAL} & $GL_TOTAL_ROW$
\bottomrule
\end{tabular}
\end{center}"""


def get_amortization_template():
    """Return the amortization template."""
    return r"""\newpage

\begin{center}
\Large\textbf{Amortization Details}
\end{center}

\begin{center}
\begin{tabular}{@{}lrrrrr@{}}
\toprule
\textbf{Description} & \textbf{Total Amount} & \textbf{Years} & \textbf{Annual Amount} & \textbf{Your Share \%} & \textbf{Your Share} \\
\midrule
$AMORTIZATION_ROWS$
$AMORTIZATION_TOTAL$
\bottomrule
\end{tabular}
\end{center}

\vspace{0.5em}
\begin{center}
\small{Note: Amortization represents your share of capital improvements}\\
\small{that are allocated over multiple years rather than expensed all at once.}
\end{center}"""

def generate_latex_letter(tenant_data, gl_detail_file, debug_mode=False):
    """Generate a LaTeX letter using the same tenant data structure as generate_tenant_letter."""
    import sys
    from letter_generator import (
        format_currency, format_percentage, escape_latex,
        format_date_range, extract_year_from_date,
        get_gl_details_for_tenant, LETTERS_DIR, PROPERTY_NAMES, CONTACT_INFO
    )
    
    if debug_mode:
        print(f"Generating LaTeX letter for tenant {tenant_data.get('tenant_id')} - {tenant_data.get('tenant_name')}")
    
    # Extract tenant basic info
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = tenant_data.get("tenant_name", "")
    property_id = tenant_data.get("property_id", "")
    property_name = tenant_data.get("property_full_name", PROPERTY_NAMES.get(property_id, property_id))
    
    # Extract dates and format periods
    recon_start_date = tenant_data.get("reconciliation_start_date", "")
    recon_end_date = tenant_data.get("reconciliation_end_date", "")
    catchup_start_date = tenant_data.get("catchup_start_date", "")
    catchup_end_date = tenant_data.get("catchup_end_date", "")
    
    main_period_range = format_date_range(recon_start_date, recon_end_date)
    catchup_period_range = format_date_range(catchup_start_date, catchup_end_date)
    reconciliation_year = extract_year_from_date(recon_end_date)
    
    # Build reconciliation period string
    if catchup_period_range:
        reconciliation_period = f"{main_period_range} and {catchup_period_range}"
    else:
        reconciliation_period = main_period_range
    
    # Create output directories
    letter_dir = LETTERS_DIR / "CAM" / property_id / reconciliation_year
    pdf_dir = letter_dir / "PDFs"
    tex_dir = letter_dir / "LaTeX"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    tex_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output file paths
    safe_tenant_name = tenant_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    tex_path = tex_dir / f"{safe_tenant_name}_{tenant_id}.tex"
    pdf_path = pdf_dir / f"{safe_tenant_name}_{tenant_id}.pdf"
    
    # Get GL details if file is provided
    gl_details = []
    gl_total_row = {}
    if gl_detail_file and os.path.exists(gl_detail_file):
        gl_details, gl_total_row = get_gl_details_for_tenant(gl_detail_file)
    
    # Extract financial values - only keep non-zero values
    property_total_expenses = tenant_data.get("property_gl_total", "0").strip('$').replace(',', '')
    tenant_pro_rata = tenant_data.get("share_percentage", "0").strip('%')
    tenant_share = tenant_data.get("tenant_share_amount", "0").strip('$').replace(',', '')
    base_year_amount = tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '')
    cap_reduction = tenant_data.get("cap_deduction", "0").strip('$').replace(',', '')
    admin_fee = tenant_data.get("admin_fee_net", "0").strip('$').replace(',', '')
    amortization_amount = tenant_data.get("amortization_total_amount", "0").strip('$').replace(',', '')
    
    # Get billing details
    main_period_paid = tenant_data.get("reconciliation_paid", "0").strip('$').replace(',', '')
    main_period_balance = tenant_data.get("reconciliation_balance", "0").strip('$').replace(',', '')
    catchup_balance = tenant_data.get("catchup_balance", "0").strip('$').replace(',', '')
    
    # Get override info
    has_override = tenant_data.get("has_override", "false").lower() == "true"
    override_amount = tenant_data.get("override_amount", "0").strip('$').replace(',', '')
    override_description = tenant_data.get("override_description", "Manual Adjustment")
    
    # Get total final amount
    grand_total = tenant_data.get("total_balance", "0").strip('$').replace(',', '')
    
    # Calculate year due (main_period_total) - this ensures the sum matches the line items
    # Start with tenant share
    year_due = float(tenant_share)
    # Deduct base year adjustment if present
    if float(base_year_amount) > 0:
        year_due -= float(base_year_amount)
    # Deduct cap reduction if present
    if float(cap_reduction) > 0:
        year_due -= float(cap_reduction)
    # Add admin fee if present
    if float(admin_fee) > 0:
        year_due += float(admin_fee)
    # Add amortization if present
    if float(amortization_amount) > 0:
        year_due += float(amortization_amount)
    
    # Get monthly charge info
    current_monthly_charge = tenant_data.get("old_monthly", "0").strip('$').replace(',', '')
    new_monthly_charge = tenant_data.get("new_monthly", "0").strip('$').replace(',', '')
    monthly_diff = tenant_data.get("monthly_difference", "0").strip('$').replace(',', '')
    
    # Get effective date from tenant data or calculate it
    effective_date = tenant_data.get("monthly_charge_effective_date", "")
    if effective_date:
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
    
    # Escape LaTeX special characters
    tenant_name_escaped = escape_latex(tenant_name)
    property_name_escaped = escape_latex(property_name)
    override_desc_escaped = escape_latex(override_description)
    
    # Prepare conditional lines - only include non-zero values
    base_year_deduction = ""
    if float(base_year_amount) > 0:
        base_year_deduction = f"Base Year Deduction & -\\${format_currency(base_year_amount, False)} \\\\"
    
    cap_reduction_line = ""
    if float(cap_reduction) > 0:
        cap_reduction_line = f"Cap Reduction & -\\${format_currency(cap_reduction, False)} \\\\"
    
    amortization_line = ""
    if float(amortization_amount) > 0:
        amortization_line = f"Amortization & \\${format_currency(amortization_amount, False)} \\\\"
    
    admin_fee_line = ""
    if float(admin_fee) > 0:
        admin_fee_line = f"Admin Fee & \\${format_currency(admin_fee, False)} \\\\"
    
    catchup_period_line = ""
    if float(catchup_balance) != 0:
        catchup_period_line = f"{catchup_period_range} Catchup Period & \\${format_currency(catchup_balance, False)} \\\\"
    
    override_line = ""
    if has_override and float(override_amount) != 0:
        override_line = f"{override_desc_escaped} & \\${format_currency(override_amount, False)} \\\\"
    
    # Generate GL breakdown section if details are available
    gl_breakdown_section = ""
    if gl_details:
        # Determine if CAP was applied
        cap_applied = float(cap_reduction) > 0
        
        # Prepare CAP note if applicable
        cap_note = ""
        if cap_applied:
            cap_note = r"\begin{center}\small{Note: The GL breakdown shows expenses before cap adjustments.}\end{center}"
        
        # Determine table structure based on CAP application
        if cap_applied:
            # 5-column table for CAP reduction
            gl_table_start = r"\begin{tabular}{@{}p{2.2in}rrrrr@{}}"
            gl_table_header = r"\textbf{Description} & \multicolumn{1}{c}{\textbf{Total}} & \multicolumn{1}{c}{\textbf{Your}} & \multicolumn{1}{c}{\textbf{CAP}} & \multicolumn{1}{c}{\textbf{Admin}} & \multicolumn{1}{c}{\textbf{Total}} \\\n & \multicolumn{1}{c}{\textbf{Amount}} & \multicolumn{1}{c}{\textbf{Share}} & \multicolumn{1}{c}{\textbf{Reduction}} & \multicolumn{1}{c}{\textbf{Fee}} &"
        else:
            # Standard 4-column table without CAP
            gl_table_start = r"\begin{tabular}{@{}p{2.2in}rrrr@{}}"
            gl_table_header = r"\textbf{Description} & \multicolumn{1}{c}{\textbf{Total Amount}} & \multicolumn{1}{c}{\textbf{Your Share}} & \multicolumn{1}{c}{\textbf{Admin Fee}} & \multicolumn{1}{c}{\textbf{Total}}"
        
        # Generate GL rows
        gl_rows = []
        for row in gl_details:
            description = escape_latex(row.get("description", ""))
            
            # Extract necessary values
            gl_amount = row.get("combined_gross", "0").strip('$').replace(',', '')
            tenant_gl_share = row.get("tenant_share_amount", "0").strip('$').replace(',', '')
            gl_admin_fee = row.get("admin_fee_amount", "0").strip('$').replace(',', '')
            gl_cap_impact = row.get("cap_impact", "0").strip('$').replace(',', '')
            
            # Skip rows with zero amounts
            if float(gl_amount) == 0:
                continue
            
            # Check if excluded from admin fee
            is_admin_excluded = False
            if "Excluded" in row.get("admin_fee_exclusion_rules", ""):
                is_admin_excluded = True
            
            # Check if excluded from CAP
            is_cap_excluded = False
            if "Excluded" in row.get("cap_exclusion_rules", ""):
                is_cap_excluded = True
            
            # For long descriptions, make them fit on one line
            if len(description) > 30:
                description = f"\\small{{{description}}}"
            
            # Format the row based on CAP application
            if cap_applied:
                if is_cap_excluded:
                    # For GL accounts excluded from CAP reduction
                    gl_rows.append(f"{description} & \\${format_currency(gl_amount, False)} & \\${format_currency(tenant_gl_share, False)} & \\textit{{Excluded}} & \\${format_currency(gl_admin_fee, False)} & \\${format_currency(float(tenant_gl_share) + float(gl_admin_fee), False)} \\\\")
                else:
                    # Standard GL with CAP reduction
                    gl_rows.append(f"{description} & \\${format_currency(gl_amount, False)} & \\${format_currency(tenant_gl_share, False)} & -\\${format_currency(gl_cap_impact, False)} & \\${format_currency(gl_admin_fee, False)} & \\${format_currency(float(tenant_gl_share) - float(gl_cap_impact) + float(gl_admin_fee), False)} \\\\")
            else:
                # Standard row format without CAP
                if is_admin_excluded:
                    # For GL accounts excluded from admin fee
                    gl_rows.append(f"{description} & \\${format_currency(gl_amount, False)} & \\${format_currency(tenant_gl_share, False)} & \\textit{{Excluded}} & \\${format_currency(tenant_gl_share, False)} \\\\")
                else:
                    # Normal GL accounts
                    gl_rows.append(f"{description} & \\${format_currency(gl_amount, False)} & \\${format_currency(tenant_gl_share, False)} & \\${format_currency(gl_admin_fee, False)} & \\${format_currency(float(tenant_gl_share) + float(gl_admin_fee), False)} \\\\")
        
        # Format total row from the TOTAL row in gl_details
        if gl_total_row:
            total_expenses = gl_total_row.get("combined_gross", "0").strip('$').replace(',', '')
            total_tenant_share = gl_total_row.get("tenant_share_amount", "0").strip('$').replace(',', '')
            total_admin_fee = gl_total_row.get("admin_fee_amount", "0").strip('$').replace(',', '')
            total_cap_impact = gl_total_row.get("cap_impact", "0").strip('$').replace(',', '')
            
            if cap_applied:
                # 5-column total with CAP reduction
                gl_total_row_str = f"\\textbf{{\\${format_currency(total_expenses, False)}}} & \\textbf{{\\${format_currency(total_tenant_share, False)}}} & \\textbf{{-\\${format_currency(total_cap_impact, False)}}} & \\textbf{{\\${format_currency(total_admin_fee, False)}}} & \\textbf{{\\${format_currency(year_due, False)}}} \\\\"
            else:
                # Standard 4-column total without CAP
                gl_total_row_str = f"\\textbf{{\\${format_currency(total_expenses, False)}}} & \\textbf{{\\${format_currency(total_tenant_share, False)}}} & \\textbf{{\\${format_currency(total_admin_fee, False)}}} & \\textbf{{\\${format_currency(year_due, False)}}} \\\\"
        else:
            # If no total row, use calculated values
            if cap_applied:
                gl_total_row_str = f"\\textbf{{\\${format_currency(property_total_expenses, False)}}} & \\textbf{{\\${format_currency(tenant_share, False)}}} & \\textbf{{-\\${format_currency(cap_reduction, False)}}} & \\textbf{{\\${format_currency(admin_fee, False)}}} & \\textbf{{\\${format_currency(year_due, False)}}} \\\\"
            else:
                gl_total_row_str = f"\\textbf{{\\${format_currency(property_total_expenses, False)}}} & \\textbf{{\\${format_currency(tenant_share, False)}}} & \\textbf{{\\${format_currency(admin_fee, False)}}} & \\textbf{{\\${format_currency(year_due, False)}}} \\\\"
        
        # Get the GL breakdown template and fill in the placeholders
        gl_template = get_gl_breakdown_template()
        gl_breakdown_section = gl_template.replace("$PROPERTY_NAME$", property_name_escaped)
        gl_breakdown_section = gl_breakdown_section.replace("$RECONCILIATION_YEAR$", reconciliation_year)
        gl_breakdown_section = gl_breakdown_section.replace("$CAP_NOTE$", cap_note)
        gl_breakdown_section = gl_breakdown_section.replace("$GL_TABLE_START$", gl_table_start)
        gl_breakdown_section = gl_breakdown_section.replace("$GL_TABLE_HEADER$", gl_table_header)
        gl_breakdown_section = gl_breakdown_section.replace("$GL_ROWS$", "\n".join(gl_rows))
        gl_breakdown_section = gl_breakdown_section.replace("$GL_TOTAL_ROW$", gl_total_row_str)
    
    # Generate amortization section if applicable
    amortization_section = ""
    has_amortization = tenant_data.get("amortization_exists", "false").lower() == "true"
    
    if has_amortization:
        # Get the number of amortization items
        amort_count = int(tenant_data.get("amortization_items_count", "0"))
        
        if amort_count > 0:
            # Create amortization rows
            amort_rows = []
            for i in range(1, amort_count + 1):
                # Get amortization item details
                description = escape_latex(tenant_data.get(f"amortization_{i}_description", ""))
                total_amount = tenant_data.get(f"amortization_{i}_total_amount", "0").strip('$').replace(',', '')
                years = tenant_data.get(f"amortization_{i}_years", "")
                annual_amount = tenant_data.get(f"amortization_{i}_annual_amount", "0").strip('$').replace(',', '')
                tenant_share = tenant_data.get(f"amortization_{i}_your_share", "0").strip('$').replace(',', '')
                
                # Calculate share percentage (tenant_share / annual_amount)
                share_pct = 0
                if float(annual_amount) > 0:
                    share_pct = (float(tenant_share) / float(annual_amount)) * 100
                
                # Add row
                amort_rows.append(f"{description} & \\${format_currency(total_amount, False)} & {years} & \\${format_currency(annual_amount, False)} & {format_currency(share_pct, False)}\\% & \\${format_currency(tenant_share, False)} \\\\")
            
            # Add total row if multiple items
            amort_total_row = ""
            if amort_count > 1:
                amort_total_row = r"\midrule" + "\n" + f"\\textbf{{TOTAL}} & & & & & \\textbf{{\\${format_currency(amortization_amount, False)}}} \\\\"
            
            # Get the amortization template and fill in the placeholders
            amort_template = get_amortization_template()
            amortization_section = amort_template.replace("$AMORTIZATION_ROWS$", "\n".join(amort_rows))
            amortization_section = amortization_section.replace("$AMORTIZATION_TOTAL$", amort_total_row)
    
    # Get the main letter template
    template = get_letter_template()
    
    # Replace placeholders in the template
    template = template.replace("$CONTACT_INFO$", CONTACT_INFO)
    template = template.replace("$DRAFT_WATERMARK$", "")
    template = template.replace("$DRAFT_HEADER$", "")
    template = template.replace("$PROPERTY_NAME$", property_name_escaped)
    template = template.replace("$RECONCILIATION_PERIOD$", reconciliation_period)
    template = template.replace("$TENANT_NAME$", tenant_name_escaped)
    template = template.replace("$RECONCILIATION_YEAR$", reconciliation_year)
    template = template.replace("$PROPERTY_TOTAL_EXPENSES$", format_currency(property_total_expenses, False))
    template = template.replace("$TENANT_PRO_RATA$", format_currency(tenant_pro_rata, False))
    template = template.replace("$TENANT_SHARE$", format_currency(tenant_share, False))
    template = template.replace("$BASE_YEAR_DEDUCTION$", base_year_deduction)
    template = template.replace("$CAP_REDUCTION_LINE$", cap_reduction_line)
    template = template.replace("$AMORTIZATION_LINE$", amortization_line)
    template = template.replace("$ADMIN_FEE_LINE$", admin_fee_line)
    template = template.replace("$YEAR_DUE$", format_currency(year_due, False))
    template = template.replace("$MAIN_PERIOD_PAID$", format_currency(main_period_paid, False))
    template = template.replace("$MAIN_PERIOD_BALANCE$", format_currency(main_period_balance, False))
    template = template.replace("$CATCHUP_PERIOD_LINE$", catchup_period_line)
    template = template.replace("$OVERRIDE_LINE$", override_line)
    template = template.replace("$GRAND_TOTAL$", format_currency(grand_total, False))
    template = template.replace("$CURRENT_MONTHLY_CHARGE$", format_currency(current_monthly_charge, False))
    template = template.replace("$NEW_MONTHLY_CHARGE$", format_currency(new_monthly_charge, False))
    template = template.replace("$MONTHLY_DIFF$", format_currency(monthly_diff, False))
    template = template.replace("$EFFECTIVE_DATE$", effective_date)
    template = template.replace("$GL_BREAKDOWN_SECTION$", gl_breakdown_section)
    template = template.replace("$AMORTIZATION_SECTION$", amortization_section)
    
    return template, str(pdf_path), str(tex_path)

def main():
    """Test the LaTeX letter generator with a sample tenant."""
    import sys
    import os
    from pathlib import Path
    
    # Create a simple tenant data dictionary for testing
    sample_tenant = {
        "tenant_id": "1234",
        "tenant_name": "Sample Tenant, LLC",
        "property_id": "WAT",
        "property_name": "Main Portfolio",
        "property_full_name": "Watchung",
        "share_percentage": "5.1234%",
        "property_gl_total": "$173,638.08",
        "cam_net_total": "$173,028.49",
        "admin_fee_percentage": "10.00%",
        "admin_fee_net": "$1,730.28",
        "base_year_adjustment": "$0.00",
        "cap_deduction": "$0.00",
        "tenant_share_amount": "$8,866.61",
        "amortization_total_amount": "$0.00",
        "reconciliation_paid": "$7,200.00",
        "reconciliation_balance": "$1,666.61",
        "catchup_balance": "$555.53",
        "total_balance": "$2,222.14",
        "override_amount": "$0.00",
        "override_description": "",
        "has_override": "false",
        "old_monthly": "$600.00",
        "new_monthly": "$738.88",
        "monthly_difference": "$138.88",
        "reconciliation_start_date": "2024-01-01",
        "reconciliation_end_date": "2024-12-31",
        "catchup_start_date": "2025-01-01",
        "catchup_end_date": "2025-04-30",
        "monthly_charge_effective_date": "2025-06-01",
        "amortization_exists": "false"
    }
    
    # Temporarily change the LETTERS_DIR
    old_letters_dir = None
    if 'letter_generator' in sys.modules:
        if hasattr(sys.modules['letter_generator'], 'LETTERS_DIR'):
            old_letters_dir = sys.modules['letter_generator'].LETTERS_DIR
            sys.modules['letter_generator'].LETTERS_DIR = Path("Letters/Test")
    
    try:
        print("Generating test LaTeX letter...")
        latex_content, pdf_path, tex_path = generate_latex_letter(sample_tenant, None, debug_mode=True)
        
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
        # Restore the original LETTERS_DIR
        if 'letter_generator' in sys.modules and old_letters_dir:
            sys.modules['letter_generator'].LETTERS_DIR = old_letters_dir
    
    print("\nTest complete. You can now add these functions to letter_generator.py.")

if __name__ == "__main__":
    main()