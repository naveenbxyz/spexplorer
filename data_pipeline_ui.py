"""
Comprehensive Streamlit UI for the complete data pipeline:
1. SharePoint Connection & Download
2. JSON Extraction & Pattern Clustering
3. Schema Discovery & Data Model Analysis
"""

import streamlit as st
import os
from pathlib import Path
import time
from datetime import datetime
import pandas as pd

# Import existing modules
from sharepoint_client import SharePointClient
from concurrent_downloader import ConcurrentDownloader
from client_processor import ClientProcessor
from client_processor_robust import RobustClientProcessor
from json_storage import JSONStorage
from client_database import ClientDatabase
from pattern_clustering import PatternClusterer
from schema_builder import SchemaBuilder


# Page configuration
st.set_page_config(
    page_title="Data Extraction Pipeline",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """Initialize session state variables."""
    if 'sharepoint_connected' not in st.session_state:
        st.session_state.sharepoint_connected = False
    if 'sharepoint_client' not in st.session_state:
        st.session_state.sharepoint_client = None
    if 'files_downloaded' not in st.session_state:
        st.session_state.files_downloaded = []
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'clustering_complete' not in st.session_state:
        st.session_state.clustering_complete = False


def main():
    """Main application."""
    init_session_state()

    st.title("📊 Data Extraction Pipeline")
    st.markdown("---")

    # Sidebar navigation
    st.sidebar.title("Pipeline Stages")
    stage = st.sidebar.radio(
        "Select Stage",
        [
            "🔗 1. SharePoint Download",
            "📦 2. JSON Extraction & Clustering",
            "🔍 3. Schema Discovery & Analysis"
        ]
    )

    if stage == "🔗 1. SharePoint Download":
        stage_sharepoint_download()
    elif stage == "📦 2. JSON Extraction & Clustering":
        stage_json_extraction()
    elif stage == "🔍 3. Schema Discovery & Analysis":
        stage_schema_discovery()


# =============================================================================
# STAGE 1: SharePoint Download
# =============================================================================

def stage_sharepoint_download():
    """Stage 1: Connect to SharePoint and download files."""
    st.header("🔗 Stage 1: SharePoint Connection & File Download")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Connection Settings")

        site_url = st.text_input(
            "SharePoint Site URL",
            value="https://yoursite.sharepoint.com/sites/YourSite",
            help="Full URL to your SharePoint site"
        )

        auth_method = st.selectbox(
            "Authentication Method",
            ["Windows Integrated (Current User)", "Username/Password", "Access Token"]
        )

        verify_ssl = st.checkbox("Verify SSL Certificate", value=True)

        # Auth-specific fields
        username = None
        password = None
        access_token = None

        if auth_method == "Username/Password":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
        elif auth_method == "Access Token":
            access_token = st.text_area("Access Token")

        if st.button("🔌 Connect to SharePoint", type="primary"):
            with st.spinner("Connecting to SharePoint..."):
                try:
                    client = SharePointClient(
                        site_url=site_url,
                        verify_ssl=verify_ssl
                    )

                    # Authenticate based on method
                    if auth_method == "Windows Integrated (Current User)":
                        client.authenticate_windows()
                    elif auth_method == "Username/Password":
                        if username and password:
                            client.authenticate_basic(username, password)
                        else:
                            st.error("Please enter username and password")
                            return
                    elif auth_method == "Access Token":
                        if access_token:
                            client.authenticate_token(access_token)
                        else:
                            st.error("Please enter access token")
                            return

                    st.session_state.sharepoint_client = client
                    st.session_state.sharepoint_connected = True
                    st.success(f"✅ Connected to SharePoint!")

                except Exception as e:
                    st.error(f"❌ Connection failed: {e}")

    with col2:
        if st.session_state.sharepoint_connected:
            st.subheader("✅ Connected")
            st.info(f"Site: {site_url}")
        else:
            st.subheader("Not Connected")
            st.warning("Please connect to SharePoint first")

    # File search and download section
    if st.session_state.sharepoint_connected:
        st.markdown("---")
        st.subheader("📁 Search and Download Files")

        col1, col2 = st.columns([2, 1])

        with col1:
            folder_path = st.text_input(
                "Folder Path",
                value="Shared Documents",
                help="Path to search (e.g., 'Shared Documents/Client Folders')"
            )

            search_recursive = st.checkbox("Search Recursively (all subfolders)", value=True)

            filename_patterns = st.text_input(
                "Filename Patterns (comma-separated)",
                value="",
                help="e.g., GGGG, PPPP (leave empty for all .xlsx files)"
            )

        with col2:
            output_folder = st.text_input(
                "Output Folder",
                value="./output",
                help="Local folder to save files"
            )

            max_concurrent = st.number_input(
                "Concurrent Downloads",
                min_value=1,
                max_value=10,
                value=5,
                help="Number of parallel downloads"
            )

        if st.button("🔍 Search & Download Files", type="primary"):
            patterns = [p.strip() for p in filename_patterns.split(',')] if filename_patterns else []

            progress_bar = st.progress(0)
            status_text = st.empty()
            results_placeholder = st.empty()

            try:
                client = st.session_state.sharepoint_client

                # Search for files
                status_text.text("🔍 Searching for files...")
                files = client.search_files_recursive(
                    folder_path=folder_path,
                    patterns=patterns,
                    file_extension=".xlsx"
                ) if search_recursive else client.list_files(folder_path)

                if patterns:
                    files = [f for f in files if any(p.lower() in f['name'].lower() for p in patterns)]

                status_text.text(f"📊 Found {len(files)} files")

                if files:
                    # Download files
                    downloader = ConcurrentDownloader(
                        client,
                        output_folder=output_folder,
                        max_workers=max_concurrent
                    )

                    downloaded_files = []
                    failed_files = []

                    for idx, file_info in enumerate(files):
                        try:
                            local_path = downloader.download_file(file_info)
                            downloaded_files.append({
                                'name': file_info['name'],
                                'path': local_path,
                                'size': file_info.get('size', 0)
                            })
                        except Exception as e:
                            failed_files.append({
                                'name': file_info['name'],
                                'error': str(e)
                            })

                        # Update progress
                        progress = (idx + 1) / len(files)
                        progress_bar.progress(progress)
                        status_text.text(f"📥 Downloading {idx + 1}/{len(files)}...")

                    # Show results
                    st.session_state.files_downloaded = downloaded_files
                    progress_bar.progress(1.0)
                    status_text.text("✅ Download complete!")

                    with results_placeholder.container():
                        st.success(f"✅ Downloaded {len(downloaded_files)} files to {output_folder}")

                        if failed_files:
                            st.warning(f"⚠️ {len(failed_files)} files failed")
                            with st.expander("View failed files"):
                                st.json(failed_files)

                        # Show downloaded files
                        if downloaded_files:
                            df = pd.DataFrame(downloaded_files)
                            st.dataframe(df, use_container_width=True)

                else:
                    status_text.text("❌ No files found")

            except Exception as e:
                st.error(f"❌ Error: {e}")


# =============================================================================
# STAGE 2: JSON Extraction & Clustering
# =============================================================================

def stage_json_extraction():
    """Stage 2: Extract to JSON and run pattern clustering."""
    st.header("📦 Stage 2: JSON Extraction & Pattern Clustering")

    # Check prerequisites
    if not Path("./output").exists() or not list(Path("./output").rglob("*.xlsx")):
        st.warning("⚠️ No Excel files found in ./output folder. Please download files first (Stage 1).")
        return

    tab1, tab2 = st.tabs(["📄 JSON Extraction", "🎯 Pattern Clustering"])

    # TAB 1: JSON Extraction
    with tab1:
        st.subheader("Extract Excel Files to JSON")

        col1, col2 = st.columns([2, 1])

        with col1:
            output_folder = st.text_input(
                "Excel Files Folder",
                value="./output",
                help="Folder containing downloaded Excel files"
            )

            json_folder = st.text_input(
                "JSON Output Folder",
                value="./extracted_json",
                help="Folder to save extracted JSON files"
            )

        with col2:
            processing_mode = st.selectbox(
                "Processing Engine",
                [
                    "Standard (ClientProcessor)",
                    "Robust (with timeout)"
                ],
                help="Standard mode uses the latest ClientProcessor with detailed error reporting. Robust mode adds timeouts and retries."
            )

            enable_sqlite = st.checkbox("Enable SQLite (optional)", value=True)
            db_path = st.text_input("SQLite DB Path", value="client_data.db") if enable_sqlite else None

            max_workers = st.slider(
                "Concurrent Workers",
                min_value=1,
                max_value=8,
                value=4,
                help="More workers = faster (but uses more CPU)"
            )

            timeout_seconds = None
            max_retries = None

            if processing_mode.startswith("Robust"):
                timeout_seconds = st.number_input(
                    "Timeout per file (seconds)",
                    min_value=30,
                    max_value=600,
                    value=120,
                    help="Maximum time to process each file (prevents hanging)"
                )

                max_retries = st.number_input(
                    "Max retries for failed files",
                    min_value=0,
                    max_value=3,
                    value=1,
                    help="Number of retry attempts for failed files"
                )

            reprocess = st.checkbox("Reprocess existing files", value=False)

        if st.button("🚀 Start Extraction", type="primary"):
            progress_container = st.container()

            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()
                stats_col1, stats_col2, stats_col3 = st.columns(3)

                metric_processed = stats_col1.empty()
                metric_failed = stats_col2.empty()
                metric_speed = stats_col3.empty()

                # Add more detailed stats
                stats_col4, stats_col5, stats_col6 = st.columns(3)
                metric_timeout = stats_col4.empty()
                metric_corrupted = stats_col5.empty()
                metric_current = stats_col6.empty()

                log_container = st.expander("📋 Processing Log", expanded=True)
                log_placeholder = log_container.empty()
                logs = []

                def progress_callback(info):
                    phase = info.get('phase')

                    if phase == 'discovery':
                        message = info.get('message', 'Discovering files...')
                        logs.append(f"📂 {message}")
                        log_placeholder.text('\n'.join(logs[-50:]))

                    elif phase == 'discovery_complete':
                        logs.append(f"✅ Discovered {info.get('total_files', 0)} files")
                        log_placeholder.text('\n'.join(logs[-50:]))

                    elif phase == 'processing_start':
                        message = info.get('message')
                        total_to_process = info.get('total_to_process')
                        if message:
                            logs.append(f"🔄 {message}")
                        elif total_to_process is not None:
                            logs.append(f"🔄 Processing {total_to_process} files")
                        log_placeholder.text('\n'.join(logs[-50:]))

                    elif phase == 'processing':
                        current = info.get('current', 0)
                        total = info.get('total', 0)
                        client_name = info.get('client_name') or 'Unknown client'
                        status = info.get('status', 'unknown')

                        progress = current / total if total > 0 else 0
                        progress_bar.progress(progress)
                        status_text.text(f"Processing {current}/{total}: {client_name}")

                        stats = info.get('stats', {})
                        metric_processed.metric("✅ Processed", stats.get('processed', 0))
                        metric_failed.metric("❌ Failed", stats.get('failed', 0))

                        start_time = stats.get('start_time')
                        speed_display = "-"
                        if isinstance(start_time, datetime) and current > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            if elapsed > 0:
                                speed_display = f"{current / elapsed:.1f} files/sec"
                        metric_speed.metric("⚡ Speed", speed_display)

                        timeout_val = stats.get('timeout')
                        metric_timeout.metric("⏱️ Timeout", timeout_val if timeout_val is not None else "-")

                        corrupted_val = stats.get('corrupted')
                        metric_corrupted.metric("🔥 Corrupted", corrupted_val if corrupted_val is not None else "-")

                        current_file_path = stats.get('current_file')
                        if current_file_path:
                            current_display = Path(current_file_path).name
                        else:
                            current_display = client_name
                        if current_display and len(current_display) > 40:
                            current_display = current_display[:37] + "..."
                        metric_current.metric("📄 Current", current_display or "-")

                        icon = '✅' if status == 'success' else '❌'
                        logs.append(f"{icon} [{current}/{total}] {client_name}")

                        if status == 'error':
                            error_message = info.get('error') or 'Unknown error'
                            logs.append(f"   ↳ {error_message}")

                        log_placeholder.text('\n'.join(logs[-50:]))

                    elif phase == 'retry':
                        retry_client = info.get('client_name') or 'Unknown client'
                        retry_count = info.get('retry_count', 0)
                        error_message = info.get('error') or 'Retry triggered'
                        logs.append(f"🔁 Retry #{retry_count} for {retry_client}: {error_message}")
                        log_placeholder.text('\n'.join(logs[-50:]))

                    elif phase == 'completed':
                        progress_bar.progress(1.0)
                        stats = info['stats']
                        status_text.text("✅ Extraction complete!")

                        # Show completion summary
                        col1, col2 = st.columns(2)

                        with col1:
                            st.success(f"""
                            ✅ **Extraction Complete!**
                            - Processed: {stats['processed']}
                            - Failed: {stats['failed']}
                            - JSON files: {stats.get('json_written', 0)}
                            - SQLite records: {stats.get('sqlite_written', 0)}
                            """)

                        with col2:
                            timeout_val = stats.get('timeout', 0)
                            corrupted_val = stats.get('corrupted', 0)
                            failed_val = stats.get('failed', 0)
                            retried_val = stats.get('retried', 0)
                            if any([
                                (timeout_val or 0) > 0,
                                (corrupted_val or 0) > 0,
                                (failed_val or 0) > 0,
                                (retried_val or 0) > 0
                            ]):
                                st.warning(f"""
                                ⚠️ **Issues Detected**
                                - Timeout: {timeout_val or 0}
                                - Corrupted: {corrupted_val or 0}
                                - Retried: {retried_val or 0}
                                - Failed: {failed_val or 0}
                                """)

                        # Show stuck files if any
                        if stats.get('stuck_files'):
                            with st.expander(f"⚠️ {len(stats['stuck_files'])} Files Timed Out"):
                                for stuck_file in stats['stuck_files']:
                                    st.text(f"- {stuck_file}")

                        logs.append("✨ Processing completed")
                        log_placeholder.text('\n'.join(logs[-50:]))

                        st.session_state.processing_complete = True

                processor = None

                try:
                    if processing_mode.startswith("Standard"):
                        db_path_value = db_path or "client_data.db"
                        processor = ClientProcessor(
                            output_folder=output_folder,
                            db_path=db_path_value,
                            json_path=json_folder,
                            enable_json=True,
                            enable_sqlite=enable_sqlite,
                            max_workers=max_workers,
                            progress_callback=progress_callback
                        )
                    else:
                        processor = RobustClientProcessor(
                            output_folder=output_folder,
                            json_path=json_folder,
                            db_path=db_path if enable_sqlite else None,
                            enable_json=True,
                            enable_sqlite=enable_sqlite,
                            max_workers=max_workers,
                            timeout_seconds=timeout_seconds or 120,
                            max_retries=max_retries or 0,
                            progress_callback=progress_callback
                        )

                    processor.process_all(reprocess=reprocess)

                except Exception as e:
                    st.error(f"❌ Error during extraction: {e}")

                finally:
                    if processor:
                        processor.close()

    # TAB 2: Pattern Clustering
    with tab2:
        st.subheader("Pattern Clustering")

        if not st.session_state.processing_complete:
            st.info("ℹ️ Please extract files to JSON first (JSON Extraction tab)")
            return

        col1, col2 = st.columns([2, 1])

        with col1:
            db_path = st.text_input("SQLite Database", value="client_data.db")

        with col2:
            min_cluster_size = st.number_input("Min Cluster Size", min_value=1, value=2)
            similarity_threshold = st.slider("Similarity Threshold", 0.0, 1.0, 0.7, 0.05)

        if st.button("🎯 Run Pattern Clustering", type="primary"):
            with st.spinner("Running pattern clustering..."):
                try:
                    db = ClientDatabase(db_path)
                    clusterer = PatternClusterer(db)

                    results = clusterer.cluster_clients(
                        min_cluster_size=min_cluster_size,
                        similarity_threshold=similarity_threshold
                    )

                    st.success(f"""
                    ✅ **Clustering Complete!**
                    - Total clients: {results['total_clients']}
                    - Clusters found: {results.get('total_clusters', 0)}
                    - Outliers: {results.get('outliers', 0)}
                    """)

                    # Show cluster summary
                    st.markdown("### 📊 Cluster Summary")

                    for cluster in results.get('clusters', []):
                        if cluster['cluster_id'] >= 0:
                            with st.expander(f"**{cluster['cluster_name']}** ({cluster['client_count']} clients)"):
                                structure = cluster['structure_summary']

                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Common Sheet Names:**")
                                    for sheet in structure.get('common_sheet_names', [])[:5]:
                                        st.markdown(f"- {sheet}")

                                with col2:
                                    st.markdown("**Section Types:**")
                                    for stype, count in structure.get('section_type_distribution', {}).items():
                                        st.markdown(f"- {stype}: {count}")

                                st.markdown("**Top Fields:**")
                                for field in structure.get('common_fields', [])[:10]:
                                    st.markdown(f"- `{field}`")

                    st.session_state.clustering_complete = True
                    db.close()

                except Exception as e:
                    st.error(f"❌ Clustering error: {e}")


# =============================================================================
# STAGE 3: Schema Discovery & Analysis
# =============================================================================

def stage_schema_discovery():
    """Stage 3: Schema discovery and data model analysis."""
    st.header("🔍 Stage 3: Schema Discovery & Data Model Analysis")

    if not st.session_state.clustering_complete:
        st.warning("⚠️ Please run pattern clustering first (Stage 2)")
        return

    tab1, tab2, tab3 = st.tabs(["📋 Cluster Analysis", "🏗️ Schema Builder", "🗺️ Field Mapping"])

    # TAB 1: Cluster Analysis
    with tab1:
        st.subheader("Analyze Pattern Clusters")

        json_storage = JSONStorage("./extracted_json")
        db = ClientDatabase("client_data.db")

        # Get available clusters
        clusters = db.get_pattern_clusters()

        if not clusters:
            st.warning("No clusters found. Run clustering first.")
            return

        cluster_options = {f"Cluster {c['cluster_id']} ({c['client_count']} clients)": c['cluster_id']
                          for c in clusters if c['cluster_id'] >= 0}

        selected_cluster_name = st.selectbox("Select Cluster to Analyze", list(cluster_options.keys()))
        selected_cluster_id = cluster_options[selected_cluster_name]

        sample_size = st.slider("Sample Size", min_value=5, max_value=50, value=10)

        if st.button("🔍 Analyze Cluster", type="primary"):
            with st.spinner(f"Analyzing cluster {selected_cluster_id}..."):
                try:
                    builder = SchemaBuilder(json_storage)
                    analysis = builder.analyze_pattern_cluster(selected_cluster_id, sample_size=sample_size)

                    st.success(f"✅ Analyzed {analysis['sample_size']} clients from cluster {selected_cluster_id}")

                    # Show field statistics
                    st.markdown("### 📊 Field Frequency Analysis")

                    field_stats = analysis['field_statistics']
                    field_df = pd.DataFrame([
                        {
                            'Field Name': field_name,
                            'Frequency': f"{stats['frequency']:.1%}",
                            'Occurrences': stats['occurrences'],
                            'Section Types': ', '.join(stats['section_types']),
                            'Sample Values': str(stats['sample_values'][:2])
                        }
                        for field_name, stats in list(field_stats.items())[:30]
                    ])

                    st.dataframe(field_df, use_container_width=True)

                    # Show canonical suggestions
                    st.markdown("### 🏗️ Canonical Field Suggestions")

                    suggestions = analysis['canonical_suggestions']
                    if suggestions:
                        for canonical, variants in suggestions.items():
                            with st.expander(f"**{canonical}** ({len(variants)} variants)"):
                                for variant in variants:
                                    st.markdown(f"- `{variant}`")
                    else:
                        st.info("No strong canonical field suggestions for this cluster")

                    # Show section types
                    st.markdown("### 📑 Section Type Distribution")
                    section_types = analysis['section_types']
                    section_df = pd.DataFrame([
                        {'Section Type': stype, 'Count': count}
                        for stype, count in section_types.items()
                    ])
                    st.bar_chart(section_df.set_index('Section Type'))

                except Exception as e:
                    st.error(f"❌ Analysis error: {e}")

        db.close()

    # TAB 2: Schema Builder
    with tab2:
        st.subheader("Build Canonical Schema")

        st.markdown("""
        Define your canonical data model based on cluster analysis.

        **Steps:**
        1. Review field frequency across clusters
        2. Identify core fields (present in 80%+ of files)
        3. Define canonical field names and types
        4. Create field mappings per cluster
        """)

        st.markdown("### Define Canonical Fields")

        num_fields = st.number_input("Number of canonical fields", min_value=1, max_value=50, value=5)

        canonical_fields = []
        for i in range(num_fields):
            col1, col2, col3, col4 = st.columns([2, 1, 2, 1])

            with col1:
                field_name = st.text_input(f"Field Name {i+1}", key=f"field_name_{i}")
            with col2:
                field_type = st.selectbox(
                    f"Type {i+1}",
                    ["string", "number", "date", "boolean"],
                    key=f"field_type_{i}"
                )
            with col3:
                description = st.text_input(f"Description {i+1}", key=f"field_desc_{i}")
            with col4:
                required = st.checkbox(f"Required", key=f"field_req_{i}")

            if field_name:
                canonical_fields.append({
                    'name': field_name,
                    'type': field_type,
                    'description': description,
                    'required': required
                })

        if st.button("💾 Save Canonical Schema"):
            import json
            schema_file = "canonical_schema.json"
            with open(schema_file, 'w') as f:
                json.dump(canonical_fields, f, indent=2)

            st.success(f"✅ Saved canonical schema to {schema_file}")
            st.json(canonical_fields)

    # TAB 3: Field Mapping
    with tab3:
        st.subheader("Field Mapping Configuration")

        st.markdown("""
        Map source fields from each cluster to your canonical schema.

        **Example:**
        - Cluster 0: `Client_Name` → `Client_Name`
        - Cluster 0: `Customer_Name` → `Client_Name`
        - Cluster 1: `Entity_Name` → `Client_Name`
        """)

        st.info("ℹ️ Use the programmatic approach in field_mapper.py for complete mapping configuration")

        st.code("""
# Example field mapping code
from field_mapper import FieldMapper, register_default_transformations

mapper = FieldMapper()
register_default_transformations(mapper)

# Define canonical schema
mapper.define_canonical_field(
    'Client_Name', 'string', 'Client legal name',
    required=True, validation_rules=['not_empty']
)

# Add mappings for cluster 0
mapper.add_field_mapping(0, 'Client_Name', 'Client_Name', 'trim')
mapper.add_field_mapping(0, 'Customer_Name', 'Client_Name', 'trim')

# Save mappings
mapper.save_mappings('field_mappings.json')
        """, language="python")


if __name__ == "__main__":
    main()
