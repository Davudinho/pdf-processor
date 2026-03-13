# PDF Intelligence System

*English Version | [Deutsche Version](README_DE.md)*

A production-ready system for intelligent PDF processing with AI-powered OCR, text extraction, semantic search (RAG), entity extraction, and automatic document categorization.

---

## 🏗️ System Architecture

### Overview

```
┌──────────────────────────────────────────────────────────────────┐
│               Web Interface (Flask + Premium Glassmorphism UI)    │
│     Upload • KI-Chat (RAG) • Entity Extraction • Categorization   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Application Layer (app.py)                     │
│       API Endpoints • Request Routing • Task Coordination         │
└───┬────────────┬────────────┬──────────────┬────────────────────-┘
    │            │            │              │
    ▼            ▼            ▼              ▼
┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
│   PDF   │ │Database │ │    AI    │ │   Qdrant     │
│Processor│ │ Manager │ │Processor │ │ Vector Store │
└─────────┘ └─────────┘ └──────────┘ └──────────────┘
    │            │            │
    ▼            ▼            ▼
┌─────────┐ ┌──────────────────────────────────────┐
│OCRmyPDF │ │           MongoDB Database            │
│Tesseract│ │  • documents  • pages  • GridFS      │
└─────────┘ └──────────────────────────────────────┘
```

### Core Modules

#### 1. **pdf_processor.py** - PDF Text Extraction & OCR
**Purpose:** Extract text from PDFs with high-quality OCR support

**Key Features:**
- PyMuPDF for fast text extraction
- OCRmyPDF for superior OCR quality (German + English)
- Automatic scanned document detection
- Pytesseract fallback for individual pages

#### 2. **database.py** - Data Persistence & Storage
**Purpose:** Manage MongoDB operations and file storage

**Key Features:**
- Separated collections (documents + pages)
- GridFS for unlimited PDF file size
- Text indexes for keyword search
- Full CRUD operations with error handling

#### 3. **ai_processor.py** - AI-Powered Intelligence Hub
**Purpose:** Summaries, keywords, RAG, entity extraction, and categorization

**Key Features:**
- OpenAI `gpt-4o-mini` integration
- Page-level summaries and keyword extraction
- Retrieval-Augmented Generation (RAG) with Qdrant vector search
- Named Entity Extraction (persons, companies, amounts, dates, addresses)
- Automatic document categorization (smart tags)
- Follow-up question suggestions

#### 4. **app.py** - Web Application & API
**Purpose:** HTTP interface and request handling

**Key Features:**
- RESTful API endpoints
- Asynchronous AI processing (background threads)
- File upload management (drag & drop)
- Cross-document RAG queries

#### 5. **qdrant_manager.py** - Vector Search Engine
**Purpose:** Manage vector embeddings for semantic document search

**Key Features:**
- Qdrant vector database integration
- OpenAI `text-embedding-ada-002` embeddings
- Semantic similarity search across documents

### Data Structure

```javascript
// documents collection - Document metadata
{
  doc_id: "uuid-123",
  filename: "report.pdf",
  pdf_file_id: "gridfs-id",        // Original PDF in GridFS
  total_pages: 10,
  document_summary: "...",          // AI-generated summary
  document_keywords: ["key1"],      // AI-extracted keywords
  category: "Rechnung",             // AI auto-categorized tag
  status: "structured",
  created_at: "2026-01-21T..."
}

// pages collection - Page-level data
{
  doc_id: "uuid-123",
  page_num: 1,
  raw_text: "Full page text...",   // OCR-extracted
  page_summary: "...",              // AI-generated
  keywords: ["word1", "word2"],     // AI-extracted
  embedding: [0.1, 0.2, ...],      // Vector for semantic search
  structured_data: {
    sections: [...],
    measurements: [...],
    key_fields: {...},
    tables: [...]
  },
  status: "structured"
}

// GridFS - Binary storage (automatic chunking)
fs.files: { _id, filename, length, uploadDate }
fs.chunks: { files_id, n, data }  // 255KB chunks
```

