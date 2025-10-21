# Troubleshooting: Processing Gets Stuck

## Problem
Processing gets stuck midway through the file list and stops progressing.

## Common Causes & Solutions

### 1. **Corrupted or Malformed Excel File** (Most Common)

**Symptom:** Processing hangs on a specific file indefinitely

**Cause:** openpyxl tries to read a corrupted .xlsx file and hangs

**Solution:**
```bash
# Use the robust processor with timeout
streamlit run data_pipeline_ui.py

# In UI: Set "Timeout per file" to 120 seconds (2 minutes)
```

**How it helps:**
- Automatically skips files that take too long
- Tracks which files timed out
- Retries failed files once

### 2. **Very Large Excel File**

**Symptom:** Processing appears stuck but is actually just slow

**Cause:** Files > 10MB with thousands of rows take time to process

**Solution:**
- Increase timeout to 300-600 seconds for large files
- Reduce concurrent workers to 2-4 (less memory pressure)
- Check file sizes first:
  ```bash
  find ./output -name "*.xlsx" -size +10M
  ```

### 3. **SQLite Database Lock**

**Symptom:** Multiple threads writing to SQLite causes deadlock

**Cause:** Concurrent writes to SQLite without proper locking

**Solution:**
- Use JSON-only mode (disable SQLite):
  ```bash
  # In UI: Uncheck "Enable SQLite"
  ```
- Or reduce workers to 1-2 when using SQLite

### 4. **Complex Merged Cells Pattern**

**Symptom:** Hangs during cell matrix building

**Cause:** Deeply nested or circular merged cell references

**Solution:**
- The robust processor now has timeout protection
- Files with this issue will timeout and be logged

### 5. **Memory Exhaustion**

**Symptom:** System slows down, processing stalls

**Cause:** Too many concurrent workers on large files

**Solution:**
- Reduce concurrent workers to 2-4
- Monitor system memory:
  ```bash
  # Mac/Linux
  top

  # Windows
  Task Manager → Performance
  ```

## New Robust Processor Features

### File: `client_processor_robust.py`

**Enhanced Features:**
1. ✅ **Per-file timeout** (default: 120 seconds)
2. ✅ **Automatic retry** (1-2 retries for failed files)
3. ✅ **Detailed error tracking** (timeout, corrupted, etc.)
4. ✅ **Stuck file logging** (shows which files caused problems)
5. ✅ **Better error messages** (identifies specific issues)
6. ✅ **Current file tracking** (see which file is being processed)

### Updated UI Features

**New Metrics:**
- ⏱️ **Timeout count** - Files that exceeded timeout
- 🔥 **Corrupted count** - Files that are malformed
- 📄 **Current file** - Which file is currently being processed
- 🔄 **Retried count** - Files that were retried

**New Settings:**
- **Timeout per file** - Set maximum time per file (30-600 seconds)
- **Max retries** - Retry failed files (0-3 times)

## Diagnostic Steps

### Step 1: Identify the Stuck File

**Before (old processor):**
- Can't tell which file is stuck
- Have to kill process and restart

**After (robust processor):**
- See "Current file" metric in UI
- Timeout automatically triggers after 120s
- File path logged in "Files Timed Out" list

### Step 2: Examine the Stuck File

```bash
# Try opening the file manually
python -c "import openpyxl; wb = openpyxl.load_workbook('stuck_file.xlsx'); print('OK')"
```

**If it hangs:** File is corrupted
**If it errors:** File format issue
**If it works:** Might be size or complexity issue

### Step 3: Handle Problematic Files

**Option A: Skip them**
- Let timeout handle it
- Files will be logged in `stuck_files` list
- Process them manually later

**Option B: Fix them**
- Open in Excel and re-save
- Remove complex formatting
- Split large files into smaller ones

**Option C: Increase timeout**
- For legitimately large files
- Set timeout to 300-600 seconds

## Using the Robust Processor

### In Streamlit UI

1. Run the updated UI:
   ```bash
   streamlit run data_pipeline_ui.py
   ```

2. In Stage 2 → JSON Extraction:
   - Set "Timeout per file": `120` seconds
   - Set "Max retries": `1`
   - Set "Concurrent workers": `4`

3. Watch the new metrics:
   - ⏱️ Timeout (files that timed out)
   - 🔥 Corrupted (invalid files)
   - 📄 Current (file being processed)

4. After completion, check "Files Timed Out" expandable section

### Command Line

```bash
# Create a script using robust processor
python -c "
from client_processor_robust import RobustClientProcessor

processor = RobustClientProcessor(
    output_folder='./output',
    json_path='./extracted_json',
    max_workers=4,
    timeout_seconds=120,
    max_retries=1
)

processor.process_all()

# Get stuck files
stuck_files = processor.get_stuck_files()
print(f'Stuck files: {stuck_files}')

processor.close()
"
```

## Prevention Tips

### 1. Pre-validate Files

```python
# Check all files before processing
from pathlib import Path
import openpyxl

def check_file(file_path, timeout=10):
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        wb.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)

excel_files = list(Path('./output').rglob('*.xlsx'))

for f in excel_files:
    valid, msg = check_file(f)
    if not valid:
        print(f"Invalid: {f} - {msg}")
```

### 2. Process in Batches

```python
# Process 100 files at a time
from client_processor_robust import RobustClientProcessor

files = list(Path('./output').rglob('*.xlsx'))

for i in range(0, len(files), 100):
    batch = files[i:i+100]
    print(f"Processing batch {i//100 + 1}")

    # Process batch
    processor = RobustClientProcessor(
        output_folder='./output',
        max_workers=4,
        timeout_seconds=120
    )
    processor.process_all()
    processor.close()
```

### 3. Monitor System Resources

```bash
# Watch CPU and memory while processing
watch -n 1 "ps aux | grep python | head -5"
```

## Example: Handling Stuck Processing

### Scenario
Processing 2000 files, stuck at file #847

### Old Behavior
```
Processed: 847/2000
... (nothing happens)
... (still nothing)
... (have to kill process)
```

### New Behavior with Robust Processor
```
Processed: 847/2000
Current: problematic_file.xlsx
... (120 seconds pass)
⏱️ Timeout: 1
Failed: 1
Processed: 848/2000 (skipped the stuck file)
... (continues processing)

At end:
✅ Processed: 1999
❌ Failed: 1
⏱️ Timeout: 1
🔥 Corrupted: 0

Files Timed Out:
  - /path/to/problematic_file.xlsx
```

## Quick Fix Commands

### Restart with Robust Processor

1. Stop the current Streamlit process (Ctrl+C)

2. Restart with updated UI:
   ```bash
   streamlit run data_pipeline_ui.py
   ```

3. Go to Stage 2 → JSON Extraction

4. Settings:
   - Timeout: `120` seconds
   - Workers: `4`
   - Retries: `1`

5. Click "Start Extraction"

6. Watch for:
   - Files timing out (shown in metrics)
   - Current file being processed
   - Automatic retries

## Summary

| Issue | Old Processor | Robust Processor |
|-------|---------------|------------------|
| **Stuck file** | Hangs forever | Times out after 120s |
| **Visibility** | Can't see what's stuck | Shows current file |
| **Recovery** | Have to restart | Auto-continues |
| **Retries** | No retries | Auto-retry once |
| **Diagnostics** | No info | Detailed stats |
| **Stuck file list** | Unknown | Logged and shown |

The robust processor ensures that **one bad file won't stop your entire pipeline**. It will timeout, log the problematic file, and continue processing the rest.
