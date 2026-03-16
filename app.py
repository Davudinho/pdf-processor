import os
import sys
import importlib.util
import pkgutil

# Monkeypatch for Python 3.14 compatibility where pkgutil.find_loader is removed
if not hasattr(pkgutil, 'find_loader'):
    def find_loader(fullname):
        spec = importlib.util.find_spec(fullname)
        return spec.loader if spec else None
    pkgutil.find_loader = find_loader

import threading
import logging
from flask import Flask, request, jsonify, render_template, abort, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from pdf_processor import PDFProcessor
from database import MongoDBManager
from ai_processor import AIProcessor
from text_chunker import TextChunker
from qdrant_manager import QdrantManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
def _get_int_env(key, default):
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(str(val).split('#')[0].strip())
    except ValueError:
        return default

app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads/')
app.config['MAX_CONTENT_LENGTH'] = _get_int_env('MAX_CONTENT_LENGTH', 50 * 1024 * 1024)
app.config['MAX_PAGES_PER_PDF'] = _get_int_env('MAX_PAGES_PER_PDF', 500)  # Hard limit per upload
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
app.config['DB_NAME'] = os.getenv('DB_NAME', 'pdf_intelligence_db')
app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
app.config['OPENAI_MODEL'] = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Patch 1: Validate Critical Configuration
api_key = app.config['OPENAI_API_KEY']
if not api_key:
    logger.error("CRITICAL: OPENAI_API_KEY is missing. AI features will not work.")
elif not api_key.startswith("sk-"):
    logger.warning(f"WARNING: API Key starts with '{api_key[:3]}...', expected 'sk-'. Check .env.")

logger.info(f"AI Config: Model={app.config.get('OPENAI_MODEL', 'unknown')} | Key=...{str(api_key)[-4:] if api_key else 'None'}")

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize components
db = MongoDBManager(uri=app.config['MONGO_URI'], db_name=app.config['DB_NAME'])
pdf_processor = PDFProcessor()
ai_processor = AIProcessor(api_key=app.config['OPENAI_API_KEY'], model=app.config['OPENAI_MODEL'])
text_chunker = TextChunker()  # Einmalig initialisiert, nicht bei jedem Request
qdrant_manager = QdrantManager()  # Verbindet zu localhost:6333 (Docker)
if not qdrant_manager.is_connected():
    logger.warning("Qdrant nicht erreichbar. RAG-Features deaktiviert. Starte Docker: docker compose up -d")

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def request_entity_too_large(e):
    """Return a clean JSON error when an uploaded file exceeds MAX_CONTENT_LENGTH."""
    max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return jsonify({
        "success": False,
        "error": f"Datei zu groß. Maximum: {max_mb} MB. Bitte eine kleinere Datei hochladen."
    }), 413

