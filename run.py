"""
Simple startup wrapper for Railway
Reads PORT environment variable and starts uvicorn
"""
import os
import sys

# Get PORT from environment
port = os.environ.get('PORT', '8080')

# Validate it's a valid port number
try:
    port_int = int(port)
    if not (1 <= port_int <= 65535):
        print(f"ERROR: Invalid port number: {port}")
        sys.exit(1)
except ValueError:
    print(f"ERROR: PORT must be a number, got: {port}")
    sys.exit(1)

# Import and run uvicorn programmatically
import uvicorn

print(f"Starting uvicorn on 0.0.0.0:{port_int}")
uvicorn.run("main:app", host="0.0.0.0", port=port_int, log_level="info")
