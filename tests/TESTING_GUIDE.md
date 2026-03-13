# Testing Guide – PDF Intelligenz System v3.0

This guide helps you test the PDF Intelligence System systematically, including all AI features (RAG Chat, Entity Extraction, Auto-Categorization).

---

## 📋 Overview

| File | Purpose | OpenAI? | Zeit | Empfehlung |
|------|---------|---------|------|------------|
| `test_mongodb_connection.py` | Core system & imports | Nein | 10s | ⭐ Immer zuerst |
| `test_and_keep_data.py` | Upload & Daten behalten | Nein | 15s | ⭐ Für Inspektion |
| `inspect_database.py` | Datenbank-Inhalte anzeigen | Nein | 5s | Nach Upload |
| `check_openai_status.py` | API Quota prüfen | Ja (minimal) | 5s | Vor KI-Tests |
| `test_complete_workflow.py` | Vollständiger Workflow + KI | Ja | 2–3 Min | Mit API Credits |
| `test_auto_category.py` | Auto-Kategorisierung testen | Ja | 30s | Separat im Root |

---

## 🚀 Schritt-für-Schritt Testen

### Voraussetzungen

```bash
# Virtuelle Umgebung aktivieren
cd c:\Users\User\projects\pdf-processor
venv\Scripts\activate

# MongoDB muss laufen (Service prüfen)

# In tests-Ordner wechseln
cd tests
```

---

### Schritt 1: Core-System testen (kostenlos)

**Datei:** `test_mongodb_connection.py`

**Was wird getestet:**
- ✓ Alle Python-Pakete installiert (inkl. qdrant-client, openai)
- ✓ MongoDB Verbindung
- ✓ Datenbankinitialisierung + Collections
- ✓ GridFS Dateispeicher
- ✓ PDF Textextraktion

**Ausführen:**
```bash
python test_mongodb_connection.py
```

**Erwartete Ausgabe:**
```
Imports                   PASSED ✓
MongoDB                   PASSED ✓
DB Manager                PASSED ✓
GridFS                    PASSED ✓
PDF Processing            PASSED ✓
Workflow                  PASSED ✓
Indexes                   PASSED ✓
OpenAI                    PASSED ✓

Results: 8 passed, 0 failed, 0 skipped
✓ All tests passed! System is ready to use.
```

---

### Schritt 2: Test-Daten hochladen (kostenlos)

**Datei:** `test_and_keep_data.py`

**Was es tut:**
- Lädt eine Test-PDF in MongoDB
- Speichert Original in GridFS
- Testet Keyword-Suche
- **Löscht Daten NICHT** (für Inspektion)

```bash
python test_and_keep_data.py
```

---

### Schritt 3: Datenbank-Inhalte inspizieren (kostenlos)

**Datei:** `inspect_database.py`

**Zeigt:**
- Anzahl Dokumente & Seiten
- GridFS Dateien
- Such-Ergebnisse

```bash
python inspect_database.py
```

---

### Schritt 4: OpenAI API Status prüfen (optional, minimal)

**Datei:** `check_openai_status.py`

**Prüft:** API-Key, Verbindung, Quota

```bash
python check_openai_status.py
```

**Ausgabe (OK):**
```
✓ API Key found
✓ API connection successful!
✓ API key is valid and has available quota
```

---

### Schritt 5: Vollständiger Workflow-Test (benötigt API)

**Datei:** `test_complete_workflow.py`

> ⚠️ **Achtung:** Nutzt OpenAI API (~$0.02–0.05 pro Durchlauf)

**Was getestet wird:**
- PDF-Extraktion (alle Seiten)
- MongoDB-Operationen
- KI-Seitenstrukturierung (Zusammenfassungen + Keywords)
- Vektor-Embeddings in Qdrant
- Keyword-Suche
- PDF-Download
- Dokumenten-Status
- Cleanup

```bash
python test_complete_workflow.py
```

**Erwartete Ausgabe (mit Credits):**
```
Total: 20/20 tests passed (100%)

✓ Environment Configuration       3/3 PASSED
✓ PDF Text Extraction             2/2 PASSED
✓ Database Operations             5/5 PASSED
✓ AI Processing                   2/2 PASSED
✓ Keyword Search                  1/1 PASSED
✓ PDF Download                    1/1 PASSED
✓ Document Status                 2/2 PASSED
✓ Structured Data                 1/1 PASSED
✓ Cleanup                         2/2 PASSED
```

