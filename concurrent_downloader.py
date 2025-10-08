"""
Concurrent file downloader for SharePoint files.
Downloads files in parallel while search is ongoing.
"""

import queue
import threading
import time
from pathlib import Path
from typing import Dict, Optional
import re


class ConcurrentDownloader:
    """
    Downloads files concurrently while search is running.
    Thread-safe implementation for use with Streamlit.
    """

    def __init__(self, sp_client, output_folder: str, num_workers: int = 5):
        """
        Initialize concurrent downloader.

        Args:
            sp_client: SharePoint client instance
            output_folder: Base folder for downloads
            num_workers: Number of concurrent download threads
        """
        self.sp_client = sp_client
        self.output_folder = Path(output_folder)
        self.num_workers = num_workers

        # Thread-safe queue for files to download
        self.download_queue = queue.Queue()

        # Thread-safe counters
        self.lock = threading.Lock()
        self.downloaded_count = 0
        self.failed_count = 0
        self.total_queued = 0

        # Error tracking
        self.errors = []

        # Control flags
        self.stop_flag = threading.Event()
        self.workers = []
        self.started = False

    def start(self):
        """Start worker threads."""
        if self.started:
            return

        self.started = True
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # Start worker threads
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"Downloader-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

    def add_file(self, file_info: Dict):
        """
        Add a file to the download queue.

        Args:
            file_info: File dictionary with metadata
        """
        with self.lock:
            self.total_queued += 1

        self.download_queue.put(file_info)

    def _worker(self):
        """Worker thread that processes download queue."""
        while not self.stop_flag.is_set():
            try:
                # Get file from queue with timeout
                file_info = self.download_queue.get(timeout=1)

                try:
                    self._download_file(file_info)

                    with self.lock:
                        self.downloaded_count += 1

                except Exception as e:
                    with self.lock:
                        self.failed_count += 1
                        self.errors.append({
                            'filename': file_info.get('name', 'unknown'),
                            'error': str(e)
                        })

                finally:
                    self.download_queue.task_done()

            except queue.Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                # Unexpected error in worker
                print(f"Worker error: {e}")
                continue

    def _download_file(self, file_info: Dict):
        """
        Download a single file.

        Args:
            file_info: File dictionary with metadata
        """
        # Create folder structure to preserve hierarchy
        relative_folder = file_info.get('relative_folder', 'root')
        if relative_folder in ['(current)', '(root)', 'N/A']:
            relative_folder = 'root'

        # Sanitize folder path
        safe_folder = re.sub(r'[<>:"|?*]', '_', relative_folder)
        file_output_path = self.output_folder / safe_folder

        # Create subfolder
        file_output_path.mkdir(parents=True, exist_ok=True)

        # Download file from SharePoint
        file_content = self.sp_client.download_file(
            file_info['server_relative_url']
        )

        # Save file
        full_file_path = file_output_path / file_info['name']
        with open(full_file_path, 'wb') as f:
            f.write(file_content)

    def get_status(self) -> Dict:
        """
        Get current download status.

        Returns:
            Dictionary with status information
        """
        with self.lock:
            pending = self.total_queued - self.downloaded_count - self.failed_count
            return {
                'total_queued': self.total_queued,
                'downloaded': self.downloaded_count,
                'failed': self.failed_count,
                'pending': max(0, pending),
                'errors': self.errors.copy()
            }

    def wait_for_completion(self, timeout: Optional[float] = None):
        """
        Wait for all downloads to complete.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
        """
        self.download_queue.join()

    def stop(self):
        """Stop all worker threads."""
        self.stop_flag.set()

        # Wait for workers to finish current tasks
        for worker in self.workers:
            worker.join(timeout=5)

    def is_active(self) -> bool:
        """Check if downloader has pending work."""
        with self.lock:
            pending = self.total_queued - self.downloaded_count - self.failed_count
            return pending > 0 or not self.download_queue.empty()


class BatchDownloader:
    """
    Downloads files in batches during search.
    Simpler alternative to thread-based approach.
    """

    def __init__(self, sp_client, output_folder: str, batch_size: int = 50):
        """
        Initialize batch downloader.

        Args:
            sp_client: SharePoint client instance
            output_folder: Base folder for downloads
            batch_size: Number of files to collect before downloading
        """
        self.sp_client = sp_client
        self.output_folder = Path(output_folder)
        self.batch_size = batch_size

        self.current_batch = []
        self.downloaded_count = 0
        self.failed_count = 0
        self.errors = []

        self.output_folder.mkdir(parents=True, exist_ok=True)

    def add_file(self, file_info: Dict):
        """
        Add file to current batch.

        Args:
            file_info: File dictionary with metadata
        """
        self.current_batch.append(file_info)

        # Download batch if full
        if len(self.current_batch) >= self.batch_size:
            self.download_batch()

    def download_batch(self):
        """Download all files in current batch."""
        if not self.current_batch:
            return

        for file_info in self.current_batch:
            try:
                self._download_file(file_info)
                self.downloaded_count += 1
            except Exception as e:
                self.failed_count += 1
                self.errors.append({
                    'filename': file_info.get('name', 'unknown'),
                    'error': str(e)
                })

        # Clear batch
        self.current_batch = []

    def _download_file(self, file_info: Dict):
        """Download a single file."""
        # Create folder structure
        relative_folder = file_info.get('relative_folder', 'root')
        if relative_folder in ['(current)', '(root)', 'N/A']:
            relative_folder = 'root'

        safe_folder = re.sub(r'[<>:"|?*]', '_', relative_folder)
        file_output_path = self.output_folder / safe_folder
        file_output_path.mkdir(parents=True, exist_ok=True)

        # Download and save
        file_content = self.sp_client.download_file(
            file_info['server_relative_url']
        )

        full_file_path = file_output_path / file_info['name']
        with open(full_file_path, 'wb') as f:
            f.write(file_content)

    def finalize(self):
        """Download any remaining files in batch."""
        self.download_batch()

    def get_status(self) -> Dict:
        """Get download status."""
        return {
            'downloaded': self.downloaded_count,
            'failed': self.failed_count,
            'pending': len(self.current_batch),
            'errors': self.errors.copy()
        }
