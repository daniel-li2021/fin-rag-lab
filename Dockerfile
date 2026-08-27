# Fin-RAG Lab — local Streamlit application
# Build:  docker build -t fin-rag-lab .
# Run:    docker run --rm --env-file .env -p 8501:8501 \
#            -v "$(pwd)/data/uploads:/app/data/uploads" \
#            -v "$(pwd)/index:/app/index" \
#            -v "$(pwd)/cache:/app/cache" \
#            fin-rag-lab
#
# Secrets (.env) are NOT copied into the image — pass them at runtime.

FROM python:3.11-slim-bookworm

WORKDIR /app

# Minimal build deps (wheels cover most packages; this helps edge cases)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code only (see .dockerignore — no .env, no local index secrets)
COPY src/ src/
COPY app/ app/
COPY scripts/ scripts/
COPY data/golden_set/ data/golden_set/
COPY .env.example .env.example

RUN mkdir -p data/uploads cache index \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
