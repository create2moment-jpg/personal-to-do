# Build:  docker compose -f deploy/docker-compose.yml build
# Code lives in /app; private data is a bind mount at /data (never baked in).
FROM node:22-bookworm-slim AS web
WORKDIR /app/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PPOS_LOCAL_DATA_DIR=/data PPOS_HOST=0.0.0.0 PPOS_PORT=8765
RUN useradd --create-home --uid 1000 ppos
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages/ packages/
COPY apps/api/ apps/api/
COPY migrations/ migrations/
COPY prompts/ prompts/
RUN pip install --no-cache-dir -e .
COPY --from=web /app/apps/web/dist apps/web/dist
USER ppos
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8765/api/health'); sys.exit(0)"
CMD ["ppos", "serve"]
