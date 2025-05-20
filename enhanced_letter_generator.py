#!/usr/bin/env python3
"""
Enhanced LaTeX letter generator for CAM reconciliation.
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
# Use absolute path to ensure consistency regardless of working directory
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LETTERS_DIR = SCRIPT_DIR / "Letters"

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
        if isinstance(amount, str):
            # Check if this is a non-numeric value that shouldn't be formatted
            if amount.strip() and not any(c.isdigit() or c in '.-$,' for c in amount):
                return "0.00"  # Return default for non-numeric text values
            
            # Remove any existing formatting
            value = float(amount.strip('$').replace(',', ''))
        else:
            value = float(amount)
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"

def format_percentage(value, precision=2):
    """Format value as percentage."""
    try:
        if isinstance(value, str):
            # Check if this is a non-numeric value that shouldn't be formatted
            if value.strip() and not any(c.isdigit() or c in '.-$%,' for c in value):
                return "0.00"  # Return default for non-numeric text values
                
            # Remove % sign if present
            value = float(value.strip('%'))
        else:
            value = float(value)
        # If value is in decimal form (e.g., 0.0514 for 5.14%)
        if value < 1:
            value = value * 100
        return f"{value:.{precision}f}"
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

def get_gl_details_for_tenant(gl_detail_file):
    """Read GL details from a specific GL detail file."""
    try:
        gl_details = read_csv_file(gl_detail_file)
        print(f"DEBUG [GL file]: Reading GL details from {gl_detail_file}")
        print(f"DEBUG [GL file]: Found {len(gl_details)} rows in GL detail file")
        
        if not gl_details:
            print(f"DEBUG [GL file]: No rows found in {gl_detail_file}")
            return [], {}
        
        print(f"DEBUG [GL file]: Column headers: {', '.join(gl_details[0].keys()) if gl_details else 'No columns found'}")
        
        # Print sample of what's in the description field
        if gl_details:
            for i, row in enumerate(gl_details[:3]):  # First 3 rows
                print(f"DEBUG [GL file]: Sample row {i+1} - GL account: '{row.get('gl_account', '')}', Description: '{row.get('description', '')}'")        
        
        # First, capture the TOTAL row separately before filtering
        # This ensures we always have access to the TOTAL row even if it's in the NEGATIVE BALANCE section
        total_row = next((row for row in gl_details if row.get('gl_account', '').upper() == 'TOTAL'), {})
        if total_row:
            print(f"DEBUG [GL file]: Found TOTAL row before filtering: '{total_row.get('gl_account', '')}'")
        
        # Filter out any special rows (FORMULA EXPLANATIONS, NEGATIVE BALANCE section)
        filtered_gl_details = []
        formula_explanation_row = None
        negative_balance_header = None
        in_negative_balance_section = False
        
        for row in gl_details:
            gl_account = row.get('gl_account', '')
            description = row.get('description', '')
            exclusion_categories = row.get('exclusion_categories', '')
            
            # Don't skip the TOTAL row regardless of where it is
            if gl_account.upper() == 'TOTAL':
                print(f"DEBUG [GL file]: Keeping TOTAL row in filtered details")
                if not total_row:  # If we didn't capture it earlier
                    total_row = row
                continue  # Skip adding to filtered_gl_details as we've already captured it
            
            # Track if we're in the negative balance section
            if "--- NEGATIVE BALANCE ACCOUNTS" in gl_account:
                in_negative_balance_section = True
                negative_balance_header = row
                print(f"DEBUG [GL file]: Found NEGATIVE BALANCE ACCOUNTS header: '{gl_account}'")
                continue
            
            # Capture the formula explanation row for reference
            if gl_account == "FORMULA EXPLANATIONS:":
                formula_explanation_row = row
                print(f"DEBUG [GL file]: Found FORMULA EXPLANATIONS row: '{gl_account}'")
                continue
                
            # Check for any rows with "Direct value" in combined_gross (formula explanations)
            if row.get('combined_gross', '') == 'Direct value':
                print(f"DEBUG [GL file]: Skipping row with 'Direct value' in combined_gross: '{gl_account}'")
                continue
                
            # Skip rows with "NEGATIVE BALANCE" exclusion category
            if exclusion_categories == "NEGATIVE BALANCE" or in_negative_balance_section:
                print(f"DEBUG [GL file]: Skipping NEGATIVE BALANCE row: '{gl_account}'")
                continue
                
            # Skip any non-numeric amounts
            combined_gross = row.get('combined_gross', '0')
            if isinstance(combined_gross, str) and combined_gross.strip() and not any(c.isdigit() or c in '.-$,' for c in combined_gross):
                print(f"DEBUG [GL file]: Skipping row with non-numeric combined_gross: '{combined_gross}'")
                continue
                
            filtered_gl_details.append(row)
        
        # All detail rows (excluding TOTAL)
        tenant_gl_details = filtered_gl_details
        
        # If we still don't have a total row, try to find one with 'total' in description
        if not total_row and filtered_gl_details:
            total_row = next((row for row in filtered_gl_details if 'total' in str(row.get('description', '')).lower()), {})
        
        # If no TOTAL row found, look for any row that might be a summary
        if not total_row and filtered_gl_details:
            # Check for a row with 'Total' or 'total' in description or gl_account
            total_row = next((row for row in filtered_gl_details if 'total' in str(row.get('description', '')).lower() or 
                             'total' in str(row.get('gl_account', '')).lower()), {})
            
        print(f"DEBUG [GL file]: Filtered to {len(tenant_gl_details)} non-TOTAL rows")
        print(f"DEBUG [GL file]: Total row found: {bool(total_row)}")
        
        # Filter to only rows with actual amounts
        rows_with_amounts = []
        for row in tenant_gl_details:
            combined_gross = row.get('combined_gross', '0')
            # Skip rows that are marked with Direct value which aren't actual data
            if row.get('combined_gross', '') == 'Direct value':
                print(f"DEBUG [GL file]: Skipping row with 'Direct value': {row.get('gl_account', '')}")
                continue
                
            # Convert to Decimal, handling formatting
            try:
                if isinstance(combined_gross, str):
                    # Skip non-numeric values
                    if combined_gross.strip() and not any(c.isdigit() or c in '.-$,' for c in combined_gross):
                        print(f"DEBUG [GL file]: Skipping row with non-numeric value: {combined_gross}")
                        continue
                        
                    combined_gross = combined_gross.replace('$', '').replace(',', '')
                amount = float(combined_gross)
                if amount != 0:
                    rows_with_amounts.append(row)
            except (ValueError, TypeError):
                print(f"DEBUG [GL file]: Skipping row with non-parseable amount: {combined_gross}")
                continue
        
        print(f"DEBUG [GL file]: Found {len(rows_with_amounts)} rows with non-zero amounts")
        
        return rows_with_amounts, total_row
    except Exception as e:
        print(f"Error getting GL details from file {gl_detail_file}: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], {}

def compile_to_pdf(latex_content, output_file, tex_file=None):
    """Compile LaTeX content to PDF using texlive.net online service."""
    try:
        # Create parent directories
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Save LaTeX content to file (in the LaTeX directory)
        if tex_file is None:
            # Default behavior for backward compatibility
            tex_file = output_file.replace('.pdf', '.tex')
        
        # Ensure the directory for the tex file exists
        Path(tex_file).parent.mkdir(parents=True, exist_ok=True)
        
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

def find_gl_detail_file(tenant_id, gl_detail_dir):
    """Find the MOST RECENT GL detail file for a specific tenant."""
    if not gl_detail_dir or not os.path.exists(gl_detail_dir):
        print(f"DEBUG [find_gl]: GL detail directory does not exist: {gl_detail_dir}")
        return None
    
    print(f"DEBUG [find_gl]: Looking for GL detail files for tenant {tenant_id} in {gl_detail_dir}")
    matching_files = []
    
    # Look for GL detail file with pattern GL_detail_{tenant_id}_*
    try:
        for filename in os.listdir(gl_detail_dir):
            if filename.startswith(f"GL_detail_{tenant_id}_") and filename.endswith(".csv"):
                matching_files.append(filename)
                print(f"DEBUG [find_gl]: Found matching file: {filename}")
    except Exception as e:
        print(f"DEBUG [find_gl]: Error listing directory {gl_detail_dir}: {str(e)}")
        return None
    
    if matching_files:
        # Sort files by timestamp in filename (most recent last)
        # The format is GL_detail_{tenant_id}_{recon_year}_{timestamp}.csv
        # where timestamp is in format YYYYMMDD_HHMMSS
        try:
            # Extract timestamp from filename and sort
            def extract_timestamp(filename):
                # Split by underscore and get the parts after "GL_detail_{tenant_id}_{recon_year}_"
                parts = filename.replace('.csv', '').split('_')
                if len(parts) >= 5:  # GL_detail_TENANT_YEAR_DATE_TIME
                    return parts[-2] + parts[-1]  # Concatenate date and time parts
                return filename  # Fallback to filename if format doesn't match
            
            matching_files.sort(key=extract_timestamp)
        except Exception as e:
            print(f"DEBUG [find_gl]: Error sorting by timestamp, using fallback sort: {str(e)}")
            # Fallback: sort by modification time
            matching_files.sort(key=lambda f: os.path.getmtime(os.path.join(gl_detail_dir, f)))
        
        # Select the most recent file (last after sorting)
        most_recent_file = matching_files[-1]
        selected_file = os.path.join(gl_detail_dir, most_recent_file)
        print(f"DEBUG [find_gl]: Found {len(matching_files)} matching GL detail files")
        print(f"DEBUG [find_gl]: Selected MOST RECENT file: {selected_file}")
        return selected_file
    else:
        # As a last resort, try to find any GL file containing this tenant_id
        print(f"DEBUG [find_gl]: No matching GL detail file found with standard pattern, trying broader search")
        all_csv_files = []
        try:
            for filename in os.listdir(gl_detail_dir):
                if filename.endswith(".csv") and tenant_id in filename:
                    all_csv_files.append(filename)
                    print(f"DEBUG [find_gl]: Found potential GL file: {filename}")
        except Exception as e:
            print(f"DEBUG [find_gl]: Error in broader file search: {str(e)}")
            return None
            
        if all_csv_files:
            # Sort files by modification time
            all_csv_files.sort(key=lambda f: os.path.getmtime(os.path.join(gl_detail_dir, f)))
            most_recent_file = all_csv_files[-1]
            selected_file = os.path.join(gl_detail_dir, most_recent_file)
            print(f"DEBUG [find_gl]: Selected file from broader search: {selected_file}")
            return selected_file
        else:
            print(f"DEBUG [find_gl]: No GL detail file found for tenant {tenant_id}")
            return None

def generate_tenant_letter(tenant_data, gl_detail_dir=None, debug_mode=False):
    """Generate a LaTeX letter for a tenant."""
    tenant_id = tenant_data.get("tenant_id", "")
    tenant_name = tenant_data.get("tenant_name", "")
    
    # Skip special rows that aren't real tenants
    # Skip formula explanations rows
    if tenant_id == "FORMULA EXPLANATIONS:" or "FORMULA EXPLANATIONS" in tenant_name:
        print(f"  Skipping special entry: {tenant_id} - {tenant_name}")
        return False, "", ""
        
    # Skip rows with "Direct value" which are explanations, not data
    if tenant_id == "Direct value" or tenant_name == "Direct value":
        print(f"  Skipping Direct value entry: {tenant_id} - {tenant_name}")
        return False, "", ""
        
    # Skip negative balance rows
    if "NEGATIVE BALANCE" in tenant_id or "NEGATIVE BALANCE" in tenant_name:
        print(f"  Skipping negative balance entry: {tenant_id} - {tenant_name}")
        return False, "", ""
    
    if debug_mode:
        print(f"Generating letter for tenant {tenant_id} - {tenant_name}")
    
    # Always print GL detail directory information
    print(f"DEBUG [generate_tenant_letter]: GL detail directory for tenant {tenant_id}: {gl_detail_dir}")
    if gl_detail_dir and os.path.exists(gl_detail_dir):
        print(f"DEBUG [generate_tenant_letter]: GL directory exists")
        # Check if there are any CSV files in this directory
        csv_files = [f for f in os.listdir(gl_detail_dir) if f.endswith('.csv')]
        print(f"DEBUG [generate_tenant_letter]: Found {len(csv_files)} CSV files in GL directory")
        if csv_files:
            print(f"DEBUG [generate_tenant_letter]: First few CSV files: {', '.join(csv_files[:3])}")
    
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
    
    # Extract financial values - using cam_net_total instead of property_gl_total as per field mapping
    property_total = format_currency(tenant_data.get("cam_net_total", tenant_data.get("property_gl_total", "0")))
    tenant_pro_rata = format_percentage(tenant_data.get("share_percentage", "0"))
    # tenant_share is calculated based on subtotal_after_tenant_share as per field mapping if available
    tenant_share = format_currency(tenant_data.get("subtotal_after_tenant_share", tenant_data.get("tenant_share_amount", "0")))
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
    has_base_year = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '') or 0) > 0
    has_cap = float(tenant_data.get("cap_deduction", "0").strip('$').replace(',', '') or 0) > 0
    has_amortization = float(tenant_data.get("amortization_total_amount", "0").strip('$').replace(',', '') or 0) > 0
    has_admin_fee = float(tenant_data.get("admin_fee_net", "0").strip('$').replace(',', '') or 0) > 0
    has_catchup = float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', '') or 0) != 0
    has_override = has_override and float(tenant_data.get("override_amount", "0").strip('$').replace(',', '') or 0) != 0
    
    # Check if we need to include the GL breakdown
    gl_details = []
    gl_total_row = {}
    gl_detail_file = None
    if gl_detail_dir:
        try:
            print(f"DEBUG [gl_breakdown]: Looking for GL detail file in {gl_detail_dir}")
            gl_detail_file = find_gl_detail_file(tenant_id, gl_detail_dir)
            if gl_detail_file:
                print(f"DEBUG [gl_breakdown]: Found GL detail file: {gl_detail_file}")
                gl_details, gl_total_row = get_gl_details_for_tenant(gl_detail_file)
                print(f"DEBUG [gl_breakdown]: Got {len(gl_details)} GL detail rows and total row: {bool(gl_total_row)}")
            else:
                print(f"DEBUG [gl_breakdown]: No GL detail file found for tenant {tenant_id}")
        except Exception as e:
            print(f"DEBUG [gl_breakdown]: Error processing GL details: {str(e)}")
            # Continue without GL details
    
    # Start building the LaTeX document with proper escaping
    document = f"""\\documentclass{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{booktabs}}
