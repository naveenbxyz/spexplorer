"""
File selection logic for Excel files.
Handles date parsing, latest file selection, and folder filtering.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict


class FileSelector:
    """
    Selects appropriate Excel files based on folder structure and date logic.
    """

    def __init__(self):
        # Date patterns to try (in order of preference)
        self.date_patterns = [
            # ddMMMYYYY formats
            (r'(\d{1,2})([A-Za-z]{3})(\d{4})', '%d%b%Y'),
            # YYYY-MM-DD
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
            # MM-DD-YYYY
            (r'(\d{2})-(\d{2})-(\d{4})', '%m-%d-%Y'),
            # YYYYMMDD
            (r'(\d{8})', '%Y%m%d'),
            # DD-MM-YYYY
            (r'(\d{2})-(\d{2})-(\d{4})', '%d-%m-%Y'),
            # MMM-DD-YYYY (Jan-15-2024)
            (r'([A-Za-z]{3})-(\d{1,2})-(\d{4})', '%b-%d-%Y'),
            # YYYY_MM_DD
            (r'(\d{4})_(\d{2})_(\d{2})', '%Y_%m_%d'),
            # DD_MMM_YYYY
            (r'(\d{1,2})_([A-Za-z]{3})_(\d{4})', '%d_%b_%Y'),
        ]

    def parse_folder_structure(self, file_path: str, root_folder: str) -> Dict[str, Optional[str]]:
        """
        Parse folder structure to extract country, client, product.

        Expected: root/Country/ClientName/Product/.../file.xlsx

        Args:
            file_path: Full path to the Excel file
            root_folder: Root output folder

        Returns:
            Dictionary with country, client_name, product
        """
        path = Path(file_path)
        root = Path(root_folder)

        try:
            relative_path = path.relative_to(root)
            parts = relative_path.parts

            # Remove filename
            folder_parts = parts[:-1]

            if len(folder_parts) >= 3:
                return {
                    'country': folder_parts[0],
                    'client_name': folder_parts[1],
                    'product': folder_parts[2],
                    'relative_folder': '/'.join(folder_parts)
                }
            elif len(folder_parts) == 2:
                return {
                    'country': folder_parts[0],
                    'client_name': folder_parts[1],
                    'product': None,
                    'relative_folder': '/'.join(folder_parts)
                }
            elif len(folder_parts) == 1:
                return {
                    'country': folder_parts[0],
                    'client_name': None,
                    'product': None,
                    'relative_folder': folder_parts[0]
                }
            else:
                return {
                    'country': None,
                    'client_name': None,
                    'product': None,
                    'relative_folder': ''
                }
        except ValueError:
            # Path not relative to root
            return {
                'country': None,
                'client_name': None,
                'product': None,
                'relative_folder': ''
            }

    def extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract date from filename using various patterns.

        Args:
            filename: Excel filename

        Returns:
            datetime object or None if no date found
        """
        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]

        for pattern, date_format in self.date_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                try:
                    date_str = match.group(0)
                    return datetime.strptime(date_str, date_format)
                except ValueError:
                    # Try next pattern
                    continue

        return None

    def should_ignore_path(self, file_path: str) -> bool:
        """
        Check if path should be ignored (contains '/old').

        Args:
            file_path: Full file path

        Returns:
            True if should ignore
        """
        path_lower = file_path.lower()

        # Check for '/old' in path (with variations)
        ignore_patterns = [
            '/old/',
            '\\old\\',
            '/old',
            '\\old',
            '/archive/',
            '\\archive\\',
            '/backup/',
            '\\backup\\',
        ]

        return any(pattern in path_lower for pattern in ignore_patterns)

    def select_files(self, file_paths: List[str], root_folder: str) -> List[Dict[str, any]]:
        """
        Select appropriate files based on date logic and filtering.

        Args:
            file_paths: List of Excel file paths
            root_folder: Root output folder

        Returns:
            List of selected file info dictionaries
        """
        # First, filter out ignored paths
        filtered_files = [
            fp for fp in file_paths
            if not self.should_ignore_path(fp)
        ]

        # Group files by client/product combination
        client_groups = defaultdict(list)

        for file_path in filtered_files:
            path = Path(file_path)
            filename = path.name

            # Parse folder structure
            folder_info = self.parse_folder_structure(file_path, root_folder)

            # Extract date
            extracted_date = self.extract_date_from_filename(filename)

            # Create grouping key (country/client/product)
            group_key = (
                folder_info.get('country'),
                folder_info.get('client_name'),
                folder_info.get('product')
            )

            file_info = {
                'file_path': file_path,
                'filename': filename,
                'country': folder_info.get('country'),
                'client_name': folder_info.get('client_name'),
                'product': folder_info.get('product'),
                'relative_folder': folder_info.get('relative_folder'),
                'extracted_date': extracted_date,
                'is_latest': False,
                'form_variant': None
            }

            client_groups[group_key].append(file_info)

        # Select files from each group
        selected_files = []

        for group_key, files in client_groups.items():
            if len(files) == 1:
                # Only one file, select it
                files[0]['is_latest'] = True
                selected_files.append(files[0])

            else:
                # Multiple files - check for dates
                files_with_dates = [f for f in files if f['extracted_date'] is not None]
                files_without_dates = [f for f in files if f['extracted_date'] is None]

                if files_with_dates:
                    # Select the latest dated file
                    latest_file = max(files_with_dates, key=lambda f: f['extracted_date'])
                    latest_file['is_latest'] = True
                    selected_files.append(latest_file)

                if files_without_dates:
                    # Treat each as separate form variant
                    for idx, file_info in enumerate(files_without_dates, start=1):
                        client_name = file_info['client_name'] or 'Unknown'
                        file_info['form_variant'] = f"Form {idx}"
                        file_info['client_name'] = f"{client_name} - {file_info['form_variant']}"
                        selected_files.append(file_info)

        return selected_files

    def discover_and_select_files(self, root_folder: str) -> List[Dict[str, any]]:
        """
        Discover all Excel files and select appropriate ones.

        Args:
            root_folder: Root folder to search

        Returns:
            List of selected file info dictionaries
        """
        root_path = Path(root_folder)

        if not root_path.exists():
            raise ValueError(f"Root folder does not exist: {root_folder}")

        # Find all Excel files
        excel_files = []
        excel_files.extend(root_path.rglob("*.xlsx"))
        excel_files.extend(root_path.rglob("*.xls"))

        # Convert to strings
        file_paths = [str(f) for f in excel_files]

        # Select files
        return self.select_files(file_paths, root_folder)

    def generate_client_id(self, file_info: Dict[str, any]) -> str:
        """
        Generate unique client ID from file info.

        Args:
            file_info: File information dictionary

        Returns:
            Unique client ID string
        """
        country = file_info.get('country') or 'Unknown'
        client_name = file_info.get('client_name') or 'Unknown'
        product = file_info.get('product') or 'Unknown'
        form_variant = file_info.get('form_variant') or ''

        # Sanitize for ID
        def sanitize(s):
            return re.sub(r'[^a-zA-Z0-9]', '_', str(s))

        parts = [
            sanitize(country),
            sanitize(client_name),
            sanitize(product)
        ]

        if form_variant:
            parts.append(sanitize(form_variant))

        return '_'.join(parts)
