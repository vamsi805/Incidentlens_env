FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "fastapi>=0.100.0" "uvicorn[standard]>=0.20.0" "pydantic>=2.0.0" "openenv-core>=0.2.0"

COPY . /app/incidentlens_env/

RUN pip install --no-cache-dir -e /app/incidentlens_env/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "incidentlens_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
