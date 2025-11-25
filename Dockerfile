# Use official Playwright Python image with browsers preinstalled
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for Railway persistent volume
RUN mkdir -p /data/projects

# Expose port
EXPOSE 8080

# Use shell form to allow environment variable expansion
CMD ["/bin/bash", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info"]
