# Client-Centric Workflow Guide

This guide explains the new client-centric approach for processing and analyzing your 1000+ Excel files.

## Overview

The system treats each Excel file as **one client's data**, automatically:
- ✅ Extracts client name from folder structure (Country/ClientName/Product)
- ✅ Selects latest dated file per client (ignores old files)
- ✅ Detects section types (key-value, table, complex headers)
- ✅ Handles merged cells and multi-level headers
- ✅ Generates searchable JSON documents per client
- ✅ Clusters similar structures using ML (CPU-only, local)

## Quick Start

### Step 1: Download Files from SharePoint

```bash
streamlit run app.py
```

1. Connect to SharePoint
2. Enable "Download & Save Files"
3. Search recursively for your Excel files
4. Files are saved to `./output` with folder structure preserved

### Step 2: Process Excel Files into Client JSONs

Option A: **Using the UI**

```bash
streamlit run client_browser.py
```

- Click "Start Processing" on the welcome screen
- Watch progress in real-time
- View results once complete

Option B: **Using Command Line**

```bash
python client_processor.py ./output --db client_data.db
```

This will:
- Scan all Excel files in `./output`
- Apply date filtering (latest files only)
- Skip folders containing "old" in path
- Generate one JSON per client
- Store in SQLite database

### Step 3: Browse and Search Clients

```bash
streamlit run client_browser.py
```

Features:
- **Search** by client name, country, product
- **View** full client JSON with all sheets/sections
- **Filter** by pattern clusters
- **Download** individual client JSONs

## Folder Structure Requirements

Your downloaded files should follow this structure:

```
output/
├── USA/                          # Country
│   ├── Acme Corp/                # Client Name
│   │   ├── FX Intermediation/   # Product
│   │   │   ├── form_15Jan2024.xlsx    ← Latest (selected)
│   │   │   └── form_10Dec2023.xlsx    ← Older (ignored)
│   │   └── Equity Trading/
│   │       └── onboarding.xlsx
│   └── Widget Inc/
│       └── old/                  # Ignored (contains 'old')
│           └── form.xlsx
└── Canada/
    └── ...
```

## File Selection Logic

### Date Parsing

The system recognizes multiple date formats in filenames:
- `15Jan2024`, `Jan15_2024`
- `2024-01-15`, `01-15-2024`
- `20240115`

### Selection Rules

For each **Country/Client/Product** combination:

1. **Files with dates**: Keep only the **latest** dated file
2. **Files without dates**: Keep all, labeled as "ClientName - Form 1", "ClientName - Form 2", etc.
3. **"old" folders**: Ignore completely

Examples:

```
# Scenario 1: Multiple dated files
Client A/Product 1/form_15Jan2024.xlsx    ← Selected
Client A/Product 1/form_10Dec2023.xlsx    ← Ignored

# Scenario 2: Files without dates
Client B/Product 1/template.xlsx          ← "Client B - Form 1"
Client B/Product 1/questionnaire.xlsx     ← "Client B - Form 2"

# Scenario 3: Old folder
Client C/old/form.xlsx                    ← Ignored
Client C/Product 1/form.xlsx              ← Selected
```

## Section Type Detection

The system automatically identifies three types of data structures:

### 1. Key-Value Sections

Two-column layout with labels and values:

```
| Client Name     | Acme Corp         |
| Registration #  | 123456            |
| Country         | USA               |
```

Stored as:
```json
{
  "section_type": "key_value",
  "data": {
    "Client_Name": "Acme Corp",
    "Registration": "123456",
    "Country": "USA"
  }
}
```

### 2. Standard Tables

Header row followed by data rows:

```
| Transaction ID | Date       | Amount |
|----------------|------------|--------|
| TXN001         | 2024-01-01 | 1000   |
| TXN002         | 2024-01-02 | 2000   |
```

Stored as:
```json
{
  "section_type": "table",
  "headers": ["Transaction_ID", "Date", "Amount"],
  "data": [
    {"Transaction_ID": "TXN001", "Date": "2024-01-01", "Amount": 1000},
    {"Transaction_ID": "TXN002", "Date": "2024-01-02", "Amount": 2000}
  ]
}
```

### 3. Complex Headers (with Merged Cells)

Example: "ELECTIONS" section with multi-level headers

```
Row 1: ELECTIONS
Row 2: [Merged A-B: Category 1] | [Merged C-E: Category 2]
Row 3: Field A | Field B | Col C | Col D | Col E
Row 4: value1  | value2  | val3  | val4  | val5
```

Stored as:
```json
{
  "section_type": "complex_header",
  "section_header": "ELECTIONS",
  "header_structure": {
    "levels": 2,
    "final_columns": ["Category_1_Field_A", "Category_1_Field_B", ...]
  },
  "data": [...]
}
```

**Merged cells** are automatically propagated to all cells in the merge range.

## Client JSON Structure

Each client is stored as a complete JSON document:

```json
{
  "client_id": "USA_AcmeCorp_FXIntermediation",
  "client_name": "Acme Corp",
  "country": "USA",
  "product": "FX Intermediation",
  "file_info": {
    "file_path": "USA/Acme Corp/FX Intermediation/form_15Jan2024.xlsx",
    "filename": "form_15Jan2024.xlsx",
    "extracted_date": "2024-01-15",
    "is_latest": true,
    "form_variant": null
  },
  "sheets": [
    {
      "sheet_name": "Client Overview",
      "sections": [
        {
          "section_id": "section_0",
          "section_type": "key_value",
          "section_header": null,
          "region": {"start_row": 1, "end_row": 10, ...},
          "data": {"Client_Name": "Acme Corp", ...}
        },
        {
          "section_id": "section_1",
          "section_type": "table",
          "section_header": "Transaction History",
          "headers": ["Date", "Amount", "Currency"],
          "data": [...]
        }
      ]
    }
  ],
  "pattern_signature": "a1b2c3d4...",
  "processing_metadata": {
    "processed_at": "2024-10-12T10:30:00",
    "status": "success"
  }
}
```

