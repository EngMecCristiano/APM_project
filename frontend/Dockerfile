FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Contexto é a raiz do projeto → copiar do path correto
COPY frontend/requirements.txt ./requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY frontend/ ./frontend/
COPY images/ ./images/

ENV PYTHONPATH=/app

EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--theme.primaryColor=#00d4ff", \
     "--theme.backgroundColor=#01050A", \
     "--theme.secondaryBackgroundColor=#071A2B", \
     "--theme.textColor=#DEF7FF"]
