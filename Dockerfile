# DataWarp Production Container
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY pyproject.toml .
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy application code
COPY scripts/ scripts/
COPY config/ config/

# Create data directories
RUN mkdir -p data/exports data/logs data/state manifests/canonical

# Default command
CMD ["python", "-c", "print('DataWarp ready. Use docker-compose exec datawarp <command>')"]
