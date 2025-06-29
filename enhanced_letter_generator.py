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
            
        # Value is already in percentage form (e.g., 5.14 for 5.14%) from the CSV
        # No need to multiply by 100 again
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

def escape_amount_for_latex(amount_str):
    """Escape commas in monetary amounts for LaTeX tabular environments."""
    if not amount_str:
        return ""
    # Remove any existing $ signs and escape commas
    amount_clean = str(amount_str).replace('$', '')
    amount_escaped = amount_clean.replace(',', '{,}')
    return amount_escaped

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
    
    # Extract financial values - use tenant-specific CAM if available, fallback to property CAM
    property_total = format_currency(tenant_data.get("tenant_cam_net_total", tenant_data.get("cam_net_total", tenant_data.get("property_gl_total", "0"))))
    tenant_pro_rata = format_percentage(tenant_data.get("share_percentage", "0"))
    # tenant_share is calculated based on subtotal_after_tenant_share as per field mapping if available
    tenant_share = format_currency(tenant_data.get("subtotal_after_tenant_share", tenant_data.get("tenant_share_amount", "0")))
    base_year_amount = format_currency(tenant_data.get("base_year_adjustment", "0"))
    cap_reduction = format_currency(tenant_data.get("cap_deduction", "0"))
    # Use appropriate amounts for letter display
    admin_fee = format_currency(tenant_data.get("tenant_admin_fee_total", tenant_data.get("admin_fee_raw", "0")))
    amortization_amount = format_currency(tenant_data.get("capital_expenses_total", tenant_data.get("amortization_total_amount", "0")))
    
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
        # This fallback follows the same logic as in New Full.py:
        # If no effective date is provided, use January of the year following the reconciliation year
        print(f"WARNING: No monthly_charge_effective_date found in tenant data. Using fallback logic.")
        
        # Get reconciliation year from tenant data
        recon_year_str = tenant_data.get("recon_year", "")
        if recon_year_str:
            try:
                recon_year = int(recon_year_str)
                # Set to January of the next year
                effective_date = datetime.datetime(recon_year + 1, 1, 1).strftime("%b %d, %Y")
            except (ValueError, TypeError):
                # If recon_year can't be parsed, use default logic
                print(f"WARNING: Invalid recon_year: {recon_year_str}. Using current year + 1.")
                effective_date = datetime.datetime(datetime.datetime.now().year + 1, 1, 1).strftime("%b %d, %Y")
        else:
            # If no recon_year, use current year + 1
            print(f"WARNING: No recon_year in tenant data. Using current year + 1.")
            effective_date = datetime.datetime(datetime.datetime.now().year + 1, 1, 1).strftime("%b %d, %Y")
    
    # Prepare conditional lines
    has_base_year = float(tenant_data.get("base_year_adjustment", "0").strip('$').replace(',', '') or 0) > 0
    has_cap = float(tenant_data.get("cap_deduction", "0").strip('$').replace(',', '') or 0) > 0
    has_amortization = float(tenant_data.get("capital_expenses_total", tenant_data.get("amortization_total_amount", "0")).strip('$').replace(',', '') or 0) > 0
    has_admin_fee = float(tenant_data.get("tenant_admin_fee_total", tenant_data.get("admin_fee_raw", "0")).strip('$').replace(',', '') or 0) > 0
    has_catchup = float(tenant_data.get("catchup_balance", "0").strip('$').replace(',', '') or 0) != 0
    has_override = has_override and float(tenant_data.get("override_amount", "0").strip('$').replace(',', '') or 0) != 0
    
    # Check if we need to include the GL breakdown
    gl_details = []
    gl_total_row = {}
    gl_detail_file = None
    
    # More aggressively search for GL detail files
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
Total Property CAM Expenses ({reconciliation_year}) & \\${escape_amount_for_latex(property_total)} \\\\
"""

    # Add conditional lines
    if has_base_year:
        document += f"Base Year Deduction & -\\${escape_amount_for_latex(base_year_amount)} \\\\\n"
    if has_cap:
        document += f"Cap Reduction & -\\${escape_amount_for_latex(cap_reduction)} \\\\\n"
    if has_amortization:
        document += f"Total Capitalized Expenses & \\${escape_amount_for_latex(amortization_amount)} \\\\\n"
    if has_admin_fee:
        document += f"Total Property Admin Fee & \\${escape_amount_for_latex(admin_fee)} \\\\\n"
        
    # Get letter display property total (preferred) or fall back to tenant property total
    property_total_with_additions = tenant_data.get("letter_display_property_total", tenant_data.get("tenant_property_total_expenses", None))
    if not property_total_with_additions:
        # Fallback to legacy field or calculation
        property_total_with_additions = tenant_data.get("property_total_with_admin_fee", None)
        if not property_total_with_additions:
            # Calculate the total if not available in the data
            try:
                property_total_val = float(property_total.replace('$', '').replace(',', '') or 0)
                admin_fee_val = float(admin_fee.replace('$', '').replace(',', '') or 0) if has_admin_fee else 0
                amortization_val = float(amortization_amount.replace('$', '').replace(',', '') or 0) if has_amortization else 0
                property_total_with_additions = format_currency(property_total_val + admin_fee_val + amortization_val)
            except (ValueError, TypeError):
                # If calculation fails, default to a reasonable value
                property_total_with_additions = property_total
    
    document += f"\\midrule\nTotal Property Expenses & \\${escape_amount_for_latex(property_total_with_additions)} \\\\\n"

    document += f"""\\midrule
