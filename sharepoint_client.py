import requests
from requests_ntlm import HttpNtlmAuth
from typing import List, Dict, Optional
from datetime import datetime
import json
import urllib.parse

# Optional imports for Windows Integrated Auth
try:
    from requests_negotiate_sspi import HttpNegotiateAuth
    SSPI_AVAILABLE = True
except ImportError:
    SSPI_AVAILABLE = False

try:
    from requests_kerberos import HTTPKerberosAuth, OPTIONAL
    KERBEROS_AVAILABLE = True
except ImportError:
    KERBEROS_AVAILABLE = False


class SharePointClient:
    """
    SharePoint REST API Client for authentication, folder browsing, and file operations.
    Supports OAuth2, Access Token, NTLM, Windows Integrated (SSPI), and Kerberos authentication.
    """

    def __init__(
        self,
        site_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: str = "oauth",
        verify_ssl: bool = True
    ):
        """
        Initialize SharePoint client.

        Args:
            site_url: Full SharePoint site URL
            client_id: Azure AD App Client ID (for OAuth)
            client_secret: Azure AD App Client Secret (for OAuth)
            tenant_id: Azure AD Tenant ID (for OAuth)
            access_token: Pre-obtained access token
            username: Username for NTLM/Basic auth (not needed for "integrated")
            password: Password for NTLM/Basic auth (not needed for "integrated")
            auth_method: Authentication method - "oauth", "token", "ntlm", "basic", "integrated"
            verify_ssl: Verify SSL certificates (default True, set False for self-signed certs)
        """
        self.site_url = site_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.access_token = access_token
        self.username = username
        self.password = password
        self.auth_method = auth_method.lower()
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # Disable SSL warnings if verify is False
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Extract tenant and site info
        parts = site_url.split('/')
        if len(parts) > 2:
            self.tenant = parts[2].split('.')[0]
        else:
            self.tenant = None

    def authenticate(self) -> str:
        """
        Authenticate using the specified method.

        Returns:
            Success message or access token string
        """
        # Set common headers
        self.session.headers.update({
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose'
        })

        if self.auth_method == "integrated":
            # Windows Integrated Authentication (UseDefaultCredentials = true)
            # Uses current logged-in Windows credentials
            if SSPI_AVAILABLE:
                # Windows SSPI (preferred for Windows)
                self.session.auth = HttpNegotiateAuth()
                self._test_connection()
                return "Windows Integrated (SSPI) authenticated"
            elif KERBEROS_AVAILABLE:
                # Kerberos (for Linux/Mac)
                self.session.auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)
                self._test_connection()
                return "Windows Integrated (Kerberos) authenticated"
            else:
                raise ValueError(
                    "Windows Integrated Authentication requires additional package.\n"
                    "Install: pip install requests-negotiate-sspi (Windows)\n"
                    "     or: pip install requests-kerberos (Linux/Mac)"
                )

        elif self.auth_method == "ntlm":
            # Windows Authentication (NTLM)
            if not self.username or not self.password:
                raise ValueError("Username and password required for NTLM authentication")

            self.session.auth = HttpNtlmAuth(self.username, self.password)
            self._test_connection()
            return "NTLM authenticated"

        elif self.auth_method == "basic":
            # Basic Authentication
            if not self.username or not self.password:
                raise ValueError("Username and password required for Basic authentication")

            self.session.auth = (self.username, self.password)
            self._test_connection()
            return "Basic auth authenticated"

        elif self.auth_method == "token" and self.access_token:
            # Use provided access token
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            self._test_connection()
            return self.access_token

        elif self.auth_method == "oauth" and self.client_id and self.client_secret and self.tenant_id:
            # OAuth2 Client Credentials Flow
            token_url = f"https://accounts.accesscontrol.windows.net/{self.tenant_id}/tokens/OAuth/2"

            # SharePoint uses a specific OAuth flow
            resource = f"00000003-0000-0ff1-ce00-000000000000/{self.tenant}.sharepoint.com@{self.tenant_id}"

            data = {
                'grant_type': 'client_credentials',
                'client_id': f"{self.client_id}@{self.tenant_id}",
                'client_secret': self.client_secret,
                'resource': resource
            }

            response = requests.post(token_url, data=data)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']

                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_token}'
                })

                return self.access_token
            else:
                raise Exception(f"OAuth authentication failed: {response.status_code} - {response.text}")
        else:
            raise ValueError("Invalid authentication configuration. Please provide valid credentials for your chosen auth method.")

    def _test_connection(self):
        """Test the connection by making a simple API call."""
        url = f"{self.site_url}/_api/web"
        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code == 401:
            error_msg = f"Authentication failed (401 Unauthorized). "
            if self.auth_method == "ntlm":
                error_msg += "Please check:\n"
                error_msg += "  - Username format: Use 'DOMAIN\\username' or 'username@domain.com'\n"
                error_msg += "  - Password is correct\n"
                error_msg += "  - Account has access to SharePoint site\n"
                error_msg += f"  - Attempted username: {self.username}"
            raise Exception(error_msg)
        elif response.status_code != 200:
            raise Exception(f"Connection test failed: {response.status_code} - {response.text if response.text else 'No error message'}")

    def get_site_info(self) -> Dict:
        """
        Get information about the SharePoint site.

        Returns:
            Dictionary with site information
        """
        url = f"{self.site_url}/_api/web"
        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code != 200:
            raise Exception(f"Failed to get site info: {response.status_code} - {response.text}")

        data = response.json()

        if 'd' in data:
            web_data = data['d']
            return {
                'title': web_data.get('Title', ''),
                'url': web_data.get('Url', ''),
                'server_relative_url': web_data.get('ServerRelativeUrl', ''),
                'description': web_data.get('Description', '')
            }

        return {}

    def get_files_in_folder(self, folder_path: str = "", recursive: bool = False) -> List[Dict]:
        """
        Get all files in a SharePoint folder.

        Args:
            folder_path: Server-relative folder path or relative path
                        Can be full path like "/sites/project/Document Library/Folder"
                        or relative like "Document Library/Folder"
            recursive: If True, also get files from subfolders

        Returns:
            List of file dictionaries with metadata
        """
        # Handle empty path
        if not folder_path:
            folder_path = "Shared Documents"

        # If path doesn't start with /, it's relative - try to construct server-relative path
        if not folder_path.startswith('/'):
            # Get site's server relative URL
            try:
                site_info = self.get_site_info()
                server_relative_url = site_info.get('server_relative_url', '')
                # Construct full path
                folder_path = f"{server_relative_url}/{folder_path}".replace('//', '/')
            except:
                # If we can't get site info, use path as-is
                pass

        # URL encode the path properly
        # First, normalize the path
        folder_path = folder_path.replace('\\', '/')

        # SharePoint REST API endpoint
        # Use server-relative URL format
        encoded_path = urllib.parse.quote(folder_path)

        url = f"{self.site_url}/_api/web/GetFolderByServerRelativeUrl('{encoded_path}')/Files"
        url += "?$expand=ListItemAllFields,ModifiedBy"

        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code == 404:
            raise Exception(f"Folder not found: {folder_path}. Try using the full server-relative path (e.g., /sites/project/Document Library/Folder)")
        elif response.status_code != 200:
            raise Exception(f"Failed to get files: {response.status_code} - {response.text}")

        data = response.json()
        files = []

        # Parse response
        if 'd' in data and 'results' in data['d']:
            for item in data['d']['results']:
                file_info = {
                    'name': item['Name'],
                    'size': item['Length'],
                    'modified': self._parse_date(item['TimeLastModified']),
                    'created': self._parse_date(item['TimeCreated']),
                    'url': item['ServerRelativeUrl'],
                    'server_relative_url': item['ServerRelativeUrl'],
                    'modified_by': item.get('ModifiedBy', {}).get('Title', 'Unknown') if 'ModifiedBy' in item else 'Unknown'
                }
                files.append(file_info)

        return files

    def get_folders_in_folder(self, folder_path: str = "") -> List[Dict]:
        """
        Get all subfolders in a SharePoint folder.

        Args:
            folder_path: Relative folder path

        Returns:
            List of folder dictionaries
        """
        if not folder_path:
            folder_path = "Shared Documents"

        encoded_path = requests.utils.quote(folder_path)
        url = f"{self.site_url}/_api/web/GetFolderByServerRelativeUrl('{encoded_path}')/Folders"

        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code != 200:
            raise Exception(f"Failed to get folders: {response.status_code} - {response.text}")

        data = response.json()
        folders = []

        if 'd' in data and 'results' in data['d']:
            for item in data['d']['results']:
                folder_info = {
                    'name': item['Name'],
                    'server_relative_url': item['ServerRelativeUrl'],
                    'item_count': item.get('ItemCount', 0)
                }
                folders.append(folder_info)

        return folders

    def download_file(self, server_relative_url: str) -> bytes:
        """
        Download a file from SharePoint.

        Args:
            server_relative_url: Server-relative URL of the file

        Returns:
            File content as bytes
        """
        # Use $value endpoint to get file content
        encoded_url = requests.utils.quote(server_relative_url)
        url = f"{self.site_url}/_api/web/GetFileByServerRelativeUrl('{encoded_url}')/$value"

        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code != 200:
            raise Exception(f"Failed to download file: {response.status_code} - {response.text}")

        return response.content

    def search_files(self, query: str, file_extensions: Optional[List[str]] = None) -> List[Dict]:
        """
        Search for files in SharePoint using REST API search.

        Args:
            query: Search query string
            file_extensions: List of file extensions to filter (e.g., ['xlsx', 'xls'])

        Returns:
            List of matching files
        """
        # Build search query
        search_query = query

        if file_extensions:
            ext_filter = ' OR '.join([f"FileExtension:{ext}" for ext in file_extensions])
            search_query = f"{query} AND ({ext_filter})"

        encoded_query = requests.utils.quote(search_query)
        url = f"{self.site_url}/_api/search/query?querytext='{encoded_query}'"

        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code != 200:
            raise Exception(f"Search failed: {response.status_code} - {response.text}")

        data = response.json()
        files = []

        # Parse search results
        if 'd' in data and 'query' in data['d']:
            results = data['d']['query'].get('PrimaryQueryResult', {}).get('RelevantResults', {}).get('Table', {}).get('Rows', {}).get('results', [])

            for result in results:
                cells = result.get('Cells', {}).get('results', [])
                file_info = {}

                for cell in cells:
                    key = cell.get('Key', '')
                    value = cell.get('Value', '')

                    if key == 'Title':
                        file_info['name'] = value
                    elif key == 'Path':
                        file_info['url'] = value
                    elif key == 'LastModifiedTime':
                        file_info['modified'] = value
                    elif key == 'Size':
                        file_info['size'] = int(value) if value else 0

                if file_info:
                    files.append(file_info)

        return files

    @staticmethod
    def _parse_date(date_string: str) -> str:
        """
        Parse SharePoint date string to readable format.

        Args:
            date_string: SharePoint date string

        Returns:
            Formatted date string
        """
        try:
            # SharePoint returns ISO format
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return date_string

    def get_list_items(self, list_name: str) -> List[Dict]:
        """
        Get items from a SharePoint list.

        Args:
            list_name: Name of the SharePoint list

        Returns:
            List of items
        """
        encoded_list = requests.utils.quote(list_name)
        url = f"{self.site_url}/_api/web/lists/getbytitle('{encoded_list}')/items"

        response = self.session.get(url, verify=self.verify_ssl)

        if response.status_code != 200:
            raise Exception(f"Failed to get list items: {response.status_code} - {response.text}")

        data = response.json()
        items = []

        if 'd' in data and 'results' in data['d']:
            items = data['d']['results']

        return items
