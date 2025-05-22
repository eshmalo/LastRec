# Letter Generator Improvements

## Fixes and Enhancements

The enhanced letter generator (`enhanced_letter_generator.py`) has been updated to handle various edge cases and to provide more robust debugging information. The following fixes have been implemented:

1. **Better handling of FORMULA EXPLANATIONS rows**:
   - Special handling for rows with gl_account = "FORMULA EXPLANATIONS:"
   - Filtering out rows where combined_gross = "Direct value"
   - Improved error handling for non-numeric values

2. **Enhanced filtering for NEGATIVE BALANCE sections**:
   - Detecting and skipping the "--- NEGATIVE BALANCE ACCOUNTS (EXCLUDED) ---" header
   - Tracking when we're inside a negative balance section
   - Skipping rows with "NEGATIVE BALANCE" in the exclusion_categories field

3. **Improved GL total row handling**:
   - Capturing the TOTAL row regardless of its position in the file
   - Additional fallback methods for finding the total if not explicitly marked
   - Preserving the total row even when in a NEGATIVE BALANCE section

4. **More robust debugging options**:
   - Added --log_file option for capturing detailed logs
   - Added --verify_csv option to check CSV structure before processing
   - Added --integration_mode flag for additional debugging when run from New Full.py
   - Added --tenant_id option to process only a specific tenant

5. **Testing and Verification**:
   - Created test_gl_processing.py to verify correct handling of edge cases
   - Added comprehensive debugging output to help identify issues

## Using the New Options

The enhanced letter generator now supports the following command-line options:

```
usage: enhanced_letter_generator.py [-h] [--csv CSV] [--gl_dir GL_DIR] [--property PROPERTY] 
                                    [--year YEAR] [--debug] [--log_file LOG_FILE] 
                                    [--tenant_id TENANT_ID] [--verify_csv] [--integration_mode]

Generate CAM reconciliation letters with LaTeX

options:
  -h, --help            show this help message and exit
  --csv CSV             Path to reconciliation CSV file (if not provided, finds most recent)
  --gl_dir GL_DIR       Directory containing GL detail CSV files
  --property PROPERTY   Property ID to filter reports (e.g., WAT)
  --year YEAR           Reconciliation year to filter reports (e.g., 2024)
  --debug               Enable verbose debug output
  --log_file LOG_FILE   Path to save detailed debug logs
  --tenant_id TENANT_ID Process only a specific tenant ID
  --verify_csv          Verify CSV structure before processing
  --integration_mode    Add extra debugging for New Full.py integration
```

## Examples

### Basic Usage (Direct Run)
```bash
# Generate letters for most recent CSV report
python enhanced_letter_generator.py

# Generate letters for a specific CSV with GL detail directory
python enhanced_letter_generator.py --csv /path/to/tenant_billing.csv --gl_dir /path/to/gl_details
```

### Debugging Issues
```bash
# Process a single tenant with detailed debugging
python enhanced_letter_generator.py --tenant_id 1336 --debug --log_file debug.log

# Verify CSV structure and enable integration mode debugging
python enhanced_letter_generator.py --verify_csv --integration_mode --debug

# Test GL detail processing
python test_gl_processing.py
```

## Integration with New Full.py

When running the letter generator from New Full.py, it's recommended to add the `--integration_mode` flag to enable additional diagnostics. This will help identify any issues with file paths, directory structures, or data formats.

```python
# Example code snippet for integrating with New Full.py
from enhanced_letter_generator import generate_letters_from_results

# Prepare results dictionary
results_dict = {
    'csv_report_path': csv_report_path,
    'gl_dir': gl_detail_directory,
    'debug_mode': True,
    'integration_mode': True,
    'specific_tenant_id': None  # Set to a tenant ID for testing
}

# Generate letters
successful, total = generate_letters_from_results(results_dict)
```

## Verifying Output

The letter generator will produce more detailed logs to help identify issues:
- Each GL detail processing step is logged with [GL file] prefix
- Each tenant letter generation step is logged with tenant ID information
- When integration_mode is enabled, additional directory structure information is shown
- If a letter fails to generate, detailed error information is provided

This should make it easier to diagnose issues when running through New Full.py versus running directly.