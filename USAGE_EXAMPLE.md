# Usage Example: Finding Excel Files in Country-Specific Folders

This guide shows how to use the SharePoint Excel Explorer to recursively search through country-specific client folders.

## Scenario

You have a SharePoint structure like:
```
https://oursites.domain.com/sites/XXProducts/XX/
└── Document Library/
    └── Secure Area/
        └── Client Folders/
            ├── USA/
            │   ├── ClientA/
            │   │   ├── Reports/
            │   │   │   ├── Report_GGGG_2024.xlsx ✓
            │   │   │   └── Summary.xlsx
            │   │   └── Data/
            │   │       └── Data_PPPP_Jan.xlsx ✓
            │   └── ClientB/
            ├── UK/
            │   └── ClientC/
            │       └── Analysis_GGGG_Q1.xlsx ✓
            └── Germany/
                └── ClientD/
                    └── Forecast_PPPP_2024.xlsx ✓
```

You want to find all `.xlsx` files containing `GGGG` or `PPPP` in their names.

## Step-by-Step Instructions

### 1. Install and Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Windows Integrated Auth (for internal SharePoint)
pip install requests-negotiate-sspi

# Find your correct site URL
python test_url_format.py
```

When prompted, enter:
- **URL**: `https://oursites.domain.com/sites/XXProducts/XX`
- **Verify SSL**: `n` (if using self-signed certificates)
- **Auth method**: `1` (Windows Integrated)

This will confirm your site URL is correct.

### 2. Launch the App

```bash
streamlit run app.py
```

### 3. Configure Connection

**In the Streamlit sidebar:**

| Setting | Value |
|---------|-------|
| Site URL | `https://oursites.domain.com/sites/XXProducts/XX` |
| Authentication Method | Windows Integrated (Current User) |
| Verify SSL Certificate | ☐ Unchecked (for self-signed certs) |

Click **"Connect to SharePoint"**

You should see: ✅ Connected to: [Your Site Name]

### 4. Configure Search

**In the main area:**

| Setting | Value |
|---------|-------|
| Search Mode | ● Recursive (All Subfolders) |
| Folder Path | `Document Library/Secure Area/Client Folders` |
| Filename Patterns | `GGGG, PPPP` |

Click **"🔍 Search for Files"**

### 5. Monitor Progress

You'll see real-time updates:
```
🔄 Searching... Folders processed: 25 | Files found: 4
Current: /sites/XXProducts/XX/Document Library/Secure Area/Client Folders/USA/ClientA/Reports
```

### 6. Review Results

The app will display a table like:

| Filename | Folder | Full Path | Modified | Size (KB) | Modified By |
|----------|--------|-----------|----------|-----------|-------------|
| Report_GGGG_2024.xlsx | USA/ClientA/Reports | /sites/.../Client Folders/USA/ClientA/Reports | 2024-12-15 10:30:00 | 2,450 | John Doe |
| Data_PPPP_Jan.xlsx | USA/ClientA/Data | /sites/.../Client Folders/USA/ClientA/Data | 2024-12-10 14:22:00 | 1,230 | Jane Smith |
| Analysis_GGGG_Q1.xlsx | UK/ClientC | /sites/.../Client Folders/UK/ClientC | 2024-12-08 09:15:00 | 890 | Bob Wilson |
| Forecast_PPPP_2024.xlsx | Germany/ClientD | /sites/.../Client Folders/Germany/ClientD | 2024-12-12 16:45:00 | 3,100 | Anna Mueller |

✅ Found 4 Excel file(s) matching criteria

### 7. Export Results

Click **"📥 Download Results as CSV"** to save the file list with metadata.

The CSV will contain:
- Full folder paths (so you can identify Country/Client structure)
- All metadata (modified date, size, modified by)
- Ready for Excel/Python analysis

### 8. Extract Excel Content (Optional)

If you want to extract the actual data from any file:

