FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data \
    VECTOR_BACKEND=chroma \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

RUN groupadd --system copilot && useradd --system --gid copilot --create-home copilot

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
RUN mkdir -p /app/data/uploads /app/data/chroma /app/data/evaluations \
    /app/storage/uploads /app/storage/chroma \
    && chown -R copilot:copilot /app

USER copilot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)); raise SystemExit(0 if data.get('status') in ('healthy','degraded') else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
