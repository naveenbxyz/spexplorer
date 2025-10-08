import streamlit as st
import pandas as pd
from sharepoint_client import SharePointClient
from excel_extractor import ExcelExtractor
import json
from datetime import datetime

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
    ["Windows Authentication (NTLM)", "Basic Authentication", "Client Credentials (OAuth)", "Access Token"]
)

if auth_method in ["Windows Authentication (NTLM)", "Basic Authentication"]:
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
            if auth_method == "Windows Authentication (NTLM)":
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

    # Folder navigation
    st.header("📂 Browse Folders")

    st.markdown("""
    💡 **Path format tips:**
    - Use full server-relative path: `/sites/project/subproject/Document Library/Folder`
    - Or relative from site: `Document Library/Secure Area/Client Folders/Country`
    - URL-encoded spaces are handled automatically
    """)

    col1, col2 = st.columns([3, 1])

    with col1:
        folder_path = st.text_input(
            "Folder Path",
            value=st.session_state.current_folder,
            placeholder="Document Library/Secure Area/Client Folders",
            help="Enter server-relative path (e.g., '/sites/project/Document Library/Folder') or relative path"
        )

    with col2:
        if st.button("📁 Browse Folder", use_container_width=True):
            st.session_state.current_folder = folder_path

    if st.session_state.current_folder or st.button("Load Root Folder"):
        try:
            with st.spinner("Loading files..."):
                # Get files from SharePoint
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

                if excel_files:
                    st.success(f"Found {len(excel_files)} Excel file(s) matching criteria")

                    # Display files in a table
                    st.subheader("📊 Matching Files")

                    # Prepare data for display
                    file_data = []
                    for file in excel_files:
                        file_data.append({
                            "Filename": file['name'],
                            "Modified": file['modified'],
                            "Size (KB)": round(file['size'] / 1024, 2),
                            "Modified By": file.get('modified_by', 'N/A'),
                            "URL": file['url']
                        })

                    df = pd.DataFrame(file_data)

                    # Display table
                    st.dataframe(df, use_container_width=True, hide_index=True)

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
