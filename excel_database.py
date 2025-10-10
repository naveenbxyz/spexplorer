"""
SQLite database manager for storing parsed Excel data.
Preserves folder hierarchy and enables pattern analysis.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib


class ExcelDatabase:
    """
    Manages SQLite database for Excel parsing results.
    """

    def __init__(self, db_path: str = "excel_data.db"):
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

    def _connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        """Create database schema."""

        # Files table - stores file metadata and folder structure
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                folder_country TEXT,
                folder_client TEXT,
                folder_product TEXT,
                relative_folder_path TEXT,
                file_size_bytes INTEGER,
                modified_date TEXT,
                downloaded_date TEXT,
                processed_date TEXT,
                processing_status TEXT DEFAULT 'pending',
                processing_error TEXT,
                UNIQUE(file_path)
            )
        """)

        # Sheets table - stores sheet-level information
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sheets (
                sheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                sheet_name TEXT NOT NULL,
                sheet_index INTEGER,
                total_rows INTEGER,
                total_columns INTEGER,
                merged_cells_count INTEGER,
                tables_detected INTEGER,
                FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
                UNIQUE(file_id, sheet_name)
            )
        """)

        # Tables table - stores individual table structures
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tables (
                table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER NOT NULL,
                table_index INTEGER,
                table_identifier TEXT,
                start_row INTEGER,
                end_row INTEGER,
                start_col INTEGER,
                end_col INTEGER,
                header_detected BOOLEAN,
                header_row_index INTEGER,
                row_count INTEGER,
                column_count INTEGER,
                pattern_signature TEXT,
                headers_json TEXT,
                full_data_json TEXT,
                FOREIGN KEY (sheet_id) REFERENCES sheets(sheet_id) ON DELETE CASCADE
            )
        """)

        # Pattern analysis table - tracks similar table patterns
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_analysis (
                pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_signature TEXT UNIQUE,
                pattern_name TEXT,
                occurrence_count INTEGER DEFAULT 1,
                sample_headers_json TEXT,
                first_seen_date TEXT,
                last_seen_date TEXT,
                example_file_ids TEXT
            )
        """)

        # Create indexes for better query performance
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_folder
            ON files(folder_country, folder_client, folder_product)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_status
            ON files(processing_status)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tables_pattern
            ON tables(pattern_signature)
        """)

        self.conn.commit()

    def add_file(self, file_info: Dict[str, Any]) -> int:
        """
        Add or update a file record.

        Args:
            file_info: Dictionary with file metadata

        Returns:
            file_id of inserted/updated record
        """
        # Parse folder structure from relative path
        folder_parts = self._parse_folder_structure(file_info.get('relative_folder', ''))

        self.cursor.execute("""
            INSERT INTO files (
                filename, file_path, folder_country, folder_client, folder_product,
                relative_folder_path, file_size_bytes, modified_date, downloaded_date,
                processing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                modified_date = excluded.modified_date,
                downloaded_date = excluded.downloaded_date,
                processing_status = 'pending'
        """, (
            file_info.get('filename'),
            file_info.get('file_path'),
            folder_parts.get('country'),
            folder_parts.get('client'),
            folder_parts.get('product'),
            file_info.get('relative_folder', ''),
            file_info.get('file_size'),
            file_info.get('modified_date'),
            datetime.now().isoformat(),
            'pending'
        ))

        self.conn.commit()

        # Get the file_id
        self.cursor.execute("SELECT file_id FROM files WHERE file_path = ?", (file_info.get('file_path'),))
        result = self.cursor.fetchone()
        return result['file_id'] if result else None

    def _parse_folder_structure(self, relative_folder: str) -> Dict[str, Optional[str]]:
        """
        Parse folder path into country/client/product structure.

        Expected structure: Country/Client/Product
        e.g., "USA/Acme Corp/Product A"

        Args:
            relative_folder: Relative folder path

        Returns:
            Dictionary with country, client, product
        """
        parts = relative_folder.split('/') if relative_folder else []

        return {
            'country': parts[0] if len(parts) > 0 else None,
            'client': parts[1] if len(parts) > 1 else None,
            'product': parts[2] if len(parts) > 2 else None
        }

    def save_parsed_data(self, file_id: int, parsed_data: Dict[str, Any]):
        """
        Save parsed Excel data to database.

        Args:
            file_id: File ID from files table
            parsed_data: Parsed data from TableExtractor
        """
        try:
            # Process each sheet
            for sheet_idx, sheet_data in enumerate(parsed_data.get('sheets', [])):
                # Insert sheet record
                self.cursor.execute("""
                    INSERT INTO sheets (
                        file_id, sheet_name, sheet_index, total_rows, total_columns,
                        merged_cells_count, tables_detected
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id, sheet_name) DO UPDATE SET
                        sheet_index = excluded.sheet_index,
                        total_rows = excluded.total_rows,
                        total_columns = excluded.total_columns,
                        merged_cells_count = excluded.merged_cells_count,
                        tables_detected = excluded.tables_detected
                """, (
                    file_id,
                    sheet_data['sheet_name'],
                    sheet_idx,
                    sheet_data['metadata'].get('total_rows', 0),
                    sheet_data['metadata'].get('total_columns', 0),
                    sheet_data['metadata'].get('merged_cells', 0),
                    len(sheet_data.get('tables', []))
                ))

                # Get sheet_id
                self.cursor.execute(
                    "SELECT sheet_id FROM sheets WHERE file_id = ? AND sheet_name = ?",
                    (file_id, sheet_data['sheet_name'])
                )
                sheet_id = self.cursor.fetchone()['sheet_id']

                # Process each table in the sheet
                for table_data in sheet_data.get('tables', []):
                    self._save_table(sheet_id, file_id, table_data)

            # Update file processing status
            self.cursor.execute("""
                UPDATE files
                SET processing_status = 'completed',
                    processed_date = ?,
                    processing_error = NULL
                WHERE file_id = ?
            """, (datetime.now().isoformat(), file_id))

            self.conn.commit()

        except Exception as e:
            # Update file with error status
            self.cursor.execute("""
                UPDATE files
                SET processing_status = 'failed',
                    processing_error = ?
                WHERE file_id = ?
            """, (str(e), file_id))
            self.conn.commit()
            raise

    def _save_table(self, sheet_id: int, file_id: int, table_data: Dict[str, Any]):
        """
        Save individual table data.

        Args:
            sheet_id: Sheet ID
            file_id: File ID
            table_data: Table data from parser
        """
        region = table_data.get('region', {})
        metadata = table_data.get('metadata', {})
        pattern_sig = metadata.get('pattern_signature')

        # Insert table record
        self.cursor.execute("""
            INSERT INTO tables (
                sheet_id, table_index, table_identifier,
                start_row, end_row, start_col, end_col,
                header_detected, header_row_index,
                row_count, column_count, pattern_signature,
                headers_json, full_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sheet_id,
            int(table_data['table_id'].split('_')[1]) if '_' in table_data['table_id'] else 0,
            table_data['table_id'],
            region.get('start_row'),
            region.get('end_row'),
            region.get('start_col'),
            region.get('end_col'),
            table_data.get('header_detected', False),
            table_data.get('header_row_index'),
            len(table_data.get('rows', [])),
            metadata.get('total_columns', 0),
            pattern_sig,
            json.dumps(metadata.get('headers', [])) if metadata.get('headers') else None,
            json.dumps(table_data.get('rows', []))
        ))

        # Update pattern analysis
        if pattern_sig:
            self._update_pattern_analysis(pattern_sig, file_id, metadata.get('headers', []))

    def _update_pattern_analysis(self, pattern_signature: str, file_id: int, headers: List[str]):
        """
        Update pattern analysis table.

        Args:
            pattern_signature: Pattern hash
            file_id: File ID
            headers: Table headers
        """
        # Check if pattern exists
        self.cursor.execute(
            "SELECT pattern_id, occurrence_count, example_file_ids FROM pattern_analysis WHERE pattern_signature = ?",
            (pattern_signature,)
        )
        existing = self.cursor.fetchone()

        now = datetime.now().isoformat()

        if existing:
            # Update existing pattern
            example_files = json.loads(existing['example_file_ids'] or '[]')
            if file_id not in example_files:
                example_files.append(file_id)
                # Keep only last 10 examples
                example_files = example_files[-10:]

            self.cursor.execute("""
                UPDATE pattern_analysis
                SET occurrence_count = occurrence_count + 1,
                    last_seen_date = ?,
                    example_file_ids = ?
                WHERE pattern_signature = ?
            """, (now, json.dumps(example_files), pattern_signature))
        else:
            # Insert new pattern
            self.cursor.execute("""
                INSERT INTO pattern_analysis (
                    pattern_signature, occurrence_count, sample_headers_json,
                    first_seen_date, last_seen_date, example_file_ids
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pattern_signature,
                1,
                json.dumps(headers),
                now,
                now,
                json.dumps([file_id])
            ))

    def get_files_to_process(self, status: str = 'pending', limit: int = None) -> List[Dict[str, Any]]:
        """
        Get files that need processing.

        Args:
            status: Processing status filter
            limit: Maximum number of files to return

        Returns:
            List of file records
        """
        query = "SELECT * FROM files WHERE processing_status = ?"
        params = [status]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def get_pattern_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of detected patterns.

        Returns:
            List of pattern statistics
        """
        self.cursor.execute("""
            SELECT
                pattern_signature,
                pattern_name,
                occurrence_count,
                sample_headers_json,
                first_seen_date,
                last_seen_date
            FROM pattern_analysis
            ORDER BY occurrence_count DESC
        """)

        patterns = []
        for row in self.cursor.fetchall():
            pattern = dict(row)
            pattern['sample_headers'] = json.loads(pattern['sample_headers_json'] or '[]')
            del pattern['sample_headers_json']
            patterns.append(pattern)

        return patterns

    def get_folder_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary by folder structure.

        Returns:
            List of folder statistics
        """
        self.cursor.execute("""
            SELECT
                folder_country,
                folder_client,
                folder_product,
                COUNT(*) as file_count,
                SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as processed_count,
                SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed_count
            FROM files
            GROUP BY folder_country, folder_client, folder_product
            ORDER BY folder_country, folder_client, folder_product
        """)

        return [dict(row) for row in self.cursor.fetchall()]

    def search_tables_by_header(self, header_name: str) -> List[Dict[str, Any]]:
        """
        Search for tables containing a specific header.

        Args:
            header_name: Header name to search for

        Returns:
            List of matching tables with file context
        """
        self.cursor.execute("""
            SELECT
                t.table_id,
                t.headers_json,
                t.row_count,
                s.sheet_name,
                f.filename,
                f.file_path,
                f.folder_country,
                f.folder_client,
                f.folder_product
            FROM tables t
            JOIN sheets s ON t.sheet_id = s.sheet_id
            JOIN files f ON s.file_id = f.file_id
            WHERE t.headers_json LIKE ?
        """, (f'%{header_name}%',))

        return [dict(row) for row in self.cursor.fetchall()]

    def get_table_data(self, table_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full table data by ID.

        Args:
            table_id: Table ID

        Returns:
            Table data with all rows
        """
        self.cursor.execute("""
            SELECT
                t.*,
                s.sheet_name,
                f.filename,
                f.file_path
            FROM tables t
            JOIN sheets s ON t.sheet_id = s.sheet_id
            JOIN files f ON s.file_id = f.file_id
            WHERE t.table_id = ?
        """, (table_id,))

        row = self.cursor.fetchone()
        if not row:
            return None

        table = dict(row)
        table['headers'] = json.loads(table['headers_json'] or '[]')
        table['rows'] = json.loads(table['full_data_json'] or '[]')

        # Clean up JSON strings
        del table['headers_json']
        del table['full_data_json']

        return table

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall database statistics.

        Returns:
            Statistics dictionary
        """
        stats = {}

        # File counts
        self.cursor.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(CASE WHEN processing_status = 'completed' THEN 1 ELSE 0 END) as processed_files,
                SUM(CASE WHEN processing_status = 'pending' THEN 1 ELSE 0 END) as pending_files,
                SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END) as failed_files
            FROM files
        """)
        stats.update(dict(self.cursor.fetchone()))

        # Sheet and table counts
        self.cursor.execute("SELECT COUNT(*) as total_sheets FROM sheets")
        stats.update(dict(self.cursor.fetchone()))

        self.cursor.execute("SELECT COUNT(*) as total_tables FROM tables")
        stats.update(dict(self.cursor.fetchone()))

        # Pattern count
        self.cursor.execute("SELECT COUNT(*) as unique_patterns FROM pattern_analysis")
        stats.update(dict(self.cursor.fetchone()))

        # Folder counts
        self.cursor.execute("SELECT COUNT(DISTINCT folder_country) as countries FROM files")
        stats.update(dict(self.cursor.fetchone()))

        self.cursor.execute("SELECT COUNT(DISTINCT folder_client) as clients FROM files")
        stats.update(dict(self.cursor.fetchone()))

        return stats

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
