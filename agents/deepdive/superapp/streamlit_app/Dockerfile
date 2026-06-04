# Cloud Run container for the SuperApp export API (Google Sheets + Docs push,
# Airtable store-locations endpoint). Listens on $PORT (injected by Cloud Run).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXPORT_API_HOST=0.0.0.0

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Application code + geocache (locations endpoint).
COPY gdrive_utils.py export_api.py locations_geocache.json ./

# Cloud Run sets $PORT (default 8080); export_api.py honors it.
EXPOSE 8080
CMD ["python", "export_api.py"]
