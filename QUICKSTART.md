# Quick Start Guide

## 🚀 Launch the Application

```bash
streamlit run data_pipeline_ui.py
```

Browser will open at: `http://localhost:8501`

---

## 📋 Complete Workflow (3 Stages)

### Stage 1: SharePoint Download (5-10 minutes)

1. **Connect to SharePoint**
   - Enter site URL
   - Select authentication method
   - Click "Connect to SharePoint"

2. **Download Files**
   - Enter folder path (e.g., "Shared Documents/Client Folders")
   - Check "Search Recursively"
   - Set output folder: `./output`
   - Set concurrent downloads: `5`
   - Click "Search & Download Files"

**Result:** Excel files in `./output/`

---

### Stage 2: JSON Extraction & Clustering (1-2 minutes)

#### Tab 1: JSON Extraction

1. **Configure**
   - Excel folder: `./output`
   - JSON folder: `./extracted_json`
   - Enable SQLite: ✅ (optional)
   - **Concurrent workers: `4-8`** (faster!)

2. **Extract**
   - Click "Start Extraction"
   - Watch progress bar and live logs
   - Wait for completion

**Result:** JSON files in `./extracted_json/clients/`

#### Tab 2: Pattern Clustering

1. **Cluster**
   - Min cluster size: `2`
   - Similarity threshold: `0.7`
   - Click "Run Pattern Clustering"

**Result:** 5-20 pattern groups identified

---

### Stage 3: Schema Discovery & Analysis (10-30 minutes)

#### Tab 1: Cluster Analysis

1. **Analyze Each Cluster**
   - Select cluster from dropdown
   - Sample size: `10`
   - Click "Analyze Cluster"
   - Review field frequencies
   - Note canonical suggestions

2. **Repeat for all clusters**

**Result:** Understanding of common fields per cluster

#### Tab 2: Schema Builder

1. **Define Canonical Fields**
   - Number of fields: `10-50` (your core fields)
   - For each field:
     - Name (e.g., `Client_Name`)
     - Type (`string`, `number`, `date`, `boolean`)
     - Description
     - Required (yes/no)

2. **Save Schema**
   - Click "Save Canonical Schema"

**Result:** `canonical_schema.json` with your data model

#### Tab 3: Field Mapping

1. **Use programmatic approach**
   - Copy example code from UI
   - Create field mappings per cluster
   - See [GETTING_STARTED.md](GETTING_STARTED.md) for details

---

## ⚡ Performance Tips

### For 2000+ Files

**Optimal Settings:**
- **Workers:** `6-8` (faster extraction)
- **Sample size:** `10` clients (good balance)
- **Concurrent downloads:** `5` (SharePoint stage)

**Expected Times:**
- Stage 1 (Download): ~5-10 minutes
- Stage 2 (Extract): ~30-120 seconds (with 8 workers)
- Stage 2 (Cluster): ~10 seconds
- Stage 3 (Analyze): ~5-10 minutes (manual review)

**Total: ~15-25 minutes** for complete pipeline

---

## 🎯 Key Features

### Concurrent Processing
- **1 worker:** ~5-10 files/sec
- **4 workers:** ~20-40 files/sec
- **8 workers:** ~40-80 files/sec
- **8-10x faster** than sequential!

### Real-time Feedback
- ✅ Progress bars
- ✅ Live logs
- ✅ Processing stats (processed, failed, speed)
- ✅ Interactive charts

### Smart Analysis
- ✅ Field frequency tables
- ✅ Canonical field suggestions
- ✅ Section type distribution
- ✅ Outlier detection

---

## 🔧 Troubleshooting

### "No Excel files found"
**Fix:** Run Stage 1 first to download files

### Slow processing
**Fix:** Increase workers to 6-8 in Stage 2

### Out of memory
**Fix:** Reduce workers to 2-4

### Can't connect to SharePoint
**Fix:** Check VPN, credentials, site URL

---

## 📚 Documentation

- **This guide:** Quick overview
- **[STREAMLIT_UI_GUIDE.md](STREAMLIT_UI_GUIDE.md):** Detailed UI guide
- **[GETTING_STARTED.md](GETTING_STARTED.md):** Complete step-by-step
- **[REFACTORING_GUIDE.md](REFACTORING_GUIDE.md):** Technical details

---

## ✅ Success Criteria

After completion, you should have:

- ✅ All Excel files downloaded (`./output/`)
- ✅ JSON files extracted (`./extracted_json/clients/`)
- ✅ 5-20 pattern clusters identified
- ✅ Field frequency analysis per cluster
- ✅ Canonical schema defined (`canonical_schema.json`)
- ✅ Field mappings created (next step)

---

## 🎉 Next Steps

After the UI workflow:

1. **Create field mappings** (use `field_mapper.py`)
2. **Apply mappings** to normalize data
3. **Export to CSV** for analysis
4. **Build analytics** on normalized data

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed instructions.

---

Happy data wrangling! 🚀