### Processing Pipeline

```
1. User uploads PDF
   ↓
2. Auto-detect if OCR needed (sample first 3 pages)
   ↓
3. If needed: OCRmyPDF preprocessing
   • German + English languages
   • Automatic deskewing
   • Image optimization
   ↓
4. PyMuPDF text extraction (all pages)
   ↓
5. Store in MongoDB
   • Original PDF → GridFS
   • Document metadata → documents collection
   • Page data → pages collection
   ↓
6. AI processing (async background)
   • Generate page summaries & keywords
   • Create vector embeddings → Qdrant
   • Generate document-level summary
   • Auto-categorize document (smart tag)
   ↓
7. Update database with AI results
   ↓
8. Ready for RAG chat, entity extraction, search & download
```

---

## ✨ Features

- 📄 **High-Quality OCR**: OCRmyPDF + Tesseract for German/English documents
- 💾 **GridFS Storage**: Store original PDFs (no size limits)
- 🧠 **AI Structuring**: Automatic summaries, keywords, and structured data
- 💬 **RAG Chat**: Ask questions about your documents (single or cross-document)
- 🔍 **Semantic Search**: Vector-based search via Qdrant + keyword fallback
- 🏷️ **Auto-Categorization**: AI assigns document categories (Rechnung, Vertrag, etc.)
- 🗂️ **Entity Extraction**: Extract persons, companies, amounts, dates & addresses into tables
- 📥 **Download Support**: Retrieve original PDF files
- 🌐 **Premium UI**: Glassmorphism design with animations and multi-select chip UI
- ⚡ **Async Processing**: Non-blocking background AI processing

---

## 📋 Prerequisites

- **Python 3.9+**
- **MongoDB** (local installation)
- **Tesseract OCR**
- **OCRmyPDF** (optional but recommended)
- **OpenAI API Key**
- **Qdrant** (optional, for vector search; falls back to keyword search)

---

## 🚀 Quick Installation

