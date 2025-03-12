FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create necessary directories
RUN mkdir -p logs

# Generate self-signed SSL certificates if they don't exist
RUN if [ ! -f cert.pem ] || [ ! -f key.pem ]; then \
    apt-get update && apt-get install -y openssl && \
    openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost" && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "app.main"]
