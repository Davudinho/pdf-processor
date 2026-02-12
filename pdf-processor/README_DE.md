# PDF Intelligence System

*Deutsche Version | [English Version](README.md)*

Ein produktionsreifes System zur PDF-Verarbeitung mit KI-gestützter Textextraktion, Strukturierung und Stichwortsuche.

---

## 🏗️ Systemarchitektur

### Überblick

```
┌─────────────────────────────────────────────────────────────┐
│                   Weboberfläche (Flask)                      │
│           Upload • Suche • Ansicht • Download                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Anwendungsschicht                          │
│                       (app.py)                               │
│    API-Endpunkte • Request-Routing • Task-Koordination     │
└───┬────────────┬────────────┬────────────────┬─────────────┘
    │            │            │                │
    ▼            ▼            ▼                ▼
┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐
│   PDF   │ │Datenbank│ │    KI    │ │   GridFS       │
│Processor│ │ Manager │ │Processor │ │ Dateispeicher  │
└─────────┘ └─────────┘ └──────────┘ └────────────────┘
    │            │            │                │
    ▼            ▼            ▼                ▼
┌─────────┐ ┌──────────────────────────────────────┐
│OCRmyPDF │ │         MongoDB Datenbank            │
│Tesseract│ │  • documents  • pages  • GridFS     │
└─────────┘ └──────────────────────────────────────┘
```

### Kernmodule

#### 1. **pdf_processor.py** - PDF-Textextraktion & OCR
**Zweck:** Text aus PDFs mit hochwertiger OCR-Unterstützung extrahieren

**Hauptfunktionen:**
- PyMuPDF für schnelle Textextraktion
- OCRmyPDF für überlegene OCR-Qualität (Deutsch + Englisch)
- Automatische Erkennung gescannter Dokumente
- Pytesseract-Fallback für einzelne Seiten
- Temporäre Dateiverwaltung

#### 2. **database.py** - Datenpersistenz & Speicherung
**Zweck:** MongoDB-Operationen und Dateispeicherung verwalten

**Hauptfunktionen:**
- Getrennte Sammlungen (documents + pages)
- GridFS für unbegrenzte PDF-Dateigröße
- Textindizes für Stichwortsuche
- CRUD-Operationen mit Fehlerbehandlung

#### 3. **ai_processor.py** - KI-gestützte Strukturierung
**Zweck:** Zusammenfassungen, Schlüsselwörter und strukturierte Daten generieren

**Hauptfunktionen:**
- OpenAI GPT-Integration
- Seitenzusammenfassungen (50-100 Wörter)
- Schlüsselwortextraktion (5-15 pro Seite)
- Intelligente Textkürzung (8000 Zeichen)
- Umfassende Fehlerprotokollierung

#### 4. **app.py** - Webanwendung & API
**Zweck:** HTTP-Schnittstelle und Request-Handling

**Hauptfunktionen:**
- RESTful API-Endpunkte
- Asynchrone KI-Verarbeitung
- Datei-Upload-Verwaltung
- Weboberfläche

### Datenstruktur

```javascript
// documents-Sammlung - Dokumentmetadaten
{
  doc_id: "uuid-123",
  filename: "bericht.pdf",
  pdf_file_id: "gridfs-id",        // Original-PDF in GridFS
  total_pages: 10,
  document_summary: "...",          // KI-generiert
  keywords: ["wort1", "wort2"],     // KI-extrahiert
  status: "structured",
  created_at: "2026-01-21T..."
}

// pages-Sammlung - Daten auf Seitenebene
{
  doc_id: "uuid-123",
  page_num: 1,
  raw_text: "Vollständiger Text...", // OCR-extrahiert
  page_summary: "...",               // KI-generiert
  keywords: ["wort1", "wort2"],      // KI-extrahiert
  structured_data: {
    sections: [...],
    measurements: [...],
    key_fields: {...},
    tables: [...]
  },
  status: "structured"
}

// GridFS - Binärspeicher (automatische Aufteilung)
fs.files: { _id, filename, length, uploadDate }
fs.chunks: { files_id, n, data }  // 255KB Blöcke
```

