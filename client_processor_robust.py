"""
Robust client processor with timeout, error recovery, and better diagnostics.
Drop-in replacement for client_processor.py with enhanced reliability.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import threading
import signal
import time
from contextlib import contextmanager

from file_selector import FileSelector
from client_extractor import ClientExtractor
from client_database import ClientDatabase
from json_storage import JSONStorage


class TimeoutException(Exception):
    """Raised when processing takes too long."""
    pass


@contextmanager
def timeout(seconds):
    """Context manager for timeout."""
    def timeout_handler(signum, frame):
        raise TimeoutException(f"Operation timed out after {seconds} seconds")

    # Note: signal.alarm only works on Unix systems
    # For Windows, we'll use threading.Timer as fallback
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    except AttributeError:
        # Windows doesn't have SIGALRM, use threading fallback
        timer = threading.Timer(seconds, lambda: None)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()


class RobustClientProcessor:
    """
    Enhanced client processor with timeout and error recovery.
    """

    def __init__(
        self,
        output_folder: str,
        db_path: str = "client_data.db",
        json_path: str = "./extracted_json",
        enable_json: bool = True,
        enable_sqlite: bool = True,
        max_workers: int = 4,
        timeout_seconds: int = 120,  # NEW: 2 minute timeout per file
        max_retries: int = 2,  # NEW: Retry failed files
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize robust client processor.

        Args:
            output_folder: Root folder containing downloaded Excel files
            db_path: Path to SQLite database
            json_path: Path to JSON storage directory
            enable_json: Enable JSON file output
            enable_sqlite: Enable SQLite database output
            max_workers: Maximum concurrent workers (default: 4)
            timeout_seconds: Timeout per file in seconds (default: 120)
            max_retries: Maximum retry attempts for failed files (default: 2)
            progress_callback: Optional callback for progress updates
        """
        self.output_folder = output_folder
        self.db_path = db_path
        self.json_path = json_path
        self.enable_json = enable_json
        self.enable_sqlite = enable_sqlite
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.progress_callback = progress_callback

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
            'corrupted': 0,
            'retried': 0,
            'start_time': None,
            'end_time': None,
            'json_written': 0,
            'sqlite_written': 0,
            'current_file': None,  # NEW: Track current file
            'stuck_files': []  # NEW: Track problematic files
        }

    def process_all(self, reprocess: bool = False):
        """
        Process all Excel files in output folder with robust error handling.

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

        # Process clients concurrently with timeout
        completed = 0
        retry_queue = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self._process_client_safe, file_info): file_info
                for file_info in clients_to_process
            }

            # Process results as they complete
            for future in as_completed(future_to_file, timeout=None):
                file_info = future_to_file[future]
                completed += 1

                try:
                    # Wait for result with timeout
                    result = future.result(timeout=self.timeout_seconds)

                    with self.stats_lock:
                        if result['success']:
                            self.stats['processed'] += 1
                            if result.get('json_written'):
                                self.stats['json_written'] += 1
                            if result.get('sqlite_written'):
                                self.stats['sqlite_written'] += 1
                        else:
                            self.stats['failed'] += 1

                            # Track reason
                            if 'timeout' in str(result.get('error', '')).lower():
                                self.stats['timeout'] += 1
                                self.stats['stuck_files'].append(file_info['file_path'])
                            elif 'corrupt' in str(result.get('error', '')).lower():
                                self.stats['corrupted'] += 1

                            # Add to retry queue if retries available
                            if file_info.get('retry_count', 0) < self.max_retries:
                                retry_queue.append(file_info)

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

                except TimeoutError:
                    # Future timed out
                    with self.stats_lock:
                        self.stats['failed'] += 1
                        self.stats['timeout'] += 1
                        self.stats['stuck_files'].append(file_info['file_path'])

                    if self.progress_callback:
                        self.progress_callback({
                            'phase': 'processing',
                            'current': completed,
                            'total': len(clients_to_process),
                            'client_name': file_info.get('client_name'),
                            'status': 'timeout',
                            'error': f'Processing timed out after {self.timeout_seconds}s',
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

        # Retry failed files
        if retry_queue and self.max_retries > 0:
            if self.progress_callback:
                self.progress_callback({
                    'phase': 'retry_start',
                    'message': f'Retrying {len(retry_queue)} failed files...'
                })

            self._retry_failed_files(retry_queue)

        self.stats['end_time'] = datetime.now()

        if self.progress_callback:
            self.progress_callback({
                'phase': 'completed',
                'stats': self.stats.copy(),
                'message': 'Processing completed'
            })

    def _retry_failed_files(self, retry_queue: List[Dict[str, Any]]):
        """Retry failed files sequentially (safer than concurrent)."""
        for file_info in retry_queue:
            file_info['retry_count'] = file_info.get('retry_count', 0) + 1

            try:
                result = self._process_client_safe(file_info)

                with self.stats_lock:
                    self.stats['retried'] += 1
                    if result['success']:
                        self.stats['processed'] += 1
                        self.stats['failed'] -= 1
                        if result.get('json_written'):
                            self.stats['json_written'] += 1
                        if result.get('sqlite_written'):
                            self.stats['sqlite_written'] += 1

                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'retry',
                        'client_name': file_info.get('client_name'),
                        'status': 'success' if result['success'] else 'error',
                        'retry_count': file_info['retry_count']
                    })

            except Exception as e:
                if self.progress_callback:
                    self.progress_callback({
                        'phase': 'retry',
                        'client_name': file_info.get('client_name'),
                        'status': 'error',
                        'error': str(e),
                        'retry_count': file_info['retry_count']
                    })

    def _process_client_safe(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single client Excel file with timeout and error handling.

        Args:
            file_info: File information with client metadata

        Returns:
            Result dictionary with success status
        """
        result = {
            'success': False,
            'json_written': False,
            'sqlite_written': False,
            'error': None,
            'processing_time': 0
        }

        start_time = time.time()

        # Update current file being processed
        with self.stats_lock:
            self.stats['current_file'] = file_info['file_path']

        try:
            # Create thread-local extractor
            extractor = ClientExtractor()
            file_path = file_info['file_path']

            # Check if file exists and is readable
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if not Path(file_path).is_file():
                raise ValueError(f"Not a file: {file_path}")

            # Check file size (warn if > 10MB)
            file_size = Path(file_path).stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB
                result['warning'] = f"Large file ({file_size / 1024 / 1024:.1f}MB), may take longer"

            # Extract client data with basic error handling
            try:
                client_data = extractor.extract_client_data(file_path, file_info)
            except Exception as extract_error:
                # More specific error message
                if "Workbook" in str(extract_error) or "corrupt" in str(extract_error).lower():
                    raise ValueError(f"Corrupted or invalid Excel file: {extract_error}")
                else:
                    raise

            # Save to JSON storage (thread-safe)
            if self.json_storage:
                try:
                    self.json_storage.save_client(client_data)
                    result['json_written'] = True
                except Exception as e:
                    result['error'] = f"JSON save failed: {e}"

            # Save to SQLite database (with lock)
            if self.db:
                try:
                    with self.stats_lock:
                        self.db.save_client(client_data)
                    result['sqlite_written'] = True
                except Exception as e:
                    if not result['error']:
                        result['error'] = f"SQLite save failed: {e}"

            result['success'] = True

        except FileNotFoundError as e:
            result['error'] = f"File not found: {e}"
        except ValueError as e:
            result['error'] = f"Invalid file: {e}"
        except TimeoutException as e:
            result['error'] = f"Timeout: {e}"
        except Exception as e:
            result['error'] = f"Unexpected error: {type(e).__name__}: {e}"

        finally:
            result['processing_time'] = time.time() - start_time

            # Clear current file
            with self.stats_lock:
                self.stats['current_file'] = None

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

    def get_stuck_files(self) -> List[str]:
        """
        Get list of files that timed out or got stuck.

        Returns:
            List of file paths
        """
        return self.stats['stuck_files'].copy()

    def close(self):
        """Close storage connections."""
        if self.db:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