---

## 🧪 Manuelles Testen der neuen KI-Features (via Browser)

Die folgenden Features können direkt in der Web-Oberfläche getestet werden. Starte dafür zuerst die App:

```bash
# Im Root-Verzeichnis
python app.py
```

Dann öffne: **http://localhost:5000**

---

### Feature 1: Dokument hochladen & Auto-Kategorisierung

1. Öffne die App im Browser
2. Lade eine PDF hoch (z.B. eine Rechnung oder einen Vertrag)
3. Warte bis der Status auf **"KI-Analyse fertig"** wechselt (~30–60s)
4. **Prüfen:** Ein farbiges Badge erscheint auf der Dokumentkarte (z.B. `Rechnung` oder `Vertrag`)

**Erwartetes Verhalten:**
- Badge ist sichtbar und korrekt kategorisiert
- Kategorie passt zum Dokumenttyp

**Alternativ via API:**
```bash
curl http://localhost:5000/documents
# → Prüfe "category"-Feld im JSON
```

---

### Feature 2: RAG-Chat (Einzeldokument)

1. Warte bis Dokument verarbeitet ist
2. Stelle eine Frage in der Chat-Box (z.B. "Was sind die wichtigsten Punkte?")
3. **Kein Dokument auswählen** im Dropdown → alle Dokumente werden durchsucht

**Erwartetes Verhalten:**
- Antwort erscheint innerhalb von 3–8 Sekunden
- Quell-Tags (`S. 3 (87%)`) werden unter der Antwort angezeigt
- 3 Folgefragen werden vorgeschlagen

**Alternativ via API:**
```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Was ist der Gesamtbetrag?", "doc_ids": null}'
```

**Erwartete JSON-Antwort:**
```json
{
  "success": true,
  "data": {
    "answer": "Der Gesamtbetrag beträgt...",
    "sources": [{"page_num": 1, "score": 0.92, "text": "..."}],
    "follow_ups": ["Welche Positionen sind enthalten?", "..."]
  }
}
```

---

### Feature 3: Cross-Document RAG (mehrere Dokumente)

1. Lade mind. 2 PDFs hoch und warte auf Verarbeitung
2. Klicke auf das Dropdown **"Alle Dokumente"** oben rechts im Chat
3. Wähle 2 oder mehr Dokumente aus
4. Stelle eine vergleichende Frage (z.B. "Welches Dokument hat den höheren Betrag?")

**Erwartetes Verhalten:**
- Ausgewählte Dokumente erscheinen als blaue Chips im Dropdown
- Antwort bezieht sich auf alle ausgewählten Dokumente
- Quell-Tags zeigen aus welchem Dokument der Kontext stammt

**Via API:**
```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Vergleiche die Dokumente", "doc_ids": ["uuid-1", "uuid-2"]}'
```

---

### Feature 4: Entitäten-Extraktion

1. Öffne den Bereich **"Daten extrahieren"**
2. Wähle ein verarbeitetes Dokument aus der Dropdown
3. Wähle Entitätstypen (z.B. Personen + Beträge)
4. Klicke **"Extrahieren"**
5. Warte auf Ergebnis (~5–15s)

**Erwartetes Verhalten:**
- Tabellen erscheinen mit den erkannten Entitäten
- Jeder Entitätstyp hat eine eigene Tabelle mit Zähler-Badge
- **"⬇ CSV"**-Button lädt Daten als Excel-kompatible Datei

**Test-Kriterien:**
| Entitätstyp | Erwartete Spalten |
|---|---|
| Personen | Name, Rolle/Titel, Kontext |
| Firmen | Name, Typ, Kontext |
| Beträge | Betrag, Währung, Kontext/Zweck |
| Daten | Datum, Typ/Bezeichnung, Kontext |
| Adressen | Straße, PLZ, Ort, Land |

**Via API:**
```bash
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "deine-doc-id", "entity_types": ["personen", "betraege"]}'
```

