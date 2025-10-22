"""
Client Data Viewer
Displays extracted client data from JSON storage or SQLite database in a readable format.
"""

import json
from typing import Dict, List, Any, Optional
import pandas as pd
from pathlib import Path


class ClientDataViewer:
    """
    Viewer for displaying extracted client data in various formats.
    """

    def __init__(self, json_storage=None, database=None):
        """
        Initialize data viewer.

        Args:
            json_storage: JSONStorage instance (optional)
            database: ClientDatabase instance (optional)
        """
        self.json_storage = json_storage
        self.database = database

    def search_clients(
        self,
        search_term: Optional[str] = None,
        country: Optional[str] = None,
        product: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for clients.

        Args:
            search_term: Search term for client name
            country: Filter by country
            product: Filter by product
            limit: Maximum results

        Returns:
            List of client metadata
        """
        if self.json_storage:
            return self.json_storage.search_clients(
                query=search_term,
                country=country,
                product=product,
                limit=limit
            )
        elif self.database:
            return self.database.search_clients(
                query=search_term,
                country=country,
                product=product,
                limit=limit
            )
        return []

    def get_client_data(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full client data.

        Args:
            client_id: Client ID

        Returns:
            Client data dictionary or None
        """
        if self.json_storage:
            return self.json_storage.get_client(client_id)
        elif self.database:
            return self.database.get_client(client_id)
        return None

    def get_countries(self) -> List[str]:
        """Get list of all countries."""
        if self.json_storage:
            return self.json_storage.get_countries()
        elif self.database:
            return self.database.get_countries()
        return []

    def get_products(self) -> List[str]:
        """Get list of all products."""
        if self.json_storage:
            return self.json_storage.get_products()
        elif self.database:
            return self.database.get_products()
        return []

    def format_key_value_section(self, section: Dict[str, Any]) -> pd.DataFrame:
        """
        Format key-value section as DataFrame.

        Args:
            section: Section data

        Returns:
            DataFrame with keys and values
        """
        data = section.get('data', {})

        if not data:
            return pd.DataFrame()

        rows = []
        for key, value in data.items():
            rows.append({
                'Field': key.replace('_', ' ').title(),
                'Value': value if value is not None else ''
            })

        return pd.DataFrame(rows)

    def format_table_section(self, section: Dict[str, Any]) -> pd.DataFrame:
        """
        Format table section as DataFrame.

        Args:
            section: Section data

        Returns:
            DataFrame with table data
        """
        data = section.get('data', [])

        if not data:
            return pd.DataFrame()

        # Remove internal fields starting with _
        cleaned_data = []
        for row in data:
            cleaned_row = {
                k.replace('_', ' ').title(): v
                for k, v in row.items()
                if not k.startswith('_')
            }
            cleaned_data.append(cleaned_row)

        return pd.DataFrame(cleaned_data)

    def format_complex_header_section(self, section: Dict[str, Any]) -> pd.DataFrame:
        """
        Format complex header section as DataFrame.

        Args:
            section: Section data

        Returns:
            DataFrame with table data
        """
        # Similar to table section
        return self.format_table_section(section)

    def format_raw_section(self, section: Dict[str, Any]) -> pd.DataFrame:
        """
        Format raw section as DataFrame.

        Args:
            section: Section data

        Returns:
            DataFrame with raw data
        """
        data = section.get('data', [])

        if not data:
            return pd.DataFrame()

        # Convert list of lists to DataFrame
        return pd.DataFrame(data)

    def format_section(self, section: Dict[str, Any]) -> tuple[str, pd.DataFrame]:
        """
        Format any section type as DataFrame.

        Args:
            section: Section data

        Returns:
            Tuple of (section_type, DataFrame)
        """
        section_type = section.get('section_type', 'unknown')

        if section_type == 'key_value':
            df = self.format_key_value_section(section)
        elif section_type == 'table':
            df = self.format_table_section(section)
        elif section_type == 'complex_header':
            df = self.format_complex_header_section(section)
        elif section_type == 'raw':
            df = self.format_raw_section(section)
        else:
            df = pd.DataFrame()

        return section_type, df

    def get_client_summary(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get summary information about a client.

        Args:
            client_data: Client data dictionary

        Returns:
            Summary dictionary
        """
        sheets = client_data.get('sheets', [])

        total_sections = sum(len(sheet.get('sections', [])) for sheet in sheets)

        section_types = {}
        for sheet in sheets:
            for section in sheet.get('sections', []):
                section_type = section.get('section_type', 'unknown')
                section_types[section_type] = section_types.get(section_type, 0) + 1

        processing_meta = client_data.get('processing_metadata', {})
        file_info = client_data.get('file_info', {})

        return {
            'client_id': client_data.get('client_id'),
            'client_name': client_data.get('client_name'),
            'country': client_data.get('country'),
            'product': client_data.get('product'),
            'filename': file_info.get('filename'),
            'file_path': file_info.get('file_path'),
            'extracted_date': file_info.get('extracted_date'),
            'is_latest': file_info.get('is_latest'),
            'sheet_count': len(sheets),
            'total_sections': total_sections,
            'section_types': section_types,
            'processing_status': processing_meta.get('status'),
            'processed_at': processing_meta.get('processed_at'),
            'pattern_signature': client_data.get('pattern_signature'),
        }

    def export_client_to_excel(self, client_id: str, output_path: str):
        """
        Export client data to Excel with multiple sheets.

        Args:
            client_id: Client ID
            output_path: Output Excel file path
        """
        client_data = self.get_client_data(client_id)

        if not client_data:
            raise ValueError(f"Client not found: {client_id}")

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary = self.get_client_summary(client_data)
            summary_df = pd.DataFrame([summary])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Process each sheet
            for sheet in client_data.get('sheets', []):
                sheet_name = sheet.get('sheet_name', 'Unknown')

                # Truncate sheet name if too long (Excel limit is 31 chars)
                sheet_name = sheet_name[:31]

                # Write each section to the sheet
                sections = sheet.get('sections', [])

                if not sections:
                    continue

                # Combine all sections in this sheet
                start_row = 0
                for idx, section in enumerate(sections):
                    section_header = section.get('section_header') or f"Section {idx + 1}"
                    section_type, df = self.format_section(section)

                    if df.empty:
                        continue

                    # Write section header
                    header_df = pd.DataFrame([[f"=== {section_header} ({section_type}) ==="]])
                    header_df.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        startrow=start_row,
                        index=False,
                        header=False
                    )
                    start_row += 1

                    # Write section data
                    df.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        startrow=start_row,
                        index=False
                    )
                    start_row += len(df) + 3  # Add spacing

        print(f"✅ Client data exported to: {output_path}")

    def export_client_to_json(self, client_id: str, output_path: str):
        """
        Export client data to JSON file.

        Args:
            client_id: Client ID
            output_path: Output JSON file path
        """
        client_data = self.get_client_data(client_id)

        if not client_data:
            raise ValueError(f"Client not found: {client_id}")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(client_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Client data exported to: {output_path}")


def main():
    """
    Command-line interface for client data viewer.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='View and export client data'
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
        '--search',
        help='Search for clients by name'
    )
    parser.add_argument(
        '--client-id',
        help='View specific client by ID'
    )
    parser.add_argument(
        '--export-excel',
        help='Export client data to Excel'
    )
    parser.add_argument(
        '--export-json',
        help='Export client data to JSON'
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

    # Create viewer
    viewer = ClientDataViewer(json_storage=json_storage, database=database)

    # Search
    if args.search:
        print(f"\n🔍 Searching for: {args.search}")
        results = viewer.search_clients(search_term=args.search)

        if results:
            print(f"\nFound {len(results)} results:")
            for r in results:
                print(f"  - {r.get('client_name')} ({r.get('country')}/{r.get('product')}) [{r.get('client_id')}]")
        else:
            print("No results found.")

    # View client
    if args.client_id:
        print(f"\n📄 Viewing client: {args.client_id}")
        client_data = viewer.get_client_data(args.client_id)

        if client_data:
            summary = viewer.get_client_summary(client_data)
            print(f"\nClient: {summary['client_name']}")
            print(f"Country: {summary['country']}")
            print(f"Product: {summary['product']}")
            print(f"Sheets: {summary['sheet_count']}")
            print(f"Sections: {summary['total_sections']}")
            print(f"Status: {summary['processing_status']}")

            # Export if requested
            if args.export_excel:
                viewer.export_client_to_excel(args.client_id, args.export_excel)

            if args.export_json:
                viewer.export_client_to_json(args.client_id, args.export_json)
        else:
            print("Client not found.")


if __name__ == '__main__':
    main()
