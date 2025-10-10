# SharePoint Excel Explorer

A Streamlit application for recursively browsing SharePoint folders, finding Excel files matching specific patterns, and extracting their content to generic JSON format.

## Features

- 🔐 **Windows Integrated Authentication**: Uses your current Windows login (no password needed!)
- 🔐 **Multiple Auth Methods**: NTLM, Basic Auth, OAuth2, and Access Token support
- 🔍 **Recursive Search**: Search through entire folder hierarchies including all subfolders
- 📁 **Pattern Matching**: Find Excel files by filename patterns (e.g., containing "GGGG", "PPPP", etc.)
- 📊 **Full Path Tracking**: See complete folder paths for each file (Country/Client/Subfolder)
- 📄 **Generic JSON Extraction**: Convert polymorphic Excel files to a standard JSON format
- 📥 **Export Results**: Download search results as CSV or extracted data as JSON
- ⚡ **Progress Tracking**: Real-time updates during recursive folder scanning
- 🔬 **Batch Processing**: Automatically parse 1000+ Excel files and store in SQLite database
- 🎯 **Table Detection**: Intelligently identifies table structures within Excel sheets
- 📊 **Pattern Discovery**: Automatically detects and groups similar table structures
- 🗄️ **SQLite Storage**: Efficient storage with folder hierarchy preservation (Country/Client/Product)
- 📈 **Analytics Dashboard**: Analyze patterns across thousands of files

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **For Windows Integrated Authentication (Recommended for internal SharePoint)**:
   ```bash
   pip install requests-negotiate-sspi
   ```

## SharePoint Authentication Setup

### Option 1: Azure AD App Registration (Recommended)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations** > **New registration**
3. Configure your app:
   - Name: Give it a meaningful name (e.g., "SharePoint Excel Explorer")
   - Supported account types: Choose based on your needs
   - Click **Register**

4. **Get your credentials**:
   - **Client ID**: Copy from the Overview page
   - **Tenant ID**: Copy from the Overview page
   - **Client Secret**: Go to "Certificates & secrets" > "New client secret" > Copy the value

5. **Grant API permissions**:
   - Go to **API permissions** > **Add a permission**
   - Select **SharePoint** > **Application permissions**
   - Add: `Sites.Read.All` or `Sites.FullControl.All`
   - Click **Grant admin consent**

### Option 2: Personal Access Token

Use an existing SharePoint access token obtained through other means.

## Usage

### Quick Start (For Internal SharePoint)

1. **Find your correct Site URL**:
   ```bash
   python test_url_format.py
   ```
   This will help you identify the correct site URL (e.g., `https://teamsites.company.net/sites/XXProducts/XX`)

2. **Run the Streamlit app**:
   ```bash
   streamlit run app.py
   ```

3. **Connect to SharePoint**:
   - **Site URL**: Enter your site URL (from step 1)
   - **Authentication**: Select "Windows Integrated (Current User)" - no password needed!
   - **Verify SSL Certificate**: Uncheck if you have self-signed certificates
   - Click "Connect to SharePoint"

4. **Search for Files**:
   - **Search Mode**: Choose "Recursive (All Subfolders)" to search entire hierarchy
   - **Folder Path**: Enter root path (e.g., `Document Library/Secure Area/Client Folders`)
   - **Filename Patterns**: Enter patterns to match (e.g., `GGGG, PPPP`)
   - Click "🔍 Search for Files"

5. **View Results**:
   - Browse files with full folder paths showing Country/Client/Subfolder structure
   - See metadata: filename, folder location, modified date, size, modified by
   - Download results as CSV for further analysis

6. **Extract Excel Content** (Optional):
   - Select any file from results
   - Click "Extract to JSON" to convert Excel to generic JSON format
   - Download the JSON data

## Troubleshooting Authentication (401 Error)

If you're getting a **401 Unauthorized** error:

### 1. Run the diagnostic tool:
```bash
python diagnose_auth.py
```

This will test all authentication methods and tell you which one works.

### 2. Try different username formats:
- `DOMAIN\username` (e.g., `CONTOSO\john.doe`)
- `username@domain.com` (e.g., `john.doe@company.com`)
- `username` (just username)

### 3. Disable SSL verification:
For internal SharePoint with self-signed certificates, uncheck "Verify SSL Certificate" in the app.

### 4. Check the troubleshooting guide:
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions.

## File Structure

