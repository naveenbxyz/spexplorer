"""
Client-centric SQLite database for storing parsed Excel data.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class ClientDatabase:
    """
    Manages SQLite database for client data storage.
    """

    def __init__(self, db_path: str = "client_data.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()

        # Enable WAL mode for better concurrent write performance
        try:
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.conn.commit()
        except Exception as e:
            print(f"Warning: Could not enable WAL mode: {e}")

    def _connect(self):
        """Establish database connection."""
        # check_same_thread=False allows the connection to be shared across threads
        # We handle thread safety with locks in ClientProcessor
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        """Create database schema."""

        # Main clients table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                client_name TEXT,
                country TEXT,
                product TEXT,
                file_path TEXT UNIQUE,
                filename TEXT,
                extracted_date TEXT,
                is_latest BOOLEAN,
                form_variant TEXT,
                full_json TEXT,
                pattern_signature TEXT,
                pattern_cluster_id INTEGER,
                processing_status TEXT DEFAULT 'pending',
                processed_at TEXT,
                error_message TEXT,
                UNIQUE(file_path)
            )
        """)

        # Section metadata for querying
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                sheet_name TEXT,
                section_index INTEGER,
                section_type TEXT,
                section_header TEXT,
                key_fields TEXT,
                FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
            )
        """)

        # Pattern clusters
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_clusters (
                cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                client_count INTEGER DEFAULT 0,
                structure_summary TEXT,
                example_client_ids TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Create indexes
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_country
            ON clients(country)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_name
            ON clients(client_name)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_product
            ON clients(product)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_pattern
            ON clients(pattern_signature)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_cluster
            ON clients(pattern_cluster_id)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_client
            ON sections(client_id)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sections_type
            ON sections(section_type)
        """)

        self.conn.commit()

    def save_client(self, client_data: Dict[str, Any]) -> str:
        """
        Save or update client data.

        Args:
            client_data: Complete client JSON document

        Returns:
            client_id
        """
        client_id = client_data['client_id']
        processing_meta = client_data.get('processing_metadata', {})

        try:
            self.cursor.execute("""
                INSERT INTO clients (
                    client_id, client_name, country, product,
                    file_path, filename, extracted_date, is_latest, form_variant,
                    full_json, pattern_signature, processing_status,
                    processed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    client_name = excluded.client_name,
                    country = excluded.country,
                    product = excluded.product,
                    full_json = excluded.full_json,
                    pattern_signature = excluded.pattern_signature,
                    processing_status = excluded.processing_status,
                    processed_at = excluded.processed_at,
                    error_message = excluded.error_message
            """, (
                client_id,
                client_data.get('client_name'),
                client_data.get('country'),
                client_data.get('product'),
                client_data.get('file_info', {}).get('file_path'),
                client_data.get('file_info', {}).get('filename'),
                client_data.get('file_info', {}).get('extracted_date'),
                client_data.get('file_info', {}).get('is_latest', False),
                client_data.get('file_info', {}).get('form_variant'),
                json.dumps(client_data),
                client_data.get('pattern_signature'),
                processing_meta.get('status', 'success'),
                processing_meta.get('processed_at'),
                processing_meta.get('error')
            ))

            # Save section metadata
            self._save_section_metadata(client_id, client_data)

            # Force commit immediately
            self.conn.commit()

            # Verify the data was written
            self.cursor.execute("SELECT client_id FROM clients WHERE client_id = ?", (client_id,))
            if not self.cursor.fetchone():
                raise Exception(f"Failed to verify write of client_id {client_id}")

            return client_id

        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Database save failed for {client_id}: {str(e)}")

    def _save_section_metadata(self, client_id: str, client_data: Dict[str, Any]):
        """Save section metadata for querying."""
        # Delete existing sections for this client
        self.cursor.execute("DELETE FROM sections WHERE client_id = ?", (client_id,))

        # Insert new sections
        for sheet in client_data.get('sheets', []):
            sheet_name = sheet['sheet_name']

            for idx, section in enumerate(sheet.get('sections', [])):
                section_type = section.get('section_type')
                section_header = section.get('section_header')

                # Extract key fields
                key_fields = []
                if section_type == 'key_value':
                    key_fields = list(section.get('data', {}).keys())
                elif section_type in ['table', 'complex_header']:
                    key_fields = section.get('headers', [])
                    if not key_fields:
                        key_fields = section.get('header_structure', {}).get('final_columns', [])

                self.cursor.execute("""
                    INSERT INTO sections (
                        client_id, sheet_name, section_index,
                        section_type, section_header, key_fields
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    client_id,
                    sheet_name,
                    idx,
                    section_type,
                    section_header,
                    json.dumps(key_fields)
                ))

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get client data by ID.

        Args:
            client_id: Client ID

        Returns:
            Client data dictionary or None
        """
        self.cursor.execute("""
            SELECT full_json FROM clients WHERE client_id = ?
        """, (client_id,))

        row = self.cursor.fetchone()
        if row:
            return json.loads(row['full_json'])
        return None

    def search_clients(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        product: Optional[str] = None,
        pattern_cluster: Optional[int] = None,
        status: Optional[str] = None,
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
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of client records (metadata only, not full JSON)
        """
        sql = """
            SELECT
                client_id, client_name, country, product,
                filename, extracted_date, is_latest, form_variant,
                pattern_signature, pattern_cluster_id,
                processing_status, processed_at
            FROM clients
            WHERE 1=1
        """
        params = []

        if query:
            sql += " AND client_name LIKE ?"
            params.append(f"%{query}%")

        if country:
            sql += " AND country = ?"
            params.append(country)

        if product:
            sql += " AND product = ?"
            params.append(product)

        if pattern_cluster is not None:
            sql += " AND pattern_cluster_id = ?"
            params.append(pattern_cluster)

        if status:
            sql += " AND processing_status = ?"
            params.append(status)

        sql += " ORDER BY client_name, extracted_date DESC"
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        self.cursor.execute(sql, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def search_by_field(self, field_name: str) -> List[Dict[str, Any]]:
        """
        Search for clients containing a specific field/key name.

        Args:
            field_name: Field name to search for

        Returns:
            List of matching clients
        """
        self.cursor.execute("""
            SELECT DISTINCT
                c.client_id, c.client_name, c.country, c.product,
                s.sheet_name, s.section_type, s.section_header
            FROM sections s
            JOIN clients c ON s.client_id = c.client_id
            WHERE s.key_fields LIKE ?
        """, (f'%{field_name}%',))

        return [dict(row) for row in self.cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall database statistics.

        Returns:
            Statistics dictionary
        """
        stats = {}

        # Client counts
        self.cursor.execute("""
            SELECT
                COUNT(*) as total_clients,
                SUM(CASE WHEN processing_status = 'success' THEN 1 ELSE 0 END) as processed_clients,
                SUM(CASE WHEN processing_status = 'pending' THEN 1 ELSE 0 END) as pending_clients,
                SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed_clients
            FROM clients
        """)
        stats.update(dict(self.cursor.fetchone()))

        # Country and product counts
        self.cursor.execute("SELECT COUNT(DISTINCT country) as countries FROM clients")
        stats.update(dict(self.cursor.fetchone()))

        self.cursor.execute("SELECT COUNT(DISTINCT product) as products FROM clients")
        stats.update(dict(self.cursor.fetchone()))

        # Pattern counts
        self.cursor.execute("SELECT COUNT(DISTINCT pattern_signature) as unique_patterns FROM clients")
        stats.update(dict(self.cursor.fetchone()))

        self.cursor.execute("SELECT COUNT(DISTINCT pattern_cluster_id) as pattern_clusters FROM clients WHERE pattern_cluster_id IS NOT NULL")
        stats.update(dict(self.cursor.fetchone()))

        return stats

    def get_countries(self) -> List[str]:
        """Get list of all countries."""
        self.cursor.execute("""
            SELECT DISTINCT country FROM clients
            WHERE country IS NOT NULL
            ORDER BY country
        """)
        return [row['country'] for row in self.cursor.fetchall()]

    def get_products(self) -> List[str]:
        """Get list of all products."""
        self.cursor.execute("""
            SELECT DISTINCT product FROM clients
            WHERE product IS NOT NULL
            ORDER BY product
        """)
        return [row['product'] for row in self.cursor.fetchall()]

    def get_clients_by_pattern(self, pattern_signature: str) -> List[Dict[str, Any]]:
        """
        Get all clients with a specific pattern signature.

        Args:
            pattern_signature: Pattern signature hash

        Returns:
            List of client records
        """
        self.cursor.execute("""
            SELECT
                client_id, client_name, country, product,
                filename, pattern_cluster_id
            FROM clients
            WHERE pattern_signature = ?
        """, (pattern_signature,))

        return [dict(row) for row in self.cursor.fetchall()]

    def update_pattern_cluster(self, client_id: str, cluster_id: int):
        """
        Update pattern cluster assignment for a client.

        Args:
            client_id: Client ID
            cluster_id: Cluster ID
        """
        self.cursor.execute("""
            UPDATE clients
            SET pattern_cluster_id = ?
            WHERE client_id = ?
        """, (cluster_id, client_id))
        self.conn.commit()

    def save_pattern_cluster(
        self,
        cluster_id: int,
        cluster_name: Optional[str],
        structure_summary: Dict[str, Any],
        example_client_ids: List[str]
    ):
        """
        Save or update pattern cluster.

        Args:
            cluster_id: Cluster ID
            cluster_name: Optional cluster name
            structure_summary: Summary of cluster structure
            example_client_ids: Example client IDs
        """
        now = datetime.now().isoformat()

        # Count clients in this cluster
        self.cursor.execute("""
            SELECT COUNT(*) as count FROM clients
            WHERE pattern_cluster_id = ?
        """, (cluster_id,))
        client_count = self.cursor.fetchone()['count']

        self.cursor.execute("""
            INSERT INTO pattern_clusters (
                cluster_id, cluster_name, client_count,
                structure_summary, example_client_ids,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cluster_id) DO UPDATE SET
                cluster_name = excluded.cluster_name,
                client_count = excluded.client_count,
                structure_summary = excluded.structure_summary,
                example_client_ids = excluded.example_client_ids,
                updated_at = excluded.updated_at
        """, (
            cluster_id,
            cluster_name,
            client_count,
            json.dumps(structure_summary),
            json.dumps(example_client_ids),
            now,
            now
        ))
        self.conn.commit()

    def get_pattern_clusters(self) -> List[Dict[str, Any]]:
        """
        Get all pattern clusters.

        Returns:
            List of cluster information
        """
        self.cursor.execute("""
            SELECT * FROM pattern_clusters
            ORDER BY client_count DESC
        """)

        clusters = []
        for row in self.cursor.fetchall():
            cluster = dict(row)
            cluster['structure_summary'] = json.loads(cluster['structure_summary'] or '{}')
            cluster['example_client_ids'] = json.loads(cluster['example_client_ids'] or '[]')
            clusters.append(cluster)

        return clusters

    def get_folder_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary by folder structure.

        Returns:
            List of folder statistics
        """
        self.cursor.execute("""
            SELECT
                country,
                product,
                COUNT(*) as client_count,
                SUM(CASE WHEN processing_status = 'success' THEN 1 ELSE 0 END) as processed_count,
                SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM clients
            GROUP BY country, product
            ORDER BY country, product
        """)

        return [dict(row) for row in self.cursor.fetchall()]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
