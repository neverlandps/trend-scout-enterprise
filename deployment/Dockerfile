FROM python:3.12-slim

WORKDIR /app

# WeasyPrint system dependencies (Debian 12 / Ubuntu 24.04 package names)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
COPY backend/src ./src
COPY README.md ./README.md

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "trend_scout_enterprise.main:app", "--host", "0.0.0.0", "--port", "8000"]
