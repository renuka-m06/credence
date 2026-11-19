# Stage 1: Build production React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.12-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install minimal OS dependencies for network health checks and SQLite WAL
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root system user for security
RUN groupadd -r credence && useradd -r -g credence -d /app -s /sbin/nologin credence

# Copy backend application, configurations, and baseline data
COPY credence/ /app/credence/
COPY config.py /app/
COPY data/ /app/data/

# Copy built frontend static bundle from stage 1
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Ensure persistent directories exist and are owned by non-root user
RUN mkdir -p /app/data /app/.cache /tmp/credence_uploads && \
    chown -R credence:credence /app /tmp/credence_uploads

USER credence

EXPOSE 8000

# Dynamic PORT binding for Docker, Cloud Run, Render, Railway, AWS ECS
CMD ["sh", "-c", "uvicorn credence.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
