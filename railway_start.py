#!/usr/bin/env python3
"""
Railway startup script - handles PORT environment variable
"""
import os
import sys
import subprocess

# Get PORT from environment, default to 8080
port = os.getenv('PORT', '8080')

print(f"🚀 Starting uvicorn on port {port}...")

# Start uvicorn with the port
cmd = [
    'uvicorn',
    'main:app',
    '--host', '0.0.0.0',
    '--port', port,
    '--log-level', 'info'
]

# Execute uvicorn
sys.exit(subprocess.call(cmd))
