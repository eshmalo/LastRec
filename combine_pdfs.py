#!/usr/bin/env python3
"""
Utility to combine PDF files in a directory with filtering capabilities.
"""

import sys
import os
import subprocess
import time
import re
import shutil
import PyPDF2
from pathlib import Path

def combine_pdfs(directory_path, expected_count=None, max_wait_seconds=60, check_interval=2, 
                 filter_func=None, output_subfolder="Combined", additional_output_name=None):
    """
    Combine all PDFs in a directory into one file, with optional filtering.
    
    Args:
        directory_path: Path to directory containing PDFs
        expected_count: Expected number of PDF files to wait for (if None, combine immediately)
        max_wait_seconds: Maximum time to wait for expected files
        check_interval: Time between checks for new files
        filter_func: Optional function to filter PDFs. Takes PDF path, returns boolean.
        output_subfolder: Subfolder to store combined PDFs (created if doesn't exist)
        additional_output_name: Optional name suffix for additional filtered output
    """
    try:
        # Ensure the directory exists
        print(f"Starting PDF combination in directory: {directory_path}")
        pdf_dir = Path(directory_path)
        if not pdf_dir.exists():
            print(f"Directory does not exist: {pdf_dir}")
            return False
        
        # Wait for expected number of PDFs if specified
        if expected_count is not None and expected_count > 0:
            print(f"Waiting for {expected_count} PDF files to be generated...")
            wait_start_time = time.time()
            while time.time() - wait_start_time < max_wait_seconds:
                # Get all PDF files except ones starting with 'All_'
                pdf_files = [f for f in pdf_dir.glob("*.pdf") if not f.name.startswith("All_")]
                current_count = len(pdf_files)
                
                if current_count >= expected_count:
                    print(f"Found all {current_count} expected PDF files")
                    break
                    
                print(f"Found {current_count} of {expected_count} PDF files, waiting {check_interval} seconds...")
                time.sleep(check_interval)
            
            elapsed_time = time.time() - wait_start_time
            if elapsed_time >= max_wait_seconds:
                print(f"Warning: Timed out after {max_wait_seconds} seconds, proceeding with {current_count} of {expected_count} PDF files")
        
        # Get all PDF files except ones starting with 'All_'
        pdf_files = [f for f in pdf_dir.glob("*.pdf") if not f.name.startswith("All_")]
        
        if not pdf_files:
            print(f"No PDF files found in {pdf_dir}")
            return False
        
        # Get property and year from directory structure
        try:
            property_id = pdf_dir.parent.parent.name
            year = pdf_dir.parent.name
            base_name = f"All_{property_id}_{year}_Letters"
        except:
            # Fallback name if directory structure is not as expected
            base_name = "All_Combined_Letters"
        
        # Create output subfolder if it doesn't exist
        output_dir = pdf_dir / output_subfolder
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{base_name}.pdf"
            
        print(f"Found {len(pdf_files)} PDF files to combine")
        print(f"Output file will be: {output_file}")
        
        # Copy all PDFs and create main combined PDF
        success = _create_combined_pdf(pdf_dir, pdf_files, output_file)
        
        # If filtering function provided, create additional filtered PDF
        if filter_func is not None and additional_output_name is not None and success:
            try:
                # Apply filter to PDFs
                filtered_pdfs = [f for f in pdf_files if filter_func(f)]
                if filtered_pdfs:
                    filtered_output = output_dir / f"{base_name}_{additional_output_name}.pdf"
                    print(f"Creating filtered PDF with {len(filtered_pdfs)} files: {filtered_output}")
                    _create_combined_pdf(pdf_dir, filtered_pdfs, filtered_output)
                else:
                    print(f"No PDFs matched the filter criteria for {additional_output_name}")
            except Exception as e:
                print(f"Error creating filtered PDF: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return success
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def _create_combined_pdf(pdf_dir, pdf_files, output_file):
    """Helper function to create a combined PDF file from a list of PDF files."""
    original_dir = os.getcwd()
    try:
        # Change to the PDF directory to avoid path issues
        os.chdir(pdf_dir)
        
        # Build gs command
        cmd = ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", f"-sOutputFile={output_file}"]
        cmd.extend([str(f.relative_to(pdf_dir)) for f in pdf_files])
        
        print(f"Running command: {' '.join(cmd)}")
        
        # Execute the command
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"Successfully combined {len(pdf_files)} PDFs into {output_file}")
            try:
                print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
            except Exception as e:
                print(f"Warning: Could not get file size: {str(e)}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error executing gs command: {e}")
            print(f"Command output: {e.stdout}")
            print(f"Command error: {e.stderr}")
            # Try using PyPDF2 as a fallback
            try:
                from PyPDF2 import PdfMerger
                print("Falling back to PyPDF2 for PDF merging...")
                merger = PdfMerger()
                for pdf_file in pdf_files:
                    print(f"Adding {pdf_file}")
                    merger.append(str(pdf_file))
                
                # Ensure parent directory exists
                output_file.parent.mkdir(exist_ok=True)
                merger.write(str(output_file))
                merger.close()
                print(f"Successfully combined PDFs using PyPDF2 into {output_file}")
                return True
            except Exception as pdf_error:
                print(f"PyPDF2 fallback failed: {pdf_error}")
                return False
        except Exception as e:
            print(f"Error combining PDFs: {str(e)}")
            return False
    finally:
        # Make sure we go back to the original directory
        os.chdir(original_dir)

def has_nonzero_amount_due(pdf_path):
    """
    Check if a PDF has a non-zero 'ADDITIONAL AMOUNT DUE' value.
    Returns True if amount > 0, False otherwise.
    """
    try:
        # Use PyPDF2 to extract text from the PDF
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            # Look for the ADDITIONAL AMOUNT DUE line
            pattern = r'ADDITIONAL\s+AMOUNT\s+DUE.*?(\$\s*[\d,]+\.\d+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                # Extract the dollar amount and convert to float
                amount_str = match.group(1).replace('$', '').replace(',', '').strip()
                amount = float(amount_str)
                print(f"Found ADDITIONAL AMOUNT DUE: ${amount:.2f} in {pdf_path.name}")
                return amount > 0
            else:
                print(f"No ADDITIONAL AMOUNT DUE found in {pdf_path.name}")
                return False
    except Exception as e:
        print(f"Error checking amount due in {pdf_path.name}: {str(e)}")
        return False

if __name__ == "__main__":
    # If run directly, take a directory argument
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        expected_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
        
        # Check if we should filter for non-zero amounts
        filter_nonzero = len(sys.argv) > 3 and sys.argv[3].lower() == 'true'
        
        if filter_nonzero:
            print("Will create additional PDF with non-zero ADDITIONAL AMOUNT DUE")
            combine_pdfs(
                directory, 
                expected_count=expected_count, 
                filter_func=has_nonzero_amount_due,
                additional_output_name="NonZeroDue"
            )
        else:
            combine_pdfs(directory, expected_count=expected_count)
    else:
        print("Usage: python combine_pdfs.py <directory_containing_pdfs> [expected_pdf_count] [filter_nonzero]")