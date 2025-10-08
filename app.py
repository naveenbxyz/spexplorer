import streamlit as st
import pandas as pd
from sharepoint_client import SharePointClient
from excel_extractor import ExcelExtractor
from concurrent_downloader import BatchDownloader
import json
from datetime import datetime
import time

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
    """)
