#!/usr/bin/env python3
"""Fix response status checks in generate_report.py"""

import re

# Read the file
with open('generate_report.py', 'r') as f:
    content = f.read()

# Add import for ResponseStatus (after the existing imports)
import_pattern = r'(from src\.utils import setup_logging, load_config, ensure_directory)'
import_replacement = r'\1\nfrom enum import Enum\n\n# Import ResponseStatus from a feature (they all use the same enum)\ntry:\n    from FEATURE_003_001_Data_Reader_Parser.src.feature_integration import ResponseStatus\nexcept ImportError:\n    # Fallback definition\n    class ResponseStatus(Enum):\n        SUCCESS = "success"\n        ERROR = "error"\n        WARNING = "warning"\n        PARTIAL_SUCCESS = "partial_success"'

content = re.sub(import_pattern, import_replacement, content)

# Fix all .is_success() calls
# Pattern 1: response.status.is_success() -> response.status == ResponseStatus.SUCCESS
content = re.sub(
    r'(\w+)\.status\.is_success\(\)',
    r'\1.status == ResponseStatus.SUCCESS',
    content
)

# Pattern 2: response.is_success() -> response.status == ResponseStatus.SUCCESS  
content = re.sub(
    r'(\w+)\.is_success\(\)',
    r'\1.status == ResponseStatus.SUCCESS',
    content
)

# Fix .message attribute (enum doesn't have message, use .value)
content = re.sub(
    r'\.status\.message',
    r'.status.value',
    content
)

# Write back
with open('generate_report.py', 'w') as f:
    f.write(content)

print("✅ Fixed all response status checks!")
