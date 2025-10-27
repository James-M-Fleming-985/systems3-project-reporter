"""Utility functions for ZnNi Line Report Generator."""
import logging
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Set up application logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("ZnNiReportGenerator")


def load_config(config_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def ensure_output_directory(base_dir: str = "output") -> Path:
    """Ensure output directory exists."""
    output_path = Path(base_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def generate_output_filename(prefix: str, extension: str, timestamp_format: str = "%Y%m%d_%H%M%S") -> str:
    """Generate output filename with timestamp."""
    timestamp = datetime.now().strftime(timestamp_format)
    return f"{prefix}_{timestamp}.{extension}"


def validate_input_files(file_paths: list) -> list:
    """Validate that input files exist."""
    valid_files = []
    for file_path in file_paths:
        path = Path(file_path)
        if path.exists() and path.is_file():
            valid_files.append(str(path))
        else:
            raise FileNotFoundError(f"Input file not found: {file_path}")
    return valid_files


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"