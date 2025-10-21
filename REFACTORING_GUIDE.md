# Refactoring Guide: JSON-First Architecture

This document explains the refactored architecture with enhanced extraction and JSON-first storage.

## Overview

The refactored system introduces:

1. **Enhanced extraction** with confidence scores and formatting metadata
2. **JSON-first storage** as primary artifact (SQLite optional)
3. **Schema discovery tools** to rationalize data across 2000+ files
4. **Field mapping framework** to normalize heterogeneous data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Excel Files (2000+)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │   ClientExtractor (Enhanced)  │
          │   - Confidence scores         │
          │   - Cell formatting metadata  │
          │   - Section type detection    │
          └───────────────┬───────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │     Client JSON Documents     │
          │   (One per client, all data)  │
          └───────┬───────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│ JSONStorage  │    │ SQLite Database  │
│  (Primary)   │    │   (Optional)     │
└──────┬───────┘    └────────┬─────────┘
       │                     │
       └─────────┬───────────┘
                 │
                 ▼
       ┌──────────────────┐
       │  Pattern Clusters │
       │  (ML-based)       │
       └─────────┬─────────┘
                 │
                 ▼
       ┌──────────────────┐
       │ Schema Builder    │
       │ - Field analysis  │
       │ - Canonical names │
       └─────────┬─────────┘
                 │
                 ▼
       ┌──────────────────┐
       │  Field Mapper     │
       │ - Normalization   │
       │ - Validation      │
       └──────────────────┘
```

## Key Changes

### 1. Enhanced ClientExtractor

**File:** [client_extractor.py](client_extractor.py:1)

**New Features:**
- **Confidence scores** (0-1) for each section type detection
- **Cell formatting metadata** (bold, colors, borders, alignment)
- **Detection algorithm improvements** using formatting hints

**Example Output:**
```json
{
  "section_id": "section_0",
  "section_type": "table",
  "detection_confidence": 0.85,
  "header_formatting": {
    "bold": true,
    "fill_color": "FFCCCCCC"
  },
  "cell_coordinates": {
    "start_row": 5,
    "end_row": 20,
    "start_col": 1,
    "end_col": 8
  },
  "headers": ["Transaction_ID", "Date", "Amount"]
}
```

**Confidence Score Calculation:**
- Merged cells in header area → +0.8 for complex_header
- 2 columns with strings in col 1 → +0.7 for key_value
- Bold first row → +0.2 for table
- Multiple columns with string headers → +0.5 for table

### 2. JSON Storage (Primary Storage)

**File:** [json_storage.py](json_storage.py:1)

**Features:**
- One JSON file per client (`extracted_json/country/client_id.json`)
- Lightweight metadata index for fast search
- Pattern cluster assignments
- Field-level indexing

**Advantages:**
- ✅ Direct artifact (no DB schema dependency)
- ✅ Git-friendly (diff, version control)
- ✅ Human-readable
- ✅ Easy to share and backup
- ✅ No lock-in

**Metadata Index Structure:**
```json
{
  "version": "1.0",
  "total_clients": 2000,
  "last_updated": "2024-10-21T12:00:00",
  "clients": {
    "USA_AcmeCorp_FX": {
      "client_id": "USA_AcmeCorp_FX",
      "client_name": "Acme Corp",
      "country": "USA",
      "product": "FX",
      "file_path": "clients/USA/USA_AcmeCorp_FX.json",
      "pattern_signature": "abc123",
      "pattern_cluster_id": 5,
      "fields": ["Client_Name", "Registration_ID", "Country"]
    }
  }
}
```

**Usage:**
```python
from json_storage import JSONStorage

storage = JSONStorage("./extracted_json")

# Save client
storage.save_client(client_data)

# Search
results = storage.search_clients(country="USA", has_field="Client_Name")

# Get client
client = storage.get_client("USA_AcmeCorp_FX")

# Export to CSV
storage.export_to_csv("clients.csv")
```

### 3. Updated ClientProcessor

**File:** [client_processor.py](client_processor.py:1)

**New Options:**
```bash
# Write to both JSON and SQLite (default)
python client_processor.py ./output

# JSON only (recommended for new workflows)
python client_processor.py ./output --no-sqlite

# SQLite only (legacy compatibility)
python client_processor.py ./output --no-json

