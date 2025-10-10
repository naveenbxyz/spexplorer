# Excel Processing Usage Guide

This guide explains how to use the Excel parsing and pattern discovery features.

## Overview

The Excel processing pipeline helps you:
1. **Download** Excel files from SharePoint with folder structure preservation
2. **Parse** files to identify table structures (handles polymorphic formats)
3. **Store** results in SQLite with folder hierarchy (Country/Client/Product)
4. **Analyze** patterns across thousands of files

## Workflow

### Step 1: Download Files from SharePoint

1. Connect to SharePoint using the sidebar
2. Enter your folder path (e.g., `Document Library/Secure Area/Client Folders`)
3. Select "Recursive (All Subfolders)" search mode
4. Enter filename patterns (e.g., `Form, Template, Onboarding`)
5. **Enable "Download & Save Files"** checkbox
6. Click "Search for Files"

The files will be downloaded to `./output` with this structure:
```
output/
├── USA/
│   ├── Acme Corp/
│   │   ├── Product A/
│   │   │   └── ClientForm.xlsx
│   │   └── Product B/
│   │       └── OnboardingTemplate.xlsx
│   └── Widget Inc/
│       └── ...
└── Canada/
    └── ...
```

### Step 2: Process Downloaded Files

#### Option A: Using the Streamlit UI

1. Navigate to the **"Excel File Processing"** section
2. Go to the **"Process Files"** tab
3. Verify the output folder path
4. Click **"Start Batch Processing"**

Watch the progress bar as files are processed:
- ✅ Successful parses
- ❌ Failed parses with error messages
- Real-time statistics

#### Option B: Using Command Line

```bash
python batch_processor.py ./output --db excel_data.db
```

Options:
- `--reprocess`: Reprocess files that were already processed
- `--db`: Specify database path (default: excel_data.db)

### Step 3: Analyze Results

#### View Overall Statistics

Go to the **"Analysis"** tab to see:
- Total files, sheets, tables
- Processing status (completed/pending/failed)
- Number of unique patterns discovered
- Country and client counts

#### View Folder Structure

The folder summary shows:
- Files per country/client/product
- Processing completion rates
- Failed file counts

Download as CSV for further analysis.

#### Search by Header

Use the search box to find all tables containing a specific header:

Example searches:
- "Customer_Name"
- "Product_ID"
- "Date"
- "Total_Amount"

Results show:
- Which files contain that header
- Sheet names
- Table row counts
- Full folder paths (country/client/product)

#### Discover Patterns

Go to the **"Pattern Discovery"** tab to see:

- **Pattern Groups**: Similar table structures grouped together
- **Occurrence Counts**: How many times each pattern appears
- **Sample Headers**: What columns each pattern contains
- **Timeline**: When patterns were first/last seen

This helps you:
- Identify the most common form templates
- Find outlier/unusual structures
- Track form version changes over time
- Group files by structure for automated processing

## Understanding Table Detection

### What Gets Detected

The parser identifies:
- **Table boundaries**: Where tables start and end
- **Header rows**: Column names
- **Data regions**: Actual data rows
- **Multiple tables**: Handles sheets with multiple tables

### Pattern Signatures

Each detected table gets a signature hash based on:
- Column headers (if detected)
- Number of columns
- Row count range (bucketed)

Tables with identical signatures likely use the same template.

## Database Structure

### Files Table
```sql
SELECT * FROM files WHERE folder_country = 'USA';
```

Columns:
- `filename`, `file_path`
- `folder_country`, `folder_client`, `folder_product`
- `processing_status` (pending/completed/failed)
- `processed_date`, `processing_error`

### Sheets Table
```sql
SELECT * FROM sheets WHERE file_id = 1;
```

Columns:
- `sheet_name`, `sheet_index`
- `total_rows`, `total_columns`
- `tables_detected`

### Tables Table
```sql
SELECT * FROM tables WHERE pattern_signature = 'abc123...';
```

Columns:
- `start_row`, `end_row`, `start_col`, `end_col`
- `header_detected`, `row_count`, `column_count`
- `pattern_signature`
- `headers_json`: Array of column names
- `full_data_json`: Complete table data

### Pattern Analysis Table
```sql
SELECT * FROM pattern_analysis ORDER BY occurrence_count DESC;
```

Columns:
- `pattern_signature`: Unique hash
- `occurrence_count`: How many times seen
- `sample_headers_json`: Example column names
- `first_seen_date`, `last_seen_date`

## Advanced Queries

### Find All Files from a Specific Client

```python
from excel_database import ExcelDatabase

db = ExcelDatabase("excel_data.db")

db.cursor.execute("""
    SELECT filename, file_path, processed_date
    FROM files
    WHERE folder_client = 'Acme Corp'
    AND processing_status = 'completed'
""")

results = db.cursor.fetchall()
db.close()
```

### Get All Tables with Specific Structure

```python
db = ExcelDatabase("excel_data.db")

# Find all tables with a specific pattern
db.cursor.execute("""
    SELECT f.filename, s.sheet_name, t.headers_json, t.row_count
    FROM tables t
    JOIN sheets s ON t.sheet_id = s.sheet_id
    JOIN files f ON s.file_id = f.file_id
    WHERE t.pattern_signature = 'YOUR_PATTERN_HASH'
""")

results = db.cursor.fetchall()
db.close()
```

### Export Pattern Data

```python
db = ExcelDatabase("excel_data.db")
patterns = db.get_pattern_summary()

import json
with open('patterns.json', 'w') as f:
    json.dump(patterns, f, indent=2)

db.close()
```

## Performance Tips

### For Large File Sets (1000+ files)

1. **Process in batches**: The batch processor handles this automatically
2. **Monitor disk space**: Full JSON is stored per table
3. **Use indexes**: The database has indexes on key fields
4. **Reprocess selectively**: Only reprocess failed files

### Database Size Estimation

- Average file: ~100 KB in database
- 1000 files: ~100 MB database
- Includes full table JSON for each table

### Optimizing Pattern Discovery

To reduce pattern noise:
1. Filter by minimum occurrence count
2. Group patterns with similar headers manually
3. Assign pattern names for common templates

## Troubleshooting

### "No files to process"

- Ensure files were downloaded to the output folder first
- Check that "Download & Save Files" was enabled during search

### "Processing failed" errors

- Check file permissions
- Verify Excel files are not corrupted
- Look at specific error messages in the UI

### "Pattern signature null"

- File may have unusual structure
- Check if file is truly an Excel file
- Review the raw JSON output

### Database locked errors

- Close other connections to the database
- Ensure only one process is writing at a time
- The Streamlit app manages connections automatically

## Next Steps

After processing and pattern discovery:

1. **Name common patterns**: Add pattern names to the database
2. **Build ETL pipelines**: Use pattern signatures to route files to specific processors
3. **Data validation**: Compare new files against known patterns
4. **Compliance reporting**: Generate reports by country/client
5. **Template standardization**: Identify and standardize outlier formats

## Support

For issues or questions:
- Check TROUBLESHOOTING.md for common issues
- Review database schema in excel_database.py
- Examine sample outputs in the Analysis tab
