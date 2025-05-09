#!/usr/bin/env python3
"""
Script to combine all Python files in the project into a single text file.
Each file is preceded by a header with its path.
"""

import os
import glob

def combine_python_files():
    # Output file path
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output", "combined_python_files.txt")
    
    # Ensure Output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Get all Python files in the project
    current_script = os.path.basename(__file__)
    py_files = []
    
    # Directories to exclude
    exclude_dirs = ["venv", ".venv", "env", ".env", "__pycache__", ".git"]
    
    # Walk through directories manually to have more control
    for root, dirs, files in os.walk("."):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith(".py") and file != current_script:
                full_path = os.path.join(root, file)
                # Convert to absolute path if it's not already
                if not os.path.isabs(full_path):
                    full_path = os.path.abspath(full_path)
                py_files.append(full_path)
    
    # Sort files for consistent output
    py_files.sort()
    
    # Combine all files
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for file_path in py_files:
            # Add a header with the file path
            header = f"\n{'='*80}\n{file_path}\n{'='*80}\n\n"
            outfile.write(header)
            
            # Add the file content
            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(content)
                    # Add a newline if the file doesn't end with one
                    if content and not content.endswith('\n'):
                        outfile.write('\n')
            except Exception as e:
                outfile.write(f"ERROR: Could not read file due to {str(e)}\n")
    
    print(f"Combined {len(py_files)} Python files into: {output_path}")
    return output_path

if __name__ == "__main__":
    combined_file = combine_python_files()
    print(f"Successfully created: {combined_file}")