FROM python:3.10-slim

WORKDIR /app

# Install curl and other dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY AlertAnalyticsServer.py .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=1h --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f https://localhost:8000/alerts -k || curl -f http://localhost:8000/alerts || exit 1

# Run the application
CMD ["python", "AlertAnalyticsServer.py"]