#!/usr/bin/env python3
"""
Simple test script for LaTeX compilation through texlive.net
"""

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
        print(f"LaTeX content saved to: {tex_file}")
        
        # Use texlive.net's API with curl
        print("Using texlive.net online compilation service...")
        
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
                print(f"PDF generated successfully: {output_file}")
                return True
            else:
                # Not a valid PDF, might be an error log
                print(f"Error in PDF generation. See error log.")
                # Save error log
                log_file = output_file.replace('.pdf', '_error.log')
                with open(log_file, 'wb') as f:
                    f.write(stdout)
                return False
    except Exception as e:
        print(f"Error compiling PDF: {str(e)}")
        return False

# Create a simple LaTeX document
simple_content = r"""\documentclass{article}
\usepackage{booktabs}
\begin{document}

\begin{center}
\begin{tabular}{@{}p{3in}r@{}}
\toprule
\textbf{Description} & \textbf{Amount} \\
\midrule
Total Property CAM Expenses & \$173,638.08 \\
Tenant's Pro-Rata Share (6.73\%) & \$11,644.82 \\
\midrule
\textbf{TOTAL} & \textbf{\$2,473.30} \\
\bottomrule
\end{tabular}
\end{center}

\end{document}"""

# Compile it
compile_to_pdf(simple_content, "test_simple.pdf")