\\usepackage{{longtable}}
\\usepackage{{array}}
\\usepackage{{xcolor}}
\\usepackage{{fancyhdr}}
\\usepackage{{adjustbox}}
\\usepackage{{makecell}}

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
"""

    # Add override line if needed (right after Previously Billed)
    if has_override:
        # Negative amounts need special handling
        if override_amount.startswith('-'):
            override_value = override_amount[1:]  # Remove the negative sign
            document += f"{override_description} & -\\${override_value} \\\\\n"
        else:
            document += f"{override_description} & \\${override_amount} \\\\\n"

    document += f"""\\midrule
{reconciliation_year} Reconciliation Amount & \\${main_period_balance} \\\\
"""

    # Add catchup line if needed
    if has_catchup:
        document += f"{catchup_period_range} Catchup Period & \\${catchup_balance} \\\\\n"

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
"""

    # Add GL Breakdown section if available
    if gl_details and len(gl_details) > 0:
        print(f"DEBUG [gl_breakdown]: Adding GL breakdown with {len(gl_details)} detail rows")
        # Add a cap note if applicable
        cap_note = ""
        if has_cap:
            cap_note = "\\begin{center}\\small{Note: The GL breakdown shows expenses before cap adjustments.}\\end{center}\n\n"
        
        # Determine table structure (with or without CAP column)
        if has_cap:
            # 5-column table with CAP
            gl_table_header = "\\begin{tabular}{@{}p{2.2in}rrrrr@{}}\n\\toprule\n\\textbf{Description} & \\multicolumn{1}{c}{\\textbf{Total}} & \\multicolumn{1}{c}{\\textbf{Your}} & \\multicolumn{1}{c}{\\textbf{CAP}} & \\multicolumn{1}{c}{\\textbf{Admin}} & \\multicolumn{1}{c}{\\textbf{Total}} \\\\\n & \\multicolumn{1}{c}{\\textbf{Amount}} & \\multicolumn{1}{c}{\\textbf{Share}} & \\multicolumn{1}{c}{\\textbf{Reduction}} & \\multicolumn{1}{c}{\\textbf{Fee}} & \\\\\n"
        else:
            # 4-column standard table
            gl_table_header = "\\begin{tabular}{@{}p{2.2in}rrrr@{}}\n\\toprule\n\\textbf{Description} & \\multicolumn{1}{c}{\\textbf{Total Amount}} & \\multicolumn{1}{c}{\\textbf{Your Share}} & \\multicolumn{1}{c}{\\textbf{Admin Fee}} & \\multicolumn{1}{c}{\\textbf{Total}} \\\\\n"
        
        document += f"""\\newpage

\\begin{{center}}
\\Large\\textbf{{CAM Expense Breakdown}}

\\normalsize
\\textbf{{{property_name} - {reconciliation_year}}}
\\end{{center}}

{cap_note}
\\begin{{center}}
{gl_table_header}
\\midrule
"""
        
        # Initialize variables to track column totals
        total_gl_amount_raw = 0.0
        total_tenant_gl_amount = 0.0
        total_tenant_admin_fee = 0.0
        total_cap_impact_raw = 0.0
        total_final_amount = 0.0
        
        # Add GL rows
        for row in gl_details:
            # Extract row values - ensure we're getting the GL account description from the file
            gl_account = row.get("gl_account", "")
            original_description = row.get("description", "")
            print(f"DEBUG [GL {gl_account}]: Original description from CSV: '{original_description}'")
            
            # Skip specific rows that aren't actual GL accounts
            if gl_account == "FORMULA EXPLANATIONS:":
                print(f"DEBUG [GL {gl_account}]: Skipping formula explanations row")
                continue
                
            if "--- NEGATIVE BALANCE ACCOUNTS" in gl_account:
                print(f"DEBUG [GL {gl_account}]: Skipping negative balance accounts header")
                continue
                
            # Skip rows with "Direct value" which are explanations, not data
            if original_description == "Direct value" or row.get("combined_gross", "") == "Direct value":
                print(f"DEBUG [GL {gl_account}]: Skipping Direct value row")
                continue
                
            description = escape_latex(original_description)
            print(f"DEBUG [GL {gl_account}]: After LaTeX escaping: '{description}'")
            
            # Use the GL account as a fallback if description is empty
            if not description and gl_account:
                description = gl_account
                print(f"DEBUG [GL {gl_account}]: Description was empty, using GL account number instead")
                print(f"DEBUG [GL {gl_account}]: Empty description, using GL account as fallback: '{description}'")
            
            # Skip rows with non-numeric values in combined_gross
            combined_gross = row.get("combined_gross", "0")
            if isinstance(combined_gross, str) and combined_gross.strip() and not any(c.isdigit() or c in '.-$,' for c in combined_gross):
                print(f"DEBUG [GL {gl_account}]: Skipping row with non-numeric value for combined_gross: '{combined_gross}'")
                continue
                
            # Get raw values for calculations - with better error handling
            try:
                if isinstance(combined_gross, str):
                    combined_gross = combined_gross.strip('$').replace(',', '')
                gl_amount_raw = float(combined_gross or 0)
                
                tenant_share_pct_str = row.get("tenant_share_percentage", "0")
                if isinstance(tenant_share_pct_str, str):
                    tenant_share_pct_str = tenant_share_pct_str.strip('%').replace(',', '')
                tenant_share_pct = float(tenant_share_pct_str or 0) / 100
                
                admin_fee_pct_str = row.get("admin_fee_percentage", "0")
                if isinstance(admin_fee_pct_str, str):
                    admin_fee_pct_str = admin_fee_pct_str.strip('%').replace(',', '')
                admin_fee_pct = float(admin_fee_pct_str or 0) / 100
                
            except (ValueError, TypeError) as e:
                print(f"DEBUG [GL {gl_account}]: Error parsing values: {str(e)}")
                continue
                
            # Calculate tenant's share of GL amount (without admin fee)
            tenant_gl_amount = gl_amount_raw * tenant_share_pct
            
            # Calculate tenant's share of admin fee
            property_admin_fee = gl_amount_raw * admin_fee_pct
            tenant_admin_fee = property_admin_fee * tenant_share_pct
            
            # Format for display
            gl_amount = format_currency(gl_amount_raw)
            tenant_gl_share = format_currency(tenant_gl_amount)
            gl_admin_fee = format_currency(tenant_admin_fee)
            
            # Handle cap impact
            cap_impact_str = row.get("cap_impact", "0")
            if isinstance(cap_impact_str, str):
                cap_impact_str = cap_impact_str.strip('$').replace(',', '')
            cap_impact_raw = float(cap_impact_str or 0)
            gl_cap_impact = format_currency(cap_impact_raw)
            
            # Skip rows with zero amounts
            if gl_amount_raw == 0:
                print(f"DEBUG [GL {gl_account}]: Skipping row with zero amount")
                continue
            
            # Skip negative balance accounts
            if row.get("exclusion_categories", "") == "NEGATIVE BALANCE":
                print(f"DEBUG [GL {gl_account}]: Skipping negative balance account")
                continue
            
            # Skip GL accounts with zero tenant share (excluded accounts)
            try:
                tenant_share_value_str = row.get("tenant_share_amount", "0")
                if isinstance(tenant_share_value_str, str):
                    tenant_share_value_str = tenant_share_value_str.strip('$').replace(',', '')
                tenant_share_value = float(tenant_share_value_str or 0)
                if tenant_share_value == 0:
                    print(f"DEBUG [GL {gl_account}]: Skipping excluded account with zero tenant share")
                    continue
            except (ValueError, TypeError) as e:
                print(f"DEBUG [GL {gl_account}]: Error parsing tenant share amount: {str(e)}")
                continue
                
            # Check if excluded from admin fee or CAP
            is_admin_excluded = row.get("admin_fee_exclusion_rules", "").strip() != ""
            is_cap_excluded = row.get("cap_exclusion_rules", "").strip() != ""
            
            # Track totals for each column
            total_gl_amount_raw += gl_amount_raw
            total_tenant_gl_amount += tenant_gl_amount
            total_tenant_admin_fee += tenant_admin_fee
            total_cap_impact_raw += cap_impact_raw
            
            # Calculate and track the final amount for each row
            if has_cap:
                if is_cap_excluded:
                    row_final_amount = tenant_gl_amount + tenant_admin_fee
                else:
                    row_final_amount = tenant_gl_amount - cap_impact_raw + tenant_admin_fee
            else:
                if is_admin_excluded:
                    row_final_amount = tenant_gl_amount
                else:
                    row_final_amount = tenant_gl_amount + tenant_admin_fee
                    
            total_final_amount += row_final_amount
            
            print(f"DEBUG [GL {gl_account}]: Description: '{description}', GL account: '{gl_account}'")
            print(f"DEBUG [GL {gl_account}]: Description equals GL account? {description == gl_account}")
            
            # Check if we only have the GL account number as description (no actual description text)
            if description == gl_account:
                # Use just the GL account number without any prefix
                formatted_desc = description
                print(f"DEBUG [GL {gl_account}]: Description equals GL account, using GL account number: '{formatted_desc}'")
            else:
                # Use standard LaTeX font size commands for better reliability
                desc_len = len(description)
                if desc_len > 50:
                    # Very long descriptions need tiny font
                    formatted_desc = f"\\tiny{{{description}}}"
                    print(f"DEBUG [GL {gl_account}]: Using tiny font for very long description ({desc_len} chars): '{description}'")
                elif desc_len > 40:
                    # Long descriptions need scriptsize font
                    formatted_desc = f"\\scriptsize{{{description}}}"
                    print(f"DEBUG [GL {gl_account}]: Using scriptsize font for long description ({desc_len} chars): '{description}'")
                elif desc_len > 30:
                    # Moderate descriptions need footnotesize font
                    formatted_desc = f"\\footnotesize{{{description}}}"
                    print(f"DEBUG [GL {gl_account}]: Using footnotesize font for moderate description ({desc_len} chars): '{description}'")
                elif desc_len > 25:
                    # Slightly long descriptions need small font
                    formatted_desc = f"\\small{{{description}}}"
                    print(f"DEBUG [GL {gl_account}]: Using small font for slightly long description ({desc_len} chars): '{description}'")
                else:
                    formatted_desc = description
                    print(f"DEBUG [GL {gl_account}]: Using standard format for description ({desc_len} chars): '{formatted_desc}'")
            
            # Add row based on table structure
            if has_cap:
                if is_cap_excluded:
                    # GL accounts excluded from CAP
                    final_amount = float(tenant_gl_share.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                    latex_row = f"{formatted_desc} & \\${gl_amount} & \\${tenant_gl_share} & \\textit{{Excluded}} & \\${gl_admin_fee} & \\${format_currency(final_amount)} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding CAP excluded row: '{latex_row.strip()}'")
                    document += latex_row
                else:
                    # Standard GL with CAP
                    final_amount = float(tenant_gl_share.replace(',', '')) - float(gl_cap_impact.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                    latex_row = f"{formatted_desc} & \\${gl_amount} & \\${tenant_gl_share} & -\\${gl_cap_impact} & \\${gl_admin_fee} & \\${format_currency(final_amount)} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding standard CAP row: '{latex_row.strip()}'")
                    document += latex_row
            else:
                # Standard row without CAP
                if is_admin_excluded:
                    latex_row = f"{formatted_desc} & \\${gl_amount} & \\${tenant_gl_share} & \\textit{{Excluded}} & \\${tenant_gl_share} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding admin fee excluded row: '{latex_row.strip()}'")
                    document += latex_row
                else:
                    final_amount = float(tenant_gl_share.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                    latex_row = f"{formatted_desc} & \\${gl_amount} & \\${tenant_gl_share} & \\${gl_admin_fee} & \\${format_currency(final_amount)} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding standard row: '{latex_row.strip()}'")
                    document += latex_row
        
        # Format the calculated column totals for display
        total_gl_amount_formatted = format_currency(total_gl_amount_raw)
        total_tenant_gl_share_formatted = format_currency(total_tenant_gl_amount)
        total_admin_fee_formatted = format_currency(total_tenant_admin_fee)
        total_cap_impact_formatted = format_currency(total_cap_impact_raw)
        total_final_amount_formatted = format_currency(total_final_amount)
        
        print(f"DEBUG [GL totals]: Calculated totals from individual rows:")
        print(f"DEBUG [GL totals]:   Total GL Amount: ${total_gl_amount_formatted}")
        print(f"DEBUG [GL totals]:   Total Tenant Share: ${total_tenant_gl_share_formatted}")
        print(f"DEBUG [GL totals]:   Total Admin Fee: ${total_admin_fee_formatted}")
        print(f"DEBUG [GL totals]:   Total CAP Impact: ${total_cap_impact_formatted}")
        print(f"DEBUG [GL totals]:   Total Final Amount: ${total_final_amount_formatted}")
        
        # Add the totals row using the calculated values
        if has_cap:
            document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${total_gl_amount_formatted}}} & \\textbf{{\\${total_tenant_gl_share_formatted}}} & \\textbf{{-\\${total_cap_impact_formatted}}} & \\textbf{{\\${total_admin_fee_formatted}}} & \\textbf{{\\${total_final_amount_formatted}}} \\\\\n"
        else:
            document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${total_gl_amount_formatted}}} & \\textbf{{\\${total_tenant_gl_share_formatted}}} & \\textbf{{\\${total_admin_fee_formatted}}} & \\textbf{{\\${total_final_amount_formatted}}} \\\\\n"
        
        document += "\\bottomrule\n\\end{tabular}\n\\end{center}\n\n"

    # Add amortization section if applicable
    if has_amortization:
        # Get the number of amortization items
        amort_count = int(tenant_data.get("amortization_items_count", "0") or 0)
        
        if amort_count > 0:
            document += """\\newpage

\\begin{center}
\\Large\\textbf{Amortization Details}
\\end{center}

\\begin{center}
\\begin{tabular}{@{}lrrrrr@{}}
\\toprule
\\textbf{Description} & \\textbf{Total Amount} & \\textbf{Years} & \\textbf{Annual Amount} & \\textbf{Your Share \\%} & \\textbf{Your Share} \\\\
\\midrule
"""
            # Add amortization rows
            amort_total = 0.0
            for i in range(1, amort_count + 1):
                # Get item details
                description = escape_latex(tenant_data.get(f"amortization_{i}_description", ""))
                total_amount = format_currency(tenant_data.get(f"amortization_{i}_total_amount", "0"))
                years = tenant_data.get(f"amortization_{i}_years", "")
                annual_amount = format_currency(tenant_data.get(f"amortization_{i}_annual_amount", "0"))
                tenant_share = format_currency(tenant_data.get(f"amortization_{i}_your_share", "0"))
                
                # Calculate share percentage
                annual_amount_val = float(tenant_data.get(f"amortization_{i}_annual_amount", "0").strip('$').replace(',', '') or 0)
                tenant_share_val = float(tenant_data.get(f"amortization_{i}_your_share", "0").strip('$').replace(',', '') or 0)
                share_pct = 0
                if annual_amount_val > 0:
                    share_pct = (tenant_share_val / annual_amount_val) * 100
                
                # Add row
                document += f"{description} & \\${total_amount} & {years} & \\${annual_amount} & {format_percentage(share_pct)}\\% & \\${tenant_share} \\\\\n"
                amort_total += tenant_share_val
            
            # Add total row if multiple items
            if amort_count > 1:
                document += f"\\midrule\n\\textbf{{TOTAL}} & & & & & \\textbf{{\\${format_currency(amort_total)}}} \\\\\n"
            
            document += """\\bottomrule
\\end{tabular}
\\end{center}

\\vspace{0.5em}
\\begin{center}
\\small{Note: Amortization represents your share of capital improvements}\\\\
\\small{that are allocated over multiple years rather than expensed all at once.}
\\end{center}
"""

    # Close the document
    document += "\\end{document}\n"

    # Compile to PDF
    compile_success = compile_to_pdf(document, str(pdf_path), str(tex_path))
    
    return compile_success, str(pdf_path), str(tex_path)

