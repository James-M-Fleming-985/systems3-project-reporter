#!/bin/bash
# Railway startup script with Playwright browser installation

echo "🚀 Starting Systems³ Project Reporter..."

# Install Playwright browsers if not already present
if [ ! -d "/root/.cache/ms-playwright/chromium_headless_shell-1194" ]; then
    echo "📦 Installing Playwright browsers (first run)..."
    python -m playwright install chromium --with-deps
    echo "✅ Playwright browsers installed"
else
    echo "✅ Playwright browsers already installed"
fi

# Start the application
echo "🎬 Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info
