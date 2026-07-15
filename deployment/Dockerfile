# syntax=docker/dockerfile:1

FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/src ./src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -e "."

# Ensure output directory exists and is writable
RUN mkdir -p /data/outputs && chmod 777 /data/outputs

EXPOSE 8000

CMD ["uvicorn", "trend_scout_enterprise.main:app", "--host", "0.0.0.0", "--port", "8000"]