def find_most_recent_csv_report(base_dir=None, property_id=None, recon_year=None):
    """Find the most recent CSV report file based on timestamp in filename."""
    if not base_dir:
        # Default to standard output directory
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output", "Reports")
    
    print(f"DEBUG [find_csv]: Looking for CSV reports in {base_dir}")
    
    # Pattern to match: tenant_billing_{property_id}_{category}_{recon_year}_{timestamp}.csv
    pattern_prefix = "tenant_billing_"
    if property_id:
        pattern_prefix += f"{property_id}_"
    if recon_year:
        pattern_prefix += f"*_{recon_year}_"
    
    matching_files = []
    
    try:
        for root, dirs, files in os.walk(base_dir):
            for filename in files:
                if filename.startswith(pattern_prefix) and filename.endswith(".csv"):
                    full_path = os.path.join(root, filename)
                    matching_files.append(full_path)
                    print(f"DEBUG [find_csv]: Found matching file: {filename}")
    except Exception as e:
        print(f"DEBUG [find_csv]: Error searching for CSV files: {str(e)}")
        return None
    
    if not matching_files:
        print(f"DEBUG [find_csv]: No matching CSV report files found")
        return None
    
    # Sort files by timestamp extracted from filename
    try:
        def extract_timestamp(filepath):
            filename = os.path.basename(filepath)
            # Remove .csv extension and split by underscore
            parts = filename.replace('.csv', '').split('_')
            if len(parts) >= 2:
                # Get the last two parts (date and time)
                return parts[-2] + parts[-1]
            return filename
        
        matching_files.sort(key=extract_timestamp)
    except Exception as e:
        print(f"DEBUG [find_csv]: Error sorting by timestamp, using modification time: {str(e)}")
        # Fallback to modification time
        matching_files.sort(key=os.path.getmtime)
    
    # Select the most recent file
    most_recent_file = matching_files[-1]
    print(f"DEBUG [find_csv]: Found {len(matching_files)} matching CSV files")
    print(f"DEBUG [find_csv]: Selected MOST RECENT file: {most_recent_file}")
    return most_recent_file

