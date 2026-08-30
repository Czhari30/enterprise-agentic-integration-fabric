FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY enterprise_fabric ./enterprise_fabric
RUN python -m pip install --prefix=/install .

FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FABRIC_DB_PATH=/data/fabric.db \
    PORT=8080

RUN groupadd --system --gid 10001 fabric \
    && useradd --system --uid 10001 --gid fabric --home-dir /app fabric \
    && mkdir -p /app /data \
    && chown -R fabric:fabric /app /data

WORKDIR /app
COPY --from=builder /install /usr/local
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"

CMD ["opentelemetry-instrument", "uvicorn", "enterprise_fabric.api:app", "--host", "0.0.0.0", "--port", "8080"]
