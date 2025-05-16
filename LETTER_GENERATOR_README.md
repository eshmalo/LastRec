# CAM Reconciliation Letter Generators

This project includes two letter generator implementations:

1. **letter_generator.py** - The original text-based letter generator
2. **latex_letter_generator.py** - The new LaTeX-based letter generator that also supports PDF creation

## Requirements

For the LaTeX letter generator to compile PDFs:

- `curl` must be installed and accessible in your PATH
- Internet access (for the texlive.net API)

## Usage

### From Python Code

```python
from letter_generator import generate_tenant_letter as generate_text_letter
from latex_letter_generator import generate_tenant_letter as generate_latex_letter, compile_to_pdf

# Generate a text letter
letter_text = generate_text_letter(tenant_data, gl_detail_file, debug_mode=True)

# Generate a LaTeX letter and compile to PDF
latex_content, pdf_path, tex_path = generate_latex_letter(tenant_data, gl_detail_file, debug_mode=True)
if compile_to_pdf(latex_content, pdf_path):
    print(f"PDF created: {pdf_path}")
```

### From New Full.py

In New Full.py, you can use the `generate_letters_from_results` function from either module:

```python
# For text letters
from letter_generator import generate_letters_from_results

# OR for LaTeX/PDF letters
from latex_letter_generator import generate_letters_from_results

# At the end of the reconciliation process
success_count, total_count = generate_letters_from_results(results_dict)
```

## Customization

Both letter generators use the same configuration values:

- **LETTERS_DIR**: Base directory for letter output
- **PROPERTY_NAMES**: Mapping of property codes to full names
- **CONTACT_INFO**: Contact information for the letter footer

You can customize these values by modifying the relevant module.

## Testing

To test the letter generators, use the provided test scripts:

```bash
# Test the text letter generator
python test_letter_generator.py

# Test the LaTeX letter generator
python test_latex_letter.py
```

## Troubleshooting

### PDF Generation Issues

If PDF generation fails, check:

1. That `curl` is installed and working correctly
2. That you have internet access to reach texlive.net
3. The error log file (same name as the PDF with `_error.log` suffix)

### Letter Content Issues

Most letter content issues come from formatting problems in the tenant data. Ensure that:

1. Currency values include the `$` sign and proper formatting
2. Percentage values include the `%` sign
3. Dates use the format `YYYY-MM-DD`

## Local LaTeX Installation

If you have LaTeX installed locally (TeX Live or MiKTeX), you can modify the `compile_to_pdf` function to use the local pdflatex command instead of the online service.