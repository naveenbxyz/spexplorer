# File Persistence Feature

Download and save all matching Excel files from SharePoint to your local machine with preserved folder structure.

## Overview

When searching through thousands of folders with hundreds or thousands of matching files, you can now automatically download and persist all files locally while maintaining the folder hierarchy (Country/Client/Subfolder structure).

## How It Works

### 1. Enable File Persistence

In the Streamlit sidebar:

**File Persistence Section:**
- **Output Folder**: Specify where to save files (default: `./output`)
- **Download & Save Files**: Check this box to enable persistence

### 2. Run Your Search

1. Connect to SharePoint (Windows Integrated Authentication)
2. Configure your search:
   - Search Mode: Recursive (All Subfolders)
   - Folder Path: `Document Library/Secure Area/Client Folders`
   - Filename Patterns: `GGGG, PPPP`
3. Click "🔍 Search for Files"

### 3. Download Files

After search results appear:
1. Review the results table
2. Click "📥 Download All Matching Files" button
3. Watch the progress bar as files download
4. Files are saved with folder structure preserved

## Folder Structure

Files are saved preserving the SharePoint folder hierarchy:

```
output/
├── USA/
│   ├── ClientA/
│   │   ├── Reports/
│   │   │   └── Report_GGGG_2024.xlsx
│   │   └── Data/
│   │       └── Data_PPPP_Jan.xlsx
│   └── ClientB/
│       └── Analysis_GGGG_March.xlsx
├── UK/
│   └── ClientC/
│       └── Analysis_GGGG_Q1.xlsx
├── Germany/
│   └── ClientD/
│       └── Forecast_PPPP_2024.xlsx
└── metadata_20241215_143022.csv
```

### Metadata File

A CSV file with complete metadata is also saved:
- Filename
- Folder (relative path showing Country/Client structure)
- Full SharePoint path
- Modified date
- Size
- Modified by

This allows you to:
- Track which files were downloaded
- Map local files back to SharePoint locations
- Audit download history
- Re-run analysis on metadata

## Features

### ✅ Preserved Hierarchy
Files maintain their folder structure so you can easily identify:
- Which country the file belongs to
- Which client/project it's associated with
- Subfolder organization

### ✅ Progress Tracking
Real-time progress updates show:
- Current file being downloaded (e.g., "Downloading 145/1000: Report_GGGG_2024.xlsx")
- Progress bar
- Success/error counts

### ✅ Error Handling
- Continues downloading even if some files fail
- Shows summary of successful vs. failed downloads
- Lists all errors with file names
- Doesn't stop the entire process due to one error

### ✅ Safe File Names
Automatically sanitizes folder and file names:
- Removes invalid characters (`<>:"|?*`)
- Preserves readable folder structure
- Prevents file system errors

## Example Workflow

### Scenario: 1000 Files Across Multiple Countries

1. **Search** (takes 2-3 minutes for several thousand folders):
   ```
   Found 1,247 Excel file(s) matching criteria
   ```

2. **Review** results in the UI table

3. **Download** all files:
   ```
   Downloading 1/1247: Report_GGGG_2024.xlsx
   Downloading 2/1247: Data_PPPP_Jan.xlsx
   ...
   ✅ Successfully downloaded 1,245 file(s) to: ./output
   ⚠️ Failed to download 2 file(s)
   📋 Metadata saved to: ./output/metadata_20241215_143022.csv
   ```

4. **Analyze** locally:
   ```bash
   cd output
   ls -R  # See all downloaded files
   ```

## Output Folder Options

### Default: `./output`
Files saved in the current directory's `output` folder.

### Absolute Path: `C:/SharePointFiles`
Specify any absolute path:
```
C:/SharePointFiles
/Users/username/Documents/SharePointFiles
/mnt/shared/data/sharepoint
```

### Relative Path: `../data/sharepoint`
Relative to the app's current directory.

## Use Cases

### 1. Bulk Data Analysis
Download all matching files once, then analyze locally:
- Faster access (no network latency)
- Work offline
- Run batch processing scripts

### 2. Backup & Archive
Create local backups of specific files:
- Preserve folder structure
- Include metadata for tracking
- Historical snapshots

### 3. Data Migration
Move files from SharePoint to another system:
- Maintains folder hierarchy
- Includes complete metadata
- Easy to re-upload elsewhere

### 4. Compliance & Audit
Download files matching compliance criteria:
- Audit trail in metadata file
- Organized by country/client
- Timestamped downloads

## Performance

### Download Speed
- ~100-200 files per minute (typical)
- Depends on file sizes and network speed
- 1000 files = ~5-10 minutes

### Network Considerations
- Uses SharePoint REST API (efficient)
- Downloads files sequentially (prevents overwhelming SharePoint)
- Automatically retries on network errors (future enhancement)

## Troubleshooting

### "Permission denied" error
- Check output folder path exists and is writable
- On Windows, avoid paths with special permissions
- Try a different output folder

### "File already exists" error
- Files are overwritten by default
- No confirmation prompt (by design for automation)

### Some files fail to download
- Network timeouts (especially for large files)
- SharePoint permissions (some files may be restricted)
- Check the error list for specifics

### Out of disk space
- Check available disk space before downloading
- Estimate: ~1GB per 500-1000 Excel files (varies)

## Advanced: Post-Download Processing

After downloading files, you can process them programmatically:

```python
import os
import pandas as pd
from pathlib import Path

# Load metadata
metadata = pd.read_csv('output/metadata_20241215_143022.csv')

# Process all files
output_dir = Path('output')
for index, row in metadata.iterrows():
    file_path = output_dir / row['Folder'] / row['Filename']

    if file_path.exists():
        # Process Excel file
        df = pd.read_excel(file_path)
        # Your analysis here...
        print(f"Processed: {file_path}")
```

## Tips

1. **Test First**: Run a search without persistence enabled to verify results
2. **Check Count**: Review the file count before downloading (avoid accidentally downloading too many)
3. **Metadata**: Always keep the metadata CSV file - it's your map back to SharePoint
4. **Clean Up**: Periodically clean old download folders
5. **Organize**: Use descriptive output folder names (e.g., `./output_Q4_2024_GGGG`)

## Future Enhancements

Potential additions:
- Resume interrupted downloads
- Parallel downloads (faster)
- Selective download (choose specific files from results)
- Duplicate detection (skip already downloaded files)
- Compression (zip files for easier sharing)
- Cloud upload (e.g., to S3, Azure Blob)

---

This feature turns the SharePoint Excel Explorer from a search tool into a complete data extraction and persistence solution! 🚀
