"""
Interactive schema builder for discovering and rationalizing data models.
Helps identify common fields across pattern clusters and build canonical mappings.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from collections import Counter, defaultdict
import re
from json_storage import JSONStorage


class SchemaBuilder:
    """
    Analyzes client JSONs to discover common field patterns and build data models.
    """

    def __init__(self, json_storage: JSONStorage):
        """
        Initialize schema builder.

        Args:
            json_storage: JSONStorage instance
        """
        self.storage = json_storage
        self.field_mappings = {}  # Pattern cluster -> field mappings
        self.canonical_schema = {}  # The target data model

    def analyze_pattern_cluster(
        self,
        cluster_id: int,
        sample_size: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze a pattern cluster to discover common fields.

        Args:
            cluster_id: Pattern cluster ID
            sample_size: Number of clients to sample

        Returns:
            Analysis results
        """
        # Get clients in this cluster
        clients = self.storage.search_clients(pattern_cluster=cluster_id, limit=100)

        if not clients:
            return {
                'cluster_id': cluster_id,
                'client_count': 0,
                'message': 'No clients in this cluster'
            }

        # Sample clients
        sample_clients = clients[:sample_size]

        # Collect field statistics
        field_stats = self._collect_field_statistics(sample_clients)

        # Identify sections
        section_types = self._analyze_section_types(sample_clients)

        # Suggest canonical fields
        canonical_suggestions = self._suggest_canonical_fields(field_stats)

        return {
            'cluster_id': cluster_id,
            'client_count': len(clients),
            'sample_size': len(sample_clients),
            'field_statistics': field_stats,
            'section_types': section_types,
            'canonical_suggestions': canonical_suggestions,
            'example_clients': [c['client_id'] for c in sample_clients[:3]]
        }

    def _collect_field_statistics(
        self,
        clients: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Collect statistics about field occurrences and values.

        Returns:
            Dictionary mapping field name -> statistics
        """
        field_occurrences = Counter()
        field_sections = defaultdict(set)  # field -> {section_types}
        field_sample_values = defaultdict(list)

        for client_meta in clients:
            client_data = self.storage.get_client(client_meta['client_id'])
            if not client_data:
                continue

            for sheet in client_data.get('sheets', []):
                for section in sheet.get('sections', []):
                    section_type = section.get('section_type')

                    # Extract fields based on section type
                    fields = {}
                    if section_type == 'key_value':
                        fields = section.get('data', {})
                    elif section_type == 'table':
                        # For tables, just count headers
                        for header in section.get('headers', []):
                            field_occurrences[header] += 1
                            field_sections[header].add(section_type)
                        continue
                    elif section_type == 'complex_header':
                        for header in section.get('header_structure', {}).get('final_columns', []):
                            field_occurrences[header] += 1
                            field_sections[header].add(section_type)
                        continue

                    # Process key-value fields
                    for field_name, value in fields.items():
                        field_occurrences[field_name] += 1
                        field_sections[field_name].add(section_type)

                        # Sample non-null values
                        if value is not None and len(field_sample_values[field_name]) < 5:
                            field_sample_values[field_name].append(value)

        # Build statistics
        total_clients = len(clients)
        field_stats = {}

        for field_name, count in field_occurrences.most_common():
            field_stats[field_name] = {
                'occurrences': count,
                'frequency': count / total_clients if total_clients > 0 else 0,
                'section_types': list(field_sections[field_name]),
                'sample_values': field_sample_values.get(field_name, [])[:3]
            }

        return field_stats

    def _analyze_section_types(
        self,
        clients: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Analyze distribution of section types in cluster.

        Returns:
            Section type counts
        """
        section_type_counts = Counter()

        for client_meta in clients:
            client_data = self.storage.get_client(client_meta['client_id'])
            if not client_data:
                continue

            for sheet in client_data.get('sheets', []):
                for section in sheet.get('sections', []):
                    section_type = section.get('section_type')
                    section_type_counts[section_type] += 1

        return dict(section_type_counts)

    def _suggest_canonical_fields(
        self,
        field_stats: Dict[str, Dict[str, Any]],
        min_frequency: float = 0.5
    ) -> Dict[str, List[str]]:
        """
        Suggest canonical field names based on field statistics.

        Groups similar field names together (e.g., "Client Name", "Customer Name", "Entity Name")

        Args:
            field_stats: Field statistics
            min_frequency: Minimum frequency to consider (default: 50%)

        Returns:
            Dictionary mapping canonical_name -> [variant_names]
        """
        # Filter high-frequency fields
        common_fields = {
            name: stats
            for name, stats in field_stats.items()
            if stats['frequency'] >= min_frequency
        }

        # Group similar field names
        canonical_groups = self._group_similar_fields(list(common_fields.keys()))

        return canonical_groups

    def _group_similar_fields(self, field_names: List[str]) -> Dict[str, List[str]]:
        """
        Group similar field names using fuzzy matching.

        Examples:
        - "Client_Name", "Customer_Name", "Entity_Name" -> "client_name"
        - "Registration_ID", "Registration_Number" -> "registration_id"

        Returns:
            Dictionary mapping canonical_name -> [variant_names]
        """
        # Normalize field names
        normalized_fields = {}
        for field in field_names:
            normalized = self._normalize_field_name(field)
            if normalized not in normalized_fields:
                normalized_fields[normalized] = []
            normalized_fields[normalized].append(field)

        # Extract semantic groups
        semantic_groups = defaultdict(list)

        for normalized, variants in normalized_fields.items():
            # Extract key terms
            key_term = self._extract_key_term(normalized)
            semantic_groups[key_term].extend(variants)

        # Build canonical mappings
        canonical_mappings = {}
        for key_term, variants in semantic_groups.items():
            if len(variants) > 0:
                # Use most common variant as canonical (or create one)
                canonical = self._create_canonical_name(key_term)
                canonical_mappings[canonical] = sorted(set(variants))

        return canonical_mappings

    @staticmethod
    def _normalize_field_name(field_name: str) -> str:
        """Normalize field name for comparison."""
        # Convert to lowercase
        normalized = field_name.lower()

        # Replace separators with space
        normalized = re.sub(r'[_\-\s]+', ' ', normalized)

        # Remove special characters
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

        return normalized.strip()

    @staticmethod
    def _extract_key_term(normalized_name: str) -> str:
        """
        Extract key semantic term from normalized name.

        Examples:
        - "client name" -> "client"
        - "registration id" -> "registration"
        - "account number" -> "account"
        """
        # Common suffixes to remove
        suffixes = ['name', 'id', 'number', 'code', 'date', 'amount', 'value', 'type']

        words = normalized_name.split()

        # If single word, return as-is
        if len(words) == 1:
            return words[0]

        # Remove common suffixes
        key_words = [w for w in words if w not in suffixes]

        if key_words:
            return ' '.join(key_words)
        else:
            # All words were suffixes, keep first word
            return words[0]

    @staticmethod
    def _create_canonical_name(key_term: str) -> str:
        """Create canonical field name from key term."""
        # Convert spaces to underscores, title case
        words = key_term.split()
        canonical = '_'.join(word.capitalize() for word in words)
        return canonical

    def define_field_mapping(
        self,
        cluster_id: int,
        canonical_field: str,
        source_fields: List[str]
    ):
        """
        Define a field mapping for a cluster.

        Args:
            cluster_id: Pattern cluster ID
            canonical_field: Canonical field name
            source_fields: List of source field names that map to this canonical field
        """
        if cluster_id not in self.field_mappings:
            self.field_mappings[cluster_id] = {}

        for source_field in source_fields:
            self.field_mappings[cluster_id][source_field] = canonical_field

    def save_field_mappings(self, output_path: str):
        """
        Save field mappings to JSON file.

        Args:
            output_path: Output file path
        """
        mappings_data = {
            'version': '1.0',
            'cluster_mappings': self.field_mappings,
            'canonical_schema': self.canonical_schema
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mappings_data, f, indent=2, ensure_ascii=False)

    def load_field_mappings(self, input_path: str):
        """
        Load field mappings from JSON file.

        Args:
            input_path: Input file path
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.field_mappings = data.get('cluster_mappings', {})
        self.canonical_schema = data.get('canonical_schema', {})

    def apply_field_mappings(
        self,
        client_data: Dict[str, Any],
        cluster_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply field mappings to normalize client data.

        Args:
            client_data: Original client data
            cluster_id: Pattern cluster ID (auto-detect if not provided)

        Returns:
            Normalized client data with canonical field names
        """
        if cluster_id is None:
            cluster_id = client_data.get('pattern_cluster_id')

        if cluster_id not in self.field_mappings:
            # No mappings defined for this cluster
            return client_data

        mappings = self.field_mappings[cluster_id]

        # Create normalized version
        normalized_data = client_data.copy()

        # Apply mappings to each section
        for sheet in normalized_data.get('sheets', []):
            for section in sheet.get('sections', []):
                section_type = section.get('section_type')

                if section_type == 'key_value':
                    # Rename fields in key-value sections
                    original_data = section.get('data', {})
                    normalized_section_data = {}

                    for field_name, value in original_data.items():
                        canonical_name = mappings.get(field_name, field_name)
                        normalized_section_data[canonical_name] = value

                    section['data'] = normalized_section_data
                    section['original_data'] = original_data  # Preserve original

                elif section_type in ['table', 'complex_header']:
                    # Rename headers
                    if section_type == 'table':
                        original_headers = section.get('headers', [])
                    else:
                        original_headers = section.get('header_structure', {}).get('final_columns', [])

                    normalized_headers = [
                        mappings.get(h, h) for h in original_headers
                    ]

                    if section_type == 'table':
                        section['headers'] = normalized_headers
                        section['original_headers'] = original_headers
                    else:
                        section['header_structure']['final_columns'] = normalized_headers
                        section['header_structure']['original_columns'] = original_headers

        return normalized_data

    def export_cluster_summary(self, output_path: str):
        """
        Export summary of all pattern clusters with field analysis.

        Args:
            output_path: Output file path
        """
        # Load pattern clusters
        clusters = self.storage.load_pattern_clusters()

        if not clusters:
            print("No pattern clusters found. Run clustering first.")
            return

        summary = {
            'version': '1.0',
            'total_clusters': len(clusters),
            'clusters': []
        }

        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            if cluster_id < 0:
                continue  # Skip outliers

            print(f"Analyzing cluster {cluster_id}...")

            analysis = self.analyze_pattern_cluster(cluster_id, sample_size=10)

            cluster_summary = {
                'cluster_id': cluster_id,
                'client_count': analysis['client_count'],
                'top_fields': [
                    {
                        'name': field_name,
                        'frequency': stats['frequency'],
                        'section_types': stats['section_types']
                    }
                    for field_name, stats in list(analysis['field_statistics'].items())[:20]
                ],
                'canonical_suggestions': analysis['canonical_suggestions']
            }

            summary['clusters'].append(cluster_summary)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"Exported cluster summary to {output_path}")


