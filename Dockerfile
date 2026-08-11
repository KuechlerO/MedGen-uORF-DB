# MedGen uORF Explorer — single container (Vite build + FastAPI)
# Behind nginx at e.g. /uorf-explorer/ (path stripped by proxy_pass …/)

ARG NODE_IMAGE=node:20-bookworm-slim
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ---- frontend ----
FROM ${NODE_IMAGE} AS frontend
WORKDIR /frontend

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY} no_proxy=${NO_PROXY}

ARG VITE_BASE_PATH=/uorf-explorer/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM ${PYTHON_IMAGE}
WORKDIR /app

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV HTTP_PROXY=${HTTP_PROXY} HTTPS_PROXY=${HTTPS_PROXY} NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY} no_proxy=${NO_PROXY} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUBLIC_BASE_PATH=/uorf-explorer \
    PORT=8000

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY ingest/ /app/ingest/
COPY --from=frontend /frontend/dist /app/frontend/dist

# data/ is mounted at runtime (catalog, tracks, reference_genome)
RUN mkdir -p /app/data

EXPOSE 8000

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
