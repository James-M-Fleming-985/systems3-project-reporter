#!/bin/bash
# Railway startup script with Playwright browser installation

echo "🚀 Starting Systems³ Project Reporter..."

# Set Playwright to use persistent volume for browsers
export PLAYWRIGHT_BROWSERS_PATH=/data/playwright-browsers

# Create directory if it doesn't exist
mkdir -p $PLAYWRIGHT_BROWSERS_PATH

# Install Playwright browsers if not already present
if [ ! -d "$PLAYWRIGHT_BROWSERS_PATH/chromium-1194" ]; then
    echo "📦 Installing Playwright browsers to $PLAYWRIGHT_BROWSERS_PATH (first run)..."
    python -m playwright install chromium
    echo "✅ Playwright browsers installed"
else
    echo "✅ Playwright browsers already installed at $PLAYWRIGHT_BROWSERS_PATH"
fi

# Start the application
echo "🎬 Starting uvicorn on port $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info
