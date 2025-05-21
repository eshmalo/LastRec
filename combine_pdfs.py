#!/usr/bin/env python3
"""
Simple utility to combine PDF files in a directory.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

def combine_pdfs(directory_path, expected_count=None, max_wait_seconds=60, check_interval=2):
    """
    Combine all PDFs in a directory into one file.
    
    Args:
        directory_path: Path to directory containing PDFs
        expected_count: Expected number of PDF files to wait for (if None, combine immediately)
        max_wait_seconds: Maximum time to wait for expected files
        check_interval: Time between checks for new files
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
            output_file = pdf_dir / f"All_{property_id}_{year}_Letters.pdf"
        except:
            # Fallback name if directory structure is not as expected
            output_file = pdf_dir / "All_Combined_Letters.pdf"
            
        print(f"Found {len(pdf_files)} PDF files to combine")
        print(f"Output file will be: {output_file}")
        
        # Execute gs command
        original_dir = os.getcwd()
        try:
            # Change to the PDF directory to avoid path issues
            os.chdir(pdf_dir)
            
            # Build gs command
            cmd = ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", f"-sOutputFile={output_file.name}"]
            cmd.extend([f.name for f in pdf_files])
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Execute the command
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                # The file is created in the current directory (pdf_dir), not at the original path
                local_output_file = Path(output_file.name)
                print(f"Successfully combined {len(pdf_files)} PDFs into {local_output_file}")
                try:
                    print(f"File size: {local_output_file.stat().st_size / 1024:.1f} KB")
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
                    for pdf_file in [Path(pdf_dir) / f.name for f in pdf_files]:
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
                print(f"Error combining PDFs: {str(e)}")
                return False
        finally:
            # Make sure we go back to the original directory
            os.chdir(original_dir)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # If run directly, take a directory argument
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        expected_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
        combine_pdfs(directory, expected_count=expected_count)
    else:
        print("Usage: python combine_pdfs.py <directory_containing_pdfs> [expected_pdf_count]")