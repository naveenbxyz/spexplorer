"""
Example workflow demonstrating the complete refactored pipeline:
1. Extract to JSON
2. Pattern clustering
3. Schema discovery
4. Field mapping
5. Normalized output
"""

from pathlib import Path
from json_storage import JSONStorage
from client_database import ClientDatabase
from schema_builder import SchemaBuilder
from field_mapper import FieldMapper, register_default_transformations


def example_workflow():
    """
    Complete example of the refactored workflow.
    """

    print("=" * 70)
    print("EXAMPLE WORKFLOW: Excel → Normalized JSON")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # STEP 1: Extract Excel files to JSON
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 1: Extract Excel files to JSON")
    print("=" * 70)

    print("""
    Run this command to extract all Excel files:

        python client_processor.py ./output --json ./extracted_json

    This creates:
        - extracted_json/clients/{country}/{client_id}.json (one per client)
        - extracted_json/metadata_index.json (searchable index)
        - client_data.db (optional SQLite)

    Each JSON file contains:
        - Client metadata (name, country, product)
        - All sheets and sections with detected types
        - Confidence scores for section detection
        - Cell formatting metadata
    """)

    # Simulate checking results
    json_storage_path = "./extracted_json"
    print(f"\n✓ JSON storage directory: {json_storage_path}")
    print(f"  (This would contain 2000+ JSON files after processing)")

    # -------------------------------------------------------------------------
    # STEP 2: Load JSON Storage
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 2: Access JSON Storage")
    print("=" * 70)

    storage = JSONStorage(json_storage_path)
    stats = storage.get_statistics()

    print(f"""
    JSON Storage Statistics:
        Total clients: {stats['total_clients']}
        Countries: {stats['countries']}
        Products: {stats['products']}
        Success: {stats['success_count']}
        Failed: {stats['failed_count']}
    """)

    # Example: Search clients
    print("\n--- Example: Search Clients ---")
    print("storage.search_clients(country='USA', has_field='Client_Name')")
    # results = storage.search_clients(country='USA', has_field='Client_Name')
    # print(f"Found {len(results)} clients")

    # -------------------------------------------------------------------------
    # STEP 3: Pattern Clustering
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 3: Pattern Clustering")
    print("=" * 70)

    print("""
    Run ML-based clustering to group similar form structures:

        python pattern_clustering.py client_data.db

    This groups your 2000+ files into 5-20 pattern clusters.

    Example output:
        ✅ Clustering completed!
           Total clients: 2000
           Clusters found: 12
           Outliers: 15

        📊 Cluster Summary:
          Pattern 0
            Clients: 450
            Sheet names: Overview, Details, Transactions
            Section types: {'key_value': 350, 'table': 100}

          Pattern 1
            Clients: 320
            Sheet names: ClientInfo, AccountDetails
            Section types: {'key_value': 280, 'table': 40}
    """)

    # -------------------------------------------------------------------------
    # STEP 4: Schema Discovery
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4: Schema Discovery")
    print("=" * 70)

    print("""
    Analyze each cluster to discover common fields:

        python schema_builder.py --export-summary clusters.json

    This creates a summary showing:
        - Field frequency per cluster
        - Canonical field suggestions
        - Section type distribution
    """)

    # Example analysis
    print("\n--- Example: Analyze Cluster 0 ---")
    # builder = SchemaBuilder(storage)
    # analysis = builder.analyze_pattern_cluster(cluster_id=0, sample_size=10)

    print("""
    CLUSTER 0 ANALYSIS (Example)
    ==============================================================
    Client count: 450
    Sample size: 10

    --- Top Fields (by frequency) ---
      Client_Name
        Frequency: 98.0%
        Section types: key_value
        Sample values: ['Acme Corp', 'Widget Inc']

      Customer_Name
        Frequency: 15.0%
        Section types: key_value
        Sample values: ['Beta LLC']

      Registration_ID
        Frequency: 92.0%
        Section types: key_value

    --- Canonical Field Suggestions ---
      Client:
        - Client_Name (98% frequency)
        - Customer_Name (15% frequency)

      Registration:
        - Registration_ID (92% frequency)
        - Registration_Number (8% frequency)
    """)

    # -------------------------------------------------------------------------
    # STEP 5: Define Field Mappings
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 5: Define Field Mappings")
    print("=" * 70)

    print("\n--- Creating Field Mapper ---")
    mapper = FieldMapper()
    register_default_transformations(mapper)

    # Define canonical schema
    print("\n--- Defining Canonical Schema ---")
    mapper.define_canonical_field(
        'Client_Name',
        'string',
        'Client legal name',
        required=True,
        validation_rules=['not_empty']
    )

    mapper.define_canonical_field(
        'Registration_ID',
        'string',
        'Client registration/license number',
        required=True,
        validation_rules=['not_empty']
    )

    mapper.define_canonical_field(
        'Country',
        'string',
        'Country of registration',
        required=True
    )

    print("""
    Defined canonical fields:
        ✓ Client_Name (string, required)
        ✓ Registration_ID (string, required)
        ✓ Country (string, required)
    """)

    # Define field mappings for each cluster
    print("\n--- Defining Field Mappings per Cluster ---")

    # Cluster 0: "Standard Form A"
    mapper.add_field_mapping(0, 'Client_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Customer_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(0, 'Registration_ID', 'Registration_ID')
    mapper.add_field_mapping(0, 'Registration_Number', 'Registration_ID')

    # Cluster 1: "Standard Form B"
    mapper.add_field_mapping(1, 'Entity_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(1, 'Legal_Name', 'Client_Name', 'trim')
    mapper.add_field_mapping(1, 'License_Number', 'Registration_ID')

    print("""
    Cluster 0 mappings:
        Client_Name → Client_Name (trim)
        Customer_Name → Client_Name (trim)
        Registration_ID → Registration_ID
        Registration_Number → Registration_ID

    Cluster 1 mappings:
        Entity_Name → Client_Name (trim)
        Legal_Name → Client_Name (trim)
        License_Number → Registration_ID
    """)

    # Save mappings
    mappings_file = "field_mappings_example.json"
    mapper.save_mappings(mappings_file)
    print(f"\n✓ Saved field mappings to: {mappings_file}")

    # -------------------------------------------------------------------------
    # STEP 6: Apply Field Mappings
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 6: Apply Field Mappings")
    print("=" * 70)

    print("""
    Apply mappings to normalize all client data:
    """)

    # Example code
    print("""
    ```python
    # Load mapper
    mapper = FieldMapper('field_mappings.json')

    # Get all clients
    clients = storage.search_clients(limit=10000)

    # Apply mappings
    for client_meta in clients:
        client_data = storage.get_client(client_meta['client_id'])

        # Map to canonical schema
        mapped_data = mapper.map_client_data(client_data)

        # Check for validation errors
        errors = mapped_data['processing_metadata'].get('validation_errors', [])
        if errors:
            print(f"Validation errors for {client_data['client_name']}: {errors}")

        # Save normalized version
        # storage.save_client(mapped_data)  # or save to different directory
    ```
    """)

    # Example mapped output
    print("\n--- Example Mapped Output ---")
    print("""
    {
      "client_id": "USA_AcmeCorp_FX",
      "client_name": "Acme Corp",
      "country": "USA",
      "product": "FX",
      "original_data": { /* full original JSON */ },
      "canonical_data": {
        "Client_Name": "Acme Corp",
        "Registration_ID": "12345",
        "Country": "USA"
      },
      "processing_metadata": {
        "mapped_at": "2024-10-21T12:00:00",
        "cluster_id": 0,
        "validation_errors": []
      }
    }
    """)

    # -------------------------------------------------------------------------
    # STEP 7: Query and Export
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 7: Query and Export Normalized Data")
    print("=" * 70)

    print("""
    Now you have normalized data that you can:

    1. Query by canonical fields:
       clients = storage.search_clients(has_field='Client_Name')

    2. Export to CSV:
       storage.export_to_csv('normalized_clients.csv')

    3. Build final data pipeline:
       - Load normalized JSON files
       - Transform to your target format
       - Load into data warehouse / analytics platform

    4. Generate reports:
       - Field coverage analysis
       - Data quality metrics
       - Missing required fields
    """)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)

    print("""
    Summary:
    --------
    1. ✓ Extracted 2000+ Excel files → JSON files
    2. ✓ Clustered into 12 pattern groups
    3. ✓ Analyzed common fields per cluster
    4. ✓ Defined canonical schema (3 core fields)
    5. ✓ Created field mappings per cluster
    6. ✓ Applied mappings to normalize data
    7. ✓ Ready for export to target system

    Key Insights:
    -------------
    - 12 distinct form templates identified
    - 98% of clients have Client_Name field (but with variations)
    - 92% have Registration_ID (various names)
    - 15 outlier clients need manual review

    Next Steps:
    -----------
    1. Review validation errors
    2. Handle outlier clients manually
    3. Add more canonical fields as needed
    4. Build final ETL pipeline
    5. Load into target data warehouse
    """)

    print("\n" + "=" * 70)
    print("See REFACTORING_GUIDE.md for detailed documentation")
    print("=" * 70)


if __name__ == '__main__':
    example_workflow()
