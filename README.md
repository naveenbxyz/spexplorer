# SharePoint Excel Explorer

A Streamlit application for browsing SharePoint folders, filtering Excel files by patterns, and extracting their content to generic JSON format.

## Features

- 🔐 **SharePoint Authentication**: Supports both OAuth2 (Client Credentials) and Access Token methods
- 📁 **Folder Navigation**: Browse SharePoint document libraries and folders
- 🔍 **Pattern Filtering**: Filter Excel files by filename patterns (e.g., files containing "XX", "YY", etc.)
- 📊 **File Metadata**: View file size, modified date, and author information
- 📄 **Generic JSON Extraction**: Convert polymorphic Excel files to a standard JSON format
- ⬇️ **Download Results**: Export extracted data as JSON files

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
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

1. **Run the Streamlit app**:
   ```bash
   streamlit run app.py
   ```

2. **Configure SharePoint Connection**:
   - Enter your SharePoint site URL (e.g., `https://yourtenant.sharepoint.com/sites/yoursite`)
   - Choose authentication method and provide credentials
   - Click "Connect to SharePoint"

3. **Browse and Filter**:
   - Enter a folder path (e.g., `Shared Documents/Reports`)
   - Optionally add filename patterns to filter (e.g., `XX, YY, Report`)
   - Click "Browse Folder"

4. **Extract Excel Content**:
   - Select a file from the list
   - Click "Extract to JSON"
   - View the extracted data and download as JSON

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
├── excel_extractor.py      # Excel to JSON converter
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

## Requirements

- Python 3.8+
- SharePoint Online (Office 365)
- Valid SharePoint credentials

## License

MIT License - Feel free to use and modify as needed.
