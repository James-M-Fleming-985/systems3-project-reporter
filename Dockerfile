# Use official Playwright Python image with browsers preinstalled
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make startup script executable
RUN chmod +x run.py

# Create data directory for Railway persistent volume
RUN mkdir -p /data/projects

# Expose port
EXPOSE 8080

# Use Python script to handle PORT variable properly
CMD ["python3", "run.py"]
