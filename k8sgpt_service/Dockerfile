FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (kubectl, k8sgpt)
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

# Install k8sgpt
RUN curl -LO "https://github.com/k8sgpt-ai/k8sgpt/releases/download/v0.3.8/k8sgpt_Linux_x86_64.tar.gz" \
    && tar -xzf k8sgpt_Linux_x86_64.tar.gz \
    && chmod +x k8sgpt \
    && mv k8sgpt /usr/local/bin/ \
    && rm k8sgpt_Linux_x86_64.tar.gz

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create necessary directories
RUN mkdir -p logs analysis_results

# Generate self-signed SSL certificates if they don't exist
RUN if [ ! -f cert.pem ] || [ ! -f key.pem ]; then \
    apt-get update && apt-get install -y openssl && \
    openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost" && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Expose port
EXPOSE 8002

# Run the application
CMD ["python", "-m", "app.main"]
