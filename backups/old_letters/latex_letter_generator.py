#!/usr/bin/env python3
"""
LaTeX Letter Generator for CAM Reconciliation

This module provides letter generation functionality for CAM reconciliation results
with LaTeX and PDF output capabilities.
"""

import os
import csv
import re
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# ========== CONFIGURATION ==========

# Output directory structure
LETTERS_DIR = Path("Letters")

# Property name mapping
PROPERTY_NAMES = {
    "WAT": "Watchung",
    "CTR": "Plainview Center",
    "BOO": "Cinemark Boonton",
    "HYL": "Hylan Plaza",
    "ELW": "East Northport",
    "UKA": "Union City"
}

# Contact information for footer
CONTACT_INFO = "For questions, please contact Evelyn Diaz at (201) 871-8800 x210 or ediaz@treecocenters.com"

# ========== UTILITY FUNCTIONS ==========

def format_currency(amount: Any, include_dollar_sign: bool = True) -> str:
    """Format value as currency with $ sign and commas."""
    try:
        # Convert to float to handle various input types
        value = float(str(amount).strip('$').replace(',', ''))
        if include_dollar_sign:
            return f"${value:,.2f}"
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        if include_dollar_sign:
            return "$0.00"
        return "0.00"


def format_percentage(value: Any, precision: int = 2) -> str:
    """Format value as percentage with specified precision."""
    try:
        # Convert to float and handle percentage conversion
        value_str = str(value).strip('%')
        value = float(value_str)
        # If value is already in decimal form (e.g. 0.0514 for 5.14%)
        if value < 1:
            value = value * 100
        return f"{value:.{precision}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in text."""
    if not text:
        return ""
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}'
    }
    return ''.join(replacements.get(c, c) for c in str(text))


def format_date_range(start_date: str, end_date: str) -> str:
    """Format date range (e.g., Jan-Dec 2024)."""
    if not start_date or not end_date:
        return ""
    
    try:
        # Try to parse dates in YYYY-MM-DD format
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        
        # Get month abbreviations
        start_month = start.strftime("%b")
        end_month = end.strftime("%b")
        
        # If range is full year
        if (start.month == 1 and start.day == 1 and 
            end.month == 12 and end.day == 31 and 
            start.year == end.year):
            return f"Jan-Dec {start.year}"
        
        # If same year but not full year
        if start.year == end.year:
            return f"{start_month}-{end_month} {start.year}"
        
        # Different years
        return f"{start_month} {start.year}-{end_month} {end.year}"
    except ValueError:
        # Fallback to original strings
        return f"{start_date} to {end_date}"


def extract_year_from_date(date_str: str) -> str:
    """Extract year from date string."""
    if not date_str:
        return ""
    
    # Try to parse YYYY-MM-DD
    match = re.search(r'(\d{4})-\d{2}-\d{2}', date_str)
    if match:
        return match.group(1)
    
    # Check if year is already in string
    year_match = re.search(r'\b(20\d{2})\b', date_str)
    if year_match:
        return year_match.group(1)
    
    return ""


def compile_to_pdf(latex_content: str, output_file: str) -> bool:
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


# ========== DATA READING FUNCTIONS ==========

