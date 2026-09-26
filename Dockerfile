FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.122.0 \
    uvicorn>=0.38.0 \
    python-multipart>=0.0.20 \
    pandas>=2.3.0 \
    pyarrow>=22.0.0 \
    duckdb>=1.4.0 \
    httpx>=0.28.0

# Copy all project files (including pre-built app/frontend/out)
COPY . /app

# Expose port (Render/HuggingFace set $PORT or use 8000)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir /app/app/backend"]