def process_document_async(doc_id, pages_data):
    """Background task: AI processing + Chunking + Qdrant Embedding."""
    logger.info(f"Background thread started for doc_id: {doc_id}")
    try:
        with app.app_context():
            # Step A: AI Strukturierung (Zusammenfassung, Keywords pro Seite)
            ai_processor.process_document(db, doc_id)

            # Step B: Chunks erstellen und in Qdrant speichern
            chunks = text_chunker.chunk_document(pages_data, doc_id, chunk_size=500, overlap=50)
            logger.info(f"Chunks erstellt: {len(chunks)} aus {len(pages_data)} Seiten")

            if qdrant_manager.is_connected() and chunks:
                chunk_texts = [c["text"] for c in chunks]
                embeddings = ai_processor.create_embeddings_batch(chunk_texts)
                if embeddings:
                    qdrant_manager.store_chunks(chunks, embeddings)
                else:
                    logger.warning("Embeddings fehlgeschlagen — Qdrant-Speicherung übersprungen.")
            else:
                logger.warning("Qdrant nicht verfügbar – Chunks werden nicht gespeichert.")

    except Exception as e:
        logger.error(f"Error in background processing for {doc_id}: {e}")
        try:
            with app.app_context():
                db.documents_collection.update_one(
                    {"doc_id": doc_id},
                    {"$set": {"status": "failed", "error_message": str(e)}}
                )
        except Exception as db_e:
            logger.error(f"Failed to update error status for {doc_id}: {db_e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload and process a PDF file.
    
    Steps:
    1. Save uploaded file to disk
    2. Extract text from all pages (with OCR if needed)
    3. Store original PDF in GridFS + page data in MongoDB
    4. Trigger async AI processing for summaries and structured data
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(filepath)
            
            # Step 1: Extract text from PDF (with OCR support)
            logger.info(f"Extracting text from PDF: {filename}")
            pages_data = pdf_processor.extract_text_from_pdf(filepath)
            
            if not pages_data:
                 return jsonify({"success": False, "error": "Could not extract text from PDF"}), 400

            # Check page limit to prevent runaway costs / rate limit errors
            max_pages = app.config['MAX_PAGES_PER_PDF']
            if len(pages_data) > max_pages:
                return jsonify({
                    "success": False,
                    "error": f"PDF hat {len(pages_data)} Seiten. Maximum sind {max_pages} Seiten pro Upload."
                }), 400

            # Step 2: Save PDF file + extracted text to MongoDB (with GridFS)
            logger.info(f"Saving to database with GridFS...")
            doc_id = db.save_pdf_with_pages(filepath, filename, pages_data)
            
            if not doc_id:
                return jsonify({"success": False, "error": "Database save failed"}), 500
            
            # Step 3: Starte Background-Thread (AI + Chunking + Qdrant)
            logger.info(f"Starting async processing for {doc_id}")
            thread = threading.Thread(target=process_document_async, args=(doc_id, pages_data))
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "data": {
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_count": len(pages_data),
                    "message": "File uploaded successfully. AI processing in background."
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing upload: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            # Optional: Remove temporary file after processing
            # Keeping it for now in case we need to reprocess
            pass
            
    return jsonify({"success": False, "error": "Invalid file type. Only PDF allowed."}), 400

@app.route('/documents', methods=['GET'])
def list_documents():
    """Return a paginated list of documents.

    Query params:
    - page: Page number, 1-indexed (default: 1)
    - limit: Items per page (default: 50, max: 200)
    """
    try:
        # Parse and clamp pagination params
        try:
            page = max(1, int(request.args.get('page', 1)))
            limit = min(max(1, int(request.args.get('limit', 50))), 200)
        except ValueError:
            page = 1
            limit = 50

        skip = (page - 1) * limit
        total = db.get_document_count()
        docs = db.get_all_documents(limit=limit, skip=skip)

        import math
        total_pages = math.ceil(total / limit) if limit else 1

        return jsonify({
            "success": True,
            "data": docs,
            "pagination": {
                "total": total,
                "page": page,
                "pages": total_pages,
                "limit": limit
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>/status', methods=['GET'])
def get_document_status(doc_id):
    try:
        status = db.get_document_status(doc_id)
        if not status:
            return jsonify({"success": False, "error": "Document not found"}), 404
        return jsonify({"success": True, "data": status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>/structured', methods=['GET'])
def get_document_structured(doc_id):
    try:
        # Generate the unified structure
        structured_doc = db.create_document_structure(doc_id)
        if not structured_doc:
             # Fallback to check if document exists at all
             details = db.get_document_details(doc_id)
             if not details:
                 return jsonify({"success": False, "error": "Document not found"}), 404
             else:
                 return jsonify({"success": False, "error": "Could not create structure (maybe processing not done?)"}), 500
        
        return jsonify({"success": True, "data": structured_doc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """
    Delete a document and all associated data (pages, PDF file, metadata, Qdrant chunks).
    """
    try:
        success = db.delete_document(doc_id)
        if success:
            # Auch Qdrant-Chunks löschen (sonst verwaiste Vektoren)
            if qdrant_manager.is_connected():
                qdrant_manager.delete_document(doc_id)
            return jsonify({"success": True, "data": {"doc_id": doc_id}})
        else:
            return jsonify({"success": False, "error": "Document not found or could not be deleted"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/search', methods=['GET'])
def search_documents():
    """
    Search documents by keyword.
    
    Query params:
    - q: Search query string (required)
    - limit: Maximum number of results (optional, default: 20)
    
    Example: /search?q=invoice&limit=10
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Query parameter 'q' is required"}), 400
    
    try:
        limit = int(request.args.get('limit', 20))
        limit = min(limit, 100)  # Cap at 100 results
    except ValueError:
        limit = 20
    
    try:
        results = db.search_documents(query, limit=limit)
        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "count": len(results),
                "results": results
            }
        })
    except Exception as e:
        logger.error(f"Error in search endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>/download', methods=['GET'])
def download_pdf(doc_id):
    """
    Download the original PDF file for a document.
    Returns 404 if document or PDF file doesn't exist.
    """
    try:
        # Get document metadata
        doc_details = db.get_document_details(doc_id)
        if not doc_details:
            return jsonify({"success": False, "error": "Document not found"}), 404
        
        pdf_file_id = doc_details.get("pdf_file_id")
        if not pdf_file_id:
            return jsonify({"success": False, "error": "Original PDF file not available"}), 404
        
        # Retrieve PDF from GridFS
        pdf_file = db.get_pdf_file(pdf_file_id)
        if not pdf_file:
            return jsonify({"success": False, "error": "PDF file not found in storage"}), 404
        
        # Send file to user
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=doc_details.get("filename", "document.pdf")
        )
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """
    RAG-Endpunkt: Beantwortet Fragen zu Dokumenten oder der gesamten Datenbank.
    
    Erwartet JSON:
    {
        "doc_ids": ["id1", "id2"],  // Liste von Dokument-IDs (Cross-Document)
        "doc_id": "single_id",      // Rückwärtskompatibel: einzelne ID
        "question": "Was ist der Gesamtbetrag der Rechnung?"
    }
    """
    data = request.json
    if not data or 'question' not in data:
        return jsonify({"success": False, "error": "Missing 'question' in request body"}), 400
        
    question = data['question'].strip()
    if not question:
        return jsonify({"success": False, "error": "Empty question"}), 400
        
    # Cross-Document: Akzeptiere doc_ids (Liste) oder doc_id (String) für Rückwärtskompatibilität
    doc_ids = data.get('doc_ids')  # Neue Variante: Liste von IDs
    if not doc_ids:
        single_id = data.get('doc_id')  # Alte Variante: einzelne ID
        doc_ids = [single_id] if single_id else None
    
    if not qdrant_manager.is_connected():
        return jsonify({"success": False, "error": "Vektor-Datenbank (Qdrant) ist nicht erreichbar. RAG deaktiviert."}), 503
        
    try:
        # Step 1: Embedding für die Frage erstellen
        logger.info(f"RAG: Frage '{question}' (doc_ids={doc_ids})")
        query_embedding = ai_processor.create_embedding(question)
        
        if not query_embedding:
            return jsonify({"success": False, "error": "Konnte Frage nicht analysieren (Embedding fehlgeschlagen)."}), 500
            
        # Step 2: Ähnliche Chunks aus Qdrant suchen (unterstützt mehrere doc_ids)
        hits = qdrant_manager.search_similar(query_embedding, limit=5, doc_ids=doc_ids)
        
        if not hits:
            return jsonify({
                "success": True, 
                "data": {
                    "question": question,
                    "answer": "Ich konnte keine passenden Textstellen im Dokument finden.",
                    "sources": []
                }
            })
            
        # Step 3: Text aus den Chunks extrahieren
        context_chunks = [hit["text"] for hit in hits]
        
        # Step 4: LLM mit Kontext + Frage aufrufen
        ai_response = ai_processor.ask_question(question, context_chunks)
        answer = ai_response.get("answer", "Fehler beim Abrufen der Antwort.")
        follow_ups = ai_response.get("follow_ups", [])
        
        # Step 5: Quellen aufbereiten für UI
        sources = []
        for hit in hits:
            sources.append({
                "page_num": hit.get("page_num"),
                "score": hit.get("score"),
                "text": hit.get("text"),
                "preview": hit.get("text")[:100] + "..." if len(hit.get("text", "")) > 100 else hit.get("text"),
            })
            
        return jsonify({
            "success": True,
            "data": {
                "question": question,
                "answer": answer,
                "follow_ups": follow_ups,
                "sources": sources
            }
        })
        
    except Exception as e:
        logger.error(f"Error in /ask endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/extract', methods=['POST'])
def extract_entities():
    """
    Entity Extraction: Extrahiert strukturierte Daten (Personen, Firmen, Beträge etc.) aus einem Dokument.
    
    Erwartet JSON:
    {
        "doc_id": "document_id",
        "entity_types": ["personen", "firmen", "betraege", "daten", "adressen"]
    }
    """
    data = request.json
    if not data or 'doc_id' not in data:
        return jsonify({"success": False, "error": "Missing 'doc_id' in request body"}), 400

    doc_id = data['doc_id']
    entity_types = data.get('entity_types', [])
    
    if not entity_types:
        return jsonify({"success": False, "error": "Keine Entity-Typen ausgewählt."}), 400

    try:
        # Caching-Logik: Prüfen, was schon vorhanden ist
        existing_entities = db.get_extracted_entities(doc_id)
        
        # Finde heraus, welche Typen wirklich noch fehlen
        missing_types = [et for et in entity_types if et not in existing_entities]
        
        if not missing_types:
            logger.info(f"Entity Extraction für doc_id={doc_id}: Caching Hit (alle {len(entity_types)} Typen vorhanden).")
            # Wir haben bereits alle angeforderten Typen in der DB
            result = {t: existing_entities[t] for t in entity_types}
            return jsonify({
                "success": True,
                "data": {
                    "doc_id": doc_id,
                    "entities": result
                }
            })

        # Kompletten Rohtext aller Seiten laden (NICHT RAG-basiert)
        pages = db.get_raw_text(doc_id)
        if not pages:
            return jsonify({"success": False, "error": "Dokument nicht gefunden oder kein Text vorhanden."}), 404

        # Alle Seiten zusammenfügen
        full_text = "\n\n".join([
            f"--- Seite {p.get('page_num', '?')} ---\n{p.get('raw_text', '')}" 
            for p in pages if p.get('raw_text')
        ])

        if not full_text.strip():
            return jsonify({"success": False, "error": "Dokument enthält keinen extrahierbaren Text."}), 400

        logger.info(f"Entity Extraction für doc_id={doc_id}: {len(full_text)} Zeichen, Typen={missing_types} (fehlend)")

        # KI-Extraktion nur für fehlende Typen
        new_result = ai_processor.extract_entities(full_text, missing_types)

        if "error" in new_result:
            return jsonify({"success": False, "error": new_result["error"]}), 500

        # Mische alte und neue Ergebnisse
        combined_result = {**existing_entities, **new_result}
        
        # Speichere die neuen Ergebnisse kumulativ in der Datenbank
        db.save_extracted_entities(doc_id, combined_result)

        # Gib nur die vom User ursprünglich *angefragten* Typen zurück
        final_return = {t: combined_result.get(t, []) for t in entity_types}

        return jsonify({
            "success": True,
            "data": {
                "doc_id": doc_id,
                "entities": final_return
            }
        })

    except Exception as e:
        logger.error(f"Error in /extract endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Validate API Key on startup
    if not os.getenv("OPENAI_API_KEY"):
         print("\nCRITICAL WARNING: OPENAI_API_KEY not found in environment variables.")
         print("Please create a .env file based on .env.example\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
