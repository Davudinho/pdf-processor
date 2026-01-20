# PDF-Intelligenz-System

Ein produktionsreifes System zur Verarbeitung von PDFs, Extraktion von Text (inkl. OCR) und Strukturierung mittels AI.

## Features
- 📄 **PDF Verarbeitung**: Extrahiert Text aus nativen und gescannten PDFs (via Tesseract OCR).
- 💾 **Persistenz**: Speichert Dokumente und Metadaten in MongoDB.
- 🧠 **AI Strukturierung**: Nutzt OpenAI GPT-3.5, um unstrukturierten Text in JSON zu verwandeln.
- 🌐 **Web Interface**: Einfaches UI zum Hochladen und Verwalten von Dokumenten.

## Voraussetzungen
- Python 3.9+
- MongoDB (lokal oder remote)
- Tesseract OCR installiert (und im Pfad verfügbar)

## Installation

1. **Repository klonen**
   \`\`\`bash
   git clone <repo-url>
   cd pdf-processor
   \`\`\`

2. **Dependencies installieren**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

3. **Umgebungsvariablen konfigurieren**
   Kopiere `.env.example` zu `.env` und trage deine API-Keys ein:
   \`\`\`bash
   cp .env.example .env
   # Editiere .env mit deinem Editor
   \`\`\`
   Stelle sicher, dass `OPENAI_API_KEY` gesetzt ist.

4. **Tesseract installieren**
   - **Windows**: [Installer herunterladen](https://github.com/UB-Mannheim/tesseract/wiki) und Pfad zu den Systemvariablen hinzufügen.
   - **Linux**: \`sudo apt-get install tesseract-ocr\`
   - **macOS**: \`brew install tesseract\`

5. **Datenbank starten**
   Falls du Docker verwendest:
   \`\`\`bash
   docker run -d -p 27017:27017 --name mongodb mongo
   \`\`\`

## Starten der Anwendung

\`\`\`bash
python app.py
\`\`\`
Die App ist nun unter `http://localhost:5000` erreichbar.

## API Endpoints

- \`GET /\`: Upload Interface
- \`POST /upload\`: Upload form-data `file=@beispiel.pdf`
- \`GET /document/<doc_id>\`: JSON-Details eines Dokuments
- \`DELETE /document/<doc_id>\`: Löscht ein Dokument

## Projektstruktur
\`\`\`
pdf-processor/
├── app.py           # Flask Server
├── pdf_processor.py # Logic für PDF & OCR
├── ai_processor.py  # Logic für OpenAI
├── database.py      # Logic für MongoDB
└── templates/       # HTML Frontend
\`\`\`