# Custom paths
python client_processor.py ./output --json ./my_json --db my_db.db
```

**Dual Write:**
- Writes to JSON storage by default
- Optionally writes to SQLite for compatibility
- Independent error handling (one can fail without affecting the other)

### 4. Schema Builder (NEW)

**File:** [schema_builder.py](schema_builder.py:1)

**Purpose:** Discover common fields across pattern clusters to rationalize data model.

**Features:**
- Analyze field frequency across clients in a cluster
- Group similar field names (e.g., "Client_Name", "Customer_Name", "Entity_Name")
- Suggest canonical field names
- Export cluster summaries

**Usage:**

```bash
# Export summary of all clusters
python schema_builder.py --export-summary cluster_summary.json

# Analyze specific cluster
python schema_builder.py --cluster 5
```

**Output:**
```
CLUSTER 5 ANALYSIS
==============================================================
Client count: 450
Sample size: 10

--- Section Types ---
  key_value: 120
  table: 45
  complex_header: 8

--- Top Fields (by frequency) ---
  Client_Name
    Frequency: 98.0%
    Section types: key_value
    Sample values: ['Acme Corp', 'Widget Inc']

  Customer_Name
    Frequency: 85.0%
    Section types: key_value
    Sample values: ['Beta LLC', 'Gamma Ltd']

--- Canonical Field Suggestions ---
  Client:
    - Client_Name
    - Customer_Name
    - Entity_Name
```

**Programmatic Usage:**
```python
from json_storage import JSONStorage
from schema_builder import SchemaBuilder

storage = JSONStorage("./extracted_json")
builder = SchemaBuilder(storage)

# Analyze cluster
analysis = builder.analyze_pattern_cluster(cluster_id=5, sample_size=10)

# Get canonical suggestions
suggestions = analysis['canonical_suggestions']
# {'Client': ['Client_Name', 'Customer_Name', 'Entity_Name']}
```

### 5. Field Mapper (NEW)

**File:** [field_mapper.py](field_mapper.py:1)

**Purpose:** Map heterogeneous field names to canonical schema with validation.

**Features:**
- Define canonical schema (field names, types, validation rules)
- Map source fields → canonical fields per cluster
- Apply transformations (uppercase, trim, date format, etc.)
- Validate against schema

**Example:**

```python
from field_mapper import FieldMapper, register_default_transformations

# Create mapper
mapper = FieldMapper()
register_default_transformations(mapper)

# Define canonical schema
mapper.define_canonical_field(
    'Client_Name',
    'string',
    'Client legal name',
    required=True,
    validation_rules=['not_empty']
)

# Add field mappings for cluster 5
mapper.add_field_mapping(5, 'Client_Name', 'Client_Name', 'trim')
mapper.add_field_mapping(5, 'Customer_Name', 'Client_Name', 'trim')
mapper.add_field_mapping(5, 'Entity_Name', 'Client_Name', 'trim')

# Save mappings
mapper.save_mappings('field_mappings.json')

# Apply to client data
mapped_data = mapper.map_client_data(client_data, cluster_id=5)
```

**Mapped Output:**
```json
{
  "client_id": "USA_AcmeCorp_FX",
  "original_data": { /* full original JSON */ },
  "canonical_data": {
    "Client_Name": "Acme Corp",
    "Registration_ID": "12345",
    "Country": "USA"
  },
  "processing_metadata": {
    "mapped_at": "2024-10-21T12:00:00",
    "cluster_id": 5,
    "validation_errors": []
  }
}
```

## Workflow

### Phase 1: Extract to JSON

```bash
# Process all Excel files → JSON files + SQLite (both)
python client_processor.py ./output
```

**Output:**
- `extracted_json/clients/USA/USA_AcmeCorp_FX.json` (2000+ files)
- `extracted_json/metadata_index.json` (searchable index)
- `client_data.db` (optional SQLite)

### Phase 2: Pattern Clustering

```bash
# Run ML-based clustering
python pattern_clustering.py client_data.db
```

**Output:**
- Updates `pattern_cluster_id` in database
- Can also update JSON metadata index

```python
# Update JSON storage with clusters
from json_storage import JSONStorage
from client_database import ClientDatabase

db = ClientDatabase("client_data.db")
storage = JSONStorage("./extracted_json")

# Get cluster assignments from DB
clients = db.search_clients(limit=10000)
assignments = {c['client_id']: c['pattern_cluster_id'] for c in clients if c['pattern_cluster_id']}

