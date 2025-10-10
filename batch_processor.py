"""
Batch processor for parsing downloaded Excel files.
Walks through output folder and processes all Excel files into the database.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import time
from datetime import datetime
from table_extractor import TableExtractor
from excel_database import ExcelDatabase


class BatchProcessor:
    """
    Process all Excel files in a folder structure and store in database.
    """

    def __init__(
        self,
        output_folder: str,
        db_path: str = "excel_data.db",
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize batch processor.

        Args:
            output_folder: Root folder containing downloaded Excel files
            db_path: Path to SQLite database
            progress_callback: Optional callback for progress updates
        """
        self.output_folder = Path(output_folder)
        self.db_path = db_path
        self.progress_callback = progress_callback

        self.extractor = TableExtractor()
        self.db = ExcelDatabase(db_path)

        # Statistics
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }

    def discover_files(self) -> list[Dict[str, Any]]:
        """
        Discover all Excel files in the output folder.

        Returns:
            List of file information dictionaries
        """
        excel_files = []

        if not self.output_folder.exists():
            raise ValueError(f"Output folder does not exist: {self.output_folder}")

        # Walk through all subdirectories
        for root, dirs, files in os.walk(self.output_folder):
            for filename in files:
                if filename.endswith(('.xlsx', '.xls')):
                    file_path = Path(root) / filename

                    # Calculate relative folder path from output folder
                    relative_folder = str(Path(root).relative_to(self.output_folder))

                    # Get file stats
                    file_stat = file_path.stat()

                    file_info = {
                        'filename': filename,
                        'file_path': str(file_path),
                        'relative_folder': relative_folder,
                        'file_size': file_stat.st_size,
                        'modified_date': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    }

                    excel_files.append(file_info)

        return excel_files

    def process_all(self, reprocess: bool = False):
        """
        Process all discovered Excel files.

        Args:
            reprocess: If True, reprocess files that have already been processed
        """
        self.stats['start_time'] = datetime.now()

        # Discover files
        files = self.discover_files()
        self.stats['total_files'] = len(files)

        if self.progress_callback:
            self.progress_callback({
                'phase': 'discovery',
                'total_files': len(files),
                'message': f"Discovered {len(files)} Excel files"
            })

        # Add files to database
        for file_info in files:
            try:
                file_id = self.db.add_file(file_info)
            except Exception as e:
                print(f"Error adding file {file_info['filename']}: {e}")

        self.db.conn.commit()

        # Get files to process
        if reprocess:
            # Get all files
            files_to_process = self.db.get_files_to_process(status='completed')
            files_to_process.extend(self.db.get_files_to_process(status='pending'))
            files_to_process.extend(self.db.get_files_to_process(status='failed'))
        else:
            # Only get pending files
            files_to_process = self.db.get_files_to_process(status='pending')

        if self.progress_callback:
            self.progress_callback({
                'phase': 'processing_start',
                'total_to_process': len(files_to_process),
                'message': f"Processing {len(files_to_process)} files"
            })

        # Process each file
        for idx, file_record in enumerate(files_to_process):
            try:
                self._process_file(file_record)
                self.stats['processed'] += 1

                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'processing',
                        'current': idx + 1,
                        'total': len(files_to_process),
                        'filename': file_record['filename'],
                        'status': 'success',
                        'stats': self.stats.copy()
                    })

            except Exception as e:
                self.stats['failed'] += 1

                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'processing',
                        'current': idx + 1,
                        'total': len(files_to_process),
                        'filename': file_record['filename'],
                        'status': 'error',
                        'error': str(e),
                        'stats': self.stats.copy()
                    })

                print(f"Error processing {file_record['filename']}: {e}")

        self.stats['end_time'] = datetime.now()

        if self.progress_callback:
            self.progress_callback({
                'phase': 'completed',
                'stats': self.stats.copy(),
                'message': "Processing completed"
            })

    def _process_file(self, file_record: Dict[str, Any]):
        """
        Process a single file.

        Args:
            file_record: File record from database
        """
        file_path = file_record['file_path']
        file_id = file_record['file_id']

        # Extract tables from file
        parsed_data = self.extractor.extract_tables_from_file(
            file_path=file_path,
            filename=file_record['filename']
        )

        # Save to database
        self.db.save_parsed_data(file_id, parsed_data)

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
    Command-line interface for batch processing.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Batch process Excel files and store in SQLite database'
    )
    parser.add_argument(
        'output_folder',
        help='Folder containing downloaded Excel files'
    )
    parser.add_argument(
        '--db',
        default='excel_data.db',
        help='SQLite database path (default: excel_data.db)'
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

        elif phase == 'processing_start':
            print(f"\n🔄 {info['message']}")

        elif phase == 'processing':
            current = info['current']
            total = info['total']
            filename = info['filename']
            status = info['status']

            status_icon = '✅' if status == 'success' else '❌'
            print(f"{status_icon} [{current}/{total}] {filename}")

            if status == 'error':
                print(f"   Error: {info.get('error')}")

        elif phase == 'completed':
            stats = info['stats']
            print(f"\n✨ Processing completed!")
            print(f"   Total: {stats['total_files']}")
            print(f"   Processed: {stats['processed']}")
            print(f"   Failed: {stats['failed']}")

            if stats['end_time'] and stats['start_time']:
                duration = stats['end_time'] - stats['start_time']
                print(f"   Duration: {duration}")

    # Run processor
    with BatchProcessor(
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
        print(f"Total files in DB: {db_stats.get('total_files', 0)}")
        print(f"Processed files: {db_stats.get('processed_files', 0)}")
        print(f"Pending files: {db_stats.get('pending_files', 0)}")
        print(f"Failed files: {db_stats.get('failed_files', 0)}")
        print(f"Total sheets: {db_stats.get('total_sheets', 0)}")
        print(f"Total tables: {db_stats.get('total_tables', 0)}")
        print(f"Unique patterns: {db_stats.get('unique_patterns', 0)}")
        print(f"Countries: {db_stats.get('countries', 0)}")
        print(f"Clients: {db_stats.get('clients', 0)}")


if __name__ == '__main__':
    main()
