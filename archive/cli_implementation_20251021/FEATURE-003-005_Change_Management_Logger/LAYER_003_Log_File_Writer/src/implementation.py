import os
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class LogFileWriter:
    """Thread-safe log file writer with JSON support and rotation capabilities."""
    
    def __init__(self, log_dir: str = "logs", max_file_size: int = 10485760,
                 log_format: str = "json", buffer_size: int = 100):
        """
        Initialize LogFileWriter.
        
        Args:
            log_dir: Directory to store log files
            max_file_size: Maximum file size in bytes before rotation (default: 10MB)
            log_format: Log format ("json" or "text")
            buffer_size: Number of entries to buffer before writing
        """
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.log_format = log_format
        self.buffer_size = buffer_size
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize state
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._current_file: Optional[Path] = None
        self._file_handle: Optional[Any] = None
        self._is_closed = False
        
        # Initialize first log file
        self._rotate_file()
    
    def write(self, log_entry: Dict[str, Any]) -> None:
        """
        Write a log entry.
        
        Args:
            log_entry: Dictionary containing log data
            
        Raises:
            ValueError: If log_entry is invalid
            RuntimeError: If writer is closed
        """
        if self._is_closed:
            raise RuntimeError("LogFileWriter is closed")
            
        if not isinstance(log_entry, dict):
            raise ValueError("Log entry must be a dictionary")
            
        # Add timestamp if not present
        if 'timestamp' not in log_entry:
            log_entry['timestamp'] = datetime.now().isoformat()
            
        with self._lock:
            self._buffer.append(log_entry)
            
            # Flush if buffer is full
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
    
    def write_batch(self, log_entries: List[Dict[str, Any]]) -> None:
        """
        Write multiple log entries at once.
        
        Args:
            log_entries: List of log entries
            
        Raises:
            ValueError: If log_entries is invalid
            RuntimeError: If writer is closed
        """
        if self._is_closed:
            raise RuntimeError("LogFileWriter is closed")
            
        if not isinstance(log_entries, list):
            raise ValueError("Log entries must be a list")
            
        for entry in log_entries:
            if not isinstance(entry, dict):
                raise ValueError("Each log entry must be a dictionary")
            # Add timestamp if not present
            if 'timestamp' not in entry:
                entry['timestamp'] = datetime.now().isoformat()
        
        with self._lock:
            self._buffer.extend(log_entries)
            
            # Flush if buffer is full
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
    
    def flush(self) -> None:
        """Flush buffered entries to disk."""
        with self._lock:
            self._flush_buffer()
    
    def close(self) -> None:
        """Close the log file writer and flush remaining entries."""
        with self._lock:
            if not self._is_closed:
                self._flush_buffer()
                if self._file_handle:
                    self._file_handle.close()
                    self._file_handle = None
                self._is_closed = True
    
    def get_log_files(self) -> List[str]:
        """
        Get list of log files in the log directory.
        
        Returns:
            List of log file paths
        """
        files = []
        for file in sorted(self.log_dir.glob("*.log")):
            files.append(str(file))
        return files
    
    def rotate(self) -> None:
        """Force rotation to a new log file."""
        with self._lock:
            self._flush_buffer()
            self._rotate_file()
    
    def _flush_buffer(self) -> None:
        """Flush buffer to disk (must be called with lock held)."""
        if not self._buffer:
            return
            
        # Check if rotation is needed
        if self._current_file and self._current_file.exists():
            if self._current_file.stat().st_size >= self.max_file_size:
                self._rotate_file()
        
        # Write entries
        if self.log_format == "json":
            for entry in self._buffer:
                json_line = json.dumps(entry) + "\n"
                self._file_handle.write(json_line)
        else:  # text format
            for entry in self._buffer:
                text_line = f"{entry.get('timestamp', '')} - "
                text_line += f"{entry.get('level', 'INFO')} - "
                text_line += f"{entry.get('message', '')}\n"
                self._file_handle.write(text_line)
        
        self._file_handle.flush()
        self._buffer.clear()
    
    def _rotate_file(self) -> None:
        """Rotate to a new log file (must be called with lock held)."""
        # Close current file if open
        if self._file_handle:
            self._file_handle.close()
        
        # Generate new filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"log_{timestamp}.log"
        self._current_file = self.log_dir / filename
        
        # Open new file
        self._file_handle = open(self._current_file, 'w', encoding='utf-8')
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            self.close()
        except:
            pass