def main():
    """Command-line interface for schema builder."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Analyze pattern clusters and build data model schema'
    )
    parser.add_argument(
        '--json-dir',
        default='./extracted_json',
        help='JSON storage directory (default: ./extracted_json)'
    )
    parser.add_argument(
        '--cluster',
        type=int,
        help='Analyze specific cluster ID'
    )
    parser.add_argument(
        '--export-summary',
        help='Export cluster summary to file'
    )

    args = parser.parse_args()

    # Initialize
    storage = JSONStorage(args.json_dir)
    builder = SchemaBuilder(storage)

    if args.export_summary:
        builder.export_cluster_summary(args.export_summary)

    elif args.cluster is not None:
        # Analyze specific cluster
        analysis = builder.analyze_pattern_cluster(args.cluster, sample_size=10)

        print(f"\n{'='*60}")
        print(f"CLUSTER {args.cluster} ANALYSIS")
        print(f"{'='*60}")
        print(f"Client count: {analysis['client_count']}")
        print(f"Sample size: {analysis['sample_size']}")

        print(f"\n--- Section Types ---")
        for section_type, count in analysis['section_types'].items():
            print(f"  {section_type}: {count}")

        print(f"\n--- Top Fields (by frequency) ---")
        for field_name, stats in list(analysis['field_statistics'].items())[:15]:
            print(f"  {field_name}")
            print(f"    Frequency: {stats['frequency']:.1%}")
            print(f"    Section types: {', '.join(stats['section_types'])}")
            if stats['sample_values']:
                print(f"    Sample values: {stats['sample_values'][:2]}")

        print(f"\n--- Canonical Field Suggestions ---")
        for canonical, variants in analysis['canonical_suggestions'].items():
            print(f"  {canonical}:")
            for variant in variants:
                print(f"    - {variant}")

    else:
        print("Specify --cluster or --export-summary")


if __name__ == '__main__':
    main()
