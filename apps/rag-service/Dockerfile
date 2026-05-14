# Build context: repository root
#   docker build -f apps/rag-service/Dockerfile -t <tag> .

FROM python:3.11-slim

WORKDIR /app

# Install shared-observability from monorepo before other deps
COPY packages/shared-observability /tmp/shared-observability
RUN pip install --no-cache-dir /tmp/shared-observability && \
    rm -rf /tmp/shared-observability

# Install Python dependencies
COPY apps/rag-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source and bundled knowledge base
COPY apps/rag-service/app.py .
COPY apps/rag-service/knowledge-base ./knowledge-base

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
