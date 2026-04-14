FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY images/ ./images/

# Cria diretórios de persistência (history e models)
RUN mkdir -p /app/backend/history /app/backend/models

ENV PYTHONPATH=/app
ENV PORT=8002

EXPOSE 8002

# Usa $PORT para compatibilidade com Railway (que injeta PORT dinamicamente)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
