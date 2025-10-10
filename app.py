import streamlit as st
import pandas as pd
from sharepoint_client import SharePointClient
from excel_extractor import ExcelExtractor
from concurrent_downloader import BatchDownloader
from batch_processor import BatchProcessor
from excel_database import ExcelDatabase
import json
from datetime import datetime
import time
from pathlib import Path

st.set_page_config(page_title="SharePoint Excel Explorer", layout="wide")

st.title("📁 SharePoint Excel Explorer")

# Sidebar for authentication
st.sidebar.header("SharePoint Authentication")

site_url = st.sidebar.text_input(
    "Site URL",
    placeholder="https://teamsites.company.net/sites/project",
    help="Enter your SharePoint site URL (full path to the site)"
)

auth_method = st.sidebar.selectbox(
    "Authentication Method",
    ["Windows Integrated (Current User)", "Windows Authentication (NTLM)", "Basic Authentication", "Client Credentials (OAuth)", "Access Token"]
)

if auth_method == "Windows Integrated (Current User)":
    st.sidebar.success("✅ Uses your current Windows login")
    st.sidebar.info("💡 No username/password needed - automatically uses your logged-in Windows credentials")
    st.sidebar.warning("⚠️ Requires: pip install requests-negotiate-sspi")
elif auth_method in ["Windows Authentication (NTLM)", "Basic Authentication"]:
    st.sidebar.info("💡 Use your Windows/domain credentials")
    username = st.sidebar.text_input(
        "Username",
        placeholder="DOMAIN\\username or user@domain.com",
        help="Enter your domain username"
    )
    password = st.sidebar.text_input("Password", type="password")
elif auth_method == "Client Credentials (OAuth)":
    client_id = st.sidebar.text_input("Client ID", type="password")
    client_secret = st.sidebar.text_input("Client Secret", type="password")
    tenant_id = st.sidebar.text_input("Tenant ID", type="password")
else:
    access_token = st.sidebar.text_input("Access Token", type="password")

# SSL verification option
st.sidebar.header("Connection Options")
verify_ssl = st.sidebar.checkbox(
    "Verify SSL Certificate",
    value=True,
    help="Uncheck for self-signed certificates (internal SharePoint)"
)

# File pattern filter
st.sidebar.header("File Filters")
pattern_input = st.sidebar.text_input(
    "Filename Patterns (comma-separated)",
    placeholder="XX, YY, ABC",
    help="Enter patterns to match in filenames (e.g., XX, YY)"
)

# Convert patterns to list
patterns = [p.strip() for p in pattern_input.split(",") if p.strip()] if pattern_input else []

