# Streamlit UI Guide

## Overview

The new **data_pipeline_ui.py** provides a comprehensive web interface for the complete data extraction pipeline with 3 main stages.

## Quick Start

```bash
streamlit run data_pipeline_ui.py
```

The UI will open in your browser at `http://localhost:8501`

## UI Stages

### 🔗 Stage 1: SharePoint Download

**Purpose:** Connect to SharePoint and download Excel files

**Steps:**
1. Enter SharePoint site URL
2. Select authentication method
3. Click "Connect to SharePoint"
4. Enter folder path to search
5. Optionally add filename patterns
6. Set output folder and concurrent downloads
7. Click "Search & Download Files"

**Features:**
- ✅ Multiple authentication methods (Windows, Username/Password, Token)
- ✅ Recursive folder search
- ✅ Pattern-based filtering
- ✅ Concurrent downloads with progress bar
- ✅ Real-time status updates
- ✅ Download results table

**Output:** Excel files saved to `./output` folder

---

### 📦 Stage 2: JSON Extraction & Clustering

**Tab 1: JSON Extraction**

**Purpose:** Extract Excel files to JSON format with concurrent processing

**Steps:**
1. Verify Excel files exist in output folder
2. Set JSON output folder path
3. Choose whether to enable SQLite (optional)
4. Set number of concurrent workers (1-8)
5. Click "Start Extraction"

**Features:**
- ✅ **Concurrent processing** (4-8x faster than sequential)
- ✅ Real-time progress bar
- ✅ Processing stats (processed, failed, speed)
- ✅ Live processing log
- ✅ Dual storage (JSON + SQLite optional)

**Performance:**
- **1 worker:** ~5-10 files/sec
- **4 workers:** ~20-40 files/sec
- **8 workers:** ~40-80 files/sec

**Output:**
- JSON files in `./extracted_json/clients/{country}/{client_id}.json`
- Metadata index in `./extracted_json/metadata_index.json`
- Optional SQLite database

**Tab 2: Pattern Clustering**

**Purpose:** Group similar file structures using ML

**Steps:**
1. Wait for JSON extraction to complete
2. Set min cluster size and similarity threshold
3. Click "Run Pattern Clustering"

**Features:**
- ✅ ML-based clustering (scikit-learn)
- ✅ Cluster summary with common fields
- ✅ Section type distribution
- ✅ Outlier detection

**Output:**
- Cluster assignments in SQLite database
- Cluster summary displayed in UI

---

### 🔍 Stage 3: Schema Discovery & Analysis

**Tab 1: Cluster Analysis**

**Purpose:** Analyze each cluster to discover common fields

**Steps:**
1. Select a cluster to analyze
2. Set sample size (5-50 clients)
3. Click "Analyze Cluster"

**Features:**
- ✅ Field frequency analysis table
- ✅ Canonical field suggestions
- ✅ Section type distribution chart
- ✅ Sample values for each field

**Output:**
- Field statistics table
- Canonical field suggestions
- Section type breakdown

**Tab 2: Schema Builder**

**Purpose:** Define your canonical data model

**Steps:**
1. Set number of canonical fields
2. For each field, define:
   - Field name
   - Type (string, number, date, boolean)
   - Description
   - Required (yes/no)
3. Click "Save Canonical Schema"

**Output:**
- `canonical_schema.json` file with your data model

**Tab 3: Field Mapping**

**Purpose:** Map source fields to canonical schema

**Features:**
- ✅ Example code for programmatic mapping
- ✅ Reference guide for field_mapper.py

**Note:** Use the Python code approach for complete mapping configuration (see example in UI)

---

## Performance Optimization

### Concurrent Processing

The client processor now supports concurrent extraction:

**Command Line:**
```bash
python client_processor.py ./output --workers 8
```

**Streamlit UI:**
- Use the "Concurrent Workers" slider (1-8)
- More workers = faster processing
- Recommended: 4-8 workers for 2000+ files

**Performance Comparison:**

| Workers | Speed | Time for 2000 files |
|---------|-------|---------------------|
| 1 | ~5-10 files/sec | ~5-7 minutes |
| 4 | ~20-40 files/sec | ~1-2 minutes |
| 8 | ~40-80 files/sec | ~30-60 seconds |

**Note:** Actual speed depends on:
- File complexity
- CPU cores available
- Disk I/O speed

---

## Workflow Example

### Complete Pipeline (2000 files)

**Step 1: Download (5-10 minutes)**
- Stage 1 → Connect to SharePoint
- Search recursively
- Download 2000 files with 5 concurrent connections

**Step 2: Extract (1-2 minutes with 4 workers)**
- Stage 2 → JSON Extraction tab
- Set workers = 4
- Extract all files to JSON

**Step 3: Cluster (10 seconds)**
- Stage 2 → Pattern Clustering tab
- Run ML clustering
- Get 5-20 pattern groups

**Step 4: Analyze (5-10 minutes)**
- Stage 3 → Cluster Analysis tab
- Analyze each cluster
- Review field frequencies
- Note canonical suggestions

**Step 5: Define Schema (30 minutes)**
- Stage 3 → Schema Builder tab
- Define 10-50 canonical fields
- Save schema

**Step 6: Map Fields (1-2 hours)**
- Use programmatic approach (field_mapper.py)
- Create mappings per cluster
- Apply to all clients

**Total Time: ~2-3 hours for complete pipeline**

---

## UI Features

### Session State
- Remembers connection status across tabs
- Tracks processing progress
- Maintains clustering state

### Real-time Updates
- Progress bars for long operations
- Live logs during extraction
- Processing statistics

### Error Handling
- Graceful error messages
- Failed file tracking
- Validation warnings

---

## Troubleshooting

### Issue: "No Excel files found"
**Solution:** Run Stage 1 first to download files

### Issue: Slow extraction
**Solution:** Increase concurrent workers (4-8)

### Issue: "Clustering not complete"
**Solution:** Run Pattern Clustering in Stage 2 first

### Issue: Out of memory
**Solution:** Reduce number of concurrent workers

---

## Command Line Alternative

If you prefer command line:

```bash
# Stage 1: Use existing app.py
streamlit run app.py

# Stage 2: Extract
python client_processor.py ./output --workers 8

# Stage 2: Cluster
python pattern_clustering.py client_data.db

# Stage 3: Analyze
python schema_builder.py --export-summary clusters.json
python schema_builder.py --cluster 0
```

---

## Next Steps

After completing the UI workflow:

1. **Review cluster_summary.json** - Understand your data patterns
2. **Create field mappings** - Use field_mapper.py
3. **Apply mappings** - Normalize all data
4. **Export results** - CSV or final format
5. **Build analytics** - Use normalized data

---

## Tips

- **Start with sample:** Test with 10-20 files first
- **Monitor progress:** Watch the live logs
- **Check stats:** Review processing statistics
- **Validate results:** Look at JSON files manually
- **Adjust workers:** Find optimal number for your system

---

## Support

- Documentation: [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
- Getting Started: [GETTING_STARTED.md](GETTING_STARTED.md)
- Code examples: [example_workflow.py](example_workflow.py)
