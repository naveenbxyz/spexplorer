import requests
from typing import List, Dict, Optional
from datetime import datetime
import json


class SharePointClient:
    """
    SharePoint REST API Client for authentication, folder browsing, and file operations.
    Supports both OAuth2 (Client Credentials) and Access Token authentication.
    """

    def __init__(
        self,
        site_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        """
        Initialize SharePoint client.

        Args:
            site_url: Full SharePoint site URL (e.g., https://tenant.sharepoint.com/sites/site)
            client_id: Azure AD App Client ID (for OAuth)
            client_secret: Azure AD App Client Secret (for OAuth)
            tenant_id: Azure AD Tenant ID (for OAuth)
            access_token: Pre-obtained access token (alternative to OAuth)
        """
        self.site_url = site_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.access_token = access_token
        self.session = requests.Session()

        # Extract tenant and site info
        parts = site_url.split('/')
        self.tenant = parts[2].split('.')[0]

    def authenticate(self) -> str:
        """
        Authenticate and get access token.

        Returns:
            Access token string
        """
        if self.access_token:
            # Use provided access token
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json;odata=verbose',
                'Content-Type': 'application/json;odata=verbose'
            })
            # Test the token
            self._test_connection()
            return self.access_token

        elif self.client_id and self.client_secret and self.tenant_id:
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
                    'Authorization': f'Bearer {self.access_token}',
                    'Accept': 'application/json;odata=verbose',
                    'Content-Type': 'application/json;odata=verbose'
                })

                return self.access_token
            else:
                raise Exception(f"Authentication failed: {response.status_code} - {response.text}")
        else:
            raise ValueError("Either access_token or (client_id, client_secret, tenant_id) must be provided")

    def _test_connection(self):
        """Test the connection by making a simple API call."""
        url = f"{self.site_url}/_api/web"
        response = self.session.get(url)

        if response.status_code != 200:
            raise Exception(f"Connection test failed: {response.status_code} - {response.text}")

    def get_files_in_folder(self, folder_path: str = "") -> List[Dict]:
        """
        Get all files in a SharePoint folder.

        Args:
            folder_path: Relative folder path (e.g., "Shared Documents/Reports")
                        Empty string for root document library

        Returns:
            List of file dictionaries with metadata
        """
        # Default to Shared Documents if no path provided
        if not folder_path:
            folder_path = "Shared Documents"

        # Encode folder path
        encoded_path = requests.utils.quote(folder_path)

        # SharePoint REST API endpoint
        url = f"{self.site_url}/_api/web/GetFolderByServerRelativeUrl('{encoded_path}')/Files"
        url += "?$expand=ListItemAllFields,ModifiedBy"

        response = self.session.get(url)

        if response.status_code == 404:
            raise Exception(f"Folder not found: {folder_path}")
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

        response = self.session.get(url)

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

        response = self.session.get(url)

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

        response = self.session.get(url)

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

        response = self.session.get(url)

        if response.status_code != 200:
            raise Exception(f"Failed to get list items: {response.status_code} - {response.text}")

        data = response.json()
        items = []

        if 'd' in data and 'results' in data['d']:
            items = data['d']['results']

        return items
