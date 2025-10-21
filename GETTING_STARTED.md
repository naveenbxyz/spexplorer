# Getting Started with the Refactored System

## Quick Start Checklist

### ☐ Phase 1: Setup and Verification (15 minutes)

1. **Verify Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Test the refactored components**
   ```bash
   # Test JSON storage
   python json_storage.py

   # Test field mapper
   python field_mapper.py

   # Test schema builder (needs data first)
   # python schema_builder.py --help
   ```

3. **Review the example workflow**
   ```bash
   python example_workflow.py
   ```

### ☐ Phase 2: Extract Your Data (30-60 minutes for 2000 files)

4. **Process Excel files to JSON + SQLite**
   ```bash
   # Extract all files (dual storage)
   python client_processor.py ./output --json ./extracted_json --db client_data.db

   # OR extract to JSON only
   python client_processor.py ./output --json ./extracted_json --no-sqlite
   ```

5. **Verify extraction results**
   ```bash
   # Check JSON files were created
   ls -lh extracted_json/clients/

   # Check metadata index
   cat extracted_json/metadata_index.json | python -m json.tool | head -50
   ```

6. **Review confidence scores**
   - Open a few JSON files
   - Look at `detection_confidence` field for each section
   - Identify sections with confidence < 0.7 for manual review

### ☐ Phase 3: Pattern Discovery (5-10 minutes)

7. **Run pattern clustering**
   ```bash
   python pattern_clustering.py client_data.db
   ```

   Expected output:
   ```
   ✅ Clustering completed!
      Total clients: 2000
      Clusters found: 12
      Outliers: 15
   ```

8. **Update JSON metadata with clusters**
   ```python
   # Run this script to sync cluster IDs to JSON storage
   from json_storage import JSONStorage
   from client_database import ClientDatabase

   db = ClientDatabase("client_data.db")
   storage = JSONStorage("./extracted_json")

   clients = db.search_clients(limit=10000)
   assignments = {c['client_id']: c['pattern_cluster_id']
                  for c in clients if c.get('pattern_cluster_id')}

   storage.update_cluster_assignments(assignments)
   print(f"Updated {len(assignments)} cluster assignments")
   ```

9. **Export cluster summary**
   ```bash
   python schema_builder.py --export-summary cluster_summary.json
   ```

### ☐ Phase 4: Schema Discovery (1-2 hours)

10. **Analyze each cluster**
    ```bash
    # Analyze cluster 0
    python schema_builder.py --cluster 0

    # Analyze cluster 1
    python schema_builder.py --cluster 1

    # ... repeat for each cluster
    ```

11. **Review cluster_summary.json**
    - Open `cluster_summary.json` in editor
    - Note the top fields per cluster
    - Note the canonical suggestions

12. **Identify your canonical schema**

    Create a spreadsheet or document:

    | Canonical Field | Type | Description | Frequency | Clusters |
    |----------------|------|-------------|-----------|----------|
    | Client_Name | string | Legal name | 98% | 0,1,2,5 |
    | Registration_ID | string | Reg number | 92% | 0,1,2 |
    | Country | string | Country code | 100% | All |
    | ... | ... | ... | ... | ... |

    **Goal:** Define 10-50 core fields that represent your target data model

### ☐ Phase 5: Field Mapping (2-4 hours)

13. **Create field mappings file**

    Create `create_mappings.py`:
    ```python
    from field_mapper import FieldMapper, register_default_transformations

    mapper = FieldMapper()
    register_default_transformations(mapper)

    # Define canonical schema
    mapper.define_canonical_field(
        'Client_Name', 'string', 'Client legal name',
        required=True, validation_rules=['not_empty']
    )

    mapper.define_canonical_field(
        'Registration_ID', 'string', 'Registration number',
        required=True
    )

    # ... add all canonical fields

    # Define mappings for each cluster
    # Cluster 0
    mapper.add_field_mapping(0, 'Client_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Customer_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Registration_ID', 'Registration_ID')

    # Cluster 1
    mapper.add_field_mapping(1, 'Entity_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(1, 'Legal_Name', 'Client_Name', 'trim')

    # ... add mappings for all clusters

    mapper.save_mappings('field_mappings.json')
    print("✓ Field mappings saved")
    ```

14. **Run mapping creation**
    ```bash
    python create_mappings.py
    ```

15. **Test mappings on sample clients**
    ```python
    from json_storage import JSONStorage
    from field_mapper import FieldMapper

    storage = JSONStorage("./extracted_json")
    mapper = FieldMapper('field_mappings.json')

    # Test on a few clients
    test_clients = storage.search_clients(limit=5)

    for client_meta in test_clients:
        client_data = storage.get_client(client_meta['client_id'])
        mapped = mapper.map_client_data(client_data)

        print(f"\nClient: {client_data['client_name']}")
        print(f"Canonical data: {mapped['canonical_data']}")

        errors = mapped['processing_metadata'].get('validation_errors', [])
        if errors:
            print(f"Errors: {errors}")
    ```

### ☐ Phase 6: Apply Mappings (30-60 minutes)

