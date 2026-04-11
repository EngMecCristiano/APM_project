FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

# Contexto é a raiz do projeto → copiar do path correto
COPY backend/requirements.txt ./requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copia apenas o backend (imports relativos: backend.*)
COPY backend/ ./backend/
COPY images/ ./images/

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]
