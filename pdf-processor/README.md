# PDF-Intelligenz-System

Ein produktionsreifes System zur Verarbeitung von PDFs, Extraktion von Text (inkl. OCR) und Strukturierung mittels AI.

## Features
- 📄 **PDF Verarbeitung**: Extrahiert Text aus nativen und gescannten PDFs (via Tesseract OCR).
- 💾 **Persistenz**: Speichert Dokumente und Metadaten in MongoDB.
- 🧠 **AI Strukturierung**: 
  - Asynchrone Background-Verarbeitung für schnelle Response-Zeiten.
  - Aggregierte Dokumenten-Struktur (Sections, Tables, Key Fields) auf Basis aller Seiten.
  - Validierung und Fallback-Strategien für robuste Ergebnisse.
  - Unterstützt Deutsch und Englisch.
- 🌐 **Web Interface**: Modernes UI mit Drag & Drop, Status-Polling und strukturierter Ansicht.

## Voraussetzungen
- Python 3.9+
- MongoDB (lokal oder remote)
- Tesseract OCR installiert (und im Pfad verfügbar)
- OpenAI API Key

## Installation

1. **Repository klonen**
   ```bash
   git clone <repo-url>
   cd pdf-processor
   ```

2. **Dependencies installieren**
   ```bash
   pip install -r requirements.txt
   ```

3. **Umgebungsvariablen konfigurieren**
   Kopiere `.env.example` zu `.env` und trage deine API-Keys ein:
   ```bash
   cp .env.example .env
   # Editiere .env mit deinem Editor
   ```
   **Wichtig**: `OPENAI_API_KEY` ist erforderlich.

4. **Tesseract installieren**
   - **Windows**: [Installer herunterladen](https://github.com/UB-Mannheim/tesseract/wiki) und Pfad zu den Systemvariablen hinzufügen.
   - **Linux**: `sudo apt-get install tesseract-ocr`
   - **macOS**: `brew install tesseract`

5. **Datenbank starten**
   Falls du Docker verwendest:
   ```bash
   docker run -d -p 27017:27017 --name mongodb mongo
   ```

## Starten der Anwendung

```bash
python app.py
```
Die App ist nun unter `http://localhost:5000` erreichbar.

## API Endpoints

- `GET /`: Web Interface
- `POST /upload`: Upload PDF (form-data `file=@beispiel.pdf`) - returns Job ID immediately.
- `GET /documents`: Liste aller Dokumente.
- `GET /document/<doc_id>/status`: Status der AI-Verarbeitung.
- `GET /document/<doc_id>/structured`: **Neu**: Gibt die aggregierte, strukturierte JSON-Antwort für das gesamte Dokument zurück.
- `DELETE /document/<doc_id>`: Löscht ein Dokument und alle zugehörigen Daten.

## Projektstruktur
```
pdf-processor/
├── app.py           # Flask Server & Routes
├── pdf_processor.py # Logic für PDF & OCR
├── ai_processor.py  # Logic für OpenAI & Validation
├── database.py      # Logic für MongoDB & Aggregation
├── requirements.txt # Python Dependencies
├── .env.example     # Template für Config
└── templates/       # Modernes HTML/JS Frontend
```

## Security Hinweise
- API Keys niemals in Git committen (nutze `.env`).
- MongoDB sollte in Production mit Authentication laufen.
- HTTPS sollte für Production via WSGI (Gunicorn/Nginx) vorgeschaltet werden.