**Erwartete JSON-Antwort:**
```json
{
  "success": true,
  "data": {
    "entities": {
      "personen": [{"Name": "Max Mustermann", "Rolle": "Auftraggeber", "Kontext": "..."}],
      "betraege": [{"Betrag": 1234.56, "Währung": "EUR", "Kontext": "Nettobetrag"}]
    }
  }
}
```

---

### Feature 5: Auto-Kategorisierung (separater Test)

**Datei:** `test_auto_category.py` (im Root-Verzeichnis)

```bash
# Im Root-Verzeichnis ausführen!
cd ..
python test_auto_category.py
```

**Was es testet:**
- Verbindung zu MongoDB und OpenAI
- Kategorisiert ein bestehendes Dokument per KI
- Zeigt zugewiesene Kategorie an

---

## 🔍 API Endpoints – Übersicht

Alle Endpunkte können mit `curl` oder einem REST-Client (z.B. Postman) getestet werden.

| Methode | Endpoint | Beschreibung | Neu? |
|---------|----------|-------------|------|
| GET | `/` | Web-Oberfläche | – |
| POST | `/upload` | PDF hochladen | – |
| GET | `/documents` | Alle Dokumente (inkl. Kategorie) | Erweitert |
| GET | `/document/{id}/status` | Verarbeitungsstatus | – |
| GET | `/document/{id}/structured` | KI-Analyse + Seitendetails | – |
| GET | `/document/{id}/download` | Original-PDF herunterladen | – |
| DELETE | `/document/{id}` | Dokument löschen | – |
| GET | `/search?q={query}` | Keyword-Suche | – |
| **POST** | **`/ask`** | **RAG-Chat (Single + Cross-Doc)** | ✅ Neu |
| **POST** | **`/extract`** | **Entitäten extrahieren** | ✅ Neu |

---

## 🐛 Troubleshooting

### Problem: MongoDB connection failed
```bash
# Windows: Services-App öffnen → MongoDB prüfen
# Oder:
mongosh --eval "db.version()"
```

### Problem: Qdrant nicht verfügbar
```
INFO: Qdrant nicht verfügbar, verwende Keyword-Fallback
```
Das ist **kein Fehler** – RAG-Chat funktioniert dann mit Keyword-Suche statt Vektoren.

Um Qdrant zu starten:
```bash
# Docker
docker run -p 6333:6333 qdrant/qdrant
```

### Problem: Module not found
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### Problem: OpenAI rate limit
```
✗ Rate limit exceeded
```
→ Warte 60 Sekunden oder prüfe Kontingent auf [platform.openai.com/usage](https://platform.openai.com/usage)

### Problem: Chat antwortet "Das weiß ich nicht..."
→ Dokument ist möglicherweise noch nicht vollständig verarbeitet. Status im Dokumentbereich prüfen (muss "KI-Analyse fertig" anzeigen).

### Problem: Extraktion liefert leere Tabellen
→ Prüfe ob der Dokumenttyp die gesuchten Entitäten enthält. Nicht jede PDF hat z.B. Geldbeträge oder Adressen.

---

## ✅ Erfolgskriterien

### Minimum (kostenlos, kein OpenAI nötig):
- ✅ `test_mongodb_connection.py`: 8/8 passed
- ✅ Dokument-Upload funktioniert
- ✅ Keyword-Suche liefert Ergebnisse

### Mit OpenAI Credits:
- ✅ Alle obigen Tests bestanden
- ✅ `test_complete_workflow.py`: 20/20 passed
- ✅ Chat beantwortet Fragen korrekt
- ✅ Entitätsextraktion liefert strukturierte Tabellen
- ✅ Dokumente erhalten automatisch eine Kategorie (Badge)

---

## 📝 Schnellreferenz

```bash
# Setup
venv\Scripts\activate
cd tests

# Tests (in Reihenfolge)
python test_mongodb_connection.py   # Core (kostenlos)
python test_and_keep_data.py        # Upload (kostenlos)
python inspect_database.py          # Inspektion (kostenlos)
python check_openai_status.py       # API-Check (minimal)
python test_complete_workflow.py    # Volltest (mit Credits)

# Auto-kategorisierung (im Root-Verzeichnis)
cd ..
python test_auto_category.py

# App starten
python app.py  # → http://localhost:5000
```

---

**Version:** 3.0.0 | **Stand:** März 2026 | **Happy Testing! 🚀**
