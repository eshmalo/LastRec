#!/usr/bin/env python3
"""
Script to compile the LaTeX letters to PDF files using a simpler approach.
"""

import os
import glob
import re
import subprocess
from pathlib import Path

def compile_to_pdf(tex_file, pdf_file):
    """Compile LaTeX file to PDF using texlive.net online service."""
    try:
        # Get LaTeX content
        with open(tex_file, 'r', encoding='utf-8') as f:
            latex_content = f.read()
        
        print(f"Compiling {tex_file} to PDF...")
        
        # Use texlive.net's API with curl
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
        with open(pdf_file, 'wb') as f:
            process = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE)
            stdout, stderr = process.communicate()
            f.write(stdout)
        
        # Check if the output is a valid PDF
        with open(pdf_file, 'rb') as f:
            content = f.read(4)
            if content == b'%PDF':
                print(f"✅ PDF generated successfully: {pdf_file}")
                return True
            else:
                # Not a valid PDF, might be an error log
                print(f"❌ Error in PDF generation. See error log.")
                # Save error log
                log_file = pdf_file.replace('.pdf', '_error.log')
                with open(log_file, 'wb') as f:
                    f.write(stdout)
                return False
    except Exception as e:
        print(f"❌ Error compiling PDF: {str(e)}")
        return False

def fix_latex_file(tex_file):
    """Fix common LaTeX issues in a file."""
    try:
        with open(tex_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Replace double dollar signs
        content = content.replace(r"\$$", r"\$")
        
        # Fix dollar signs in amounts
        content = re.sub(r'&\s+\\\$', r'& \$', content)
        
        # Fix negative amounts
        content = re.sub(r'&\s+\\\$-', r'& -\$', content)
        
        # Write fixed content back
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return True
    except Exception as e:
        print(f"Error fixing LaTeX file {tex_file}: {str(e)}")
        return False

def main():
    # Find all LaTeX files
    latex_files = glob.glob("Letters/CAM/WAT/2024/LaTeX/*.tex")
    
    if not latex_files:
        print("No LaTeX files found in Letters/CAM/WAT/2024/LaTeX/")
        return
    
    print(f"Found {len(latex_files)} LaTeX files to compile")
    
    # Process each file
    success_count = 0
    
    for tex_file in latex_files:
        # Create the PDF path
        pdf_file = tex_file.replace("/LaTeX/", "/PDFs/").replace(".tex", ".pdf")
        os.makedirs(os.path.dirname(pdf_file), exist_ok=True)
        
        # Fix LaTeX issues
        if fix_latex_file(tex_file):
            # Compile to PDF
            if compile_to_pdf(tex_file, pdf_file):
                success_count += 1
    
    print(f"\nCompilation complete: {success_count} of {len(latex_files)} PDFs generated successfully")
    print("Check Letters/CAM/WAT/2024/PDFs/ for the PDF files")

if __name__ == "__main__":
    main()