```
spexplorer/
├── app.py                  # Main Streamlit application
├── sharepoint_client.py    # SharePoint REST API client
├── excel_extractor.py      # Basic Excel to JSON converter
├── table_extractor.py      # Advanced table detection and extraction
├── excel_database.py       # SQLite database manager
├── batch_processor.py      # Batch processing engine
├── concurrent_downloader.py # Concurrent file downloader
├── test_connection.py      # Connection test script
├── diagnose_auth.py        # Authentication diagnostics
├── requirements.txt        # Python dependencies
├── TROUBLESHOOTING.md      # Detailed troubleshooting guide
└── README.md              # This file
```

## JSON Output Format

The extracted JSON has the following structure:

```json
{
  "filename": "example.xlsx",
  "extracted_at": "2025-10-08T12:00:00",
  "sheets": [
    {
      "sheet_name": "Sheet1",
      "data_format": "auto-detected",
      "rows": [
        {
          "column_name_1": "value1",
          "column_name_2": "value2",
          "_row_number": 2
        }
      ],
      "metadata": {
        "total_rows": 100,
        "total_columns": 5,
        "has_header": true,
        "header_row": ["column_name_1", "column_name_2"]
      }
    }
  ]
}
```

## Features Explained

### Pattern Filtering

Enter comma-separated patterns in the sidebar (e.g., `XX, YY, Report`). The app will filter Excel files whose names contain any of these patterns (case-insensitive).

### Polymorphic Excel Support

The extractor handles Excel files with varying structures:
- Automatically detects header rows
- Falls back to generic column names when no header is detected
- Supports both `.xlsx` and `.xls` formats
- Handles multiple sheets
- Serializes dates, numbers, and text to JSON-compatible formats

### Authentication Methods

**Client Credentials (OAuth2)**:
- More secure for production use
- Requires Azure AD app registration
- Tokens refresh automatically

**Access Token**:
- Quick setup for testing
- Use existing tokens from other sources
- Manual token refresh required

## Troubleshooting

### Connection Issues

- **404 Folder not found**: Check your folder path format (e.g., `Shared Documents/SubFolder`)
- **401 Unauthorized**: Verify your credentials and API permissions
- **403 Forbidden**: Ensure admin consent is granted for app permissions

### Excel Extraction Issues

- The app uses `openpyxl` for `.xlsx` files and falls back to `pandas` for older formats
- Large files may take longer to process
- Corrupted Excel files will show an error message

## SharePoint REST API Reference

This application uses the SharePoint REST API. For more information:
- [SharePoint REST API Overview](https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/get-to-know-the-sharepoint-rest-service)

## Batch Processing & Pattern Discovery

### Process Downloaded Files

After downloading files from SharePoint, you can batch process them to identify table structures:

1. **Navigate to the "Excel File Processing" section** in the app
2. **Click "Start Batch Processing"** to parse all downloaded Excel files
3. **View results** in the Analysis and Pattern Discovery tabs

### Command-Line Batch Processing

You can also process files from the command line:

```bash
python batch_processor.py ./output --db excel_data.db
```

This will:
- Scan all Excel files in `./output` folder and subfolders
- Extract table structures from each file
- Store results in `excel_data.db` SQLite database
- Preserve folder hierarchy (Country/Client/Product)
- Generate pattern signatures for similar tables

### Database Schema

The SQLite database contains:

- **files**: File metadata with folder structure (country/client/product)
- **sheets**: Sheet-level information
- **tables**: Individual table data with full JSON content
- **pattern_analysis**: Aggregated pattern statistics

### Pattern Discovery

The system automatically:
- Detects table boundaries within sheets (handles multiple tables per sheet)
- Identifies header rows
- Generates pattern signatures based on column structure
- Groups similar tables across files
- Tracks pattern frequency and distribution

### Querying the Database

You can query the database directly using SQL:

```python
from excel_database import ExcelDatabase

db = ExcelDatabase("excel_data.db")

# Get all files by country
db.cursor.execute("SELECT * FROM files WHERE folder_country = 'USA'")

# Find tables with specific headers
results = db.search_tables_by_header("Customer_Name")

# Get pattern summary
patterns = db.get_pattern_summary()

# Get folder statistics
folder_stats = db.get_folder_summary()

db.close()
```

### Use Cases

**Pattern Analysis**: Identify common table structures across 1000+ client onboarding forms

**Data Validation**: Find files with missing or inconsistent table structures

**Automated Processing**: Build ETL pipelines based on discovered patterns

**Compliance Auditing**: Track which clients/countries use which form versions

## Requirements

- Python 3.8+
- SharePoint Online (Office 365)
- Valid SharePoint credentials

## License

MIT License - Feel free to use and modify as needed.