### Verarbeitungspipeline

```
1. Benutzer lädt PDF hoch
   ↓
2. Auto-Erkennung ob OCR benötigt (erste 3 Seiten prüfen)
   ↓
3. Falls benötigt: OCRmyPDF-Vorverarbeitung
   • Deutsch + Englisch
   • Automatische Entzerrung
   • Bildoptimierung
   ↓
4. PyMuPDF Textextraktion
   • Text von allen Seiten extrahieren
   • Layout-Informationen bewahren
   ↓
5. In MongoDB speichern
   • Original-PDF → GridFS
   • Dokumentmetadaten → documents-Sammlung
   • Seitendaten → pages-Sammlung
   ↓
6. KI-Verarbeitung (async im Hintergrund)
   • Zusammenfassungen generieren
   • Schlüsselwörter extrahieren
   • Daten strukturieren
   ↓
7. Datenbank mit KI-Ergebnissen aktualisieren
   ↓
8. Bereit für Suche & Download
```

---

## ✨ Funktionen

- 📄 **Hochwertige OCR**: OCRmyPDF + Tesseract für deutsche/englische Dokumente
- 💾 **GridFS-Speicherung**: Original-PDFs speichern (keine Größenbeschränkung)
- 🧠 **KI-Strukturierung**: Automatische Zusammenfassungen, Schlüsselwörter und strukturierte Daten
- 🔍 **Stichwortsuche**: Volltextsuche mit MongoDB-Indizes
- 📥 **Download-Support**: Original-PDF-Dateien abrufen
- 🌐 **Weboberfläche**: Moderne Drag & Drop UI
- ⚡ **Async-Verarbeitung**: Nicht-blockierende Hintergrund-KI-Verarbeitung

---

## 📋 Voraussetzungen

- **Python 3.9+**
- **MongoDB** (lokale Installation)
- **Tesseract OCR**
- **OCRmyPDF** (optional aber empfohlen)
- **OpenAI API-Schlüssel**

---

## 🚀 Schnellinstallation

