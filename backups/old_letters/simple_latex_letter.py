#!/usr/bin/env python3
"""
Simplified LaTeX letter generator for CAM reconciliation.
"""

import os
import csv
import re
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple

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

def format_currency(amount):
    """Format amount as currency without $ sign."""
    try:
        value = float(str(amount).strip('$').replace(',', ''))
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"

def format_date_range(start_date, end_date):
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

def extract_year_from_date(date_str):
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

def read_csv_file(file_path):
    """Read a CSV file and return a list of dictionaries."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading CSV file {file_path}: {str(e)}")
        return []

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

def escape_latex(text):
    """Escape LaTeX special characters."""
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

def generate_tenant_letter(tenant_data, gl_detail_file=None, debug_mode=False):
    """Generate a LaTeX letter for a tenant."""
    if debug_mode:
        print(f"Generating letter for tenant {tenant_data.get('tenant_id')} - {tenant_data.get('tenant_name')}")
    
    # Extract tenant basic info
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = escape_latex(tenant_data.get("tenant_name", ""))
    property_id = tenant_data.get("property_id", "")
    property_name = escape_latex(tenant_data.get("property_full_name", PROPERTY_NAMES.get(property_id, property_id)))
    
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
    
    # Extract financial values
    property_total = format_currency(tenant_data.get("property_gl_total", "0"))
    tenant_pro_rata = tenant_data.get("share_percentage", "0").strip('%')
    tenant_share = format_currency(tenant_data.get("tenant_share_amount", "0"))
    base_year_amount = format_currency(tenant_data.get("base_year_adjustment", "0"))
    cap_reduction = format_currency(tenant_data.get("cap_deduction", "0"))
    admin_fee = format_currency(tenant_data.get("admin_fee_net", "0"))
    amortization_amount = format_currency(tenant_data.get("amortization_total_amount", "0"))
    
    # Get billing details
    year_due = format_currency(tenant_data.get("subtotal_after_tenant_share", "0"))
    main_period_paid = format_currency(tenant_data.get("reconciliation_paid", "0"))
    main_period_balance = format_currency(tenant_data.get("reconciliation_balance", "0"))
    catchup_balance = format_currency(tenant_data.get("catchup_balance", "0"))
    
    # Get override info
    has_override = tenant_data.get("has_override", "false").lower() == "true"
    override_amount = format_currency(tenant_data.get("override_amount", "0"))
    override_description = escape_latex(tenant_data.get("override_description", "Manual Adjustment"))
    
    # Get total final amount
    grand_total = format_currency(tenant_data.get("total_balance", "0"))
    
    # Get monthly charge info
    current_monthly = format_currency(tenant_data.get("old_monthly", "0"))
    new_monthly = format_currency(tenant_data.get("new_monthly", "0"))
    monthly_diff = format_currency(tenant_data.get("monthly_difference", "0"))
    
    # Get effective date
    effective_date = tenant_data.get("monthly_charge_effective_date", "")
    if effective_date:
        try:
            date_obj = datetime.datetime.strptime(effective_date, "%Y-%m-%d")
            effective_date = date_obj.strftime("%b %d, %Y")
        except ValueError:
            pass
    else:
        today = datetime.datetime.now()
        next_month = today.replace(day=1)
        if today.month == 12:
            next_month = next_month.replace(year=today.year + 1, month=1)
        else:
            next_month = next_month.replace(month=today.month + 1)
        effective_date = next_month.strftime("%b %d, %Y")
    
    # Prepare conditional lines
    has_base_year = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '')) > 0
    has_cap = float(tenant_data.get("cap_deduction", "0").strip('$').replace(',', '')) > 0
    has_amortization = float(tenant_data.get("amortization_total_amount", "0").strip('$').replace(',', '')) > 0
    has_admin_fee = float(tenant_data.get("admin_fee_net", "0").strip('$').replace(',', '')) > 0
    has_catchup = float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', '')) != 0
    has_override = has_override and float(tenant_data.get("override_amount", "0").strip('$').replace(',', '')) != 0
    
    # Build the LaTeX document with proper escaping
    document = f"""\\documentclass{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{booktabs}}
\\usepackage{{longtable}}
\\usepackage{{array}}
\\usepackage{{xcolor}}
\\usepackage{{fancyhdr}}

% Set up fancy headers/footers
\\pagestyle{{fancy}}
\\fancyhf{{}} % Clear all headers/footers
\\renewcommand{{\\footrulewidth}}{{0.4pt}}
\\fancyfoot[C]{{{CONTACT_INFO}}}

\\begin{{document}}

\\begin{{center}}
\\Large\\textbf{{CAM Reconciliation - {property_name}}}

\\normalsize
\\textbf{{Reconciliation Period: {reconciliation_period}}}
\\end{{center}}

\\begin{{center}}
\\textbf{{{tenant_name}}}
\\end{{center}}

