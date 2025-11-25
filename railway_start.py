#!/usr/bin/env python3
"""
Railway startup script - handles PORT environment variable
"""
import os
import uvicorn

# Get PORT from environment, default to 8080
port = int(os.getenv("PORT", "8080"))

print(f"🚀 Starting uvicorn on port {port}...")

# Start uvicorn directly
uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
