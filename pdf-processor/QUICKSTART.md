# Quick Start Guide

## 1. Install Python

Download and install Python 3.9+ from [python.org](https://www.python.org/downloads/)

**Important:** Check "Add Python to PATH" during installation

Verify:
```bash
python --version
```

## 2. Install MongoDB

**Windows:** Download from [mongodb.com](https://www.mongodb.com/try/download/community)

**Linux:**
```bash
sudo apt install mongodb
sudo systemctl start mongodb
```

**Mac:**
```bash
brew install mongodb-community
brew services start mongodb-community
```

## 3. Install Tesseract OCR

**Windows:** [Download here](https://github.com/UB-Mannheim/tesseract/wiki)

**Linux:**
```bash
sudo apt install tesseract-ocr
```

**Mac:**
```bash
brew install tesseract
```

## 4. Setup Project

```bash
# Navigate to project
cd pdf-processor

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 5. Configure Environment

Create `.env` file:
```env
OPENAI_API_KEY=sk-proj-your-api-key-here
MONGO_URI=mongodb://localhost:27017/
DB_NAME=pdf_intelligence_db
```

## 6. Run Tests

```bash
cd tests
python test_mongodb_connection.py
```

## 7. Start Application

```bash
cd ..
python app.py
```

Open: http://localhost:5000

## Done! 🎉

Upload a PDF and see it in action!

