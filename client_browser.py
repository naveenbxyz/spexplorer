"""
Streamlit app for client data browsing and search.
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from client_processor import ClientProcessor
from client_database import ClientDatabase
from pattern_clustering import PatternClusterer

st.set_page_config(page_title="Client Browser", layout="wide", page_icon="🔍")

st.title("🔍 Client Data Browser")

# Sidebar for configuration
st.sidebar.header("Configuration")

output_folder = st.sidebar.text_input(
    "Excel Files Folder",
    value="./output",
    help="Folder containing downloaded Excel files"
)

db_path = st.sidebar.text_input(
    "Database Path",
    value="client_data.db",
    help="Path to SQLite database"
)

# Check if database exists
db_exists = Path(db_path).exists()

if not db_exists:
    st.warning("⚠️ Database does not exist. Please process Excel files first.")

    st.markdown("### 📊 Process Excel Files")

    if not Path(output_folder).exists():
        st.error(f"Output folder does not exist: {output_folder}")
        st.info("Please download files from SharePoint first using the main app (app.py)")
    else:
        excel_count = len(list(Path(output_folder).rglob("*.xlsx"))) + len(list(Path(output_folder).rglob("*.xls")))
        st.info(f"📁 Found {excel_count} Excel files in output folder")

        if st.button("🚀 Start Processing", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            stats_placeholder = st.empty()

            def progress_callback(info):
                phase = info.get('phase')

                if phase == 'discovery':
                    status_text.info(f"📂 {info['message']}")
                elif phase == 'discovery_complete':
                    status_text.success(f"✅ {info['message']}")
                elif phase == 'processing_start':
                    status_text.info(f"🔄 {info['message']}")
                elif phase == 'processing':
                    current = info['current']
                    total = info['total']
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(progress)

                    client_name = info['client_name']
                    status = info['status']
                    status_icon = '✅' if status == 'success' else '❌'

                    status_text.text(f"{status_icon} [{current}/{total}] {client_name}")

                    stats = info.get('stats', {})
                    col1, col2 = stats_placeholder.columns(2)
                    col1.metric("Processed", stats.get('processed', 0))
                    col2.metric("Failed", stats.get('failed', 0))

                elif phase == 'completed':
                    status_text.success("✨ Processing completed!")
                    progress_bar.progress(1.0)

            try:
                with ClientProcessor(
                    output_folder=output_folder,
                    db_path=db_path,
                    progress_callback=progress_callback
                ) as processor:
                    processor.process_all(reprocess=False)

                    final_stats = processor.get_statistics()
                    st.success("Processing complete! Refresh the page to browse clients.")

                    db_stats = final_stats.get('database', {})
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Clients", db_stats.get('total_clients', 0))
                    col2.metric("Countries", db_stats.get('countries', 0))
                    col3.metric("Products", db_stats.get('products', 0))
                    col4.metric("Unique Patterns", db_stats.get('unique_patterns', 0))

            except Exception as e:
                st.error(f"Processing failed: {str(e)}")
                st.exception(e)

else:
    # Database exists - show browser interface
    db = ClientDatabase(db_path)

    # Main tabs
    search_tab, patterns_tab, stats_tab = st.tabs(["🔍 Search Clients", "📊 Pattern Clusters", "📈 Statistics"])

    with search_tab:
        st.header("Search Clients")

        # Search filters
        col1, col2, col3 = st.columns(3)

        with col1:
            # Get countries
            countries = db.get_countries()
            country_filter = st.selectbox(
                "Country",
                options=['All'] + countries,
                index=0
            )

        with col2:
            # Get products
            products = db.get_products()
            product_filter = st.selectbox(
                "Product",
                options=['All'] + products,
                index=0
            )

        with col3:
            # Get clusters
            clusters = db.get_pattern_clusters()
            cluster_options = ['All'] + [f"Cluster {c['cluster_id']} ({c['client_count']} clients)" for c in clusters if c['cluster_id'] >= 0]
            cluster_filter = st.selectbox(
                "Pattern Cluster",
                options=cluster_options,
                index=0
            )

        # Search query
        search_query = st.text_input(
            "🔍 Search by client name",
            placeholder="Enter client name..."
        )

        # Apply filters
        search_params = {
            'query': search_query if search_query else None,
            'country': country_filter if country_filter != 'All' else None,
            'product': product_filter if product_filter != 'All' else None,
            'pattern_cluster': int(cluster_filter.split()[1]) if cluster_filter != 'All' else None,
            'limit': 100
        }

        clients = db.search_clients(**search_params)

        st.markdown(f"### Found {len(clients)} client(s)")

        if clients:
            # Display as table
            df = pd.DataFrame([
                {
                    'Client Name': c['client_name'],
                    'Country': c['country'],
                    'Product': c['product'],
                    'File': c['filename'],
                    'Date': c['extracted_date'] if c['extracted_date'] else 'N/A',
                    'Status': c['processing_status']
                }
                for c in clients
            ])

            # Client selection
            st.dataframe(df, use_container_width=True, hide_index=True)

            # View client details
            st.markdown("### 📄 View Client Details")

            selected_client_name = st.selectbox(
                "Select a client to view",
                options=[c['client_name'] for c in clients]
            )

            if selected_client_name:
                # Find selected client
                selected_client = next(c for c in clients if c['client_name'] == selected_client_name)
                client_id = selected_client['client_id']

                # Load full client data
                client_data = db.get_client(client_id)

                if client_data:
                    # Show client info
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Country", client_data.get('country', 'N/A'))
                    col2.metric("Product", client_data.get('product', 'N/A'))
                    col3.metric("Sheets", len(client_data.get('sheets', [])))
                    col4.metric("Pattern", client_data.get('pattern_signature', 'N/A')[:8])

                    # Display sheets and sections
                    st.markdown("#### 📋 Sheets and Sections")

                    for sheet in client_data.get('sheets', []):
                        with st.expander(f"📄 {sheet['sheet_name']} ({len(sheet.get('sections', []))} sections)"):
                            for section in sheet.get('sections', []):
                                section_type = section.get('section_type')
                                section_header = section.get('section_header', 'No header')

                                st.markdown(f"**Section: {section_header}** (Type: `{section_type}`)")

                                if section_type == 'key_value':
                                    # Display as key-value table
                                    data = section.get('data', {})
                                    if data:
                                        kv_df = pd.DataFrame([
                                            {'Key': k, 'Value': v}
                                            for k, v in data.items()
                                        ])
                                        st.dataframe(kv_df, use_container_width=True, hide_index=True)

                                elif section_type in ['table', 'complex_header']:
                                    # Display as table
                                    data_rows = section.get('data', [])
                                    if data_rows:
                                        # Remove internal fields
                                        display_rows = [
                                            {k: v for k, v in row.items() if not k.startswith('_')}
                                            for row in data_rows
                                        ]
                                        table_df = pd.DataFrame(display_rows)
                                        st.dataframe(table_df, use_container_width=True, hide_index=True)

                                elif section_type == 'raw':
                                    # Display as raw data
                                    st.code(json.dumps(section.get('data', []), indent=2), language='json')

                                st.markdown("---")

                    # Download JSON
                    json_str = json.dumps(client_data, indent=2)
                    st.download_button(
                        label="📥 Download Full JSON",
                        data=json_str,
                        file_name=f"{client_data['client_name']}.json",
                        mime="application/json"
                    )

    with patterns_tab:
        st.header("Pattern Clusters")

        # Run clustering button
        col1, col2 = st.columns([3, 1])

        with col1:
            st.info("Pattern clustering groups clients with similar Excel structures")

        with col2:
            if st.button("🔄 Run Clustering", use_container_width=True):
                with st.spinner("Running pattern clustering..."):
                    clusterer = PatternClusterer(db)
                    results = clusterer.cluster_clients(
                        min_cluster_size=2,
                        similarity_threshold=0.7,
                        max_clusters=20
                    )

                    st.success(f"✅ Found {results['total_clusters']} pattern clusters!")
                    st.rerun()

        # Display clusters
        clusters = db.get_pattern_clusters()

        if clusters:
            st.markdown(f"### 📊 {len(clusters)} Pattern Clusters")

            for cluster in clusters:
                if cluster['cluster_id'] >= 0:
                    with st.expander(
                        f"**{cluster['cluster_name']}** - {cluster['client_count']} clients",
                        expanded=False
                    ):
                        summary = cluster['structure_summary']

                        col1, col2 = st.columns([1, 2])

                        with col1:
                            st.metric("Clients", cluster['client_count'])
                            st.text(f"Created: {cluster['created_at'][:10]}")

                        with col2:
                            st.markdown("**Common Sheet Names:**")
                            st.write(", ".join(summary.get('common_sheet_names', [])[:5]))

                            st.markdown("**Section Types:**")
                            st.json(summary.get('section_type_distribution', {}))

                        st.markdown("**Common Fields:**")
                        fields = summary.get('common_fields', [])[:15]
                        st.code(", ".join(fields))

                        # Show example clients
                        st.markdown("**Example Clients:**")
                        example_ids = cluster['example_client_ids']
                        for client_id in example_ids:
                            client = db.search_clients(limit=1000)
                            client_names = [c['client_name'] for c in client if c['client_id'] == client_id]
                            if client_names:
                                st.text(f"  • {client_names[0]}")
        else:
            st.info("No pattern clusters yet. Click 'Run Clustering' to analyze patterns.")

    with stats_tab:
        st.header("Database Statistics")

        stats = db.get_statistics()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Clients", stats.get('total_clients', 0))
        col2.metric("Processed", stats.get('processed_clients', 0))
        col3.metric("Pending", stats.get('pending_clients', 0))
        col4.metric("Failed", stats.get('failed_clients', 0))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Countries", stats.get('countries', 0))
        col2.metric("Products", stats.get('products', 0))
        col3.metric("Unique Patterns", stats.get('unique_patterns', 0))
        col4.metric("Pattern Clusters", stats.get('pattern_clusters', 0))

        # Folder summary
        st.markdown("### 📁 Folder Structure")
        folder_summary = db.get_folder_summary()

        if folder_summary:
            folder_df = pd.DataFrame(folder_summary)
            st.dataframe(folder_df, use_container_width=True, hide_index=True)

            # Download
            csv = folder_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Folder Summary",
                data=csv,
                file_name=f"folder_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        # Search by field
        st.markdown("### 🔍 Search by Field Name")
        field_search = st.text_input("Enter field/column name to search")

        if field_search:
            results = db.search_by_field(field_search)

            if results:
                st.success(f"Found {len(results)} client(s) with field '{field_search}'")
                results_df = pd.DataFrame(results)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No clients found with field '{field_search}'")

    db.close()
