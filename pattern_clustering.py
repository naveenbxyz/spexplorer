"""
Pattern clustering using scikit-learn for client structure analysis.
CPU-only, local processing - no cloud/LLM dependencies.
"""

import json
from typing import Dict, List, Any, Optional
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN, AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from client_database import ClientDatabase


class PatternClusterer:
    """
    Cluster client structures to identify common patterns.
    """

    def __init__(self, db: ClientDatabase):
        """
        Initialize clusterer.

        Args:
            db: ClientDatabase instance
        """
        self.db = db

    def cluster_clients(
        self,
        min_cluster_size: int = 2,
        similarity_threshold: float = 0.7,
        max_clusters: int = 20
    ) -> Dict[str, Any]:
        """
        Cluster clients based on their structure.

        Args:
            min_cluster_size: Minimum clients per cluster
            similarity_threshold: Similarity threshold (0-1)
            max_clusters: Maximum number of clusters

        Returns:
            Clustering results
        """
        # Get all successfully processed clients
        clients = self.db.search_clients(status='success', limit=10000)

        if len(clients) < min_cluster_size:
            return {
                'total_clients': len(clients),
                'clusters': [],
                'message': 'Not enough clients to cluster'
            }

        # Extract features from each client
        features, client_ids = self._extract_features(clients)

        if features is None or len(features) == 0:
            return {
                'total_clients': len(clients),
                'clusters': [],
                'message': 'Failed to extract features'
            }

        # Perform clustering
        labels = self._perform_clustering(
            features,
            min_cluster_size=min_cluster_size,
            similarity_threshold=similarity_threshold,
            max_clusters=max_clusters
        )

        # Analyze clusters
        clusters = self._analyze_clusters(client_ids, labels)

        # Save clusters to database
        for cluster in clusters:
            if cluster['cluster_id'] >= 0:  # Skip outliers (-1)
                self.db.save_pattern_cluster(
                    cluster_id=cluster['cluster_id'],
                    cluster_name=cluster.get('cluster_name'),
                    structure_summary=cluster['structure_summary'],
                    example_client_ids=cluster['example_client_ids'][:10]
                )

                # Update client records with cluster assignment
                for client_id in cluster['client_ids']:
                    self.db.update_pattern_cluster(client_id, cluster['cluster_id'])

        return {
            'total_clients': len(clients),
            'total_clusters': len([c for c in clusters if c['cluster_id'] >= 0]),
            'outliers': len([c for c in clusters if c['cluster_id'] == -1]),
            'clusters': clusters
        }

    def _extract_features(self, clients: List[Dict[str, Any]]) -> tuple:
        """
        Extract feature vectors from clients.

        Features include:
        - Sheet names (one-hot)
        - Section type counts
        - Key field names (TF-IDF)
        - Structure patterns

        Returns:
            (feature_matrix, client_ids)
        """
        client_ids = []
        feature_dicts = []

        for client in clients:
            client_id = client['client_id']
            client_data = self.db.get_client(client_id)

            if not client_data:
                continue

            features = self._extract_client_features(client_data)
            feature_dicts.append(features)
            client_ids.append(client_id)

        if not feature_dicts:
            return None, []

        # Convert to feature vectors
        feature_matrix = self._vectorize_features(feature_dicts)

        return feature_matrix, client_ids

    def _extract_client_features(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract features from a single client.

        Returns:
            Feature dictionary
        """
        features = {
            'sheet_names': [],
            'section_types': [],
            'key_fields': [],
            'sheet_count': 0,
            'section_count': 0
        }

        sheets = client_data.get('sheets', [])
        features['sheet_count'] = len(sheets)

        for sheet in sheets:
            # Sheet name
            features['sheet_names'].append(sheet['sheet_name'])

            sections = sheet.get('sections', [])
            features['section_count'] += len(sections)

            for section in sections:
                # Section type
                section_type = section.get('section_type', 'unknown')
                features['section_types'].append(section_type)

                # Extract field names
                if section_type == 'key_value':
                    features['key_fields'].extend(section.get('data', {}).keys())
                elif section_type == 'table':
                    features['key_fields'].extend(section.get('headers', []))
                elif section_type == 'complex_header':
                    header_struct = section.get('header_structure', {})
                    features['key_fields'].extend(header_struct.get('final_columns', []))

        return features

    def _vectorize_features(self, feature_dicts: List[Dict[str, Any]]) -> np.ndarray:
        """
        Convert feature dictionaries to numerical vectors.

        Returns:
            Feature matrix (n_clients x n_features)
        """
        vectors = []

        # Extract all unique values for categorical features
        all_sheet_names = set()
        all_section_types = set()

        for fd in feature_dicts:
            all_sheet_names.update(fd['sheet_names'])
            all_section_types.update(fd['section_types'])

        all_sheet_names = sorted(all_sheet_names)
        all_section_types = sorted(all_section_types)

        # Create TF-IDF vectorizer for field names
        field_texts = [' '.join(fd['key_fields']) for fd in feature_dicts]
        tfidf = TfidfVectorizer(max_features=50, min_df=1)

        try:
            field_vectors = tfidf.fit_transform(field_texts).toarray()
        except:
            # Fallback if TF-IDF fails
            field_vectors = np.zeros((len(feature_dicts), 10))

        # Build feature vectors
        for idx, fd in enumerate(feature_dicts):
            vec = []

            # Sheet name one-hot encoding
            for sheet_name in all_sheet_names:
                vec.append(1 if sheet_name in fd['sheet_names'] else 0)

            # Section type counts
            section_type_counts = Counter(fd['section_types'])
            for section_type in all_section_types:
                vec.append(section_type_counts.get(section_type, 0))

            # Counts
            vec.append(fd['sheet_count'])
            vec.append(fd['section_count'])

            # TF-IDF features
            vec.extend(field_vectors[idx])

            vectors.append(vec)

        # Convert to numpy array and normalize
        feature_matrix = np.array(vectors)
        scaler = StandardScaler()
        feature_matrix = scaler.fit_transform(feature_matrix)

        return feature_matrix

    def _perform_clustering(
        self,
        features: np.ndarray,
        min_cluster_size: int,
        similarity_threshold: float,
        max_clusters: int
    ) -> np.ndarray:
        """
        Perform clustering on feature vectors.

        Returns:
            Cluster labels for each client
        """
        # Try Agglomerative Clustering first
        try:
            # Estimate number of clusters
            n_clusters = min(max_clusters, max(2, len(features) // 10))

            clusterer = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='euclidean',
                linkage='ward'
            )

            labels = clusterer.fit_predict(features)

            # Filter small clusters
            label_counts = Counter(labels)
            labels = np.array([
                label if label_counts[label] >= min_cluster_size else -1
                for label in labels
            ])

            return labels

        except Exception as e:
            # Fallback to DBSCAN
            try:
                eps = 1.0 - similarity_threshold
                clusterer = DBSCAN(eps=eps, min_samples=min_cluster_size, metric='euclidean')
                labels = clusterer.fit_predict(features)
                return labels

            except Exception as e2:
                # Last resort: no clustering
                return np.array([0] * len(features))

    def _analyze_clusters(
        self,
        client_ids: List[str],
        labels: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Analyze and summarize each cluster.

        Returns:
            List of cluster information
        """
        clusters = []

        # Group clients by cluster
        cluster_map = {}
        for client_id, label in zip(client_ids, labels):
            if label not in cluster_map:
                cluster_map[label] = []
            cluster_map[label].append(client_id)

        # Analyze each cluster
        for cluster_id, cluster_client_ids in cluster_map.items():
            cluster_info = {
                'cluster_id': int(cluster_id),
                'cluster_name': f'Pattern {cluster_id}' if cluster_id >= 0 else 'Outliers',
                'client_count': len(cluster_client_ids),
                'client_ids': cluster_client_ids,
                'example_client_ids': cluster_client_ids[:5],
                'structure_summary': self._summarize_cluster_structure(cluster_client_ids)
            }

            clusters.append(cluster_info)

        # Sort by client count
        clusters.sort(key=lambda c: c['client_count'], reverse=True)

        return clusters

    def _summarize_cluster_structure(self, client_ids: List[str]) -> Dict[str, Any]:
        """
        Summarize the common structure of a cluster.

        Returns:
            Structure summary
        """
        # Sample up to 10 clients from cluster
        sample_ids = client_ids[:10]

        sheet_names = []
        section_types = []
        common_fields = []

        for client_id in sample_ids:
            client_data = self.db.get_client(client_id)
            if not client_data:
                continue

            for sheet in client_data.get('sheets', []):
                sheet_names.append(sheet['sheet_name'])

                for section in sheet.get('sections', []):
                    section_types.append(section.get('section_type'))

                    # Extract common fields
                    if section.get('section_type') == 'key_value':
                        common_fields.extend(section.get('data', {}).keys())
                    elif section.get('section_type') in ['table', 'complex_header']:
                        headers = section.get('headers', [])
                        if not headers:
                            headers = section.get('header_structure', {}).get('final_columns', [])
                        common_fields.extend(headers)

        # Find most common elements
        sheet_name_counts = Counter(sheet_names)
        section_type_counts = Counter(section_types)
        field_counts = Counter(common_fields)

        return {
            'common_sheet_names': [name for name, _ in sheet_name_counts.most_common(5)],
            'section_type_distribution': dict(section_type_counts),
            'common_fields': [field for field, _ in field_counts.most_common(20)]
        }


def cluster_patterns(db_path: str = "client_data.db"):
    """
    Run pattern clustering on database.

    Args:
        db_path: Path to client database
    """
    db = ClientDatabase(db_path)
    clusterer = PatternClusterer(db)

    print("🔍 Starting pattern clustering...")
    results = clusterer.cluster_clients(
        min_cluster_size=2,
        similarity_threshold=0.7,
        max_clusters=20
    )

    print(f"\n✅ Clustering completed!")
    print(f"   Total clients: {results['total_clients']}")
    print(f"   Clusters found: {results['total_clusters']}")
    print(f"   Outliers: {results.get('outliers', 0)}")

    print(f"\n📊 Cluster Summary:")
    for cluster in results.get('clusters', []):
        if cluster['cluster_id'] >= 0:
            print(f"\n  {cluster['cluster_name']}")
            print(f"    Clients: {cluster['client_count']}")
            summary = cluster['structure_summary']
            print(f"    Sheet names: {', '.join(summary.get('common_sheet_names', [])[:3])}")
            print(f"    Section types: {summary.get('section_type_distribution', {})}")

    db.close()


if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "client_data.db"
    cluster_patterns(db_path)
