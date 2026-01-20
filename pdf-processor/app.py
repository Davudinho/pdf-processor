import os
from flask import Flask, request, jsonify, render_template, abort
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import logging

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

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize components
db = MongoDBManager(uri=app.config['MONGO_URI'], db_name=app.config['DB_NAME'])
pdf_processor = PDFProcessor()
ai_processor = AIProcessor()

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
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
            
            # 1. Process PDF (Extract Text)
            logger.info(f"Processing PDF: {filename}")
            pages_data = pdf_processor.extract_text_from_pdf(filepath)
            
            # 2. Save extracted text to MongoDB
            doc_id = db.save_pdf_pages(filename, pages_data)
            
            if not doc_id:
                return jsonify({"success": False, "error": "Database save failed"}), 500
            
            # 3. Trigger AI Structure (Synchronously for MVP)
            # In a real production app, this should be a background task (Celery/RQ)
            logger.info(f"Starting AI structuring for {doc_id}")
            ai_processor.process_document(db, doc_id)
            
            return jsonify({
                "success": True,
                "data": {
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_count": len(pages_data),
                    "message": "File processed and structured successfully"
                }
            })
            
        except Exception as e:
            logger.error(f"Error processing upload: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            # Cleanup uploaded file if desired, or keep it as archive
            # os.remove(filepath)
            pass
            
    return jsonify({"success": False, "error": "Invalid file type"}), 400

@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        docs = db.get_all_documents()
        return jsonify({"success": True, "data": docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>', methods=['GET'])
def get_document(doc_id):
    try:
        details = db.get_document_details(doc_id)
        if not details:
            return jsonify({"success": False, "error": "Document not found"}), 404
        return jsonify({"success": True, "data": details})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    try:
        success = db.delete_document(doc_id)
        if success:
            return jsonify({"success": True, "data": {"doc_id": doc_id}})
        else:
            return jsonify({"success": False, "error": "Document not found or could not be deleted"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
