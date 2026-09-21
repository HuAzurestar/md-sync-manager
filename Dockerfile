FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SMMD_HOST=0.0.0.0 \
    SMMD_PORT=8000 \
    SMMD_CONFIG=/data/sync.yaml \
    SMMD_LOG_DIR=/data/logs

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt \
    && addgroup --system --gid 10001 smmd \
    && adduser --system --uid 10001 --ingroup smmd --no-create-home smmd \
    && mkdir -p /data \
    && chown smmd:smmd /data

COPY --chown=smmd:smmd src ./src

USER smmd
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"]

CMD ["python", "-m", "src.controller.server"]