# Update JSON metadata
storage.update_cluster_assignments(assignments)
```

### Phase 3: Schema Discovery

```bash
# Analyze each cluster
python schema_builder.py --export-summary cluster_summary.json
```

**Review Output:**
- Identifies 5-20 distinct patterns (form templates)
- Shows common fields per cluster
- Suggests canonical field names

**Manual Step:** Review `cluster_summary.json` and decide on canonical schema.

### Phase 4: Define Field Mappings

**Create `define_mappings.py`:**
```python
from field_mapper import FieldMapper, register_default_transformations

mapper = FieldMapper()
register_default_transformations(mapper)

# Define canonical schema (your target data model)
mapper.define_canonical_field('Client_Name', 'string', 'Client name', required=True)
mapper.define_canonical_field('Registration_ID', 'string', 'Registration number', required=True)
mapper.define_canonical_field('Country', 'string', 'Country', required=True)
# ... more fields

# Define mappings for Cluster 0 (e.g., "Standard Form A")
mapper.add_field_mapping(0, 'Client_Name', 'Client_Name', 'trim')
mapper.add_field_mapping(0, 'Customer_Name', 'Client_Name', 'trim')

# Define mappings for Cluster 1 (e.g., "Standard Form B")
mapper.add_field_mapping(1, 'Entity_Name', 'Client_Name', 'trim')
mapper.add_field_mapping(1, 'Legal_Name', 'Client_Name', 'trim')

# ... more clusters

mapper.save_mappings('field_mappings.json')
```

### Phase 5: Apply Mappings

```python
from json_storage import JSONStorage
from field_mapper import FieldMapper

storage = JSONStorage("./extracted_json")
mapper = FieldMapper('field_mappings.json')

# Get all clients
clients = storage.search_clients(limit=10000)

for client_meta in clients:
    client_data = storage.get_client(client_meta['client_id'])

    # Apply mappings
    mapped_data = mapper.map_client_data(client_data)

    # Save normalized version
    storage.save_client(mapped_data)  # or save to different directory
```

## Migration Path

### Current State → Refactored

If you have existing SQLite database:

```python
from client_database import ClientDatabase
from json_storage import JSONStorage

# Migrate from SQLite to JSON
db = ClientDatabase("client_data.db")
storage = JSONStorage("./extracted_json")

clients = db.search_clients(limit=10000)

for client_meta in clients:
    client_data = db.get_client(client_meta['client_id'])
    storage.save_client(client_data)

print(f"Migrated {len(clients)} clients to JSON storage")
```

### Pure JSON Workflow (Future)

1. **Stop using SQLite** after migration
2. **Use JSON storage** for all queries:
   ```python
   storage.search_clients(country="USA")
   storage.get_client(client_id)
   storage.get_statistics()
   ```

3. **Pattern clustering** reads from JSON:
   ```python
   # Update clustering to work with JSON storage
   # (small refactor of pattern_clustering.py)
   ```

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Storage** | SQLite only | JSON primary, SQLite optional |
| **Artifact** | DB records | Individual JSON files |
| **Data Model** | Fixed schema | Flexible, evolves with JSON |
| **Confidence** | None | Per-section confidence scores |
| **Formatting** | Not captured | Bold, colors, borders |
| **Schema Discovery** | Manual | Automated with SchemaBuilder |
| **Field Mapping** | Ad-hoc | Framework with validation |
| **Version Control** | Difficult | Easy (JSON diffs) |
| **Sharing** | Export from DB | Copy JSON files |

## Next Steps

1. **Run extraction** with new ClientProcessor:
   ```bash
   python client_processor.py ./output --json ./extracted_json
   ```

2. **Analyze clusters**:
   ```bash
   python schema_builder.py --export-summary clusters.json
   ```

3. **Review and define canonical schema** (manual step)

4. **Create field mappings** using FieldMapper

5. **Apply mappings** to normalize data

6. **Phase out SQLite** once confident in JSON workflow

## Questions?

Refer to:
- [CLIENT_WORKFLOW.md](CLIENT_WORKFLOW.md) - Original client-centric workflow
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - Usage examples
- Code comments in each module

## File Reference

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| [client_extractor.py](client_extractor.py:1) | Enhanced extraction | `ClientExtractor` |
| [json_storage.py](json_storage.py:1) | JSON file management | `JSONStorage` |
| [client_processor.py](client_processor.py:1) | Batch processing | `ClientProcessor` |
| [schema_builder.py](schema_builder.py:1) | Schema discovery | `SchemaBuilder` |
| [field_mapper.py](field_mapper.py:1) | Field mapping & validation | `FieldMapper` |
| [pattern_clustering.py](pattern_clustering.py:1) | ML clustering | `PatternClusterer` |