1. Select a file from the dropdown (e.g., `Report_GGGG_2024.xlsx`)
2. Click **"🔍 Extract to JSON"**
3. View the JSON structure in the app
4. Click **"⬇️ Download JSON"** to save

## Example Output

### CSV Export (`sharepoint_files_20241215_143022.csv`)

```csv
Filename,Folder,Full Path,Modified,Size (KB),Modified By
Report_GGGG_2024.xlsx,USA/ClientA/Reports,/sites/XXProducts/XX/Document Library/Secure Area/Client Folders/USA/ClientA/Reports,2024-12-15 10:30:00,2450,John Doe
Data_PPPP_Jan.xlsx,USA/ClientA/Data,/sites/XXProducts/XX/Document Library/Secure Area/Client Folders/USA/ClientA/Data,2024-12-10 14:22:00,1230,Jane Smith
Analysis_GGGG_Q1.xlsx,UK/ClientC,/sites/XXProducts/XX/Document Library/Secure Area/Client Folders/UK/ClientC,2024-12-08 09:15:00,890,Bob Wilson
Forecast_PPPP_2024.xlsx,Germany/ClientD,/sites/XXProducts/XX/Document Library/Secure Area/Client Folders/Germany/ClientD,2024-12-12 16:45:00,3100,Anna Mueller
```

### JSON Extract Example (`Report_GGGG_2024.json`)

```json
{
  "filename": "Report_GGGG_2024.xlsx",
  "extracted_at": "2024-12-15T14:30:22",
  "sheets": [
    {
      "sheet_name": "Summary",
      "data_format": "auto-detected",
      "rows": [
        {
          "Product": "Widget A",
          "Revenue": 125000,
          "Quarter": "Q4",
          "_row_number": 2
        },
        {
          "Product": "Widget B",
          "Revenue": 98000,
          "Quarter": "Q4",
          "_row_number": 3
        }
      ],
      "metadata": {
        "total_rows": 2,
        "total_columns": 3,
        "has_header": true,
        "header_row": ["Product", "Revenue", "Quarter"]
      }
    }
  ]
}
```

## Tips & Tricks

### 1. Narrow Down Your Search

Start with a more specific folder:
```
Document Library/Secure Area/Client Folders/USA
```
Instead of:
```
Document Library/Secure Area/Client Folders
```

### 2. Multiple Patterns

Separate patterns with commas:
```
GGGG, PPPP, ZZZZ, Report_2024
```

Case is ignored, so `gggg` will match `GGGG` or `Gggg`.

### 3. Performance

- Recursive search through 100+ folders may take 1-2 minutes
- Progress updates show current folder being scanned
- Results appear immediately when search completes

### 4. Analyzing Results

Once you have the CSV:

**In Excel:**
- Sort by "Folder" column to group by country
- Filter by "Modified" date to find recent files
- Pivot on "Folder" to count files per country

**In Python/Pandas:**
```python
import pandas as pd

df = pd.read_csv('sharepoint_files_20241215_143022.csv')

# Count files per country
df['Country'] = df['Folder'].str.split('/').str[0]
print(df.groupby('Country')['Filename'].count())

# Find most recently modified
recent = df.nlargest(5, 'Modified')
print(recent[['Filename', 'Folder', 'Modified']])
```

## Troubleshooting

### "Folder not found" error
- Check your folder path spelling
- Try using just `Document Library` first, then add subfolders
- Verify the folder exists in SharePoint

### Search is slow
- Normal for large hierarchies (100+ folders)
- Consider starting from a more specific subfolder
- Progress updates show it's working

### No files found
- Check your filename patterns are correct
- Try searching without patterns first
- Verify Excel files exist in those folders

### Authentication fails
- Make sure you're logged into Windows domain
- Connect to VPN if required
- Try running `python diagnose_auth.py` to test all auth methods

## Next Steps

Now that you have the file list:
1. Analyze the CSV to understand your data distribution
2. Extract specific files to JSON for data processing
3. Build automated workflows for regular data extraction

Happy exploring! 🚀