# Output folder configuration
st.sidebar.header("File Persistence")
output_folder = st.sidebar.text_input(
    "Output Folder",
    value="./output",
    help="Local folder to save downloaded Excel files"
)
persist_files = st.sidebar.checkbox(
    "Download & Save Files",
    value=False,
    help="Automatically download and save all matching files to output folder"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'sp_client' not in st.session_state:
    st.session_state.sp_client = None
if 'current_folder' not in st.session_state:
    st.session_state.current_folder = ""

# Connect button
if st.sidebar.button("Connect to SharePoint"):
    try:
        with st.spinner("Connecting to SharePoint..."):
            if auth_method == "Windows Integrated (Current User)":
                sp_client = SharePointClient(
                    site_url=site_url,
                    auth_method="integrated",
                    verify_ssl=verify_ssl
                )
            elif auth_method == "Windows Authentication (NTLM)":
                sp_client = SharePointClient(
                    site_url=site_url,
                    username=username,
                    password=password,
                    auth_method="ntlm",
                    verify_ssl=verify_ssl
                )
            elif auth_method == "Basic Authentication":
                sp_client = SharePointClient(
                    site_url=site_url,
                    username=username,
                    password=password,
                    auth_method="basic",
                    verify_ssl=verify_ssl
                )
            elif auth_method == "Client Credentials (OAuth)":
                sp_client = SharePointClient(
                    site_url=site_url,
                    client_id=client_id,
                    client_secret=client_secret,
                    tenant_id=tenant_id,
                    auth_method="oauth",
                    verify_ssl=verify_ssl
                )
            else:  # Access Token
                sp_client = SharePointClient(
                    site_url=site_url,
                    access_token=access_token,
                    auth_method="token",
                    verify_ssl=verify_ssl
                )

            # Test connection and get site info
            sp_client.authenticate()
            site_info = sp_client.get_site_info()

            st.session_state.sp_client = sp_client
            st.session_state.authenticated = True
            st.session_state.site_info = site_info

            st.sidebar.success(f"✅ Connected to: {site_info.get('title', 'SharePoint')}")
            st.sidebar.info(f"📍 Site path: {site_info.get('server_relative_url', '')}")
    except Exception as e:
        st.sidebar.error(f"❌ Connection failed: {str(e)}")
        st.session_state.authenticated = False

# Main content
if st.session_state.authenticated:
    sp_client = st.session_state.sp_client

    # Display site info
    if 'site_info' in st.session_state:
        site_info = st.session_state.site_info
        st.info(f"📍 Connected to: **{site_info.get('title', 'SharePoint')}**  \nServer path: `{site_info.get('server_relative_url', '')}`")

    # Search mode selection
    st.header("🔍 Search for Excel Files")

    search_mode = st.radio(
        "Search Mode",
        ["Current Folder Only", "Recursive (All Subfolders)"],
        horizontal=True,
        help="Choose whether to search only the specified folder or include all subfolders"
    )

    st.markdown("""
    💡 **Path format tips:**
    - Use relative from site: `Document Library/Secure Area/Client Folders`
    - Or full server-relative path: `/sites/XXProducts/XX/Document Library/Secure Area/Client Folders`
    - URL-encoded spaces are handled automatically
    """)

    folder_path = st.text_input(
        "Folder Path",
        value=st.session_state.current_folder if st.session_state.current_folder else "Document Library/Secure Area/Client Folders",
        placeholder="Document Library/Secure Area/Client Folders",
        help="Enter the root folder path to search"
    )

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("🔍 Search for Files", use_container_width=True, type="primary"):
            st.session_state.current_folder = folder_path
            st.session_state.trigger_search = True

    with col2:
        if st.button("📁 Browse Folder", use_container_width=True):
            st.session_state.current_folder = folder_path
            st.session_state.trigger_search = False

    if st.session_state.get('trigger_search') or (st.session_state.current_folder and not st.session_state.get('trigger_search') == False):
        try:
            is_recursive = search_mode == "Recursive (All Subfolders)"

            if is_recursive:
                # Recursive search with optional concurrent downloading
                progress_placeholder = st.empty()
                status_placeholder = st.empty()
                download_status_placeholder = st.empty()

                # Initialize downloader if persistence is enabled
                downloader = None
                if persist_files:
                    downloader = BatchDownloader(
                        sp_client=sp_client,
                        output_folder=output_folder,
                        batch_size=50  # Download every 50 files
                    )

                def progress_callback(current_folder, files_found, folders_processed):
                    status_text = f"🔄 Searching... Folders: {folders_processed} | Files found: {files_found}"

                    # Add download status if persistence is enabled
                    if downloader:
                        dl_status = downloader.get_status()
                        status_text += f" | Downloaded: {dl_status['downloaded']}"
                        if dl_status['failed'] > 0:
                            status_text += f" | Failed: {dl_status['failed']}"

                    status_placeholder.info(status_text)
                    progress_placeholder.text(f"📂 Current: {current_folder}")

                def file_found_callback(file_info):
                    """Called when each file is found - add to downloader"""
                    if downloader:
                        downloader.add_file(file_info)

                with st.spinner("Starting recursive search..."):
                    excel_files = sp_client.search_files_recursive(
                        root_folder=st.session_state.current_folder,
                        filename_patterns=patterns if patterns else None,
                        file_extensions=['xlsx', 'xls'],
                        progress_callback=progress_callback,
                        file_found_callback=file_found_callback if persist_files else None
                    )

                # Finalize any remaining downloads
                if downloader:
                    with st.spinner("Finalizing downloads..."):
                        downloader.finalize()

                    dl_status = downloader.get_status()
                    if dl_status['downloaded'] > 0:
                        st.success(f"✅ Downloaded {dl_status['downloaded']} file(s) to: {output_folder}")

                    if dl_status['failed'] > 0:
                        st.warning(f"⚠️ Failed to download {dl_status['failed']} file(s)")
                        with st.expander("Show download errors"):
                            for error in dl_status['errors']:
                                st.text(f"{error['filename']}: {error['error']}")

                progress_placeholder.empty()
                status_placeholder.empty()
                download_status_placeholder.empty()

            else:
                # Single folder search
                with st.spinner("Loading files..."):
                    files = sp_client.get_files_in_folder(st.session_state.current_folder)

                    # Filter Excel files
                    excel_files = [f for f in files if f['name'].endswith(('.xlsx', '.xls'))]

                    # Apply pattern filtering
                    if patterns:
                        filtered_files = []
                        for file in excel_files:
                            if any(pattern.upper() in file['name'].upper() for pattern in patterns):
                                filtered_files.append(file)
                        excel_files = filtered_files

                    # Add folder_path for consistency
                    for file in excel_files:
                        file['folder_path'] = st.session_state.current_folder
                        file['relative_folder'] = '(current)'

            if excel_files:
                st.success(f"✅ Found {len(excel_files)} Excel file(s) matching criteria")

                # Display files in a table
                st.subheader("📊 Matching Files")

                # Prepare data for display
                file_data = []
                for file in excel_files:
                    # Handle size - ensure it's numeric
                    try:
                        size_kb = round(float(file['size']) / 1024, 2) if file.get('size') else 0
                    except (ValueError, TypeError):
                        size_kb = 0

                    file_data.append({
                        "Filename": file['name'],
                        "Folder": file.get('relative_folder', 'N/A'),
                        "Full Path": file.get('folder_path', 'N/A'),
                        "Modified": file['modified'],
                        "Size (KB)": size_kb,
                        "Modified By": file.get('modified_by', 'N/A')
                    })

                df = pd.DataFrame(file_data)

                # Display table
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Export to CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name=f"sharepoint_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

                # Save metadata if files were persisted
                if persist_files and len(excel_files) > 0:
                    from pathlib import Path
                    output_path = Path(output_folder)
                    metadata_file = output_path / f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    df.to_csv(metadata_file, index=False)
                    st.info(f"📋 Metadata saved to: {metadata_file}")

                # File selection for content extraction
                st.subheader("📄 Extract File Content")

                selected_file = st.selectbox(
                    "Select a file to extract",
                    options=[f['name'] for f in excel_files],
                    key="file_selector"
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔍 Extract to JSON", use_container_width=True):
                        try:
                            with st.spinner(f"Extracting content from {selected_file}..."):
                                # Find selected file
                                selected_file_obj = next(f for f in excel_files if f['name'] == selected_file)

                                # Download file content
                                file_content = sp_client.download_file(selected_file_obj['server_relative_url'])

                                # Extract to JSON
                                extractor = ExcelExtractor()
                                json_data = extractor.extract_to_json(file_content, selected_file)

                                st.session_state.extracted_json = json_data
                                st.session_state.extracted_filename = selected_file
                                st.success("✅ Content extracted successfully!")
                        except Exception as e:
                            st.error(f"❌ Extraction failed: {str(e)}")

                # Display extracted JSON
                if 'extracted_json' in st.session_state:
                    st.subheader(f"📋 Extracted Data: {st.session_state.extracted_filename}")

                    # Display as formatted JSON
                    st.json(st.session_state.extracted_json)

                    # Download button
                    json_str = json.dumps(st.session_state.extracted_json, indent=2)
                    st.download_button(
                        label="⬇️ Download JSON",
                        data=json_str,
                        file_name=f"{st.session_state.extracted_filename.rsplit('.', 1)[0]}.json",
                        mime="application/json"
                    )
            else:
                st.warning("No Excel files found matching the specified patterns.")

        except Exception as e:
            st.error(f"❌ Error loading files: {str(e)}")
            st.exception(e)
    # Excel Processing Section
    st.header("🔬 Excel File Processing")

    process_tab, analyze_tab, patterns_tab = st.tabs(["📊 Process Files", "📈 Analysis", "🔍 Pattern Discovery"])

    with process_tab:
        st.subheader("Batch Process Downloaded Files")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.info(f"📁 Output folder: `{output_folder}`")

            if Path(output_folder).exists():
                # Count files
                excel_files = list(Path(output_folder).rglob("*.xlsx")) + list(Path(output_folder).rglob("*.xls"))
                st.metric("Excel files in folder", len(excel_files))
            else:
                st.warning("Output folder does not exist yet. Download files first.")

        with col2:
            db_path = st.text_input("Database path", value="excel_data.db")

        reprocess = st.checkbox(
            "Reprocess already processed files",
            value=False,
            help="Check this to reprocess files that have already been parsed"
        )

        if st.button("🚀 Start Batch Processing", type="primary", use_container_width=True):
            if not Path(output_folder).exists():
                st.error("Output folder does not exist. Please download files first.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                stats_placeholder = st.empty()

                def progress_callback(info):
                    phase = info.get('phase')

                    if phase == 'discovery':
                        status_text.info(f"📂 {info['message']}")

                    elif phase == 'processing_start':
                        status_text.info(f"🔄 {info['message']}")

                    elif phase == 'processing':
                        current = info['current']
                        total = info['total']
                        progress = current / total if total > 0 else 0
                        progress_bar.progress(progress)

                        filename = info['filename']
                        status = info['status']
                        status_icon = '✅' if status == 'success' else '❌'

                        status_text.text(f"{status_icon} [{current}/{total}] {filename}")

                        # Update stats
                        stats = info.get('stats', {})
                        col1, col2, col3 = stats_placeholder.columns(3)
                        col1.metric("Processed", stats.get('processed', 0))
                        col2.metric("Failed", stats.get('failed', 0))
                        col3.metric("Progress", f"{int(progress * 100)}%")

                    elif phase == 'completed':
                        status_text.success("✨ Processing completed!")
                        progress_bar.progress(1.0)

                try:
                    with BatchProcessor(
                        output_folder=output_folder,
                        db_path=db_path,
                        progress_callback=progress_callback
                    ) as processor:
                        processor.process_all(reprocess=reprocess)

                        # Show final stats
                        final_stats = processor.get_statistics()
                        st.success("Processing complete!")

                        db_stats = final_stats.get('database', {})

                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Files", db_stats.get('total_files', 0))
                        col2.metric("Total Sheets", db_stats.get('total_sheets', 0))
                        col3.metric("Total Tables", db_stats.get('total_tables', 0))
                        col4.metric("Unique Patterns", db_stats.get('unique_patterns', 0))

                except Exception as e:
                    st.error(f"Processing failed: {str(e)}")
                    st.exception(e)

    with analyze_tab:
        st.subheader("Database Analysis")

        if Path(db_path).exists():
            try:
                db = ExcelDatabase(db_path)

                # Overall statistics
                stats = db.get_statistics()

                st.markdown("### 📊 Overall Statistics")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Files", stats.get('total_files', 0))
                col2.metric("Processed", stats.get('processed_files', 0))
                col3.metric("Pending", stats.get('pending_files', 0))
                col4.metric("Failed", stats.get('failed_files', 0))

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Sheets", stats.get('total_sheets', 0))
                col2.metric("Tables", stats.get('total_tables', 0))
                col3.metric("Unique Patterns", stats.get('unique_patterns', 0))
                col4.metric("Countries", stats.get('countries', 0))

                # Folder summary
                st.markdown("### 📁 Folder Structure Summary")
                folder_summary = db.get_folder_summary()

                if folder_summary:
                    folder_df = pd.DataFrame(folder_summary)
                    st.dataframe(folder_df, use_container_width=True, hide_index=True)

                    # Download folder summary
                    csv = folder_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Folder Summary",
                        data=csv,
                        file_name=f"folder_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No data available yet. Process files first.")

                # Search functionality
                st.markdown("### 🔍 Search Tables by Header")
                search_header = st.text_input("Enter header name to search")

                if search_header:
                    results = db.search_tables_by_header(search_header)

                    if results:
                        st.success(f"Found {len(results)} table(s) with header '{search_header}'")

                        results_df = pd.DataFrame(results)
                        st.dataframe(results_df, use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No tables found with header '{search_header}'")

                db.close()

            except Exception as e:
                st.error(f"Error accessing database: {str(e)}")
        else:
            st.info("Database does not exist yet. Process files first.")

    with patterns_tab:
        st.subheader("Pattern Discovery")

        if Path(db_path).exists():
            try:
                db = ExcelDatabase(db_path)

                patterns = db.get_pattern_summary()

                if patterns:
                    st.markdown(f"### 🔍 Discovered {len(patterns)} Unique Table Patterns")

                    for idx, pattern in enumerate(patterns):
                        with st.expander(
                            f"Pattern #{idx+1} - {pattern['occurrence_count']} occurrences",
                            expanded=(idx < 3)  # Expand first 3
                        ):
                            col1, col2 = st.columns([1, 2])

                            with col1:
                                st.metric("Occurrences", pattern['occurrence_count'])
                                st.text(f"First seen: {pattern['first_seen_date'][:10]}")
                                st.text(f"Last seen: {pattern['last_seen_date'][:10]}")

                            with col2:
                                st.markdown("**Sample Headers:**")
                                headers = pattern.get('sample_headers', [])
                                if headers:
                                    st.code(", ".join(headers[:10]))  # Show first 10 headers
                                else:
                                    st.text("No headers detected")

                            st.text(f"Pattern signature: {pattern['pattern_signature']}")

                    # Export patterns
                    patterns_df = pd.DataFrame([
                        {
                            'pattern_signature': p['pattern_signature'],
                            'occurrence_count': p['occurrence_count'],
                            'headers': ', '.join(p.get('sample_headers', [])[:5]),
                            'first_seen': p['first_seen_date'],
                            'last_seen': p['last_seen_date']
                        }
                        for p in patterns
                    ])

                    csv = patterns_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Pattern Summary",
                        data=csv,
                        file_name=f"pattern_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No patterns discovered yet. Process files first.")

                db.close()

            except Exception as e:
                st.error(f"Error accessing database: {str(e)}")
        else:
            st.info("Database does not exist yet. Process files first.")

else:
    st.info("👈 Please configure SharePoint connection in the sidebar and click 'Connect to SharePoint'")

    # Instructions
    st.markdown("""
    ### Getting Started

    1. **Authentication Setup**: You'll need either:
       - **App Registration** (Recommended): Client ID, Client Secret, and Tenant ID
       - **Personal Access Token**: A valid SharePoint access token

    2. **Enter your SharePoint site URL** in the format:
       ```
       https://yourtenant.sharepoint.com/sites/yoursite
       ```

    3. **Configure file patterns** (optional): Enter comma-separated patterns to filter files
       - Example: `XX, YY, Report` will match files containing these strings

    4. **Browse and extract**: Navigate folders and extract Excel files to JSON

    ### Features
    - 📁 Browse SharePoint folders
    - 🔍 Filter Excel files by filename patterns
    - 📊 View file metadata (size, modified date, etc.)
    - 📄 Extract Excel content to generic JSON format
    - ⬇️ Download extracted JSON data
    - 🔬 Batch process Excel files into SQLite database
    - 📈 Analyze folder structure and patterns
    - 🔍 Discover table patterns across files
    """)
