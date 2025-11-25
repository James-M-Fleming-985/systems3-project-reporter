# Systems³ Project Reporter - Production Dockerfile with Playwright
FROM python:3.12-slim

# Install system dependencies required by Playwright
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (--with-deps installs both browser and system dependencies)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /data/projects

# Expose port (Railway will override with $PORT)
EXPOSE 8080

# Start command - use shell form to allow variable expansion
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info"]