\\vspace{{1em}}

\\begin{{center}}
\\begin{{tabular}}{{@{{}}p{{3.2in}}r@{{}}}}
\\toprule
\\textbf{{Description}} & \\textbf{{Amount}} \\\\
\\midrule
Total Property CAM Expenses ({reconciliation_year}) & \\${property_total} \\\\
Tenant's Pro-Rata Share ({tenant_pro_rata}\\%) & \\${tenant_share} \\\\
"""

    # Add conditional lines
    if has_base_year:
        document += f"Base Year Deduction & -\\${base_year_amount} \\\\\n"
    if has_cap:
        document += f"Cap Reduction & -\\${cap_reduction} \\\\\n"
    if has_amortization:
        document += f"Amortization & \\${amortization_amount} \\\\\n"
    if has_admin_fee:
        document += f"Admin Fee & \\${admin_fee} \\\\\n"

    document += f"""\\midrule
Total Due for Year & \\${year_due} \\\\
Previously Billed ({reconciliation_year}) & \\${main_period_paid} \\\\
\\midrule
{reconciliation_year} Reconciliation Amount & \\${main_period_balance} \\\\
"""

    # Add catchup and override lines if needed
    if has_catchup:
        document += f"{catchup_period_range} Catchup Period & \\${catchup_balance} \\\\\n"
    if has_override:
        # Negative amounts need special handling
        if override_amount.startswith('-'):
            override_value = override_amount[1:]  # Remove the negative sign
            document += f"{override_description} & -\\${override_value} \\\\\n"
        else:
            document += f"{override_description} & \\${override_amount} \\\\\n"

    document += f"""\\midrule
\\textbf{{ADDITIONAL AMOUNT DUE}} & \\textbf{{\\${grand_total}}} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\vspace{{0.5em}}
\\hspace{{1in}}Please remit the amount shown above within 30 days.

\\vspace{{1em}}
\\begin{{center}}
\\Large\\textbf{{Monthly Charge Update}}
\\end{{center}}

\\begin{{center}}
\\begin{{tabular}}{{@{{}}p{{3.2in}}r@{{}}}}
\\toprule
Current Monthly Charge & \\${current_monthly} \\\\
New Monthly Charge & \\${new_monthly} \\\\
Difference per Month & \\${monthly_diff} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\vspace{{0.5em}}
\\hspace{{1in}}The new monthly charge will be effective starting {effective_date}.

\\vfill % Space at the bottom

\\newpage

\\begin{{center}}
\\Large\\textbf{{CAM Expense Breakdown}}

\\normalsize
\\textbf{{{property_name} - {reconciliation_year}}}
\\end{{center}}


\\begin{{center}}
\\begin{{tabular}}{{@{{}}p{{2.2in}}rrrr@{{}}}}
\\toprule
\\textbf{{Description}} & \\multicolumn{{1}}{{c}}{{\\textbf{{Total Amount}}}} & \\multicolumn{{1}}{{c}}{{\\textbf{{Your Share}}}} & \\multicolumn{{1}}{{c}}{{\\textbf{{Admin Fee}}}} & \\multicolumn{{1}}{{c}}{{\\textbf{{Total}}}} \\\\
\\midrule
 & \\${property_total} & \\${tenant_share} & \\$0.00 & \\${tenant_share} \\\\
\\midrule
\\textbf{{TOTAL}} & \\textbf{{\\${property_total}}} & \\textbf{{\\${tenant_share}}} & \\textbf{{\\$0.00}} & \\textbf{{\\${tenant_share}}} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\end{{document}}
"""

    # Compile to PDF
    compile_success = compile_to_pdf(document, str(pdf_path))
    
    return compile_success, str(pdf_path), str(tex_path)

def generate_letters_from_results(results_dict):
    """Generate letters from reconciliation results."""
    print("\nGenerating tenant letters from reconciliation results...")

    # Extract the necessary paths
    csv_report_path = results_dict.get('csv_report_path', '')
    
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
        
        try:
            # Generate letter
            success, pdf_path, tex_path = generate_tenant_letter(tenant, debug_mode=True)
            
            if success:
                successful += 1
                print(f"  ✅ Letter generated successfully for tenant {tenant_id}")
            else:
                print(f"  ❌ Failed to compile PDF for tenant {tenant_id}")
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
    
    print(f"\nLetter generation complete: {successful} of {total} letters generated successfully")
    print(f"Letters are saved in: {LETTERS_DIR}")
    
    return successful, total

def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CAM reconciliation letters with LaTeX')
    parser.add_argument('--csv', type=str, required=True, help='Path to reconciliation CSV file')
    
    args = parser.parse_args()
    
    # For standalone use
    results_dict = {'csv_report_path': args.csv}
    
    successful, total = generate_letters_from_results(results_dict)
    return successful, total

if __name__ == "__main__":
    main()