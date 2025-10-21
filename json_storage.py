"""
JSON-first storage layer for client data.
Writes individual JSON files per client with metadata indexing.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib


class JSONStorage:
    """
    Manages JSON file storage for client data with metadata indexing.
    """

    def __init__(self, base_path: str = "./extracted_json"):
        """
        Initialize JSON storage.

        Args:
            base_path: Base directory for JSON files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.json_dir = self.base_path / "clients"
        self.json_dir.mkdir(exist_ok=True)

        self.metadata_path = self.base_path / "metadata_index.json"
        self.clusters_path = self.base_path / "pattern_clusters.json"

        # Load or initialize metadata index
        self.metadata_index = self._load_metadata_index()

    def _load_metadata_index(self) -> Dict[str, Any]:
        """Load metadata index from file."""
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'total_clients': 0,
                'clients': {}
            }

    def _save_metadata_index(self):
        """Save metadata index to file."""
        self.metadata_index['last_updated'] = datetime.now().isoformat()
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata_index, f, indent=2, ensure_ascii=False)

    def save_client(self, client_data: Dict[str, Any]) -> str:
        """
        Save client data to JSON file.

        Args:
            client_data: Complete client JSON document

        Returns:
            File path where client was saved
        """
        client_id = client_data['client_id']
        country = client_data.get('country', 'unknown')

        # Create country subfolder
        country_dir = self.json_dir / self._sanitize_filename(country)
        country_dir.mkdir(exist_ok=True)

        # Generate filename
        filename = f"{self._sanitize_filename(client_id)}.json"
        file_path = country_dir / filename

        # Write JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(client_data, f, indent=2, ensure_ascii=False)

        # Update metadata index
        self._update_metadata_index(client_data, str(file_path.relative_to(self.base_path)))
        self._save_metadata_index()

        return str(file_path)

    def _update_metadata_index(self, client_data: Dict[str, Any], relative_path: str):
        """
        Update metadata index with client info.

        Args:
            client_data: Client data
            relative_path: Relative path to JSON file
        """
        client_id = client_data['client_id']

        metadata = {
            'client_id': client_id,
            'client_name': client_data.get('client_name'),
            'country': client_data.get('country'),
            'product': client_data.get('product'),
            'file_path': relative_path,
            'pattern_signature': client_data.get('pattern_signature'),
            'pattern_cluster_id': client_data.get('pattern_cluster_id'),
            'extracted_date': client_data.get('file_info', {}).get('extracted_date'),
            'processing_status': client_data.get('processing_metadata', {}).get('status', 'success'),
            'processed_at': client_data.get('processing_metadata', {}).get('processed_at'),
            'sheet_count': len(client_data.get('sheets', [])),
            'section_count': sum(len(sheet.get('sections', [])) for sheet in client_data.get('sheets', [])),
            # Extract all field names for searching
            'fields': self._extract_all_fields(client_data)
        }

        self.metadata_index['clients'][client_id] = metadata
        self.metadata_index['total_clients'] = len(self.metadata_index['clients'])

    def _extract_all_fields(self, client_data: Dict[str, Any]) -> List[str]:
        """Extract all unique field names from client data."""
        fields = set()

        for sheet in client_data.get('sheets', []):
            for section in sheet.get('sections', []):
                section_type = section.get('section_type')

                if section_type == 'key_value':
                    fields.update(section.get('data', {}).keys())
                elif section_type == 'table':
                    fields.update(section.get('headers', []))
                elif section_type == 'complex_header':
                    header_struct = section.get('header_structure', {})
                    fields.update(header_struct.get('final_columns', []))

        return sorted(list(fields))

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get client data by ID.

        Args:
            client_id: Client ID

        Returns:
            Client data dictionary or None
        """
        metadata = self.metadata_index['clients'].get(client_id)
        if not metadata:
            return None

        file_path = self.base_path / metadata['file_path']
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def search_clients(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        product: Optional[str] = None,
        pattern_cluster: Optional[int] = None,
        status: Optional[str] = None,
        has_field: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search for clients with filters.

        Args:
            query: Search query for client name
            country: Filter by country
            product: Filter by product
            pattern_cluster: Filter by pattern cluster
            status: Filter by processing status
            has_field: Filter by field name presence
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of client metadata records
        """
        results = []

        for client_id, metadata in self.metadata_index['clients'].items():
            # Apply filters
            if query and query.lower() not in (metadata.get('client_name') or '').lower():
                continue

            if country and metadata.get('country') != country:
                continue

            if product and metadata.get('product') != product:
                continue

            if pattern_cluster is not None and metadata.get('pattern_cluster_id') != pattern_cluster:
                continue

            if status and metadata.get('processing_status') != status:
                continue

            if has_field and has_field not in metadata.get('fields', []):
                continue

            results.append(metadata)

        # Sort by client name
        results.sort(key=lambda x: x.get('client_name', ''))

        # Apply pagination
        return results[offset:offset + limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall storage statistics.

        Returns:
            Statistics dictionary
        """
        clients = self.metadata_index['clients'].values()

        stats = {
            'total_clients': len(clients),
            'countries': len(set(c.get('country') for c in clients if c.get('country'))),
            'products': len(set(c.get('product') for c in clients if c.get('product'))),
            'unique_patterns': len(set(c.get('pattern_signature') for c in clients if c.get('pattern_signature'))),
            'success_count': sum(1 for c in clients if c.get('processing_status') == 'success'),
            'failed_count': sum(1 for c in clients if c.get('processing_status') == 'failed'),
            'pending_count': sum(1 for c in clients if c.get('processing_status') == 'pending'),
        }

        return stats

    def get_countries(self) -> List[str]:
        """Get list of all countries."""
        countries = set(
            metadata.get('country')
            for metadata in self.metadata_index['clients'].values()
            if metadata.get('country')
        )
        return sorted(list(countries))

    def get_products(self) -> List[str]:
        """Get list of all products."""
        products = set(
            metadata.get('product')
            for metadata in self.metadata_index['clients'].values()
            if metadata.get('product')
        )
        return sorted(list(products))

    def get_all_fields(self) -> Dict[str, int]:
        """
        Get all unique fields across all clients with occurrence counts.

        Returns:
            Dictionary of field_name -> count
        """
        field_counts = {}

        for metadata in self.metadata_index['clients'].values():
            for field in metadata.get('fields', []):
                field_counts[field] = field_counts.get(field, 0) + 1

        return dict(sorted(field_counts.items(), key=lambda x: x[1], reverse=True))

    def save_pattern_clusters(self, clusters: List[Dict[str, Any]]):
        """
        Save pattern clusters to file.

        Args:
            clusters: List of cluster information
        """
        cluster_data = {
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'total_clusters': len(clusters),
            'clusters': clusters
        }

        with open(self.clusters_path, 'w', encoding='utf-8') as f:
            json.dump(cluster_data, f, indent=2, ensure_ascii=False)

    def load_pattern_clusters(self) -> Optional[List[Dict[str, Any]]]:
        """
        Load pattern clusters from file.

        Returns:
            List of clusters or None if not found
        """
        if not self.clusters_path.exists():
            return None

        with open(self.clusters_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('clusters', [])

    def update_cluster_assignments(self, cluster_assignments: Dict[str, int]):
        """
        Update pattern cluster assignments for clients.

        Args:
            cluster_assignments: Dictionary mapping client_id -> cluster_id
        """
        for client_id, cluster_id in cluster_assignments.items():
            if client_id in self.metadata_index['clients']:
                self.metadata_index['clients'][client_id]['pattern_cluster_id'] = cluster_id

        self._save_metadata_index()

    def export_to_csv(self, output_path: str, fields: Optional[List[str]] = None):
        """
        Export metadata index to CSV.

        Args:
            output_path: Output CSV file path
            fields: Optional list of fields to export (default: all)
        """
        import csv

        if not self.metadata_index['clients']:
            return

        # Determine fields
        if fields is None:
            sample_metadata = next(iter(self.metadata_index['clients'].values()))
            fields = [k for k in sample_metadata.keys() if k != 'fields']

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for metadata in self.metadata_index['clients'].values():
                row = {k: metadata.get(k) for k in fields}
                writer.writerow(row)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize string for use in filename."""
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')

        # Remove multiple underscores
        while '__' in name:
            name = name.replace('__', '_')

        return name.strip('_')

    def rebuild_index(self):
        """
        Rebuild metadata index from existing JSON files.
        Useful for recovery or migration.
        """
        print("🔄 Rebuilding metadata index from JSON files...")

        self.metadata_index = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'total_clients': 0,
            'clients': {}
        }

        # Scan all JSON files
        json_files = list(self.json_dir.rglob("*.json"))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    client_data = json.load(f)

                relative_path = str(json_file.relative_to(self.base_path))
                self._update_metadata_index(client_data, relative_path)

            except Exception as e:
                print(f"⚠️  Error reading {json_file}: {e}")

        self._save_metadata_index()
        print(f"✅ Rebuilt index with {len(self.metadata_index['clients'])} clients")


if __name__ == '__main__':
    # Test the storage
    storage = JSONStorage("./test_extracted_json")

    # Test saving a client
    test_client = {
        'client_id': 'USA_TestClient_FX',
        'client_name': 'Test Client',
        'country': 'USA',
        'product': 'FX',
        'sheets': [
            {
                'sheet_name': 'Overview',
                'sections': [
                    {
                        'section_type': 'key_value',
                        'data': {
                            'Client_Name': 'Test Client',
                            'Registration_ID': '12345'
                        }
                    }
                ]
            }
        ],
        'pattern_signature': 'abc123',
        'processing_metadata': {
            'status': 'success',
            'processed_at': datetime.now().isoformat()
        },
        'file_info': {
            'extracted_date': '2024-01-15'
        }
    }

    path = storage.save_client(test_client)
    print(f"Saved to: {path}")

    # Test retrieval
    retrieved = storage.get_client('USA_TestClient_FX')
    print(f"Retrieved: {retrieved['client_name']}")

    # Test search
    results = storage.search_clients(country='USA')
    print(f"Found {len(results)} clients in USA")

    # Test statistics
    stats = storage.get_statistics()
    print(f"Statistics: {stats}")