def generate_letters_from_results(results_dict):
    """Generate letters from reconciliation results."""
    print("\nGenerating tenant letters from reconciliation results...")

    # Extract the necessary paths and settings
    csv_report_path = results_dict.get('csv_report_path', '')
    gl_detail_reports = results_dict.get('gl_detail_reports', [])
    debug_mode = results_dict.get('debug_mode', False)
    integration_mode = results_dict.get('integration_mode', False)
    specific_tenant_id = results_dict.get('specific_tenant_id')
    
    # Get the explicitly provided GL directory (if any)
    explicit_gl_dir = results_dict.get('gl_dir')
    if explicit_gl_dir:
        print(f"GL directory provided: {explicit_gl_dir}")
    
    # Print environment information in integration mode
    if integration_mode:
        print("\n=== Integration Mode Information ===")
        print(f"Working directory: {os.getcwd()}")
        print(f"CSV report: {csv_report_path}")
        print(f"GL detail reports count: {len(gl_detail_reports)}")
        if explicit_gl_dir:
            print(f"GL directory exists: {os.path.exists(explicit_gl_dir)}")
            if os.path.exists(explicit_gl_dir):
                print(f"GL directory contents: {len(os.listdir(explicit_gl_dir))} items")
        
    # Read the tenant data from the CSV
    print(f"\nReading tenant data from: {csv_report_path}")
    tenant_data = read_csv_file(csv_report_path)
    
    # Print tenant data summary
    print(f"Found {len(tenant_data)} rows in tenant data CSV")
    
    if debug_mode:
        # Print a sample row to help with debugging
        if tenant_data and len(tenant_data) > 0:
            print("\n=== Sample Tenant Data (First Row) ===")
            first_tenant = tenant_data[0]
            print(f"Tenant ID: {first_tenant.get('tenant_id', 'NOT FOUND')}")
            print(f"Tenant Name: {first_tenant.get('tenant_name', 'NOT FOUND')}")
            print(f"Property ID: {first_tenant.get('property_id', 'NOT FOUND')}")
            print(f"Share Percentage: {first_tenant.get('share_percentage', 'NOT FOUND')}")
            
            # Check for FORMULA EXPLANATIONS
            if any("FORMULA EXPLANATIONS" in str(row.get('tenant_id', '')) or 
                   "FORMULA EXPLANATIONS" in str(row.get('tenant_name', '')) 
                   for row in tenant_data[:5]):
                print("\nWARNING: FORMULA EXPLANATIONS row found in first 5 rows of tenant data!")
                
            # Check for Direct value
            if any("Direct value" in str(row.get('tenant_id', '')) or 
                   "Direct value" in str(row.get('tenant_name', ''))
                   for row in tenant_data[:5]):
                print("\nWARNING: Direct value row found in first 5 rows of tenant data!")
    
    # Filter out any special rows that aren't actual tenants
    filtered_tenant_data = []
    for tenant in tenant_data:
        tenant_id = tenant.get("tenant_id", "")
        tenant_name = tenant.get("tenant_name", "")
        
        # Skip formula explanations rows
        if tenant_id == "FORMULA EXPLANATIONS:" or "FORMULA EXPLANATIONS" in tenant_name:
            print(f"  Skipping special entry: {tenant_id} - {tenant_name}")
            continue
            
        # Skip rows with "Direct value" which are explanations, not data
        if tenant_id == "Direct value" or tenant_name == "Direct value":
            print(f"  Skipping Direct value entry: {tenant_id} - {tenant_name}")
            continue
            
        # Skip negative balance rows
        if "NEGATIVE BALANCE" in tenant_id or "NEGATIVE BALANCE" in tenant_name:
            print(f"  Skipping negative balance entry: {tenant_id} - {tenant_name}")
            continue
            
        filtered_tenant_data.append(tenant)
    
    tenant_data = filtered_tenant_data
    
    # Find base GL detail directory
    gl_base_dir = None
    
    # If an explicit GL directory was provided, use it first
    if explicit_gl_dir and os.path.exists(explicit_gl_dir):
        gl_base_dir = explicit_gl_dir
        print(f"DEBUG [generate_letters]: Using explicitly provided GL directory: {gl_base_dir}")
    # Otherwise try to construct it
    elif tenant_data and len(tenant_data) > 0:
        property_id = tenant_data[0].get("property_id", "")
        recon_year = tenant_data[0].get("reconciliation_year", "")
        
        # Construct the base directory path where GL detail reports are stored
        # Format should be: Output/Reports/GL_Details/WAT_2024/
        if property_id and recon_year:
            # Using absolute paths to ensure consistent behavior regardless of working directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            gl_base_dir = os.path.join(script_dir, "Output", "Reports", "GL_Details", f"{property_id}_{recon_year}")
            print(f"DEBUG [generate_letters]: Looking for GL details in {gl_base_dir}")
            if not os.path.exists(gl_base_dir):
                print(f"DEBUG [generate_letters]: GL base directory not found at {gl_base_dir}")
                # Try relative path as fallback
                gl_base_dir = os.path.join("Output", "Reports", "GL_Details", f"{property_id}_{recon_year}")
                print(f"DEBUG [generate_letters]: Trying fallback GL path: {gl_base_dir}")
    
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
        property_id = tenant.get("property_id", "")
        recon_year = tenant.get("reconciliation_year", "")
        
        # Check for special entries that aren't real tenants
        if tenant_id == "FORMULA EXPLANATIONS:" or "FORMULA EXPLANATIONS" in tenant_name:
            print(f"  Skipping special entry: {tenant_id} - {tenant_name}")
            continue
            
        # Skip rows with "Direct value" which are explanations, not data
        if tenant_id == "Direct value" or tenant_name == "Direct value":
            print(f"  Skipping Direct value entry: {tenant_id} - {tenant_name}")
            continue
            
        # Skip tenants that don't match the specified tenant ID (if provided)
        if specific_tenant_id and tenant_id != specific_tenant_id:
            print(f"  Skipping tenant {tenant_id} (only processing {specific_tenant_id})")
            continue
            
        print(f"Processing tenant {tenant_id} ({tenant_name})...")
        
        # Create tenant-specific GL detail directory path
        tenant_gl_dir = None
        if gl_base_dir:
            try:
                # Format should be: Output/Reports/GL_Details/WAT_2024/Tenant_1401_Mexico_Grill,_LLC
                # First try with underscores in tenant name
                tenant_dir_name = f"Tenant_{tenant_id}_{tenant_name.replace(' ', '_')}"
                tenant_gl_dir = os.path.join(gl_base_dir, tenant_dir_name)
                print(f"DEBUG [generate_letters]: Looking for tenant GL directory at {tenant_gl_dir}")
                
                if not os.path.exists(tenant_gl_dir):
                    print(f"DEBUG [generate_letters]: First attempt failed, trying alternative naming format")
                    # Try with just tenant ID
                    tenant_dir_name = f"Tenant_{tenant_id}"
                    tenant_gl_dir = os.path.join(gl_base_dir, tenant_dir_name)
                    print(f"DEBUG [generate_letters]: Looking for GL dir with just tenant ID: {tenant_gl_dir}")
                    
                    if not os.path.exists(tenant_gl_dir):
                        # As a last resort, directly search for GL files with this tenant ID
                        print(f"DEBUG [generate_letters]: Directory not found, searching for any GL files with tenant ID {tenant_id}")
                        # Do a manual search in the property's GL directory
                        gl_files = []
                        if os.path.exists(gl_base_dir):
                            for root, dirs, files in os.walk(gl_base_dir):
                                for file in files:
                                    if file.startswith(f"GL_detail_{tenant_id}_") and file.endswith(".csv"):
                                        gl_files.append(os.path.join(root, file))
                        
                        if gl_files:
                            # Use the directory of the first file found
                            tenant_gl_dir = os.path.dirname(gl_files[0])
                            print(f"DEBUG [generate_letters]: Found GL file in directory: {tenant_gl_dir}")
                        else:
                            print(f"  Warning: No GL detail directory found for tenant {tenant_id} after extensive search")
                            tenant_gl_dir = None
                    else:
                        print(f"DEBUG [generate_letters]: Found tenant GL directory with second attempt")
                else:
                    print(f"DEBUG [generate_letters]: Found tenant GL directory with first attempt")
            except Exception as e:
                print(f"DEBUG [generate_letters]: Error finding GL directory: {str(e)}")
                tenant_gl_dir = None
        
        try:
            # Generate letter with tenant-specific GL detail directory
            success, pdf_path, tex_path = generate_tenant_letter(tenant, tenant_gl_dir, debug_mode=debug_mode)
            
            if success:
                successful += 1
                print(f"  ✅ Letter generated successfully for tenant {tenant_id}")
                print(f"    LaTeX file: {tex_path}")
                print(f"    PDF file: {pdf_path}")
            else:
                print(f"  ❌ Failed to compile PDF for tenant {tenant_id}")
                if integration_mode:
                    print(f"  Integration mode debugging:")
                    print(f"    - Tenant data has {len(tenant.keys())} fields")
                    print(f"    - GL directory exists: {os.path.exists(tenant_gl_dir) if tenant_gl_dir else 'No GL dir'}")
                    print(f"    - Check for permission issues or write protection")
        except Exception as e:
            print(f"  ❌ Error generating letter for tenant {tenant_id}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\nLetter generation complete: {successful} of {total} letters generated successfully")
    print(f"Letters are saved in: {LETTERS_DIR}")
    
    return successful, total

