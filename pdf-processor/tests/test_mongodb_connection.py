#!/usr/bin/env python
"""
MongoDB Connection Test Script
Tests database connectivity, GridFS storage, and basic operations.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for module imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}Test: {name}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")

def print_success(message):
    try:
        print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")

def print_error(message):
    try:
        print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.FAIL}[ERROR] {message}{Colors.ENDC}")

def print_info(message):
    try:
        print(f"{Colors.OKCYAN}ℹ {message}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.OKCYAN}[INFO] {message}{Colors.ENDC}")

def print_warning(message):
    try:
        print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.WARNING}[WARNING] {message}{Colors.ENDC}")

def test_imports():
    """Test if all required packages are installed"""
    print_test("Package Imports")
    
    required_packages = {
        'pymongo': 'MongoDB driver',
        'gridfs': 'GridFS support',
        'bson': 'BSON encoding',
        'fitz': 'PyMuPDF for PDF processing',
        'openai': 'OpenAI API client',
        'flask': 'Web framework',
        'dotenv': 'Environment variables'
    }
    
    all_ok = True
    for package, description in required_packages.items():
        try:
            if package == 'fitz':
                import fitz
            elif package == 'dotenv':
                from dotenv import load_dotenv
            else:
                __import__(package)
            print_success(f"{package:15} - {description}")
        except ImportError as e:
            print_error(f"{package:15} - NOT INSTALLED ({description})")
            all_ok = False
    
    return all_ok

def test_mongodb_connection():
    """Test MongoDB connection"""
    print_test("MongoDB Connection")
    
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure
        
        # Try to connect
        print_info("Attempting to connect to MongoDB...")
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        
        # Ping the database
        client.admin.command('ping')
        print_success("Successfully connected to MongoDB")
        
        # Get server info
        server_info = client.server_info()
        print_info(f"MongoDB version: {server_info['version']}")
        
        # List databases
        dbs = client.list_database_names()
        print_info(f"Available databases: {', '.join(dbs[:5])}")
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        print_error(f"Failed to connect to MongoDB: {e}")
        print_warning("Make sure MongoDB is running on localhost:27017")
        print_info("Start MongoDB with: docker run -d -p 27017:27017 mongo")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_database_manager():
    """Test DatabaseManager initialization"""
    print_test("Database Manager Initialization")
    
    try:
        from database import MongoDBManager
        
        print_info("Initializing MongoDBManager...")
        db = MongoDBManager(
            uri='mongodb://localhost:27017/',
            db_name='pdf_test_db'
        )
        
        if db.client is None:
            print_error("Database client not initialized")
            return False
        
        print_success("MongoDBManager initialized successfully")
        
        # Check collections
        if db.documents_collection is not None:
            print_success("documents collection initialized")
        if db.pages_collection is not None:
            print_success("pages collection initialized")
        if db.fs is not None:
            print_success("GridFS initialized")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to initialize DatabaseManager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gridfs_storage(pdf_path):
    """Test GridFS file storage"""
    print_test("GridFS Storage Test")
    
    if not Path(pdf_path).exists():
        print_warning(f"Test PDF not found: {pdf_path}")
        print_info("Skipping GridFS test")
        return False
    
    try:
        from database import MongoDBManager
        import gridfs
        
        db = MongoDBManager(
            uri='mongodb://localhost:27017/',
            db_name='pdf_test_db'
        )
        
        # Store file in GridFS
        print_info(f"Uploading file to GridFS: {Path(pdf_path).name}")
        with open(pdf_path, 'rb') as f:
            file_id = db.fs.put(
                f,
                filename=Path(pdf_path).name,
                content_type='application/pdf',
                metadata={'test': True, 'uploaded_at': datetime.utcnow()}
            )
        
        print_success(f"File stored in GridFS with ID: {file_id}")
        
        # Retrieve file
        print_info("Retrieving file from GridFS...")
        grid_out = db.fs.get(file_id)
        file_size = len(grid_out.read())
        print_success(f"File retrieved successfully ({file_size} bytes)")
        
        # Check metadata
        print_info(f"Filename: {grid_out.filename}")
        print_info(f"Content-Type: {grid_out.content_type}")
        print_info(f"Upload date: {grid_out.upload_date}")
        
        # Clean up
        print_info("Cleaning up test file...")
        db.fs.delete(file_id)
        print_success("Test file deleted from GridFS")
        
        return True
        
    except Exception as e:
        print_error(f"GridFS test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pdf_processing(pdf_path):
    """Test PDF text extraction"""
    print_test("PDF Processing Test")
    
    if not Path(pdf_path).exists():
        print_warning(f"Test PDF not found: {pdf_path}")
        print_info("Skipping PDF processing test")
        return False
    
    try:
        from pdf_processor import PDFProcessor
        
        processor = PDFProcessor()
        
        print_info(f"Extracting text from: {Path(pdf_path).name}")
        pages_data = processor.extract_text_from_pdf(pdf_path)
        
        if not pages_data:
            print_error("No pages extracted")
            return False
        
        print_success(f"Extracted {len(pages_data)} pages")
        
        # Show sample from first page
        if len(pages_data) > 0:
            first_page = pages_data[0]
            print_info(f"Page 1 text length: {first_page['text_length']} characters")
            if first_page['text_length'] > 0:
                sample = first_page['raw_text'][:200].replace('\n', ' ')
                print_info(f"Sample text: {sample}...")
        
        return True
        
    except Exception as e:
        print_error(f"PDF processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_workflow(pdf_path):
    """Test complete workflow: PDF upload, storage, and data saving"""
    print_test("Full Workflow Test")
    
    if not Path(pdf_path).exists():
        print_warning(f"Test PDF not found: {pdf_path}")
        print_info("Skipping full workflow test")
        return False
    
    try:
        from database import MongoDBManager
        from pdf_processor import PDFProcessor
        
        # Initialize
        db = MongoDBManager(
            uri='mongodb://localhost:27017/',
            db_name='pdf_test_db'
        )
        processor = PDFProcessor()
        
        # Extract text
        print_info("Step 1: Extracting text from PDF...")
        pages_data = processor.extract_text_from_pdf(pdf_path)
        print_success(f"Extracted {len(pages_data)} pages")
        
        # Save to database with GridFS
        print_info("Step 2: Saving to MongoDB with GridFS...")
        doc_id = db.save_pdf_with_pages(
            pdf_path=pdf_path,
            filename=Path(pdf_path).name,
            pages_data=pages_data
        )
        
        if not doc_id:
            print_error("Failed to save document")
            return False
        
        print_success(f"Document saved with ID: {doc_id}")
        
        # Verify document
        print_info("Step 3: Verifying saved data...")
        doc_details = db.get_document_details(doc_id)
        
        if not doc_details:
            print_error("Failed to retrieve document")
            return False
        
        print_success("✓ Document metadata retrieved")
        print_info(f"  Filename: {doc_details['filename']}")
        print_info(f"  Total pages: {doc_details['total_pages']}")
        print_info(f"  PDF file ID: {doc_details.get('pdf_file_id', 'N/A')}")
        print_info(f"  Pages in DB: {len(doc_details.get('pages', []))}")
        
        # Verify GridFS file
        if doc_details.get('pdf_file_id'):
            print_info("Step 4: Verifying GridFS storage...")
            pdf_file = db.get_pdf_file(doc_details['pdf_file_id'])
            if pdf_file:
                print_success("✓ Original PDF file accessible in GridFS")
            else:
                print_error("✗ PDF file not found in GridFS")
        
        # Clean up
        print_info("Step 5: Cleaning up test data...")
        if db.delete_document(doc_id):
            print_success("Test document deleted successfully")
        
        return True
        
    except Exception as e:
        print_error(f"Full workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_text_indexes():
    """Test MongoDB text indexes for search"""
    print_test("Text Index Test")
    
    try:
        from database import MongoDBManager
        
        db = MongoDBManager(
            uri='mongodb://localhost:27017/',
            db_name='pdf_test_db'
        )
        
        # Get indexes
        print_info("Checking text indexes on pages collection...")
        indexes = list(db.pages_collection.list_indexes())
        
        text_index_found = False
        for index in indexes:
            if 'textIndexVersion' in index:
                text_index_found = True
                print_success("Text index found")
                print_info(f"  Index name: {index['name']}")
                print_info(f"  Index keys: {index['key']}")
        
        if not text_index_found:
            print_warning("No text index found - search may not work optimally")
            print_info("Text index should be created automatically on first run")
        
        return True
        
    except Exception as e:
        print_error(f"Index test failed: {e}")
        return False

def test_openai_connection():
    """Test OpenAI API connection"""
    print_test("OpenAI API Connection")
    
    try:
        from dotenv import load_dotenv
        import openai
        
        # Load environment variables
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            print_error("OPENAI_API_KEY not found in environment")
            print_warning("AI processing will fail without API key")
            print_info("Set OPENAI_API_KEY in .env file")
            return False
        
        print_info("API key found in environment")
        print_info(f"Key preview: {api_key[:10]}...{api_key[-4:]}")
        
        # Try to create client
        try:
            client = openai.OpenAI(api_key=api_key)
            print_success("OpenAI client created successfully")
            
            # Optional: Test with a simple API call (costs money, so commented out)
            # print_info("Testing API call (this will use tokens)...")
            # response = client.chat.completions.create(
            #     model="gpt-3.5-turbo",
            #     messages=[{"role": "user", "content": "Say 'test'"}],
            #     max_tokens=5
            # )
            # print_success("API call successful")
            
            return True
        except Exception as e:
            print_error(f"Failed to create OpenAI client: {e}")
            print_warning("Check if API key is valid")
            return False
        
    except Exception as e:
        print_error(f"OpenAI test failed: {e}")
        return False

def run_all_tests(pdf_path=None):
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("="*70)
    print("MongoDB Connection & System Test Suite")
    print("="*70)
    print(Colors.ENDC)
    
    if pdf_path:
        print_info(f"Test PDF: {pdf_path}")
    else:
        print_warning("No test PDF provided - some tests will be skipped")
    
    results = {}
    
    # Test 1: Package imports
    results['imports'] = test_imports()
    
    # Test 2: MongoDB connection
    results['mongodb'] = test_mongodb_connection()
    
    if not results['mongodb']:
        print_error("\n⚠ MongoDB not available - skipping database tests")
        print_info("Start MongoDB with: docker run -d -p 27017:27017 mongo")
    else:
        # Test 3: Database manager
        results['db_manager'] = test_database_manager()
        
        # Test 4: Text indexes
        results['indexes'] = test_text_indexes()
        
        if pdf_path:
            # Test 5: PDF processing
            results['pdf_processing'] = test_pdf_processing(pdf_path)
            
            # Test 6: GridFS storage
            results['gridfs'] = test_gridfs_storage(pdf_path)
            
            # Test 7: Full workflow
            results['workflow'] = test_full_workflow(pdf_path)
    
    # Test 8: OpenAI connection
    results['openai'] = test_openai_connection()
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("="*70)
    print("Test Summary")
    print("="*70)
    print(Colors.ENDC)
    
    for test_name, result in results.items():
        test_display = test_name.replace('_', ' ').title()
        if result is True:
            try:
                status = f"{Colors.OKGREEN}✓ PASSED{Colors.ENDC}"
            except:
                status = f"{Colors.OKGREEN}PASSED{Colors.ENDC}"
        elif result is False:
            try:
                status = f"{Colors.FAIL}✗ FAILED{Colors.ENDC}"
            except:
                status = f"{Colors.FAIL}FAILED{Colors.ENDC}"
        else:
            try:
                status = f"{Colors.WARNING}⊘ SKIPPED{Colors.ENDC}"
            except:
                status = f"{Colors.WARNING}SKIPPED{Colors.ENDC}"
        
        try:
            print(f"{test_display:25} {status}")
        except UnicodeEncodeError:
            # Fallback for Windows console encoding issues
            if result is True:
                print(f"{test_display:25} {Colors.OKGREEN}PASSED{Colors.ENDC}")
            elif result is False:
                print(f"{test_display:25} {Colors.FAIL}FAILED{Colors.ENDC}")
            else:
                print(f"{test_display:25} {Colors.WARNING}SKIPPED{Colors.ENDC}")
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    total = len(results)
    
    print(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed, {total - passed - failed} skipped{Colors.ENDC}")
    
    # Recommendations
    print(f"\n{Colors.BOLD}Recommendations:{Colors.ENDC}")
    
    if not results.get('mongodb'):
        print_warning("• Start MongoDB server")
    
    if not results.get('openai'):
        print_warning("• Configure OPENAI_API_KEY in .env file")
    
    if not results.get('imports'):
        print_warning("• Install missing packages: pip install -r requirements.txt")
    
    if all(v is True for v in results.values()):
        print_success("All tests passed! System is ready to use.")
    
    print()
    return results

if __name__ == "__main__":
    # Get PDF path from command line or use default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Try default test PDF
        default_pdf = "uploads/Leitfaden-Genehmigungsverfahren-2020.pdf"
        if Path(default_pdf).exists():
            pdf_path = default_pdf
        else:
            pdf_path = None
    
    results = run_all_tests(pdf_path)
    
    # Exit with appropriate code
    failed = sum(1 for v in results.values() if v is False)
    sys.exit(0 if failed == 0 else 1)

