# ============================================================
# Dockerfile – PDF Intelligence System
# Basis: Python 3.11 slim (kleiner als das Full-Image)
# Startbefehl: gunicorn (Produktions-WSGI-Server)
# ============================================================

FROM python:3.11-slim

# Systempakete für OCR und PDF-Verarbeitung
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    ocrmypdf \
    ghostscript \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis im Container
WORKDIR /app

# Zuerst nur requirements kopieren (Docker Layer Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Rest des Projekts kopieren
COPY . .

# Uploads-Verzeichnis anlegen (falls nicht vorhanden)
RUN mkdir -p uploads

# Port auf dem die App lauscht
EXPOSE 5000

# Gunicorn starten: 4 Worker, bindet auf 0.0.0.0:5000
# $PORT wird von Render/Railway automatisch gesetzt (Fallback: 5000)
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:${PORT:-5000} --timeout 120 app:app"]
