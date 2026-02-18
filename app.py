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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads/')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
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

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_document_async(doc_id):
    """Background task to process document with AI."""
    logger.info(f"Background thread started for doc_id: {doc_id}")
    try:
        # Use app context in case we need access to app config or similar in future
        with app.app_context():
            ai_processor.process_document(db, doc_id)
    except Exception as e:
        logger.error(f"Error in background processing for {doc_id}: {e}")

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

            # Step 2: Save PDF file + extracted text to MongoDB (with GridFS)
            logger.info(f"Saving to database with GridFS...")
            doc_id = db.save_pdf_with_pages(filepath, filename, pages_data)
            
            if not doc_id:
                return jsonify({"success": False, "error": "Database save failed"}), 500
            
            # Step 3: Trigger AI processing (async)
            logger.info(f"Starting async AI processing for {doc_id}")
            thread = threading.Thread(target=process_document_async, args=(doc_id,))
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
    try:
        docs = db.get_all_documents()
        return jsonify({"success": True, "data": docs})
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
    Delete a document and all associated data (pages, PDF file, metadata).
    """
    try:
        success = db.delete_document(doc_id)
        if success:
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

if __name__ == '__main__':
    # Validate API Key on startup
    if not os.getenv("OPENAI_API_KEY"):
         print("\nCRITICAL WARNING: OPENAI_API_KEY not found in environment variables.")
         print("Please create a .env file based on .env.example\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
