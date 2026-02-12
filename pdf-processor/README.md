# PDF Intelligence System

*English Version | [Deutsche Version](README_DE.md)*

A production-ready system for PDF processing with AI-powered text extraction, structuring, and keyword search capabilities.

---

## 🏗️ System Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Interface (Flask)                    │
│              Upload • Search • View • Download               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│                       (app.py)                               │
│     API Endpoints • Request Routing • Task Coordination     │
└───┬────────────┬────────────┬────────────────┬─────────────┘
    │            │            │                │
    ▼            ▼            ▼                ▼
┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐
│   PDF   │ │Database │ │    AI    │ │   GridFS       │
│Processor│ │ Manager │ │Processor │ │ File Storage   │
└─────────┘ └─────────┘ └──────────┘ └────────────────┘
    │            │            │                │
    ▼            ▼            ▼                ▼
┌─────────┐ ┌──────────────────────────────────────┐
│OCRmyPDF │ │         MongoDB Database             │
│Tesseract│ │  • documents  • pages  • GridFS     │
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
- Temporary file management

#### 2. **database.py** - Data Persistence & Storage
**Purpose:** Manage MongoDB operations and file storage

**Key Features:**
- Separated collections (documents + pages)
- GridFS for unlimited PDF file size
- Text indexes for keyword search
- CRUD operations with error handling

#### 3. **ai_processor.py** - AI-Powered Structuring
**Purpose:** Generate summaries, keywords, and structured data

**Key Features:**
- OpenAI GPT integration
- Page summaries (50-100 words)
- Keyword extraction (5-15 per page)
- Smart text truncation (8000 chars)
- Comprehensive error logging

#### 4. **app.py** - Web Application & API
**Purpose:** HTTP interface and request handling

**Key Features:**
- RESTful API endpoints
- Asynchronous AI processing
- File upload management
- Web interface

### Data Structure

```javascript
// documents collection - Document metadata
{
  doc_id: "uuid-123",
  filename: "report.pdf",
  pdf_file_id: "gridfs-id",        // Original PDF in GridFS
  total_pages: 10,
  document_summary: "...",          // AI-generated
  keywords: ["key1", "key2"],       // AI-extracted
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
4. PyMuPDF text extraction
   • Extract text from all pages
   • Preserve layout information
   ↓
5. Store in MongoDB
   • Original PDF → GridFS
   • Document metadata → documents collection
   • Page data → pages collection
   ↓
6. AI processing (async background)
   • Generate summaries
   • Extract keywords
   • Structure data
   ↓
7. Update database with AI results
   ↓
8. Ready for search & download
```

---

## ✨ Features

- 📄 **High-Quality OCR**: OCRmyPDF + Tesseract for German/English documents
- 💾 **GridFS Storage**: Store original PDFs (no size limits)
- 🧠 **AI Structuring**: Automatic summaries, keywords, and structured data
- 🔍 **Keyword Search**: Full-text search with MongoDB indexes
- 📥 **Download Support**: Retrieve original PDF files
- 🌐 **Web Interface**: Modern drag & drop UI
- ⚡ **Async Processing**: Non-blocking background AI processing

---

## 📋 Prerequisites

- **Python 3.9+**
- **MongoDB** (local installation)
- **Tesseract OCR**
- **OCRmyPDF** (optional but recommended)
- **OpenAI API Key**

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
# Create .env file with your OpenAI API key
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
| GET | `/document/{id}/status` | Get processing status |
| GET | `/document/{id}/structured` | Get structured data |
| GET | `/document/{id}/download` | Download original PDF |
| DELETE | `/document/{id}` | Delete document |

### Example Usage

```bash
# Upload PDF
curl -X POST http://localhost:5000/upload -F "file=@document.pdf"

# Search
curl "http://localhost:5000/search?q=invoice&limit=10"

# Download
curl -o original.pdf "http://localhost:5000/document/{doc_id}/download"
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Flask 3.0 | Web framework & API |
| **Database** | MongoDB 4.6+ | Document storage |
| **File Storage** | GridFS | Large file handling |
| **PDF Processing** | PyMuPDF | Text extraction |
| **OCR** | OCRmyPDF + Tesseract | Text recognition |
| **AI** | OpenAI GPT-3.5/4 | Text structuring |
| **Frontend** | HTML/JS | Web interface |

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
```

---

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide
- **[UPGRADE_NOTES.md](UPGRADE_NOTES.md)** - Phase 1 implementation details (English)
- **[UPGRADE_NOTES_DE.md](UPGRADE_NOTES_DE.md)** - Phase 1 implementation details (Deutsch)
- **[README_DE.md](README_DE.md)** - German version of this file

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

---

## 📂 Project Structure

```
pdf-processor/
├── app.py                    # Flask application
├── database.py               # MongoDB & GridFS
├── ai_processor.py           # OpenAI integration
├── pdf_processor.py          # PDF & OCR processing
├── requirements.txt          # Python dependencies
├── .env                      # Configuration
├── README.md                 # This file (English)
├── README_DE.md              # German version
├── UPGRADE_NOTES.md          # Upgrade details (English)
├── UPGRADE_NOTES_DE.md       # Upgrade details (Deutsch)
├── QUICKSTART.md             # Quick start guide
├── templates/                # HTML templates
├── tests/                    # Test scripts
│   ├── test_mongodb_connection.py
│   └── README.md
└── uploads/                  # Uploaded PDFs
```

---

## 🎯 Next Steps

After setup, you can:
1. Upload PDFs via web interface
2. Search documents by keywords
3. View structured data (summaries, keywords, tables)
4. Download original PDFs

For advanced features and Phase 2 planning (Vector DB, RAG), see [UPGRADE_NOTES.md](UPGRADE_NOTES.md).

---

**Version:** 2.0.1  
**Status:** Production Ready  
**OCR Quality:** ⭐⭐⭐⭐⭐  
**Last Updated:** January 2026
