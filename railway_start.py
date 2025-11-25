#!/usr/bin/env python3
"""
Railway startup script - handles PORT environment variable
"""
import os
import sys
import uvicorn

print("=" * 60)
print("🚀 RAILWAY STARTUP SCRIPT")
print("=" * 60)

# Debug: Print all environment variables
print("\n📋 Environment Variables:")
for key, value in sorted(os.environ.items()):
    if key in ['PORT', 'RAILWAY_ENVIRONMENT', 'RAILWAY_SERVICE_NAME', 'PATH']:
        print(f"  {key} = {value}")

# Get PORT from environment
port_str = os.getenv("PORT", "8080")
print(f"\n🔍 PORT environment variable: '{port_str}' (type: {type(port_str).__name__})")

try:
    port = int(port_str)
    print(f"✅ PORT converted to integer: {port}")
except ValueError as e:
    print(f"❌ ERROR: Cannot convert PORT to integer: {e}")
    print(f"   PORT value was: '{port_str}'")
    sys.exit(1)

print(f"\n🎬 Starting uvicorn on host 0.0.0.0, port {port}")
print("=" * 60)

# Start uvicorn directly
uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