16. **Apply mappings to all clients**

    Create `apply_mappings.py`:
    ```python
    from json_storage import JSONStorage
    from field_mapper import FieldMapper
    from pathlib import Path

    storage = JSONStorage("./extracted_json")
    mapper = FieldMapper('field_mappings.json')

    # Create output directory for normalized data
    output_storage = JSONStorage("./normalized_json")

    clients = storage.search_clients(limit=10000)

    stats = {
        'processed': 0,
        'errors': 0,
        'validation_errors': 0
    }

    for client_meta in clients:
        try:
            client_data = storage.get_client(client_meta['client_id'])
            mapped = mapper.map_client_data(client_data)

            # Save normalized version
            output_storage.save_client(mapped)

            stats['processed'] += 1

            if mapped['processing_metadata'].get('validation_errors'):
                stats['validation_errors'] += 1

        except Exception as e:
            print(f"Error processing {client_meta['client_id']}: {e}")
            stats['errors'] += 1

    print("\nMapping complete!")
    print(f"  Processed: {stats['processed']}")
    print(f"  With validation errors: {stats['validation_errors']}")
    print(f"  Failed: {stats['errors']}")
    ```

17. **Run mapping application**
    ```bash
    python apply_mappings.py
    ```

### ☐ Phase 7: Validation and QA (1-2 hours)

18. **Review validation errors**
    ```python
    from json_storage import JSONStorage

    storage = JSONStorage("./normalized_json")
    clients = storage.search_clients(limit=10000)

    # Find clients with validation errors
    error_clients = []
    for client_meta in clients:
        client = storage.get_client(client_meta['client_id'])
        errors = client['processing_metadata'].get('validation_errors', [])
        if errors:
            error_clients.append({
                'client_id': client['client_id'],
                'client_name': client['client_name'],
                'errors': errors
            })

    print(f"Found {len(error_clients)} clients with validation errors")

    # Save to file for review
    import json
    with open('validation_errors.json', 'w') as f:
        json.dump(error_clients, f, indent=2)
    ```

19. **Check data quality**
    ```python
    from json_storage import JSONStorage
    from collections import Counter

    storage = JSONStorage("./normalized_json")
    clients = storage.search_clients(limit=10000)

    # Field coverage analysis
    field_coverage = Counter()

    for client_meta in clients:
        client = storage.get_client(client_meta['client_id'])
        canonical = client['canonical_data']

        for field in canonical.keys():
            if canonical[field] is not None:
                field_coverage[field] += 1

    print("\nField Coverage:")
    for field, count in field_coverage.most_common():
        percentage = (count / len(clients)) * 100
        print(f"  {field}: {count}/{len(clients)} ({percentage:.1f}%)")
    ```

20. **Handle outliers**
    - Review clients with cluster_id = -1 (outliers)
    - These may need manual handling or custom mappings

### ☐ Phase 8: Export and Delivery (30 minutes)

21. **Export to CSV**
    ```python
    from json_storage import JSONStorage
    import csv

    storage = JSONStorage("./normalized_json")
    clients = storage.search_clients(limit=10000)

    # Define fields to export
    canonical_fields = [
        'Client_Name', 'Registration_ID', 'Country',
        # ... add all your canonical fields
    ]

    with open('normalized_clients.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['client_id'] + canonical_fields)
        writer.writeheader()

        for client_meta in clients:
            client = storage.get_client(client_meta['client_id'])
            canonical = client['canonical_data']

            row = {'client_id': client['client_id']}
            row.update(canonical)
            writer.writerow(row)

    print("✓ Exported to normalized_clients.csv")
    ```

22. **Create final report**
    ```python
    # Generate summary report
    from json_storage import JSONStorage

    storage = JSONStorage("./normalized_json")
    stats = storage.get_statistics()

    report = f"""
    DATA PROCESSING REPORT
    =====================

    Total clients processed: {stats['total_clients']}
    Countries: {stats['countries']}
    Products: {stats['products']}
    Success rate: {(stats['success_count'] / stats['total_clients']) * 100:.1f}%

    Pattern clusters: {len(storage.load_pattern_clusters() or [])}

    Canonical fields: {len(canonical_fields)}
    Field coverage: [See field_coverage.csv]

    Output files:
    - normalized_json/ (JSON files per client)
    - normalized_clients.csv (flattened CSV)
    - validation_errors.json (clients with errors)
    - field_coverage.csv (coverage statistics)
    """

    with open('PROCESSING_REPORT.txt', 'w') as f:
        f.write(report)

    print(report)
    ```

## Common Issues and Solutions

### Issue: Low confidence scores

**Solution:** Review sections with confidence < 0.7 manually. These may need custom handling or improved detection rules.

### Issue: High validation error rate

**Solution:**
1. Check if canonical field definitions are too strict
2. Review transformation rules (may need custom transformations)
3. Some clients may genuinely be missing required fields

### Issue: Too many pattern clusters

**Solution:** Adjust `similarity_threshold` parameter in clustering (lower = more clusters)

### Issue: Fields not mapping correctly

**Solution:**
1. Use SchemaBuilder to verify field names in original data
2. Check for typos in field mapping definitions
3. Add more transformation rules if needed

## Success Criteria

✅ **Extraction complete**: All Excel files converted to JSON
✅ **Pattern clustering**: 5-20 distinct clusters identified
✅ **Schema defined**: 10-50 canonical fields documented
✅ **Mappings created**: All clusters have field mappings
✅ **Data normalized**: All clients mapped to canonical schema
✅ **Quality checked**: <10% validation error rate
✅ **Output delivered**: CSV or final format ready

## Next Steps After Completion

1. **Automate the pipeline** for new files
2. **Build analytics** on normalized data
3. **Create dashboards** for data quality monitoring
4. **Schedule regular updates** as new files arrive
5. **Phase out SQLite** if JSON workflow is working well

## Support

- Documentation: [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
- Summary: [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
- Example: Run `python example_workflow.py`

Good luck! 🚀
