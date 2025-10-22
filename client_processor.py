"""
Batch processor for client-centric Excel parsing.
Writes to both SQLite database and JSON files.
Supports concurrent processing for faster throughput.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from file_selector import FileSelector
from client_extractor import ClientExtractor
from client_database import ClientDatabase
from json_storage import JSONStorage


class TimeoutException(Exception):
    """Custom exception for timeout."""
    pass


def run_with_timeout(func, args=(), kwargs=None, timeout_duration=300):
    """
    Run a function with a timeout.

    Args:
        func: Function to run
        args: Positional arguments
        kwargs: Keyword arguments
        timeout_duration: Timeout in seconds

    Returns:
        Result from function or raises TimeoutException
    """
    if kwargs is None:
        kwargs = {}

    result = [TimeoutException(f"Function timed out after {timeout_duration}s")]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            result[0] = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_duration)

    if thread.is_alive():
        # Thread is still running - timeout occurred
        raise TimeoutException(f"Processing timed out after {timeout_duration}s")

    if isinstance(result[0], Exception):
        raise result[0]

    return result[0]


class ClientProcessor:
    """
    Process Excel files and generate client JSON documents.
    """

    def __init__(
        self,
        output_folder: str,
        db_path: str = "client_data.db",
        json_path: str = "./extracted_json",
        enable_json: bool = True,
        enable_sqlite: bool = True,
        max_workers: int = 4,
        progress_callback: Optional[Callable] = None,
        timeout_seconds: int = 300
    ):
        """
        Initialize client processor.

        Args:
            output_folder: Root folder containing downloaded Excel files
            db_path: Path to SQLite database
            json_path: Path to JSON storage directory
            enable_json: Enable JSON file output
            enable_sqlite: Enable SQLite database output
            max_workers: Maximum concurrent workers (default: 4)
            progress_callback: Optional callback for progress updates
            timeout_seconds: Timeout per file in seconds (default: 300 = 5 minutes)
        """
        self.output_folder = output_folder
        self.db_path = db_path
        self.json_path = json_path
        self.enable_json = enable_json
        self.enable_sqlite = enable_sqlite
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.timeout_seconds = timeout_seconds

        self.file_selector = FileSelector()

        # Initialize storage backends
        self.db = ClientDatabase(db_path) if enable_sqlite else None
        self.json_storage = JSONStorage(json_path) if enable_json else None

        # Thread safety
        self.stats_lock = threading.Lock()
        self.stats = {
            'total_files': 0,
            'selected_files': 0,
            'ignored_files': 0,
            'processed': 0,
            'failed': 0,
            'timeout': 0,
            'slow_files': 0,
            'start_time': None,
            'end_time': None,
            'json_written': 0,
            'sqlite_written': 0,
            'slow_file_list': [],
            'timeout_file_list': []
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
                # Check if already processed (prefer JSON storage if enabled)
                existing = None
                if self.json_storage:
                    existing = self.json_storage.get_client(client_id)
                elif self.db:
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

        # Process clients concurrently
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self._process_client_safe, file_info): file_info
                for file_info in clients_to_process
            }

            # Process results as they complete
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                completed += 1

                try:
                    # Get result (timeout is already enforced within the function)
                    result = future.result()

                    # Check if this was a timeout
                    if result.get('timed_out'):
                        with self.stats_lock:
                            self.stats['failed'] += 1
                            self.stats['timeout'] += 1
                            self.stats['timeout_file_list'].append(file_info.get('client_name'))

                        if self.progress_callback:
                            self.progress_callback({
                                'phase': 'processing',
                                'current': completed,
                                'total': len(clients_to_process),
                                'client_name': file_info.get('client_name'),
                                'status': 'timeout',
                                'error': result.get('error'),
                                'stats': self.stats.copy()
                            })
                        continue

                    # Check if file was slow (over 60 seconds but didn't timeout)
                    duration = result.get('duration_seconds', 0)
                    if duration > 60 and not result.get('timed_out'):
                        with self.stats_lock:
                            self.stats['slow_files'] += 1
                            self.stats['slow_file_list'].append({
                                'file': file_info.get('client_name'),
                                'duration': duration
                            })
                        print(f"⚠️  SLOW FILE WARNING: {file_info.get('client_name')} took {duration:.1f}s")

                    with self.stats_lock:
                        if result['success']:
                            self.stats['processed'] += 1
                            if result.get('json_written'):
                                self.stats['json_written'] += 1
                            if result.get('sqlite_written'):
                                self.stats['sqlite_written'] += 1
                        else:
                            self.stats['failed'] += 1

                    if self.progress_callback:
                        self.progress_callback({
                            'phase': 'processing',
                            'current': completed,
                            'total': len(clients_to_process),
                            'client_name': file_info.get('client_name'),
                            'status': 'success' if result['success'] else 'error',
                            'error': result.get('error'),
                            'stats': self.stats.copy()
                        })

                except Exception as e:
                    with self.stats_lock:
                        self.stats['failed'] += 1

                    if self.progress_callback:
                        self.progress_callback({
                            'phase': 'processing',
                            'current': completed,
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

    def _process_client_safe(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single client Excel file (thread-safe wrapper with timeout).

        Args:
            file_info: File information with client metadata

        Returns:
            Result dictionary with success status
        """
        try:
            return run_with_timeout(
                self._process_client_internal,
                args=(file_info,),
                timeout_duration=self.timeout_seconds
            )
        except TimeoutException as e:
            # File processing timed out
            label = file_info.get('client_name') or file_info.get('filename', 'unknown')
            print(f"⏱️  TIMEOUT: {label} exceeded {self.timeout_seconds}s limit")
            return {
                'success': False,
                'json_written': False,
                'sqlite_written': False,
                'error': str(e),
                'start_time': datetime.now(),
                'end_time': datetime.now(),
                'duration_seconds': self.timeout_seconds,
                'timed_out': True
            }

    def _process_client_internal(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method to process a single client Excel file.

        Args:
            file_info: File information with client metadata

        Returns:
            Result dictionary with success status
        """
        start_time = datetime.now()
        result = {
            'success': False,
            'json_written': False,
            'sqlite_written': False,
            'error': None,
            'start_time': start_time,
            'end_time': None,
            'duration_seconds': None,
            'timed_out': False
        }

        try:
            # Create thread-local extractor
            extractor = ClientExtractor()
            file_path = Path(file_info['file_path'])
            label = file_info.get('client_name') or file_info.get('filename') or file_path.name

            print(f"[{start_time.strftime('%H:%M:%S')}] START: {label}")

            # Extract client data
            extraction_start = datetime.now()
            client_data = extractor.extract_client_data(str(file_path), file_info)
            extraction_duration = (datetime.now() - extraction_start).total_seconds()
            print(f"  → Extraction completed in {extraction_duration:.2f}s")

            processing_metadata = client_data.get('processing_metadata', {})
            errors: List[str] = []
            extraction_success = processing_metadata.get('status') == 'success'

            if not extraction_success:
                extraction_error = processing_metadata.get('error') or 'Extraction failed without a specific error message'
                errors.append(f"Extraction failed for {label}: {extraction_error}")

            # Save to JSON storage (thread-safe)
            if extraction_success and self.json_storage:
                try:
                    json_start = datetime.now()
                    self.json_storage.save_client(client_data)
                    json_duration = (datetime.now() - json_start).total_seconds()
                    print(f"  → JSON save completed in {json_duration:.2f}s")
                    result['json_written'] = True
                except Exception as e:
                    errors.append(f"JSON save failed for {label}: {e}")
                    print(f"  ✗ JSON save failed: {e}")

            # Save to SQLite database (with lock)
            if extraction_success and self.db:
                try:
                    sqlite_start = datetime.now()
                    with self.stats_lock:
                        self.db.save_client(client_data)
                    sqlite_duration = (datetime.now() - sqlite_start).total_seconds()
                    print(f"  → SQLite save completed in {sqlite_duration:.2f}s")
                    result['sqlite_written'] = True
                except Exception as e:
                    errors.append(f"SQLite save failed for {label}: {e}")
                    print(f"  ✗ SQLite save failed: {e}")

            if errors:
                result['error'] = " | ".join(errors)
            else:
                result['success'] = True

        except Exception as e:
            result['error'] = f"Processing crashed for {file_info.get('filename') or file_info.get('file_path')}: {e}"
            print(f"  ✗ Processing crashed: {e}")

        finally:
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - start_time).total_seconds()
            print(f"[{result['end_time'].strftime('%H:%M:%S')}] END: {label} (Total: {result['duration_seconds']:.2f}s)")

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()

        # Add storage statistics
        if self.db:
            stats['sqlite'] = self.db.get_statistics()

        if self.json_storage:
            stats['json'] = self.json_storage.get_statistics()

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
        """Close storage connections."""
        if self.db:
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
        '--json',
        default='./extracted_json',
        help='JSON storage directory (default: ./extracted_json)'
    )
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Disable JSON file output'
    )
    parser.add_argument(
        '--no-sqlite',
        action='store_true',
        help='Disable SQLite database output'
    )
    parser.add_argument(
        '--reprocess',
        action='store_true',
        help='Reprocess files that have already been processed'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of concurrent workers (default: 4)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Timeout per file in seconds (default: 300 = 5 minutes)'
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
            print(f"   Timeout: {stats.get('timeout', 0)}")
            print(f"   Slow files (>60s): {stats.get('slow_files', 0)}")
            print(f"   JSON files written: {stats.get('json_written', 0)}")
            print(f"   SQLite records written: {stats.get('sqlite_written', 0)}")

            if stats['end_time'] and stats['start_time']:
                duration = stats['end_time'] - stats['start_time']
                print(f"   Duration: {duration}")

            # Show timeout files if any
            if stats.get('timeout_file_list'):
                print(f"\n⏱️  Files that timed out:")
                for filename in stats['timeout_file_list']:
                    print(f"   - {filename}")

            # Show slow files if any
            if stats.get('slow_file_list'):
                print(f"\n⚠️  Slow files (took >60s):")
                for item in stats['slow_file_list']:
                    print(f"   - {item['file']}: {item['duration']:.1f}s")

    # Run processor
    with ClientProcessor(
        output_folder=args.output_folder,
        db_path=args.db,
        json_path=args.json,
        enable_json=not args.no_json,
        enable_sqlite=not args.no_sqlite,
        max_workers=args.workers,
        progress_callback=progress_callback,
        timeout_seconds=args.timeout
    ) as processor:
        processor.process_all(reprocess=args.reprocess)

        # Print final statistics
        final_stats = processor.get_statistics()

        # Print JSON statistics if enabled
        if not args.no_json:
            print("\n" + "="*60)
            print("JSON STORAGE STATISTICS")
            print("="*60)

            json_stats = final_stats.get('json', {})
            print(f"Total clients: {json_stats.get('total_clients', 0)}")
            print(f"Countries: {json_stats.get('countries', 0)}")
            print(f"Products: {json_stats.get('products', 0)}")
            print(f"Unique patterns: {json_stats.get('unique_patterns', 0)}")
            print(f"Success: {json_stats.get('success_count', 0)}")
            print(f"Failed: {json_stats.get('failed_count', 0)}")

        # Print SQLite statistics if enabled
        if not args.no_sqlite:
            print("\n" + "="*60)
            print("SQLITE DATABASE STATISTICS")
            print("="*60)

            db_stats = final_stats.get('sqlite', {})
            print(f"Total clients: {db_stats.get('total_clients', 0)}")
            print(f"Processed: {db_stats.get('processed_clients', 0)}")
            print(f"Pending: {db_stats.get('pending_clients', 0)}")
            print(f"Failed: {db_stats.get('failed_clients', 0)}")
            print(f"Countries: {db_stats.get('countries', 0)}")
            print(f"Products: {db_stats.get('products', 0)}")
            print(f"Unique patterns: {db_stats.get('unique_patterns', 0)}")


if __name__ == '__main__':
    main()
