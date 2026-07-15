# syntax=docker/dockerfile:1

FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10 \
    PIP_TIMEOUT=120

WORKDIR /app

# Install native libraries required by WeasyPrint and psycopg2.
RUN set -eux \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        shared-mime-info \
        libpq-dev \
        gcc \
        python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Copy only the files needed to install the package first so Docker caches the layer.
COPY backend/pyproject.toml ./
COPY backend/README.md ./
COPY backend/src ./src

RUN set -eux \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir --retries 10 --timeout 120 -e "."

# Ensure output directory exists and is writable
RUN mkdir -p /data/outputs && chmod 777 /data/outputs

EXPOSE 8000

CMD ["uvicorn", "trend_scout_enterprise.main:app", "--host", "0.0.0.0", "--port", "8000"]
