#!/usr/bin/env python
"""
Test Workflow - Keep Data Version
This test uploads PDF and keeps data in MongoDB for inspection.
Does NOT delete data after testing.
"""

import sys
import os
from pathlib import Path
import time

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, '.env'))

from database import MongoDBManager
from pdf_processor import PDFProcessor
from ai_processor import AIProcessor

# Colors
class Colors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_success(text):
    try:
        print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")
    except:
        print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")

def print_info(text):
    try:
        print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
    except:
        print(f"{Colors.CYAN}[INFO] {text}{Colors.ENDC}")

def print_warning(text):
    try:
        print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")
    except:
        print(f"{Colors.WARNING}[WARNING] {text}{Colors.ENDC}")

def main():
    print(f"\n{Colors.BOLD}PDF Upload Test - Data Will Be Kept{Colors.ENDC}")
    print("="*80)
    print()
    
    test_pdf = os.path.join(parent_dir, '..', 'uploads', 'Leitfaden-Genehmigungsverfahren-2020.pdf')
    
    if not os.path.exists(test_pdf):
        print(f"Error: Test PDF not found at {test_pdf}")
        return None
    
    # Step 1: Extract text
    print_info("Step 1: Extracting text from PDF...")
    processor = PDFProcessor(use_ocrmypdf=True)
    pages_data = processor.extract_text_from_pdf(test_pdf)
    print_success(f"Extracted {len(pages_data)} pages")
    print()
    
    # Step 2: Save to database
    print_info("Step 2: Saving to MongoDB with GridFS...")
    db = MongoDBManager(
        uri=os.getenv('MONGO_URI', 'mongodb://localhost:27017/'),
        db_name='pdf_intelligence_db'  # Use production DB name
    )
    
    doc_id = db.save_pdf_with_pages(
        pdf_path=test_pdf,
        filename='Leitfaden-Genehmigungsverfahren-2020.pdf',
        pages_data=pages_data
    )
    
    if not doc_id:
        print("Error: Failed to save to database")
        return None
    
    print_success(f"Document saved with ID: {doc_id}")
    print()
    
    # Step 3: Verify data
    print_info("Step 3: Verifying data in MongoDB...")
    
    # Check documents collection
    doc_details = db.get_document_details(doc_id)
    if doc_details:
        print_success(f"Document found in 'documents' collection")
        print(f"  - Filename: {doc_details['filename']}")
        print(f"  - Total pages: {doc_details['total_pages']}")
        print(f"  - PDF file ID: {doc_details.get('pdf_file_id')}")
        print(f"  - Status: {doc_details.get('status')}")
    
    # Check pages collection
    pages = db.get_raw_text(doc_id)
    print_success(f"Found {len(pages)} pages in 'pages' collection")
    if len(pages) > 0:
        first_page = pages[0]
        print(f"  - Page 1 text length: {first_page['text_length']} characters")
        print(f"  - Page 1 sample: {first_page['raw_text'][:100]}...")
    print()
    
    # Step 4: Test search
    print_info("Step 4: Testing search functionality...")
    search_results = db.search_documents("Genehmigung", limit=5)
    print_success(f"Search found {len(search_results)} results")
    if len(search_results) > 0:
        print(f"  - Top result: Page {search_results[0]['page_num']} (score: {search_results[0].get('search_score', 0):.2f})")
    print()
    
    # Step 5: Show database inspection commands
    print_info("Step 5: Inspect data in MongoDB")
    print()
    print(f"{Colors.BOLD}MongoDB Inspection Commands:{Colors.ENDC}")
    print()
    print("# Connect to MongoDB:")
    print("mongosh")
    print()
    print("# Switch to database:")
    print("use pdf_intelligence_db")
    print()
    print("# List collections:")
    print("show collections")
    print()
    print("# Count documents:")
    print("db.documents.countDocuments()")
    print("db.pages.countDocuments()")
    print("db.fs.files.countDocuments()")
    print("db.fs.chunks.countDocuments()")
    print()
    print("# View document metadata:")
    print(f"db.documents.findOne({{doc_id: \"{doc_id}\"}})")
    print()
    print("# View first page:")
    print(f"db.pages.findOne({{doc_id: \"{doc_id}\", page_num: 1}})")
    print()
    print("# View GridFS file info:")
    print("db.fs.files.find().pretty()")
    print()
    print("# Search test:")
    print('db.pages.find({$text: {$search: "Genehmigung"}}).limit(3)')
    print()
    
    print_warning("Data has been KEPT in database for inspection!")
    print_info(f"Document ID: {doc_id}")
    print()
    
    # Show how to delete if needed
    print(f"{Colors.BOLD}To delete this test data later:{Colors.ENDC}")
    print(f"python -c \"from database import MongoDBManager; db = MongoDBManager(db_name='pdf_intelligence_db'); db.delete_document('{doc_id}')\"")
    print()
    
    return doc_id

if __name__ == "__main__":
    doc_id = main()
    
    if doc_id:
        print_success("Test completed! Data kept in MongoDB for inspection.")
        print()
        print(f"{Colors.BOLD}Next steps:{Colors.ENDC}")
        print("1. Open mongosh and run the commands above")
        print("2. Or start the web app: python app.py")
        print("3. View documents at: http://localhost:5000")
        print()
    else:
        print("Test failed. Please check errors above.")
        sys.exit(1)

