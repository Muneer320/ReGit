# syntax=docker/dockerfile:1.6
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM python-base AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python-base AS runtime
WORKDIR /app
RUN groupadd --gid 10001 regit && useradd --uid 10001 --gid 10001 --create-home regit && \
    mkdir /data && chown 10001:10001 /data
COPY --from=dependencies /app/.venv /app/.venv
COPY --from=frontend /frontend/dist /app/frontend/dist
COPY backend/ /app/backend/
COPY scripts/smoke_demo.py /app/scripts/smoke_demo.py
COPY LICENSE /app/LICENSE
ENV GR_API_DATA_DIR=/data GR_ENABLE_VECTORS=0
USER 10001:10001
EXPOSE 8377
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "backend.src.api.main:app", "--host", "0.0.0.0", "--port", "8377", "--workers", "1"]
