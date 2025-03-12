FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (kubectl, helm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    apt-transport-https \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Helm
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create necessary directories
RUN mkdir -p logs uploaded_kubeconfigs

# Generate self-signed SSL certificates if they don't exist
RUN if [ ! -f cert.pem ] || [ ! -f key.pem ]; then \
    apt-get update && apt-get install -y openssl && \
    openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost" && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "-m", "app.main"]