### 1. Install Python
Download from [python.org](https://www.python.org/downloads/)  
✓ Check "Add Python to PATH" during installation

### 2. Install MongoDB
Download from [mongodb.com](https://www.mongodb.com/try/download/community)  
Install as a service (runs on localhost:27017)

### 3. Install Tesseract OCR
Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)  
Add to system PATH

### 4. Setup Project

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
cd pdf-processor
pip install -r requirements.txt

# Configure environment
# Create .env file (see Configuration section)
```

### 5. Run

```bash
# Test connection
cd tests
python test_mongodb_connection.py

# Start application
cd ..
python app.py
```

Open: http://localhost:5000

**See [QUICKSTART.md](QUICKSTART.md) for detailed step-by-step instructions.**

---

## 📖 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| POST | `/upload` | Upload PDF file |
| GET | `/documents` | List all documents |
| GET | `/search?q={query}` | Search by keyword |
| POST | `/ask` | RAG chat query (cross-document) |
| POST | `/extract` | Extract entities from a document |
| GET | `/document/{id}/status` | Get processing status |
| GET | `/document/{id}/structured` | Get structured data & summary |
| GET | `/document/{id}/download` | Download original PDF |
| DELETE | `/document/{id}` | Delete document |

### Example Usage

```bash
# Upload PDF
curl -X POST http://localhost:5000/upload -F "file=@document.pdf"

# RAG Chat (single document)
curl -X POST http://localhost:5000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What are the key findings?", "doc_ids": ["uuid-123"]}'

# Cross-Document RAG (all documents)
curl -X POST http://localhost:5000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Compare the contracts", "doc_ids": null}'

# Entity Extraction
curl -X POST http://localhost:5000/extract \
     -H "Content-Type: application/json" \
     -d '{"doc_id": "uuid-123", "entity_types": ["personen", "betraege"]}'

# Download original
curl -o original.pdf "http://localhost:5000/document/{doc_id}/download"
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Flask 3.0 | Web framework & API |
| **Database** | MongoDB 4.6+ | Document metadata & page storage |
| **File Storage** | GridFS | Large PDF file handling |
| **Vector DB** | Qdrant | Semantic search & RAG |
| **PDF Processing** | PyMuPDF | Text extraction |
| **OCR** | OCRmyPDF + Tesseract | Text recognition (scanned PDFs) |
| **AI** | OpenAI gpt-4o-mini | Summarization, RAG, extraction, categorization |
| **Embeddings** | text-embedding-ada-002 | Vector search |
| **Frontend** | HTML / CSS / JavaScript | Glassmorphism Premium UI |

---

## 🔧 Configuration

Create `.env` file:

```env
# Required
OPENAI_API_KEY=sk-proj-your-api-key-here

# Optional (defaults shown)
MONGO_URI=mongodb://localhost:27017/
DB_NAME=pdf_intelligence_db
UPLOAD_FOLDER=uploads/
MAX_CONTENT_LENGTH=52428800  # 50MB
OPENAI_MODEL=gpt-4o-mini

# Qdrant (optional - falls back to keyword search if not set)
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide
- **[UPGRADE_NOTES.md](UPGRADE_NOTES.md)** - Phase 1 implementation details (English)
- **[UPGRADE_NOTES_DE.md](UPGRADE_NOTES_DE.md)** - Phase 1 implementation details (Deutsch)
- **[README_DE.md](README_DE.md)** - German version of this file
- **[tests/README.md](tests/README.md)** - Testing guide

---

## 🐛 Troubleshooting

### MongoDB Connection Failed
```bash
# Check if MongoDB is running
mongosh --eval "db.version()"
```

### OpenAI API Key Not Found
```bash
# Create .env file with:
OPENAI_API_KEY=sk-proj-your-key-here
```

### OCRmyPDF Not Found (Optional)
```bash
pip install ocrmypdf
```
**Note:** System works without OCRmyPDF but with lower OCR quality.

### Qdrant Not Available
The system automatically falls back to MongoDB keyword search if Qdrant is not running. RAG chat will still work but with keyword-based context retrieval instead of semantic vector search.

---

## 📂 Project Structure

```
pdf-processor/
├── app.py                    # Flask application & API routes
├── database.py               # MongoDB & GridFS management
├── ai_processor.py           # AI: RAG, extraction, categorization
├── pdf_processor.py          # PDF & OCR processing
├── qdrant_manager.py         # Vector search (Qdrant)
├── requirements.txt          # Python dependencies
├── .env                      # Configuration (not in git)
├── README.md                 # This file (English)
├── README_DE.md              # German version
├── UPGRADE_NOTES.md          # Upgrade details (English)
├── UPGRADE_NOTES_DE.md       # Upgrade details (Deutsch)
├── QUICKSTART.md             # Quick start guide
├── test_auto_category.py     # Auto-categorization test script
├── templates/                # HTML templates
│   └── index.html            # Premium Glassmorphism single-page UI
├── tests/                    # Test scripts
│   ├── test_mongodb_connection.py
│   ├── test_complete_workflow.py
│   └── README.md             # Testing guide
└── uploads/                  # Uploaded PDFs (temporary)
```

---

## 🎯 What You Can Do

After setup:
1. **Upload** PDFs via drag & drop
2. **Chat** with your documents using natural language (RAG)
3. **Cross-Document Analysis**: Ask questions across multiple documents simultaneously
4. **Extract Entities**: Get structured tables of persons, companies, dates, etc.
5. **Auto-Categorized Tags**: Each document is automatically tagged (e.g. "Rechnung", "Vertrag")
6. **Search** documents by keywords
7. **View** full AI analysis (summaries, keywords, page breakdown)
8. **Download** original PDFs

---

**Version:** 3.0.0  
**Status:** Production Ready  
**OCR Quality:** ⭐⭐⭐⭐⭐  
**Last Updated:** March 2026