## Pattern Discovery

### How It Works

The system uses **scikit-learn** (CPU-only) to cluster clients with similar structures:

**Features extracted:**
- Sheet names
- Section type counts (key-value vs table vs complex)
- Field/column names (TF-IDF vectorization)
- Structural metrics

**Clustering algorithm:**
- Agglomerative Clustering (hierarchical)
- Fallback to DBSCAN if needed
- Allows ~10% variation within clusters
- Creates "Outliers" cluster for unusual structures

### Running Pattern Clustering

UI:
```bash
streamlit run client_browser.py
# Go to "Pattern Clusters" tab
# Click "Run Clustering"
```

Command line:
```bash
python pattern_clustering.py client_data.db
```

### Understanding Clusters

Each cluster shows:
- **Client count**: How many clients have this pattern
- **Common sheet names**: Most frequent sheet names in cluster
- **Section type distribution**: Mix of key-value/table/complex sections
- **Common fields**: Most frequent field/column names

Use this to:
- Identify the 5-20 different form templates
- Find outliers that need manual review
- Group clients for automated processing
- Track form version changes over time

## Database Structure

### Tables

**clients**: Main table with full JSON per client
```sql
SELECT * FROM clients WHERE client_name LIKE '%Acme%';
```

**sections**: Metadata for quick searching
```sql
SELECT * FROM sections WHERE section_type = 'key_value';
```

**pattern_clusters**: Cluster information
```sql
SELECT * FROM pattern_clusters ORDER BY client_count DESC;
```

### Common Queries

Find all clients from a country:
```python
from client_database import ClientDatabase

db = ClientDatabase("client_data.db")
clients = db.search_clients(country="USA")
```

Find clients with specific field:
```python
results = db.search_by_field("Customer_ID")
```

Get all clients in a pattern cluster:
```python
db.cursor.execute("""
    SELECT client_name, country, product
    FROM clients
    WHERE pattern_cluster_id = 5
""")
```

## Use Cases

### 1. Manual Review of Client Data

```bash
streamlit run client_browser.py
```

- Search for specific client
- View their complete JSON structure
- Download JSON for offline analysis
- Compare multiple clients side-by-side

### 2. Pattern Analysis

Identify how many different form templates exist:

```bash
python pattern_clustering.py client_data.db
```

Result: "Found 12 pattern clusters"
- Cluster 1: 450 clients (standard form A)
- Cluster 2: 320 clients (standard form B)
- Cluster 3: 180 clients (old format)
- ...
- Outliers: 15 clients (unusual structures)

### 3. Automated Processing

Once patterns are identified:

```python
from client_database import ClientDatabase

db = ClientDatabase("client_data.db")

# Get all clients in "standard form A" cluster
clients = db.search_clients(pattern_cluster=1)

for client in clients:
    client_data = db.get_client(client['client_id'])

    # Extract specific fields based on known pattern
    for sheet in client_data['sheets']:
        for section in sheet['sections']:
            if section['section_type'] == 'key_value':
                customer_name = section['data'].get('Customer_Name')
                # Process...
```

### 4. Data Quality Checks

Find clients missing required fields:

```python
clients_without_customer_id = []

all_clients = db.search_clients(limit=10000)
for client in all_clients:
    client_data = db.get_client(client['client_id'])

    # Search for Customer_ID field
    has_customer_id = False
    for sheet in client_data['sheets']:
        for section in sheet['sections']:
            if 'Customer_ID' in str(section):
                has_customer_id = True
                break

    if not has_customer_id:
        clients_without_customer_id.append(client['client_name'])
```

## Troubleshooting

### "No files selected"

- Check folder structure matches Country/ClientName/Product pattern
- Ensure files are not in "old" folders
- Verify Excel files have .xlsx or .xls extension

### "Failed to process client X"

- Check Excel file is not corrupted
- Verify file has read permissions
- Look at error message in database:
  ```python
  db.cursor.execute("SELECT error_message FROM clients WHERE client_name = ?", (name,))
  ```

### "Pattern clustering not working"

- Need at least 2 clients to cluster
- Try adjusting `similarity_threshold` (default: 0.7)
- Check scikit-learn is installed: `pip install scikit-learn`

### "Merged cells not detected"

- Ensure using `openpyxl` (not older `xlrd`)
- Check Excel file has proper merged cell formatting
- Complex merges may fall back to raw section type

## Next Steps

1. **Process your files**: `python client_processor.py ./output`
2. **Browse clients**: `streamlit run client_browser.py`
3. **Run clustering**: Identify the 5-20 patterns
4. **Manual review**: Look at JSON docs for each pattern type
5. **Build automation**: Create ETL pipelines based on patterns

## Performance

- **Processing speed**: ~5-10 files/second (varies by complexity)
- **Database size**: ~100 KB per client (includes full JSON)
- **1000 clients**: ~100 MB database, ~2-3 minutes processing time
- **Clustering**: ~5-10 seconds for 1000 clients on CPU

## Support

For issues:
- Check CLIENT_WORKFLOW.md (this file)
- Review USAGE_GUIDE.md for detailed examples
- Check TROUBLESHOOTING.md for common problems
