FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend backend
COPY data data

ENV PYTHONPATH=/app/backend \
    CATALOG_PATH=/app/data/catalog.json \
    PROXY_BASE_URL= \
    RESOLVER_PORT=5055

EXPOSE 5055

CMD ["python", "backend/resolver/api.py"]