def read_csv_file(file_path: str) -> List[Dict[str, str]]:
    """Read a CSV file and return a list of dictionaries."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading CSV file {file_path}: {str(e)}")
        return []


def get_gl_details_for_tenant(gl_detail_file: str) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """Read GL details from a specific GL detail file."""
    try:
        gl_details = read_csv_file(gl_detail_file)
        # Filter to remove the TOTAL row for processing individual rows
        tenant_gl_details = [row for row in gl_details if row.get('gl_account') != 'TOTAL']
        
        # Separately get the TOTAL row
        total_row = next((row for row in gl_details if row.get('gl_account') == 'TOTAL'), {})
        
        return tenant_gl_details, total_row
    except Exception as e:
        print(f"Error getting GL details from file {gl_detail_file}: {str(e)}")
        return [], {}


# ========== LETTER TEMPLATES ==========

def get_letter_template() -> str:
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
Total Property CAM Expenses ($RECONCILIATION_YEAR$) & \$$PROPERTY_TOTAL_EXPENSES$ \\
Tenant's Pro-Rata Share ($TENANT_PRO_RATA$\%) & \$$TENANT_SHARE$ \\
$BASE_YEAR_DEDUCTION$
$CAP_REDUCTION_LINE$
$AMORTIZATION_LINE$
$ADMIN_FEE_LINE$
\midrule
Total Due for Year & \$$YEAR_DUE$ \\
Previously Billed ($RECONCILIATION_YEAR$) & \$$MAIN_PERIOD_PAID$ \\
\midrule
$RECONCILIATION_YEAR$ Reconciliation Amount & \$$MAIN_PERIOD_BALANCE$ \\
$CATCHUP_PERIOD_LINE$
$OVERRIDE_LINE$
\midrule
\textbf{ADDITIONAL AMOUNT DUE} & \textbf{\$$GRAND_TOTAL$} \\
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
Current Monthly Charge & \$$CURRENT_MONTHLY_CHARGE$ \\
New Monthly Charge & \$$NEW_MONTHLY_CHARGE$ \\
Difference per Month & \$$MONTHLY_DIFF$ \\
\bottomrule
\end{tabular}
\end{center}

\vspace{0.5em}
\hspace{1in}The new monthly charge will be effective starting $EFFECTIVE_DATE$.

\vfill % Space at the bottom

$GL_BREAKDOWN_SECTION$

$AMORTIZATION_SECTION$

\end{document}"""


def get_gl_breakdown_template() -> str:
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


def get_amortization_template() -> str:
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


# ========== LETTER GENERATION ==========

def generate_tenant_letter(tenant_data: Dict[str, str], gl_detail_file: str, debug_mode: bool = False) -> Tuple[str, str, str]:
    """
    Generate a LaTeX letter for a tenant.
    
    Args:
        tenant_data: Dictionary with tenant billing data
        gl_detail_file: Path to the GL detail file for this tenant
        debug_mode: Whether to print debug information
        
    Returns:
        Tuple of (latex_content, pdf_path, tex_path)
    """
    if debug_mode:
        print(f"Generating letter for tenant {tenant_data.get('tenant_id')} - {tenant_data.get('tenant_name')}")
    
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
            gl_table_header = r"\textbf{Description} & \multicolumn{1}{c}{\textbf{Total}} & \multicolumn{1}{c}{\textbf{Your}} & \multicolumn{1}{c}{\textbf{CAP}} & \multicolumn{1}{c}{\textbf{Admin}} & \multicolumn{1}{c}{\textbf{Total}} \\\n & \multicolumn{1}{c}{\textbf{Amount}} & \multicolumn{1}{c}{\textbf{Share}} & \multicolumn{1}{c}{\textbf{Reduction}} & \multicolumn{1}{c}{\textbf{Fee}} & \\"
        else:
            # Standard 4-column table without CAP
            gl_table_start = r"\begin{tabular}{@{}p{2.2in}rrrr@{}}"
            gl_table_header = r"\textbf{Description} & \multicolumn{1}{c}{\textbf{Total Amount}} & \multicolumn{1}{c}{\textbf{Your Share}} & \multicolumn{1}{c}{\textbf{Admin Fee}} & \multicolumn{1}{c}{\textbf{Total}} \\"
        
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
    # Replace placeholders with properly formatted values
    # NOTE: LaTeX needs a backslash before the dollar sign: \$
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
    
    # Fix common LaTeX issues - make sure we don't have double dollar signs
    template = template.replace(r"\$$", r"\$")
    template = template.replace(r"& \$$", r"& \$")
    template = template.replace("$EFFECTIVE_DATE$", effective_date)
    template = template.replace("$GL_BREAKDOWN_SECTION$", gl_breakdown_section)
    template = template.replace("$AMORTIZATION_SECTION$", amortization_section)
    
    return template, str(pdf_path), str(tex_path)