### 1. Python installieren
Von [python.org](https://www.python.org/downloads/) herunterladen  
✓ "Add Python to PATH" während Installation aktivieren

### 2. MongoDB installieren
Von [mongodb.com](https://www.mongodb.com/try/download/community) herunterladen  
Als Service installieren (läuft auf localhost:27017)

### 3. Tesseract OCR installieren
Von [GitHub](https://github.com/UB-Mannheim/tesseract/wiki) herunterladen  
Zum System-PATH hinzufügen

### 4. Projekt einrichten

```bash
# Virtuelle Umgebung erstellen
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Abhängigkeiten installieren
cd pdf-processor
pip install -r requirements.txt

# Umgebung konfigurieren
# .env-Datei mit OpenAI API-Schlüssel erstellen
```

### 5. Ausführen

```bash
# Verbindung testen
cd tests
python test_mongodb_connection.py

# Anwendung starten
cd ..
python app.py
```

Öffnen: http://localhost:5000

**Siehe [QUICKSTART.md](QUICKSTART.md) für detaillierte Schritt-für-Schritt-Anleitung.**

---

## 📖 API-Endpunkte

| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/` | Weboberfläche |
| POST | `/upload` | PDF-Datei hochladen |
| GET | `/documents` | Alle Dokumente auflisten |
| GET | `/search?q={abfrage}` | Nach Stichwort suchen |
| GET | `/document/{id}/status` | Verarbeitungsstatus abrufen |
| GET | `/document/{id}/structured` | Strukturierte Daten abrufen |
| GET | `/document/{id}/download` | Original-PDF herunterladen |
| DELETE | `/document/{id}` | Dokument löschen |

### Verwendungsbeispiel

```bash
# PDF hochladen
curl -X POST http://localhost:5000/upload -F "file=@dokument.pdf"

# Suchen
curl "http://localhost:5000/search?q=rechnung&limit=10"

# Herunterladen
curl -o original.pdf "http://localhost:5000/document/{doc_id}/download"
```

---

## 🛠️ Technologie-Stack

| Komponente | Technologie | Zweck |
|------------|-------------|-------|
| **Backend** | Flask 3.0 | Web-Framework & API |
| **Datenbank** | MongoDB 4.6+ | Dokumentenspeicherung |
| **Dateispeicher** | GridFS | Große Dateien |
| **PDF-Verarbeitung** | PyMuPDF | Textextraktion |
| **OCR** | OCRmyPDF + Tesseract | Texterkennung |
| **KI** | OpenAI GPT-3.5/4 | Textstrukturierung |
| **Frontend** | HTML/JS | Weboberfläche |

---

## 🔧 Konfiguration

`.env`-Datei erstellen:

```env
# Erforderlich
OPENAI_API_KEY=sk-proj-ihr-api-schlüssel-hier

# Optional (Standardwerte gezeigt)
MONGO_URI=mongodb://localhost:27017/
DB_NAME=pdf_intelligence_db
UPLOAD_FOLDER=uploads/
MAX_CONTENT_LENGTH=52428800  # 50MB
```

---

## 📚 Dokumentation

- **[QUICKSTART.md](QUICKSTART.md)** - Schnellstartanleitung
- **[UPGRADE_NOTES.md](UPGRADE_NOTES.md)** - Phase-1-Implementierungsdetails (English)
- **[UPGRADE_NOTES_DE.md](UPGRADE_NOTES_DE.md)** - Phase-1-Implementierungsdetails (Deutsch)
- **[README.md](README.md)** - Englische Version dieser Datei

---

## 🐛 Fehlerbehebung

### MongoDB-Verbindung fehlgeschlagen
```bash
# Prüfen ob MongoDB läuft
mongosh --eval "db.version()"
```

### OpenAI API-Schlüssel nicht gefunden
```bash
# .env-Datei erstellen mit:
OPENAI_API_KEY=sk-proj-ihr-schlüssel-hier
```

### OCRmyPDF nicht gefunden (Optional)
```bash
pip install ocrmypdf
```

**Hinweis:** System funktioniert ohne OCRmyPDF, aber mit geringerer OCR-Qualität.

---

## 📂 Projektstruktur

```
pdf-processor/
├── app.py                    # Flask-Anwendung
├── database.py               # MongoDB & GridFS
├── ai_processor.py           # OpenAI-Integration
├── pdf_processor.py          # PDF- & OCR-Verarbeitung
├── requirements.txt          # Python-Abhängigkeiten
├── .env                      # Konfiguration
├── README.md                 # Englische Version
├── README_DE.md              # Diese Datei (Deutsch)
├── UPGRADE_NOTES.md          # Upgrade-Details (English)
├── UPGRADE_NOTES_DE.md       # Upgrade-Details (Deutsch)
├── QUICKSTART.md             # Schnellstartanleitung
├── templates/                # HTML-Vorlagen
├── tests/                    # Testskripte
│   ├── test_mongodb_connection.py
│   └── README.md
└── uploads/                  # Hochgeladene PDFs
```

---

## 🎯 Nächste Schritte

Nach dem Setup können Sie:
1. PDFs über die Weboberfläche hochladen
2. Dokumente nach Stichwörtern durchsuchen
3. Strukturierte Daten anzeigen (Zusammenfassungen, Schlüsselwörter, Tabellen)
4. Original-PDFs herunterladen

Für erweiterte Funktionen und Phase-2-Planung (Vector DB, RAG) siehe [UPGRADE_NOTES_DE.md](UPGRADE_NOTES_DE.md).

---

**Version:** 2.0.1  
**Status:** Produktionsbereit  
**OCR-Qualität:** ⭐⭐⭐⭐⭐  
**Letzte Aktualisierung:** Januar 2026

