# STAGE 1: Build Frontend
FROM node:20-slim as frontend-builder
ENV NEXT_TELEMETRY_DISABLED 1
ENV NODE_OPTIONS=--max-old-space-size=4096
WORKDIR /app/web
COPY webapp/web/package*.json ./
RUN npm install
COPY webapp/web ./
# Standard build (no export) - creates .next/standalone
RUN npm run build

# STAGE 2: Build Backend
FROM python:3.11-slim as builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# STAGE 3: Final Production Image
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app
ENV PATH=/root/.local/bin:$PATH

# Install Node.js (required for Next.js standalone)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# WeasyPrint dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy the whole repo (backend)
COPY . .

# Copy built frontend from Stage 1
# Next.js standalone folder includes its own node_modules
COPY --from=frontend-builder /app/web/.next/standalone /app/webapp/web/standalone
COPY --from=frontend-builder /app/web/.next/static /app/webapp/web/standalone/webapp/web/.next/static
COPY --from=frontend-builder /app/web/public /app/webapp/web/standalone/webapp/web/public

# Writable dirs
RUN mkdir -p memory .tmp/evidence webapp/data/screenshots

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
