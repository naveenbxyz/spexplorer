"""
Client Summary Generator
Creates a summary table of all clients with their files, products, sheets, and file types.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
from collections import defaultdict


class ClientSummary:
    """
    Generates summary reports from JSON storage or SQLite database.
    """

    def __init__(self, json_storage=None, database=None):
        """
        Initialize summary generator.

        Args:
            json_storage: JSONStorage instance (optional)
            database: ClientDatabase instance (optional)
        """
        self.json_storage = json_storage
        self.database = database

    def _extract_file_type(self, filename: str) -> Optional[str]:
        """
        Extract file type from filename (PSCAF or NECAF).

        Args:
            filename: Filename to check

        Returns:
            'PSCAF', 'NECAF', or None
        """
        filename_upper = filename.upper()
        if 'PSCAF' in filename_upper:
            return 'PSCAF'
        elif 'NECAF' in filename_upper:
            return 'NECAF'
        return None

    def _extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract date from filename using various patterns.

        Args:
            filename: Excel filename

        Returns:
            datetime object or None if no date found
        """
        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]

        date_patterns = [
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

        for pattern, date_format in date_patterns:
            match = re.search(pattern, name_without_ext)
            if match:
                try:
                    date_str = match.group(0)
                    return datetime.strptime(date_str, date_format)
                except ValueError:
                    continue

        return None

    def _get_relative_path(self, file_path: str, root_folder: str) -> str:
        """
        Get relative path excluding root folder.

        Args:
            file_path: Full file path
            root_folder: Root folder to exclude

        Returns:
            Relative path string
        """
        try:
            path = Path(file_path)
            root = Path(root_folder)
            return str(path.relative_to(root))
        except ValueError:
            # If not relative, return the path as-is
            return file_path

    def generate_summary(self, root_folder: Optional[str] = None) -> pd.DataFrame:
        """
        Generate comprehensive summary of all clients.

        Args:
            root_folder: Root folder path (for relative paths)

        Returns:
            DataFrame with summary information
        """
        summary_data = []

        if self.json_storage:
            # Use JSON storage
            with self.json_storage.index_lock:
                clients_metadata = list(self.json_storage.metadata_index['clients'].values())

            for metadata in clients_metadata:
                client_id = metadata.get('client_id')
                client_data = self.json_storage.get_client(client_id)

                if client_data:
                    summary_data.extend(self._process_client(client_data, root_folder))

        elif self.database:
            # Use SQLite database
            clients = self.database.search_clients(limit=10000)

            for client_info in clients:
                client_id = client_info['client_id']
                client_data = self.database.get_client(client_id)

                if client_data:
                    summary_data.extend(self._process_client(client_data, root_folder))

        # Convert to DataFrame
        if summary_data:
            df = pd.DataFrame(summary_data)

            # Sort by client_name, product, file_type, and date (most recent first)
            sort_columns = ['client_name', 'product', 'file_type']
            if 'extracted_date' in df.columns:
                df = df.sort_values(
                    sort_columns + ['extracted_date'],
                    ascending=[True, True, True, False]
                )
            else:
                df = df.sort_values(sort_columns)

            return df
        else:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=[
                'client_name', 'country', 'product', 'file_type',
                'filename', 'relative_path', 'sheets', 'sheet_count',
                'extracted_date', 'is_latest', 'processing_status'
            ])

    def _process_client(self, client_data: Dict[str, Any], root_folder: Optional[str]) -> List[Dict[str, Any]]:
        """
        Process a single client's data into summary records.

        Args:
            client_data: Client JSON data
            root_folder: Root folder for relative paths

        Returns:
            List of summary record dictionaries
        """
        client_name = client_data.get('client_name')
        country = client_data.get('country')
        product = client_data.get('product')

        file_info = client_data.get('file_info', {})
        file_path = file_info.get('file_path', '')
        filename = file_info.get('filename', '')

        # Extract file type
        file_type = self._extract_file_type(filename)

        # Get relative path
        relative_path = self._get_relative_path(file_path, root_folder) if root_folder else file_path

        # Get sheet names
        sheets = client_data.get('sheets', [])
        sheet_names = [sheet.get('sheet_name') for sheet in sheets if sheet.get('sheet_name')]

        # Get extracted date
        extracted_date = file_info.get('extracted_date')
        if isinstance(extracted_date, str):
            try:
                extracted_date = datetime.fromisoformat(extracted_date)
            except:
                extracted_date = None

        # If no date from metadata, try to extract from filename
        if not extracted_date:
            extracted_date = self._extract_date_from_filename(filename)

        # Processing status
        processing_status = client_data.get('processing_metadata', {}).get('status', 'unknown')

        # Is latest
        is_latest = file_info.get('is_latest', False)

        return [{
            'client_name': client_name,
            'country': country,
            'product': product,
            'file_type': file_type or 'Other',
            'filename': filename,
            'relative_path': relative_path,
            'sheets': ', '.join(sheet_names),
            'sheet_count': len(sheet_names),
            'extracted_date': extracted_date,
            'is_latest': is_latest,
            'processing_status': processing_status
        }]

    def generate_grouped_summary(self, root_folder: Optional[str] = None) -> pd.DataFrame:
        """
        Generate summary grouped by client and product, with multiple versions listed.

        Args:
            root_folder: Root folder path (for relative paths)

        Returns:
            DataFrame with grouped summary information
        """
        # Get detailed summary
        detailed_df = self.generate_summary(root_folder)

        if detailed_df.empty:
            return pd.DataFrame(columns=[
                'client_name', 'country', 'product', 'file_type',
                'version_count', 'latest_file', 'latest_date', 'all_versions',
                'sheets', 'sheet_count'
            ])

        # Group by client, product, and file_type
        grouped_data = []

        for (client_name, product, file_type), group in detailed_df.groupby(
            ['client_name', 'product', 'file_type']
        ):
            # Get country (should be same for all in group)
            country = group['country'].iloc[0]

            # Sort by date (most recent first)
            group = group.sort_values('extracted_date', ascending=False, na_position='last')

            # Get latest file info
            latest_row = group.iloc[0]
            latest_file = latest_row['filename']
            latest_date = latest_row['extracted_date']
            sheets = latest_row['sheets']
            sheet_count = latest_row['sheet_count']

            # Create version list with all files
            all_versions = []
            for idx, row in group.iterrows():
                version_info = {
                    'filename': row['filename'],
                    'date': row['extracted_date'],
                    'relative_path': row['relative_path'],
                    'is_latest': idx == group.index[0]  # First one is latest
                }
                all_versions.append(version_info)

            grouped_data.append({
                'client_name': client_name,
                'country': country,
                'product': product,
                'file_type': file_type,
                'version_count': len(group),
                'latest_file': latest_file,
                'latest_date': latest_date,
                'all_versions': all_versions,
                'sheets': sheets,
                'sheet_count': sheet_count
            })

        return pd.DataFrame(grouped_data)

    def export_to_excel(self, output_path: str, root_folder: Optional[str] = None):
        """
        Export summary to Excel with multiple sheets.

        Args:
            output_path: Output Excel file path
            root_folder: Root folder path (for relative paths)
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: Detailed summary (all files)
            detailed_df = self.generate_summary(root_folder)
            if not detailed_df.empty:
                # Format date column
                if 'extracted_date' in detailed_df.columns:
                    detailed_df['extracted_date'] = detailed_df['extracted_date'].apply(
                        lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and isinstance(x, datetime) else ''
                    )
                detailed_df.to_excel(writer, sheet_name='All Files', index=False)

            # Sheet 2: Grouped summary (by client/product)
            grouped_df = self.generate_grouped_summary(root_folder)
            if not grouped_df.empty:
                # Expand all_versions for Excel export
                export_df = grouped_df.copy()

                # Create a versions column with formatted text
                export_df['versions'] = export_df['all_versions'].apply(
                    lambda versions: '\n'.join([
                        f"{'[LATEST] ' if v['is_latest'] else ''}{v['filename']} ({v['date'].strftime('%Y-%m-%d') if v['date'] else 'No date'})"
                        for v in versions
                    ])
                )

                # Format latest_date
                if 'latest_date' in export_df.columns:
                    export_df['latest_date'] = export_df['latest_date'].apply(
                        lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and isinstance(x, datetime) else ''
                    )

                # Drop the all_versions column (not Excel-friendly)
                export_df = export_df.drop(columns=['all_versions'])

                export_df.to_excel(writer, sheet_name='Summary by Client', index=False)

            # Sheet 3: PSCAF files only
            pscaf_df = detailed_df[detailed_df['file_type'] == 'PSCAF'].copy() if not detailed_df.empty else pd.DataFrame()
            if not pscaf_df.empty:
                pscaf_df.to_excel(writer, sheet_name='PSCAF Files', index=False)

            # Sheet 4: NECAF files only
            necaf_df = detailed_df[detailed_df['file_type'] == 'NECAF'].copy() if not detailed_df.empty else pd.DataFrame()
            if not necaf_df.empty:
                necaf_df.to_excel(writer, sheet_name='NECAF Files', index=False)

        print(f"✅ Summary exported to: {output_path}")

    def export_to_csv(self, output_path: str, root_folder: Optional[str] = None):
        """
        Export summary to CSV.

        Args:
            output_path: Output CSV file path
            root_folder: Root folder path (for relative paths)
        """
        df = self.generate_summary(root_folder)

        if not df.empty:
            # Format date column
            if 'extracted_date' in df.columns:
                df['extracted_date'] = df['extracted_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and isinstance(x, datetime) else ''
                )
            df.to_csv(output_path, index=False)
            print(f"✅ Summary exported to: {output_path}")
        else:
            print("⚠️  No data to export")

    def print_summary(self, root_folder: Optional[str] = None, max_rows: int = 50):
        """
        Print summary to console.

        Args:
            root_folder: Root folder path (for relative paths)
            max_rows: Maximum rows to display
        """
        df = self.generate_summary(root_folder)

        if df.empty:
            print("No data found.")
            return

        # Format date for display
        if 'extracted_date' in df.columns:
            df['extracted_date'] = df['extracted_date'].apply(
                lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and isinstance(x, datetime) else ''
            )

        # Print statistics
        print("\n" + "=" * 80)
        print("CLIENT SUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total clients: {df['client_name'].nunique()}")
        print(f"Total files: {len(df)}")
        print(f"PSCAF files: {len(df[df['file_type'] == 'PSCAF'])}")
        print(f"NECAF files: {len(df[df['file_type'] == 'NECAF'])}")
        print(f"Other files: {len(df[df['file_type'] == 'Other'])}")
        print()

        # Print by file type
        print("Files by type:")
        print(df['file_type'].value_counts().to_string())
        print()

        # Print sample data
        print("=" * 80)
        print(f"SAMPLE DATA (first {max_rows} rows)")
        print("=" * 80)

        # Select columns for display
        display_columns = ['client_name', 'product', 'file_type', 'filename', 'sheets', 'extracted_date']
        display_df = df[display_columns].head(max_rows)

        print(display_df.to_string(index=False))
        print()


def main():
    """
    Command-line interface for summary generation.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate client summary from JSON storage or SQLite database'
    )
    parser.add_argument(
        '--json-path',
        default='./extracted_json',
        help='Path to JSON storage directory (default: ./extracted_json)'
    )
    parser.add_argument(
        '--db-path',
        help='Path to SQLite database (alternative to JSON)'
    )
    parser.add_argument(
        '--root-folder',
        help='Root folder for calculating relative paths'
    )
    parser.add_argument(
        '--output-excel',
        help='Output Excel file path'
    )
    parser.add_argument(
        '--output-csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--print',
        action='store_true',
        help='Print summary to console'
    )

    args = parser.parse_args()

    # Initialize storage
    json_storage = None
    database = None

    if args.db_path:
        from client_database import ClientDatabase
        database = ClientDatabase(args.db_path)
        print(f"📂 Using SQLite database: {args.db_path}")
    else:
        from json_storage import JSONStorage
        json_storage = JSONStorage(args.json_path)
        print(f"📂 Using JSON storage: {args.json_path}")

    # Create summary generator
    summary = ClientSummary(json_storage=json_storage, database=database)

    # Generate outputs
    if args.output_excel:
        summary.export_to_excel(args.output_excel, root_folder=args.root_folder)

    if args.output_csv:
        summary.export_to_csv(args.output_csv, root_folder=args.root_folder)

    if args.print:
        summary.print_summary(root_folder=args.root_folder)

    if not any([args.output_excel, args.output_csv, args.print]):
        # Default: print to console
        summary.print_summary(root_folder=args.root_folder)


if __name__ == '__main__':
    main()