Your Share for Year ({tenant_pro_rata}\\%) & \\${escape_amount_for_latex(year_due)} \\\\
Less Previously Billed ({reconciliation_year}) & \\${escape_amount_for_latex(main_period_paid)} \\\\
"""

    # Add override line if needed (right after Previously Billed)
    if has_override:
        # Add "Less" prefix if the amount is negative
        if override_amount.startswith('-'):
            override_value = override_amount[1:]  # Remove the negative sign
            document += f"Less {override_description} & \\${escape_amount_for_latex(override_value)} \\\\\n"
        else:
            document += f"{override_description} & \\${escape_amount_for_latex(override_amount)} \\\\\n"

    document += f"""\\midrule
{reconciliation_year} Reconciliation Amount & \\${escape_amount_for_latex(main_period_balance)} \\\\
"""

    # Add catchup line if needed
    if has_catchup:
        # Add "Less" prefix if the amount is negative
        if catchup_balance.startswith('-'):
            catchup_value = catchup_balance[1:]  # Remove the negative sign
            document += f"Less {catchup_period_range} Catchup Period & \\${escape_amount_for_latex(catchup_value)} \\\\\n"
        else:
            document += f"{catchup_period_range} Catchup Period & \\${escape_amount_for_latex(catchup_balance)} \\\\\n"

    document += f"""\\midrule