def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CAM reconciliation letters with LaTeX')
    parser.add_argument('--csv', type=str, help='Path to reconciliation CSV file (if not provided, finds most recent)')
    parser.add_argument('--gl_dir', type=str, help='Directory containing GL detail CSV files')
    parser.add_argument('--property', type=str, help='Property ID to filter reports (e.g., WAT)')
    parser.add_argument('--year', type=str, help='Reconciliation year to filter reports (e.g., 2024)')
    parser.add_argument('--debug', action='store_true', help='Enable verbose debug output')
    parser.add_argument('--log_file', type=str, help='Path to save detailed debug logs')
    parser.add_argument('--tenant_id', type=str, help='Process only a specific tenant ID')
    parser.add_argument('--verify_csv', action='store_true', help='Verify CSV structure before processing')
    parser.add_argument('--integration_mode', action='store_true', help='Add extra debugging for New Full.py integration')
    
    args = parser.parse_args()
    
    # Set up logging to file if requested
    if args.log_file:
        import logging
        log_dir = os.path.dirname(args.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.DEBUG if args.debug else logging.INFO,
            filename=args.log_file,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)
        
        logging.info("=== Enhanced Letter Generator Starting ===")
        logging.info(f"Arguments: {args}")
    
    # Print run information
    print("\n===== ENHANCED LETTER GENERATOR =====")
    print(f"Run date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Run mode: {'Integration with New Full.py' if args.integration_mode else 'Standalone'}")
    print(f"Debug mode: {'Enabled' if args.debug else 'Disabled'}")
    print(f"Script directory: {SCRIPT_DIR}")
    
    # Determine CSV report path
    csv_report_path = args.csv
    if not csv_report_path:
        # Find the most recent CSV report
        print("\nNo CSV file specified. Looking for most recent report...")
        csv_report_path = find_most_recent_csv_report(property_id=args.property, recon_year=args.year)
        if not csv_report_path:
            print("Error: No CSV report found. Please specify a CSV file with --csv")
            return 0, 0
        print(f"Using most recent CSV report: {csv_report_path}")
    
    # Verify CSV structure if requested
    if args.verify_csv and csv_report_path:
        print("\n=== Verifying CSV Structure ===")
        try:
            with open(csv_report_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                print(f"CSV has {len(headers)} columns")
                
                # Check for crucial columns
                required_columns = [
                    "tenant_id", "tenant_name", "property_id", "share_percentage", 
                    "cam_net_total", "admin_fee_net", "subtotal_after_tenant_share", "tenant_share_amount"
                ]
                
                missing_columns = [col for col in required_columns if col not in headers]
                if missing_columns:
                    print(f"WARNING: CSV is missing required columns: {', '.join(missing_columns)}")
                else:
                    print("CSV has all required columns")
                
                # Check for formula explanations row
                for i, row in enumerate(reader):
                    if i < 5:  # Just check first few rows
                        if row and "FORMULA EXPLANATIONS" in row[0]:
                            print(f"WARNING: Found FORMULA EXPLANATIONS at row {i+2}")
                            break
        except Exception as e:
            print(f"Error verifying CSV: {str(e)}")
    
    # Print verbose debug info for GL directory
    if args.gl_dir:
        print(f"\n=== GL Directory Information ===")
        print(f"GL directory specified: {args.gl_dir}")
        try:
            if os.path.exists(args.gl_dir):
                print(f"GL directory exists")
                # List directories
                tenant_dirs = []
                for item in os.listdir(args.gl_dir):
                    item_path = os.path.join(args.gl_dir, item)
                    if os.path.isdir(item_path):
                        if item.startswith("Tenant_"):
                            tenant_id = item.split("_")[1]
                            gl_files = [f for f in os.listdir(item_path) if f.endswith('.csv')]
                            tenant_dirs.append((tenant_id, len(gl_files)))
                
                print(f"Found {len(tenant_dirs)} tenant directories")
                for tenant_id, file_count in tenant_dirs[:5]:  # Show first 5
                    print(f"  Tenant {tenant_id}: {file_count} GL files")
                
                if len(tenant_dirs) > 5:
                    print(f"  ... and {len(tenant_dirs) - 5} more tenant directories")
            else:
                print(f"GL directory does not exist: {args.gl_dir}")
        except Exception as e:
            print(f"Error exploring GL directory: {str(e)}")
    
    # Prepare results dictionary
    results_dict = {
        'csv_report_path': csv_report_path,
        'gl_dir': args.gl_dir,  # Pass the GL directory directly
        'gl_detail_reports': [os.path.join(args.gl_dir, f) for f in os.listdir(args.gl_dir)] 
                             if args.gl_dir and os.path.exists(args.gl_dir) else [],
        'debug_mode': args.debug,
        'integration_mode': args.integration_mode,
        'specific_tenant_id': args.tenant_id  # Process only a specific tenant if requested
    }
    
    print("\n=== Starting Letter Generation ===")
    successful, total = generate_letters_from_results(results_dict)
    
    print(f"\n=== Letter Generation Complete ===")
    print(f"Successfully generated: {successful} of {total} letters")
    print(f"Letters saved in: {LETTERS_DIR}")
    
    return successful, total

if __name__ == "__main__":
    main()