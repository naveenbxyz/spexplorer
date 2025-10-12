"""
Batch processor for client-centric Excel parsing.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from file_selector import FileSelector
from client_extractor import ClientExtractor
from client_database import ClientDatabase


class ClientProcessor:
    """
    Process Excel files and generate client JSON documents.
    """

    def __init__(
        self,
        output_folder: str,
        db_path: str = "client_data.db",
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize client processor.

        Args:
            output_folder: Root folder containing downloaded Excel files
            db_path: Path to SQLite database
            progress_callback: Optional callback for progress updates
        """
        self.output_folder = output_folder
        self.db_path = db_path
        self.progress_callback = progress_callback

        self.file_selector = FileSelector()
        self.extractor = ClientExtractor()
        self.db = ClientDatabase(db_path)

        self.stats = {
            'total_files': 0,
            'selected_files': 0,
            'ignored_files': 0,
            'processed': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }

    def process_all(self, reprocess: bool = False):
        """
        Process all Excel files in output folder.

        Args:
            reprocess: If True, reprocess files that have already been processed
        """
        self.stats['start_time'] = datetime.now()

        # Discover and select files
        if self.progress_callback:
            self.progress_callback({
                'phase': 'discovery',
                'message': 'Discovering Excel files...'
            })

        selected_files = self.file_selector.discover_and_select_files(self.output_folder)

        self.stats['selected_files'] = len(selected_files)

        if self.progress_callback:
            self.progress_callback({
                'phase': 'discovery_complete',
                'total_files': len(selected_files),
                'message': f'Selected {len(selected_files)} files to process'
            })

        # Generate client IDs and filter if needed
        clients_to_process = []

        for file_info in selected_files:
            client_id = self.file_selector.generate_client_id(file_info)
            file_info['client_id'] = client_id

            if not reprocess:
                # Check if already processed
                existing = self.db.get_client(client_id)
                if existing and existing.get('processing_metadata', {}).get('status') == 'success':
                    continue

            clients_to_process.append(file_info)

        if self.progress_callback:
            self.progress_callback({
                'phase': 'processing_start',
                'total_to_process': len(clients_to_process),
                'message': f'Processing {len(clients_to_process)} clients'
            })

        # Process each client
        for idx, file_info in enumerate(clients_to_process):
            try:
                self._process_client(file_info)
                self.stats['processed'] += 1

                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'processing',
                        'current': idx + 1,
                        'total': len(clients_to_process),
                        'client_name': file_info.get('client_name'),
                        'status': 'success',
                        'stats': self.stats.copy()
                    })

            except Exception as e:
                self.stats['failed'] += 1

                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'processing',
                        'current': idx + 1,
                        'total': len(clients_to_process),
                        'client_name': file_info.get('client_name'),
                        'status': 'error',
                        'error': str(e),
                        'stats': self.stats.copy()
                    })

        self.stats['end_time'] = datetime.now()

        if self.progress_callback:
            self.progress_callback({
                'phase': 'completed',
                'stats': self.stats.copy(),
                'message': 'Processing completed'
            })

    def _process_client(self, file_info: Dict[str, Any]):
        """
        Process a single client Excel file.

        Args:
            file_info: File information with client metadata
        """
        file_path = file_info['file_path']

        # Extract client data
        client_data = self.extractor.extract_client_data(file_path, file_info)

        # Save to database
        self.db.save_client(client_data)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()

        # Add database statistics
        db_stats = self.db.get_statistics()
        stats['database'] = db_stats

        # Calculate processing time
        if stats['start_time'] and stats['end_time']:
            duration = stats['end_time'] - stats['start_time']
            stats['duration_seconds'] = duration.total_seconds()
            stats['files_per_second'] = (
                stats['processed'] / duration.total_seconds()
                if duration.total_seconds() > 0 else 0
            )

        return stats

    def close(self):
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """
    Command-line interface for client processing.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Process Excel files and generate client JSON documents'
    )
    parser.add_argument(
        'output_folder',
        help='Folder containing downloaded Excel files'
    )
    parser.add_argument(
        '--db',
        default='client_data.db',
        help='SQLite database path (default: client_data.db)'
    )
    parser.add_argument(
        '--reprocess',
        action='store_true',
        help='Reprocess files that have already been processed'
    )

    args = parser.parse_args()

    def progress_callback(info):
        """Print progress updates."""
        phase = info.get('phase')

        if phase == 'discovery':
            print(f"\n📂 {info['message']}")

        elif phase == 'discovery_complete':
            print(f"✅ {info['message']}")

        elif phase == 'processing_start':
            print(f"\n🔄 {info['message']}")

        elif phase == 'processing':
            current = info['current']
            total = info['total']
            client_name = info['client_name']
            status = info['status']

            status_icon = '✅' if status == 'success' else '❌'
            print(f"{status_icon} [{current}/{total}] {client_name}")

            if status == 'error':
                print(f"   Error: {info.get('error')}")

        elif phase == 'completed':
            stats = info['stats']
            print(f"\n✨ Processing completed!")
            print(f"   Selected: {stats['selected_files']}")
            print(f"   Processed: {stats['processed']}")
            print(f"   Failed: {stats['failed']}")

            if stats['end_time'] and stats['start_time']:
                duration = stats['end_time'] - stats['start_time']
                print(f"   Duration: {duration}")

    # Run processor
    with ClientProcessor(
        output_folder=args.output_folder,
        db_path=args.db,
        progress_callback=progress_callback
    ) as processor:
        processor.process_all(reprocess=args.reprocess)

        # Print final statistics
        final_stats = processor.get_statistics()
        print("\n" + "="*60)
        print("DATABASE STATISTICS")
        print("="*60)

        db_stats = final_stats.get('database', {})
        print(f"Total clients: {db_stats.get('total_clients', 0)}")
        print(f"Processed: {db_stats.get('processed_clients', 0)}")
        print(f"Pending: {db_stats.get('pending_clients', 0)}")
        print(f"Failed: {db_stats.get('failed_clients', 0)}")
        print(f"Countries: {db_stats.get('countries', 0)}")
        print(f"Products: {db_stats.get('products', 0)}")
        print(f"Unique patterns: {db_stats.get('unique_patterns', 0)}")


if __name__ == '__main__':
    main()