def generate_letters_from_results(results_dict: Dict[str, Any]) -> Tuple[int, int]:
    """
    Generate letters directly from reconciliation results dictionary.
    This is the function that will be called from New Full.py.
    
    Args:
        results_dict: Dictionary with reconciliation results
        
    Returns:
        Tuple of (success_count, total_count)
    """
    print("\nGenerating tenant letters from reconciliation results...")

    # Extract the necessary paths
    csv_report_path = results_dict.get('csv_report_path', '')
    gl_detail_reports = results_dict.get('gl_detail_reports', [])
    
    # Create a map of tenant IDs to their GL detail reports
    tenant_gl_map = {}
    for gl_path in gl_detail_reports:
        # Extract tenant ID from the filename
        filename = os.path.basename(gl_path)
        match = re.search(r'GL_detail_(\d+)_', filename)
        if match:
            tenant_id = match.group(1)
            tenant_gl_map[tenant_id] = gl_path
    
    # Read the tenant data from the CSV
    tenant_data = read_csv_file(csv_report_path)
    
    if not tenant_data:
        print(f"Error: No tenant data found in {csv_report_path}")
        return 0, 0
    
    print(f"Generating letters for {len(tenant_data)} tenants...")
    
    # Create letters directory
    LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track results
    successful = 0
    total = len(tenant_data)
    
    # Generate a letter for each tenant
    for tenant in tenant_data:
        tenant_id = tenant.get("tenant_id")
        tenant_name = tenant.get("tenant_name", "")
        
        print(f"Processing tenant {tenant_id} ({tenant_name})...")
        
        # Get the GL detail file for this tenant
        gl_detail_file = tenant_gl_map.get(tenant_id)
        
        try:
            # Generate letter
            latex_content, pdf_path, tex_path = generate_tenant_letter(tenant, gl_detail_file, debug_mode=True)
            
            # Write LaTeX content to file
            os.makedirs(os.path.dirname(tex_path), exist_ok=True)
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            print(f"  LaTeX letter written to: {tex_path}")
            
            # Compile to PDF
            if compile_to_pdf(latex_content, pdf_path):
                successful += 1
                print(f"  ✅ Letter generated successfully for tenant {tenant_id}")
            else:
                print(f"  ❌ Failed to compile PDF for tenant {tenant_id}")
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
    
    print(f"\nLetter generation complete: {successful} of {total} letters generated successfully")
    print(f"Letters are saved in: {LETTERS_DIR}")
    
    return successful, total


# For standalone script usage
def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CAM reconciliation letters for tenants')
    parser.add_argument('--billing', type=str, required=True, help='Path to tenant billing CSV file')
    parser.add_argument('--gl_dir', type=str, required=True, help='Directory containing GL detail CSV files')
    
    args = parser.parse_args()
    
    # For standalone use, read CSV and find GL files
    tenant_data = read_csv_file(args.billing)
    
    # Create a map of tenant IDs to GL detail files
    tenant_gl_map = {}
    for filename in os.listdir(args.gl_dir):
        match = re.search(r'GL_detail_(\d+)_', filename)
        if match:
            tenant_id = match.group(1)
            tenant_gl_map[tenant_id] = os.path.join(args.gl_dir, filename)
    
    # Track results
    successful = 0
    total = len(tenant_data)
    
    # Generate letters
    for tenant in tenant_data:
        tenant_id = tenant.get("tenant_id")
        gl_file = tenant_gl_map.get(tenant_id)
        
        try:
            latex_content, pdf_path, tex_path = generate_tenant_letter(tenant, gl_file, debug_mode=True)
            
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            print(f"  LaTeX content saved to: {tex_path}")
            
            if compile_to_pdf(latex_content, pdf_path):
                successful += 1
                print(f"  ✅ Letter generated successfully for tenant {tenant_id}")
            else:
                print(f"  ❌ Failed to compile PDF for tenant {tenant_id}")
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
    
    print(f"Letter generation complete: {successful} of {total} letters generated successfully")
    return successful, total


if __name__ == "__main__":
    main()