\\textbf{{ADDITIONAL AMOUNT DUE}} & \\textbf{{\\${escape_amount_for_latex(grand_total)}}} \\\\
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
Current Monthly Charge & \\${escape_amount_for_latex(current_monthly)} \\\\
New Monthly Charge & \\${escape_amount_for_latex(new_monthly)} \\\\
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
            
            # Only add to admin fee total if not excluded
            if not is_admin_excluded:
                total_tenant_admin_fee += tenant_admin_fee
            print(f"DEBUG [GL {gl_account}]: Admin fee: {tenant_admin_fee:.2f}, Running total: {total_tenant_admin_fee:.2f}, Excluded: {is_admin_excluded}")
            
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
            
            # Check if admin fee should be excluded (either individual GL exclusion or tenant has 0% admin fee)
            is_admin_fee_excluded = is_admin_excluded or not has_admin_fee
            
            # Add row based on table structure
            if has_cap:
                if is_cap_excluded:
                    # GL accounts excluded from CAP
                    if is_admin_fee_excluded:
                        final_amount = float(tenant_gl_share.replace(',', ''))
                        latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & \\textit{{Excluded}} & \\textit{{Excluded}} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                        print(f"DEBUG [GL {gl_account}]: Adding CAP excluded + admin excluded row: '{latex_row.strip()}'")
                    else:
                        final_amount = float(tenant_gl_share.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                        latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & \\textit{{Excluded}} & \\${escape_amount_for_latex(gl_admin_fee)} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                        print(f"DEBUG [GL {gl_account}]: Adding CAP excluded row: '{latex_row.strip()}'")
                    document += latex_row
                else:
                    # Standard GL with CAP
                    if is_admin_fee_excluded:
                        final_amount = float(tenant_gl_share.replace(',', '')) - float(gl_cap_impact.replace(',', ''))
                        latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & -\\${escape_amount_for_latex(gl_cap_impact)} & \\textit{{Excluded}} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                        print(f"DEBUG [GL {gl_account}]: Adding standard CAP + admin excluded row: '{latex_row.strip()}'")
                    else:
                        final_amount = float(tenant_gl_share.replace(',', '')) - float(gl_cap_impact.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                        latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & -\\${escape_amount_for_latex(gl_cap_impact)} & \\${escape_amount_for_latex(gl_admin_fee)} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                        print(f"DEBUG [GL {gl_account}]: Adding standard CAP row: '{latex_row.strip()}'")
                    document += latex_row
            else:
                # Standard row without CAP
                if is_admin_fee_excluded:
                    # For admin fee excluded rows, the total should be just the tenant's share
                    final_amount = float(tenant_gl_share.replace(',', ''))
                    latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & \\textit{{Excluded}} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding admin fee excluded row: '{latex_row.strip()}'")
                    document += latex_row
                else:
                    final_amount = float(tenant_gl_share.replace(',', '')) + float(gl_admin_fee.replace(',', ''))
                    latex_row = f"{formatted_desc} & \\${escape_amount_for_latex(gl_amount)} & \\${escape_amount_for_latex(tenant_gl_share)} & \\${escape_amount_for_latex(gl_admin_fee)} & \\${escape_amount_for_latex(format_currency(final_amount))} \\\\\n"
                    print(f"DEBUG [GL {gl_account}]: Adding standard row: '{latex_row.strip()}'")
                    document += latex_row
        
        # Format the calculated column totals for display
        total_gl_amount_formatted = format_currency(total_gl_amount_raw)
        total_tenant_gl_share_formatted = format_currency(total_tenant_gl_amount)
        total_admin_fee_formatted = format_currency(total_tenant_admin_fee)
        total_cap_impact_formatted = format_currency(total_cap_impact_raw)
        total_final_amount_formatted = format_currency(total_final_amount)
        
        # Enhanced debugging for totals
        print(f"DEBUG [GL totals]: Calculated totals from individual rows:")
        print(f"DEBUG [GL totals]:   Total GL Amount: ${total_gl_amount_formatted}")
        print(f"DEBUG [GL totals]:   Total Tenant Share: ${total_tenant_gl_share_formatted}")
        print(f"DEBUG [GL totals]:   Total Admin Fee: ${total_admin_fee_formatted}")
        print(f"DEBUG [GL totals]:   Total CAP Impact: ${total_cap_impact_formatted}")
        print(f"DEBUG [GL totals]:   Total Final Amount: ${total_final_amount_formatted}")
        
        # Extract admin fee from tenant data for comparison with our calculated value (for debugging only)
        tenant_admin_fee_value = float(tenant_data.get("admin_fee_raw", "0").strip('$').replace(',', '') or 0)
        admin_fee_match = abs(tenant_admin_fee_value - total_tenant_admin_fee) < 0.01
        
        print(f"DEBUG [GL totals]: Admin fee comparison - tenant data value: ${format_currency(tenant_admin_fee_value)}")
        print(f"DEBUG [GL totals]: Admin fee comparison - calculated value: ${format_currency(total_tenant_admin_fee)}")
        print(f"DEBUG [GL totals]: Admin fee match: {admin_fee_match}")
        
        # Verify calculation but DON'T override our calculated values
        if not admin_fee_match:
            print(f"DEBUG [GL totals]: NOTE - Admin fee mismatch, but using calculated value from GL breakdown")
            
        # Verify the total matches the sum of tenant share and admin fee (minus cap impact if applicable)
        expected_total = total_tenant_gl_amount + total_tenant_admin_fee
        if has_cap:
            expected_total -= total_cap_impact_raw
            
        print(f"DEBUG [GL totals]: Verification check - expected total: ${format_currency(expected_total)}")
        print(f"DEBUG [GL totals]: Verification check - actual total: ${total_final_amount_formatted}")
        print(f"DEBUG [GL totals]: Verification passed: {abs(expected_total - total_final_amount) < 0.01}")
        
        # Add the totals row using the calculated values
        if has_cap:
            if has_admin_fee:
                document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${escape_amount_for_latex(total_gl_amount_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_tenant_gl_share_formatted)}}} & \\textbf{{-\\${escape_amount_for_latex(total_cap_impact_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_admin_fee_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_final_amount_formatted)}}} \\\\\n"
            else:
                document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${escape_amount_for_latex(total_gl_amount_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_tenant_gl_share_formatted)}}} & \\textbf{{-\\${escape_amount_for_latex(total_cap_impact_formatted)}}} & \\textbf{{\\textit{{Excluded}}}} & \\textbf{{\\${escape_amount_for_latex(total_final_amount_formatted)}}} \\\\\n"
        else:
            if has_admin_fee:
                document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${escape_amount_for_latex(total_gl_amount_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_tenant_gl_share_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_admin_fee_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_final_amount_formatted)}}} \\\\\n"
            else:
                document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${escape_amount_for_latex(total_gl_amount_formatted)}}} & \\textbf{{\\${escape_amount_for_latex(total_tenant_gl_share_formatted)}}} & \\textbf{{\\textit{{Excluded}}}} & \\textbf{{\\${escape_amount_for_latex(total_final_amount_formatted)}}} \\\\\n"
        
        document += "\\bottomrule\n\\end{tabular}\n\\end{center}\n\n"

    # Add amortization section if applicable
    if has_amortization:
        # Get the number of amortization items
        amort_count = int(tenant_data.get("amortization_items_count", "0") or 0)
        
        if amort_count > 0:
            document += """\\newpage

\\begin{center}
\\Large\\textbf{Capitalized Expenses Details}
\\end{center}

\\begin{center}
\\adjustbox{width=\\textwidth,center}
{\\small
\\begin{tabular}{@{}lrrrrr@{}}
\\toprule
\\textbf{Description} & \\textbf{Total Amount} & \\textbf{Annual Amount} & \\textbf{Years} & \\textbf{Your Share \\%} & \\textbf{Your Share} \\\\
\\midrule
"""
            # Add amortization rows
            total_amount_sum = 0.0
            annual_amount_sum = 0.0
            amort_total = 0.0
            for i in range(1, amort_count + 1):
                # Get item details
                description = escape_latex(tenant_data.get(f"amortization_{i}_description", ""))
                
                # Add the year to the description if available
                year = tenant_data.get(f"amortization_{i}_year", "")
                if year:
                    description = f"{description} ({year})"
                
                total_amount = format_currency(tenant_data.get(f"amortization_{i}_total_amount", "0"))
                years = tenant_data.get(f"amortization_{i}_years", "")
                annual_amount = format_currency(tenant_data.get(f"amortization_{i}_annual_amount", "0"))
                tenant_share = format_currency(tenant_data.get(f"amortization_{i}_your_share", "0"))
                
                # Calculate share percentage and track totals
                total_amount_val = float(tenant_data.get(f"amortization_{i}_total_amount", "0").strip('$').replace(',', '') or 0)
                annual_amount_val = float(tenant_data.get(f"amortization_{i}_annual_amount", "0").strip('$').replace(',', '') or 0)
                tenant_share_val = float(tenant_data.get(f"amortization_{i}_your_share", "0").strip('$').replace(',', '') or 0)
                share_pct = 0
                if annual_amount_val > 0:
                    share_pct = (tenant_share_val / annual_amount_val) * 100
                
                # Add to totals
                total_amount_sum += total_amount_val
                annual_amount_sum += annual_amount_val
                amort_total += tenant_share_val
                
                # Add row
                document += f"{description} & \\${escape_amount_for_latex(total_amount)} & \\${escape_amount_for_latex(annual_amount)} & {years} & {format_percentage(share_pct)}\\% & \\${escape_amount_for_latex(tenant_share)} \\\\\n"
            
            # Add total row if multiple items
            if amort_count > 1:
                document += f"\\midrule\n\\textbf{{TOTAL}} & \\textbf{{\\${escape_amount_for_latex(format_currency(total_amount_sum))}}} & \\textbf{{\\${escape_amount_for_latex(format_currency(annual_amount_sum))}}} & & & \\textbf{{\\${escape_amount_for_latex(format_currency(amort_total))}}} \\\\\n"
            
            document += """\\bottomrule
\\end{tabular}
}
\\end{center}

\\vspace{0.5em}
\\begin{center}
\\small{Note: Total Capitalized Expenses represents your share of capital improvements}\\\\
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
    # Add diagnostics for results_dict
    print(f"Results dictionary contains {len(results_dict)} keys")
    print(f"Keys in results_dict: {', '.join(results_dict.keys())}")
    
    # Set default to combine PDFs automatically
    auto_combine_pdf = results_dict.get('auto_combine_pdf', True)
    print(f"Auto PDF combining is {'enabled' if auto_combine_pdf else 'disabled'} (value: {auto_combine_pdf}, type: {type(auto_combine_pdf)})")
    
    # Force auto_combine_pdf to be True explicitly, just to be super safe
    if 'auto_combine_pdf' not in results_dict:
        print("auto_combine_pdf not found in results_dict, adding it")
        results_dict['auto_combine_pdf'] = True
    elif results_dict['auto_combine_pdf'] is not True:
        print(f"auto_combine_pdf value was {results_dict['auto_combine_pdf']}, forcing to True")
        results_dict['auto_combine_pdf'] = True
    print(f"Final auto_combine_pdf value in results_dict: {results_dict['auto_combine_pdf']}")
    
    # Extract property_id and recon_year early for PDF combining
    property_id = results_dict.get('property_id', '')
    recon_year = str(results_dict.get('recon_year', ''))
    
    # Debug information about GL detail files
    gl_detail_reports = results_dict.get('gl_detail_reports', [])
    gl_dir = results_dict.get('gl_dir')
    if gl_detail_reports:
        print(f"Found {len(gl_detail_reports)} GL detail reports for inclusion in letters")
    if gl_dir:
        print(f"GL directory: {gl_dir}")
        # Check if the directory exists
        if os.path.exists(gl_dir):
            files_in_dir = os.listdir(gl_dir)
            print(f"GL directory contains {len(files_in_dir)} items")
        else:
            print(f"GL directory doesn't exist: {gl_dir}")
            # Create the directory
            try:
                os.makedirs(gl_dir, exist_ok=True)
                print(f"Created GL directory: {gl_dir}")
            except Exception as e:
                print(f"Error creating GL directory: {str(e)}")

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

def combine_tenant_pdfs(letter_dir, expected_pdf_count=None):
    """
    Combine all tenant PDFs into a single file for easy printing.
    
    Args:
        letter_dir: Directory containing letter files
        expected_pdf_count: Number of PDFs expected (to wait for)
    """
    print("\n=== Creating Combined PDF ===")
    try:
        pdf_dir = Path(letter_dir) / "PDFs"
        print(f"PDF directory path: {pdf_dir}")
        
        # Check if PDF directory exists
        if not pdf_dir.exists():
            print(f"PDF directory not found: {pdf_dir}")
            return False
            
        # Create a subfolder for combined PDFs
        combined_dir = pdf_dir / "Combined"
        print(f"Attempting to create Combined directory: {combined_dir}")
        try:
            combined_dir.mkdir(exist_ok=True, parents=True)
            print(f"Created or verified Combined subfolder: {combined_dir}")
        except Exception as dir_error:
            print(f"Error creating Combined directory {combined_dir}: {str(dir_error)}")
            import traceback
            traceback.print_exc()
        
        # First, try to use the standalone combine_pdfs.py module
        try:
            import importlib.util
            # Find the combine_pdfs.py in the current directory or parent directories
            combine_pdfs_path = None
            current_dir = Path().resolve()
            for _ in range(3):  # Check current dir and up to 2 levels up
                if (current_dir / "combine_pdfs.py").exists():
                    combine_pdfs_path = current_dir / "combine_pdfs.py"
                    break
                current_dir = current_dir.parent
            
            if combine_pdfs_path:
                print(f"Found combine_pdfs.py at {combine_pdfs_path}")
                # Import the module
                spec = importlib.util.spec_from_file_location("combine_pdfs", combine_pdfs_path)
                combine_pdfs_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(combine_pdfs_module)
                
                # Call the combine_pdfs function from the module with expected count and filtering
                print(f"Calling combine_pdfs with expected count: {expected_pdf_count} and non-zero filtering")
                result = combine_pdfs_module.combine_pdfs(
                    str(pdf_dir), 
                    expected_count=expected_pdf_count,
                    filter_func=combine_pdfs_module.has_nonzero_amount_due,
                    additional_output_name="NonZeroDue"
                )
                if result:
                    print("Successfully combined PDFs using combine_pdfs.py module")
                    return True
                else:
                    print("Failed to combine PDFs using combine_pdfs.py module, falling back to internal implementation")
            else:
                print("combine_pdfs.py not found, using internal implementation")
        except Exception as e:
            print(f"Error using combine_pdfs.py module: {str(e)}")
            print("Falling back to internal implementation")
            
        # Continue with internal implementation if the module failed
        # Get a list of all PDF files
        pdf_files = list(pdf_dir.glob("*.pdf"))
        # Exclude any previously generated combined PDFs
        pdf_files = [f for f in pdf_files if "All_" not in f.name]
        
        if not pdf_files:
            print("No PDF files found to combine")
            return False
            
        # Make sure we have at least one PDF file
        print(f"Found {len(pdf_files)} tenant PDFs to combine in {pdf_dir}")
        if len(pdf_files) == 0:
            print("No PDF files to combine")
            return False
        
        # Determine property and year from directory path
        property_id = pdf_dir.parent.parent.name
        reconciliation_year = pdf_dir.parent.name
        
        # Create output filename in the Combined subfolder
        output_file = combined_dir / f"All_{property_id}_{reconciliation_year}_Letters.pdf"
        
        # Also create a non-zero amount due version
        try:
            # Import our combine_pdfs module to use has_nonzero_amount_due function
            import importlib.util
            current_dir = Path().resolve()
            for _ in range(3):  # Check current dir and up to 2 levels up
                combine_pdfs_path = current_dir / "combine_pdfs.py"
                if combine_pdfs_path.exists():
                    spec = importlib.util.spec_from_file_location("combine_pdfs", combine_pdfs_path)
                    combine_pdfs_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(combine_pdfs_module)
                    
                    # Filter PDFs with non-zero amount due
                    nonzero_pdfs = [f for f in pdf_files if combine_pdfs_module.has_nonzero_amount_due(f)]
                    
                    if nonzero_pdfs:
                        nonzero_output = combined_dir / f"All_{property_id}_{reconciliation_year}_NonZeroDue_Letters.pdf"
                        print(f"Will also create a filtered PDF with {len(nonzero_pdfs)} non-zero amount due tenants")
                    break
                current_dir = current_dir.parent
        except Exception as e:
            print(f"Note: Not creating non-zero amount due PDF due to error: {str(e)}")
        
        try:
            # Try to use Ghostscript (gs)
            print(f"Combining {len(pdf_files)} tenant PDFs into {output_file}")
            
            # Change to the PDF directory
            orig_dir = os.getcwd()
            os.chdir(pdf_dir)
            
            # When running gs, we need to be careful with filenames containing special characters
            # Instead of building a command string with all files, we'll pass files as arguments
            gs_cmd = ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", f"-sOutputFile={output_file.name}"]
            gs_cmd.extend([str(f.name) for f in pdf_files])
            
            # Run gs command with proper argument handling
            print(f"Running command: {' '.join(gs_cmd)}")
            result = subprocess.run(gs_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            
            # Return to original directory
            os.chdir(orig_dir)
            
            # Print command result
            print(f"Command exit code: {result.returncode}")
            if result.returncode != 0:
                print(f"Command stderr: {result.stderr.decode() if result.stderr else 'None'}")
                print(f"Command stdout: {result.stdout.decode() if result.stdout else 'None'}")
            
            if result.returncode == 0 and output_file.exists():
                print(f"Successfully created combined PDF: {output_file}")
                print(f"Combined PDF size: {output_file.stat().st_size / 1024:.1f} KB")
                return True
            else:
                print(f"Error creating combined PDF: {result.stderr.decode()}")
                
                # Try using PyPDF2 as a fallback
                try:
                    from PyPDF2 import PdfMerger
                    print("Falling back to PyPDF2 for PDF merging...")
                    merger = PdfMerger()
                    for pdf_file in pdf_files:
                        print(f"Adding {pdf_file}")
                        merger.append(str(pdf_file))
                    merger.write(str(output_file))
                    merger.close()
                    print(f"Successfully combined PDFs using PyPDF2 into {output_file}")
                    return True
                except Exception as pdf_error:
                    print(f"PyPDF2 fallback failed: {pdf_error}")
                    return False
                
        except Exception as e:
            print(f"Error combining PDF files: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    except Exception as e:
        print(f"Error in combine_tenant_pdfs: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CAM reconciliation letters with LaTeX')
    parser.add_argument('--csv', type=str, help='Path to reconciliation CSV file (if not provided, finds most recent)')
    parser.add_argument('--gl_dir', type=str, help='Directory containing GL detail CSV files')
    parser.add_argument('--property', type=str, help='Property ID to filter reports (e.g., WAT)')
    parser.add_argument('--year', type=str, help='Reconciliation year to filter reports (e.g., 2024)')
    parser.add_argument('--debug', action='store_true', help='Enable verbose debug output')
    parser.add_argument('--debug_gl', action='store_true', help='Enable debugging for GL detail processing')
    parser.add_argument('--log_file', type=str, help='Path to save detailed debug logs')
    parser.add_argument('--tenant_id', type=str, help='Process only a specific tenant ID')
    parser.add_argument('--verify_csv', action='store_true', help='Verify CSV structure before processing')
    parser.add_argument('--integration_mode', action='store_true', help='Add extra debugging for New Full.py integration')
    parser.add_argument('--no_combined_pdf', action='store_true', help='Skip generating combined PDF')
    parser.add_argument('--force_combined_pdf', action='store_true', help='Force generating combined PDF at the end')
    
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
                    "cam_net_total", "admin_fee_raw", "subtotal_after_tenant_share", "tenant_share_amount"
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
    
    # Always create combined PDF if any letters were generated successfully and auto_combine_pdf is True
    letter_dir = None
    if successful > 0:
        print(f"\n=== Letter Generation Complete ===\nSuccessfully generated: {successful} of {total} letters")
        print(f"Letters saved in: {LETTERS_DIR}")
        
        # Check if auto_combine_pdf flag is set to True (default value if not specified)
        # Get no_combined_pdf from args if available
        no_combined_pdf = getattr(args, 'no_combined_pdf', False) if 'args' in locals() else False
        auto_combine_setting = results_dict.get('auto_combine_pdf', True)
        print(f"Auto combine PDF setting in results_dict: {auto_combine_setting} (type: {type(auto_combine_setting)})")
        print(f"no_combined_pdf value: {no_combined_pdf} (type: {type(no_combined_pdf)})")
        print(f"auto_combine_setting == False: {auto_combine_setting == False}")
        print(f"Condition evaluation: {no_combined_pdf or auto_combine_setting == False}")
        
        if no_combined_pdf or auto_combine_setting == False:
            print(f"Skipping PDF combination as requested")
        else:
            # Force PDF combination for reconciliation process
            print("Starting automatic PDF combination process...")
            
            # First try using the combine_pdfs.py script directly
            try:
                # Import combine_pdfs module
                import importlib.util
                script_dir = Path(__file__).parent.absolute()
                combine_pdfs_path = script_dir / 'combine_pdfs.py'
                
                if not os.path.exists(combine_pdfs_path):
                    # Try looking in the current working directory
                    cwd_path = Path.cwd() / 'combine_pdfs.py'
                    if os.path.exists(cwd_path):
                        combine_pdfs_path = cwd_path
                
                if os.path.exists(combine_pdfs_path):
                    print(f"Found combine_pdfs.py at {combine_pdfs_path}")
                    # Import the module
                    spec = importlib.util.spec_from_file_location("combine_pdfs", combine_pdfs_path)
                    combine_pdfs_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(combine_pdfs_module)
                    
                    # Determine which letter directory we just wrote to
                    letter_dir = LETTERS_DIR / "CAM" / property_id / recon_year
                    pdf_dir = letter_dir / "PDFs"
                    
                    if pdf_dir.exists():
                        print(f"Found PDF directory: {pdf_dir}")
                        # Call combine_pdfs with filtering for non-zero amounts
                        result = combine_pdfs_module.combine_pdfs(
                            str(pdf_dir),
                            expected_count=total,
                            filter_func=combine_pdfs_module.has_nonzero_amount_due,
                            additional_output_name="NonZeroDue",
                            output_subfolder="Combined"
                        )
                        
                        if result:
                            print(f"Successfully combined PDFs with filtering for property {property_id} year {recon_year}")
                            return
                
                # Continue with original directory logic as fallback
                # Create the letter directory path
                # Determine which letter directory we just wrote to
                # We need to find the property ID and year to locate the directory
            except Exception as e:
                print(f"Error using combine_pdfs.py module: {str(e)}")
                
            # Fallback to traditional method
            try:
                # First, try to determine the letter directory from tenant data
                tenant_data = []
                property_id = args.property  # Try to use from command line first
                recon_year = args.year  # Try to use from command line first
                
                # If not specified on command line, extract from CSV
                if not property_id or not recon_year:
                    with open(csv_report_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        tenant_data = list(reader)
                        
                    if tenant_data:
                        # Extract property ID and year from the first row
                        if not property_id:
                            property_id = tenant_data[0].get("property_id", "")
                        if not recon_year:
                            recon_year = tenant_data[0].get("reconciliation_year", "")
                
                # If we have property ID and year, proceed with combining PDFs
                if property_id and recon_year:
                    letter_dir = LETTERS_DIR / "CAM" / property_id / recon_year
                    print(f"Letter directory: {letter_dir}")
                    if letter_dir.exists():
                        combine_tenant_pdfs(letter_dir, expected_pdf_count=None)
                    else:
                        print(f"Letter directory does not exist: {letter_dir}")
                else:
                    print(f"Could not determine property ID ({property_id}) or reconciliation year ({recon_year})")
            except Exception as e:
                print(f"Error creating combined PDF: {str(e)}")
                import traceback
                traceback.print_exc()
    
    # No need to print here as we've already printed above
    
    # One last attempt to create combined PDF if it hasn't been done yet
    # Get no_combined_pdf from args if available
    no_combined_pdf = getattr(args, 'no_combined_pdf', False) if 'args' in locals() else False
    force_combined_pdf = getattr(args, 'force_combined_pdf', False) if 'args' in locals() else False
    auto_combine_pdf = results_dict.get('auto_combine_pdf', True)  # Use True as default
    print(f"Final attempt - auto_combine_pdf setting: {auto_combine_pdf}, force_combined_pdf: {force_combined_pdf}")
    
    # Add one extra, very verbose debug statement
    print("\n=== PDF AUTO-COMBINE ENVIRONMENT CHECK ===")
    import subprocess, shutil, sys, os
    from pathlib import Path
    try:
        gs_path = shutil.which('gs')
        print(f"Ghostscript path: {gs_path}")
        gs_version = subprocess.check_output(['gs', '--version'], text=True).strip()
        print(f"Ghostscript version: {gs_version}")
    except Exception as e:
        print(f"Error checking Ghostscript: {str(e)}")
        
    try:
        import PyPDF2
        print(f"PyPDF2 version: {PyPDF2.__version__}")
    except ImportError:
        print("PyPDF2 not available")
    
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Letters directory: {LETTERS_DIR}")
    if property_id and recon_year:
        print(f"Expected PDF directory: {LETTERS_DIR / 'CAM' / property_id / recon_year / 'PDFs'}")
        print(f"Directory exists: {(LETTERS_DIR / 'CAM' / property_id / recon_year / 'PDFs').exists()}")
    print("=== END ENVIRONMENT CHECK ===")
    
    # Always try to create combined PDF if auto_combine_pdf is explicitly set to True or force_combined_pdf is set
    print(f"\n=== PDF Combination Decision ===")
    print(f"successful: {successful}, property_id: {property_id}, recon_year: {recon_year}")
    print(f"auto_combine_pdf: {auto_combine_pdf} (type: {type(auto_combine_pdf)})")
    print(f"force_combined_pdf: {force_combined_pdf}")
    print(f"no_combined_pdf: {no_combined_pdf}")
    print(f"Decision condition: {successful > 0 and property_id and recon_year and (auto_combine_pdf or force_combined_pdf or not no_combined_pdf)}")
    
    if successful > 0 and property_id and recon_year and (auto_combine_pdf or force_combined_pdf or not no_combined_pdf):
        print("PDF combination WILL be attempted")
        try:
            letter_dir_final = LETTERS_DIR / "CAM" / property_id / recon_year
            print(f"Final letter directory path: {letter_dir_final}")
            if letter_dir_final.exists():
                # Make sure PDF directory exists
                pdf_dir_path = letter_dir_final / "PDFs"
                print(f"Checking PDF directory: {pdf_dir_path}")
                if not pdf_dir_path.exists():
                    print(f"Warning: PDF directory doesn't exist at {pdf_dir_path}")
                
                # Make sure Combined directory exists
                combined_dir_path = pdf_dir_path / "Combined"
                print(f"Checking Combined directory: {combined_dir_path}")
                try:
                    combined_dir_path.mkdir(exist_ok=True, parents=True)
                    print(f"Combined directory created or exists at: {combined_dir_path}")
                except Exception as dir_err:
                    print(f"Error creating Combined directory: {str(dir_err)}")
                print(f"\n=== Direct PDF Combination Attempt ===")
                # Try the most direct method possible
                import subprocess, os, sys
                from pathlib import Path
                try:
                    # Import combine_pdfs module directly
                    import importlib.util
                    
                    # Direct subprocess call to combine_pdfs.py
                    pdf_dir = letter_dir_final / "PDFs"
                    print(f"PDF directory: {pdf_dir}")
                    print(f"Directory exists: {pdf_dir.exists()}")
                    
                    # Find combine_pdfs.py
                    script_dir = Path(__file__).parent.absolute()
                    combine_pdfs_path = script_dir / 'combine_pdfs.py'
                    if not os.path.exists(combine_pdfs_path):
                        combine_pdfs_path = Path(os.getcwd()) / 'combine_pdfs.py'
                    print(f"combine_pdfs.py path: {combine_pdfs_path}")
                    print(f"File exists: {os.path.exists(combine_pdfs_path)}")
                    
                    if os.path.exists(combine_pdfs_path):
                        # Try to import and use the module directly first
                        try:
                            spec = importlib.util.spec_from_file_location("combine_pdfs", combine_pdfs_path)
                            combine_pdfs_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(combine_pdfs_module)
                            
                            print("Using combine_pdfs module directly")
                            # Call combine_pdfs with filtering for non-zero amounts
                            result = combine_pdfs_module.combine_pdfs(
                                str(pdf_dir),
                                expected_count=total,
                                filter_func=combine_pdfs_module.has_nonzero_amount_due,
                                additional_output_name="NonZeroDue",
                                output_subfolder="Combined"
                            )
                            
                            if result:
                                print(f"Successfully combined PDFs with filtering for property {property_id} year {recon_year}")
                                combined_dir = pdf_dir / "Combined"
                                output_file = combined_dir / f"All_{property_id}_{recon_year}_Letters.pdf"
                                nonzero_file = combined_dir / f"All_{property_id}_{recon_year}_Letters_NonZeroDue.pdf"
                                
                                if output_file.exists():
                                    print(f"✅ Combined PDF created successfully: {output_file}")
                                    print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
                                
                                if nonzero_file.exists():
                                    print(f"✅ Non-zero due PDF created successfully: {nonzero_file}")
                                    print(f"   Size: {nonzero_file.stat().st_size / 1024:.1f} KB")
                                    
                                return
                        except Exception as module_error:
                            print(f"Error using module directly: {str(module_error)}")
                    
                    # Fallback to subprocess call
                    print("Falling back to subprocess call")
                    expected_count = total if total > 0 else None
                    cmd = [sys.executable, str(combine_pdfs_path), str(pdf_dir.absolute()), str(expected_count), "true"]
                    print(f"Running command: {' '.join(cmd)} (expected {expected_count} PDFs with non-zero filtering)")
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                    
                    # Check if it worked
                    combined_dir = pdf_dir / "Combined"
                    output_file = combined_dir / f"All_{property_id}_{recon_year}_Letters.pdf"
                    if output_file.exists():
                        print(f"Success! Created {output_file}")
                    else:
                        print(f"Failed to create {output_file}")
                except Exception as e:
                    print(f"Error in direct combination: {str(e)}")
                    import traceback
                    traceback.print_exc()
                print(f"\n=== Final Attempt for Combined PDF ===\nTrying to create combined PDF for {property_id} {recon_year}")
                # Use direct subprocess call first - most reliable method
                pdf_path = letter_dir_final / "PDFs" / f"All_{property_id}_{recon_year}_Letters.pdf"
                print(f"Running combine_pdfs.py directly for reliability")
                import subprocess
                import os
                import sys
                from pathlib import Path
                try:
                    # Find combine_pdfs.py in current directory or project root
                    script_dir = Path(__file__).parent.absolute()
                    combine_pdfs_path = script_dir / 'combine_pdfs.py'
                    
                    if not os.path.exists(combine_pdfs_path):
                        # Try looking in the current working directory
                        cwd_path = Path.cwd() / 'combine_pdfs.py'
                        if os.path.exists(cwd_path):
                            combine_pdfs_path = cwd_path
                    
                    print(f"Using combine_pdfs.py at: {combine_pdfs_path}")
                    
                    # Use absolute paths for everything and expected tenant count with non-zero filtering
                    pdf_dir_abs = letter_dir_final / "PDFs"
                    expected_count = total if total > 0 else None
                    result = subprocess.run([sys.executable, str(combine_pdfs_path), 
                                           str(pdf_dir_abs.absolute()), str(expected_count), "true"], 
                                          check=True, capture_output=True, text=True)
                    print(result.stdout)
                    if pdf_path.exists():
                        print(f"✅ Combined PDF created successfully: {pdf_path}")
                        print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")
                    else:
                        # Fallback to internal combine_tenant_pdfs function
                        print(f"Direct method didn't create PDF, falling back to internal method")
                        pdf_success = combine_tenant_pdfs(letter_dir_final, expected_pdf_count=total)
                        if pdf_success and pdf_path.exists():
                            print(f"✅ Fallback method successful! Combined PDF exists: {pdf_path}")
                            print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")
                        else:
                            print(f"❌ All PDF combination methods failed")
                except Exception as e:
                    print(f"❌ Direct PDF combination failed: {str(e)}")
                    # Fallback to internal combine_tenant_pdfs function
                    print(f"Falling back to internal method...")
                    pdf_success = combine_tenant_pdfs(letter_dir_final, expected_pdf_count=total)
                    if pdf_success and pdf_path.exists():
                        print(f"✅ Fallback method successful! Combined PDF exists: {pdf_path}")
                        print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")
        except Exception as e:
            print(f"Note: Could not create combined PDF in final attempt: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return successful, total

def combine_latest_pdfs(property_id=None, year=None):
    """Combine PDFs from the most recent run."""
    try:
        print("\n=== Combining Latest PDFs ===")
        
        # Find latest letter directory
        if not property_id or not year:
            # Find most recent directory in Letters/CAM
            latest_dir = None
            latest_time = 0
            for prop_dir in (LETTERS_DIR / "CAM").glob("*"):
                if not prop_dir.is_dir():
                    continue
                    
                for year_dir in prop_dir.glob("*"):
                    if not year_dir.is_dir():
                        continue
                        
                    pdf_dir = year_dir / "PDFs"
                    if not pdf_dir.exists() or not pdf_dir.is_dir():
                        continue
                        
                    dir_time = pdf_dir.stat().st_mtime
                    if dir_time > latest_time:
                        latest_time = dir_time
                        latest_dir = pdf_dir
            
            if latest_dir:
                print(f"Found latest PDF directory: {latest_dir}")
                combine_tenant_pdfs(latest_dir.parent, expected_pdf_count=None)
            else:
                print("No PDF directories found")
        else:
            # Use specified property and year
            letter_dir = LETTERS_DIR / "CAM" / property_id / year
            if letter_dir.exists():
                print(f"Using specified directory: {letter_dir}")
                combine_tenant_pdfs(letter_dir, expected_pdf_count=None)
            else:
                print(f"Specified directory does not exist: {letter_dir}")
    except Exception as e:
        print(f"Error combining PDFs: {str(e)}")
        import traceback
        traceback.print_exc()

def ensure_combined_pdfs(property_id=None, year=None):
    """Force combination of PDFs for the specified property and year."""
    print("\n=== FORCING PDF COMBINATION ===")
    if not property_id or not year:
        print("Property ID and year are required")
        return False
    
    from pathlib import Path
    letters_dir = Path(__file__).parent / "Letters"
    letter_dir = letters_dir / "CAM" / property_id / year
    
    if not letter_dir.exists():
        print(f"Letter directory does not exist: {letter_dir}")
        return False
        
    pdf_dir = letter_dir / "PDFs"
    if not pdf_dir.exists():
        print(f"PDF directory does not exist: {pdf_dir}")
        return False
        
    # Create Combined directory with full path creation
    combined_dir = pdf_dir / "Combined"
    print(f"Ensuring Combined directory exists: {combined_dir}")
    combined_dir.mkdir(exist_ok=True, parents=True)
    
    # Import combine_pdfs module directly
    import importlib.util
    from pathlib import Path
    
    # Find combine_pdfs.py
    combine_pdfs_path = Path(__file__).parent / "combine_pdfs.py"
    print(f"Looking for combine_pdfs.py at: {combine_pdfs_path}")
    
    if not combine_pdfs_path.exists():
        print(f"combine_pdfs.py not found at {combine_pdfs_path}")
        return False
        
    # Import module
    print("Running combine_pdfs with virtual environment...")
    try:
        # Use virtual environment Python if available (check both .venv and venv)
        venv_python = Path.cwd() / ".venv" / "bin" / "python3"
        if not venv_python.exists():
            venv_python = Path.cwd() / "venv" / "bin" / "python3"
        if not venv_python.exists():
            venv_python = Path.cwd() / "venv" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else "python3"
        
        # Run combine_pdfs.py as subprocess with virtual environment
        result = subprocess.run([
            python_cmd, str(combine_pdfs_path), 
            str(pdf_dir), 
            "9",  # expected count
            "true"  # filter for non-zero amounts
        ], capture_output=True, text=True, cwd=Path.cwd())
        
        if result.returncode == 0:
            print("PDF combination completed successfully")
        else:
            print(f"PDF combination failed: {result.stderr}")
            print(f"stdout: {result.stdout}")
        
        return result
    except Exception as e:
        print(f"Error in ensure_combined_pdfs: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--combine":
        # Just combine PDFs from the most recent run
        prop_id = sys.argv[2] if len(sys.argv) > 2 else None
        year = sys.argv[3] if len(sys.argv) > 3 else None
        combine_latest_pdfs(prop_id, year)
    elif len(sys.argv) > 1 and sys.argv[1] == "--force-combine":
        # Force combine PDFs for a specific property and year
        prop_id = sys.argv[2].upper() if len(sys.argv) > 2 else None
        year = sys.argv[3] if len(sys.argv) > 3 else None
        ensure_combined_pdfs(prop_id, year)
    else:
        main()