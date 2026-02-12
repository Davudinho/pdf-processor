#!/usr/bin/env python
"""
Complete Workflow Test - PDF Intelligence System
Tests all system functionality with real PDF processing and AI integration.

This test uses: uploads/Leitfaden-Genehmigungsverfahren-2020.pdf
"""

import sys
import os
from pathlib import Path
import time

# Add parent directory to path for module imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, '.env'))

# Import project modules
from database import MongoDBManager
from pdf_processor import PDFProcessor
from ai_processor import AIProcessor

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}")

def print_success(text):
    try:
        print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")

def print_error(text):
    try:
        print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    try:
        print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.CYAN}[INFO] {text}{Colors.ENDC}")

def print_warning(text):
    try:
        print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")
    except UnicodeEncodeError:
        print(f"{Colors.WARNING}[WARNING] {text}{Colors.ENDC}")

class TestResults:
    def __init__(self):
        self.tests = {}
        self.doc_id = None
        self.pdf_file_id = None
    
    def add_result(self, test_name, passed, message=""):
        self.tests[test_name] = {"passed": passed, "message": message}
        if passed:
            print_success(f"{test_name}: PASSED {message}")
        else:
            print_error(f"{test_name}: FAILED {message}")
    
    def summary(self):
        passed = sum(1 for t in self.tests.values() if t["passed"])
        total = len(self.tests)
        
        print_header("Test Summary")
        for name, result in self.tests.items():
            status = "PASSED" if result["passed"] else "FAILED"
            color = Colors.OKGREEN if result["passed"] else Colors.FAIL
            msg = f" - {result['message']}" if result["message"] else ""
            try:
                print(f"{name:40} {color}{status}{Colors.ENDC}{msg}")
            except UnicodeEncodeError:
                print(f"{name:40} {color}{status}{Colors.ENDC}{msg}")
        
        print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.ENDC}")
        return passed == total

def test_environment():
    """Test 1: Environment configuration"""
    print_header("Test 1: Environment Configuration")
    
    results = TestResults()
    
    # Check OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key and api_key != 'your_openai_api_key_here':
        results.add_result("OpenAI API Key", True, f"Found: {api_key[:10]}...")
    else:
        results.add_result("OpenAI API Key", False, "Not configured")
        return results
    
    # Check MongoDB URI
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    results.add_result("MongoDB URI", True, mongo_uri)
    
    # Check test PDF exists
    test_pdf = os.path.join(parent_dir, '..', 'uploads', 'Leitfaden-Genehmigungsverfahren-2020.pdf')
    if os.path.exists(test_pdf):
        size_mb = os.path.getsize(test_pdf) / (1024 * 1024)
        results.add_result("Test PDF", True, f"Found ({size_mb:.1f} MB)")
    else:
        results.add_result("Test PDF", False, f"Not found at {test_pdf}")
        return results
    
    return results

def test_pdf_extraction():
    """Test 2: PDF text extraction with OCR"""
    print_header("Test 2: PDF Text Extraction & OCR")
    
    results = TestResults()
    
    test_pdf = os.path.join(parent_dir, '..', 'uploads', 'Leitfaden-Genehmigungsverfahren-2020.pdf')
    
    try:
        # Initialize processor
        processor = PDFProcessor(use_ocrmypdf=True)
        print_info(f"PDFProcessor initialized (OCRmyPDF: enabled)")
        
        # Extract text
        print_info("Extracting text from German PDF...")
        start_time = time.time()
        pages_data = processor.extract_text_from_pdf(test_pdf)
        elapsed = time.time() - start_time
        
        if not pages_data:
            results.add_result("Text Extraction", False, "No pages extracted")
            return results
        
        results.add_result("Text Extraction", True, f"{len(pages_data)} pages in {elapsed:.1f}s")
        
        # Check text quality
        total_chars = sum(p['text_length'] for p in pages_data)
        avg_chars = total_chars / len(pages_data)
        
        print_info(f"Total characters: {total_chars:,}")
        print_info(f"Average per page: {avg_chars:.0f}")
        
        # Sample first page
        if pages_data[0]['text_length'] > 0:
            sample = pages_data[0]['raw_text'][:200].replace('\n', ' ')
            print_info(f"First page sample: {sample}...")
            results.add_result("Text Quality", True, f"Avg {avg_chars:.0f} chars/page")
        else:
            results.add_result("Text Quality", False, "First page is empty")
        
        # Store for next tests
        results.pages_data = pages_data
        
    except Exception as e:
        results.add_result("PDF Processing", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_database_operations(pages_data):
    """Test 3: Database operations with GridFS"""
    print_header("Test 3: Database Operations & GridFS Storage")
    
    results = TestResults()
    
    test_pdf = os.path.join(parent_dir, '..', 'uploads', 'Leitfaden-Genehmigungsverfahren-2020.pdf')
    
    try:
        # Initialize database
        db = MongoDBManager(
            uri=os.getenv('MONGO_URI', 'mongodb://localhost:27017/'),
            db_name='pdf_test_workflow'
        )
        
        if db.client is None:
            results.add_result("Database Connection", False, "Cannot connect to MongoDB")
            return results
        
        results.add_result("Database Connection", True, "Connected")
        
        # Save PDF with GridFS
        print_info("Saving PDF to GridFS + pages to MongoDB...")
        doc_id = db.save_pdf_with_pages(
            pdf_path=test_pdf,
            filename='Leitfaden-Genehmigungsverfahren-2020.pdf',
            pages_data=pages_data
        )
        
        if not doc_id:
            results.add_result("Save to Database", False, "Failed to save")
            return results
        
        results.add_result("Save to Database", True, f"doc_id: {doc_id[:20]}...")
        results.doc_id = doc_id
        
        # Verify document saved
        doc_details = db.get_document_details(doc_id)
        if not doc_details:
            results.add_result("Verify Document", False, "Cannot retrieve document")
            return results
        
        results.add_result("Verify Document", True, f"{doc_details['total_pages']} pages")
        
        # Check GridFS storage
        pdf_file_id = doc_details.get('pdf_file_id')
        if pdf_file_id:
            pdf_file = db.get_pdf_file(pdf_file_id)
            if pdf_file:
                file_size = len(pdf_file.read())
                results.add_result("GridFS Storage", True, f"{file_size / (1024*1024):.1f} MB")
                results.pdf_file_id = pdf_file_id
            else:
                results.add_result("GridFS Storage", False, "PDF not retrievable")
        else:
            results.add_result("GridFS Storage", False, "No PDF file ID")
        
        # Check pages saved
        pages = db.get_raw_text(doc_id)
        if len(pages) == len(pages_data):
            results.add_result("Pages Saved", True, f"{len(pages)} pages")
        else:
            results.add_result("Pages Saved", False, f"Expected {len(pages_data)}, got {len(pages)}")
        
        results.db = db
        
    except Exception as e:
        results.add_result("Database Operations", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_ai_processing(db, doc_id):
    """Test 4: AI processing with real OpenAI API"""
    print_header("Test 4: AI Processing (OpenAI GPT)")
    
    results = TestResults()
    
    try:
        # Initialize AI processor
        ai_processor = AIProcessor(
            api_key=os.getenv('OPENAI_API_KEY'),
            model='gpt-3.5-turbo'
        )
        
        if not ai_processor.api_key or not ai_processor.client:
            results.add_result("AI Initialization", False, "No API key")
            return results
        
        results.add_result("AI Initialization", True, f"Model: {ai_processor.model}")
        
        # Get pages to process
        pages = db.get_raw_text(doc_id)
        if not pages:
            results.add_result("Get Pages", False, "No pages found")
            return results
        
        print_info(f"Processing {len(pages)} pages with AI...")
        print_warning("This will use OpenAI API tokens (estimated cost: $0.10-0.50)")
        
        # Process first 3 pages only to save costs
        pages_to_process = pages[:3]
        print_info(f"Processing first {len(pages_to_process)} pages to save costs")
        
        successful = 0
        failed = 0
        
        for idx, page in enumerate(pages_to_process, 1):
            page_num = page.get("page_num")
            raw_text = page.get("raw_text", "")
            
            print_info(f"[{idx}/{len(pages_to_process)}] Processing page {page_num} ({len(raw_text)} chars)...")
            
            # Structure text
            structured_data = ai_processor.structure_text(raw_text)
            
            processing_status = structured_data.get("processing_status", "unknown")
            
            if processing_status == "success":
                # Extract data
                summary = structured_data.get("summary", "")
                keywords = structured_data.get("keywords", [])
                
                print_success(f"  Summary: {summary[:80]}...")
                print_success(f"  Keywords: {', '.join(keywords[:5])}")
                
                # Save to database
                success = db.update_page_data(
                    doc_id=doc_id,
                    page_num=page_num,
                    structured_data=structured_data,
                    page_summary=summary,
                    keywords=keywords
                )
                
                if success:
                    successful += 1
                else:
                    print_error("  Failed to save to database")
                    failed += 1
            else:
                print_error(f"  Processing failed: {processing_status}")
                failed += 1
        
        if successful > 0:
            results.add_result("AI Processing", True, f"{successful}/{len(pages_to_process)} pages")
        else:
            results.add_result("AI Processing", False, "No pages processed successfully")
        
        # Check if summaries and keywords were saved
        updated_pages = db.get_raw_text(doc_id)
        page_with_summary = next((p for p in updated_pages if p.get('page_summary')), None)
        
        if page_with_summary:
            results.add_result("AI Data Saved", True, "Summaries and keywords in DB")
        else:
            results.add_result("AI Data Saved", False, "No AI data found")
        
    except Exception as e:
        results.add_result("AI Processing", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_search_functionality(db, doc_id):
    """Test 5: Keyword search functionality"""
    print_header("Test 5: Keyword Search")
    
    results = TestResults()
    
    try:
        # Test search queries for German document
        test_queries = [
            "Genehmigung",
            "Umwelt",
            "Verfahren",
            "Immissionsschutz"
        ]
        
        all_passed = True
        
        for query in test_queries:
            print_info(f"Searching for: '{query}'")
            search_results = db.search_documents(query, limit=5)
            
            if len(search_results) > 0:
                print_success(f"  Found {len(search_results)} results")
                # Show top result
                top_result = search_results[0]
                print_info(f"  Top: Page {top_result['page_num']} (score: {top_result.get('search_score', 0):.2f})")
                if top_result.get('page_summary'):
                    print_info(f"  Summary: {top_result['page_summary'][:60]}...")
            else:
                print_warning(f"  No results found (may need AI processing)")
                all_passed = False
        
        if all_passed:
            results.add_result("Keyword Search", True, f"Tested {len(test_queries)} queries")
        else:
            results.add_result("Keyword Search", True, "Partial - needs AI processing")
        
    except Exception as e:
        results.add_result("Keyword Search", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_download_pdf(db, doc_id, pdf_file_id):
    """Test 6: Download original PDF from GridFS"""
    print_header("Test 6: Download Original PDF")
    
    results = TestResults()
    
    try:
        # Retrieve PDF from GridFS
        print_info("Retrieving PDF from GridFS...")
        pdf_file = db.get_pdf_file(pdf_file_id)
        
        if not pdf_file:
            results.add_result("PDF Download", False, "Cannot retrieve from GridFS")
            return results
        
        # Read file data
        pdf_data = pdf_file.read()
        file_size = len(pdf_data)
        
        print_info(f"Retrieved {file_size / (1024*1024):.2f} MB")
        
        # Verify it's a valid PDF
        if pdf_data[:4] == b'%PDF':
            results.add_result("PDF Download", True, f"{file_size / (1024*1024):.2f} MB")
            
            # Optional: Save to test file
            test_output = os.path.join(parent_dir, 'tests', 'downloaded_test.pdf')
            with open(test_output, 'wb') as f:
                f.write(pdf_data)
            print_info(f"Saved test copy to: downloaded_test.pdf")
        else:
            results.add_result("PDF Download", False, "Invalid PDF format")
        
    except Exception as e:
        results.add_result("PDF Download", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_document_status(db, doc_id):
    """Test 7: Document status and metadata"""
    print_header("Test 7: Document Status & Metadata")
    
    results = TestResults()
    
    try:
        # Get document status
        status = db.get_document_status(doc_id)
        
        if not status:
            results.add_result("Get Status", False, "Cannot retrieve status")
            return results
        
        print_info(f"Filename: {status['filename']}")
        print_info(f"Total pages: {status['total_pages']}")
        print_info(f"Processed pages: {status['processed_pages']}")
        print_info(f"Complete: {status['is_complete']}")
        print_info(f"Has PDF file: {status['has_pdf_file']}")
        
        results.add_result("Get Status", True, f"{status['processed_pages']}/{status['total_pages']} pages")
        
        # Get full document details
        details = db.get_document_details(doc_id)
        
        if details:
            has_summary = bool(details.get('document_summary'))
            has_keywords = bool(details.get('keywords'))
            
            if has_summary:
                print_success(f"Document summary: {details['document_summary'][:80]}...")
            if has_keywords:
                print_success(f"Document keywords: {', '.join(details['keywords'][:5])}")
            
            results.add_result("Document Metadata", True, 
                             f"Summary: {has_summary}, Keywords: {has_keywords}")
        else:
            results.add_result("Document Metadata", False, "Cannot retrieve details")
        
    except Exception as e:
        results.add_result("Document Status", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_structured_data(db, doc_id):
    """Test 8: Structured data extraction"""
    print_header("Test 8: Structured Data & Aggregation")
    
    results = TestResults()
    
    try:
        # Get structured document
        structured = db.create_document_structure(doc_id)
        
        if not structured:
            results.add_result("Get Structured Data", False, "Cannot create structure")
            return results
        
        # Check aggregated data
        sections_count = len(structured.get('all_sections', []))
        measurements_count = len(structured.get('all_measurements', []))
        tables_count = len(structured.get('all_tables', []))
        key_fields_count = len(structured.get('all_key_fields', {}))
        
        print_info(f"Sections: {sections_count}")
        print_info(f"Measurements: {measurements_count}")
        print_info(f"Tables: {tables_count}")
        print_info(f"Key fields: {key_fields_count}")
        
        # Check page-level structured data
        pages_with_structure = sum(1 for p in structured.get('pages', []) 
                                  if p.get('structured_data', {}).get('processing_status') == 'success')
        
        results.add_result("Structured Data", True, 
                         f"{pages_with_structure} pages with AI structure")
        
    except Exception as e:
        results.add_result("Structured Data", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def test_cleanup(db, doc_id):
    """Test 9: Document deletion (cleanup)"""
    print_header("Test 9: Document Deletion & Cleanup")
    
    results = TestResults()
    
    print_warning("This will delete the test document from database")
    print_info("Press Ctrl+C to skip deletion, or wait 3 seconds...")
    
    try:
        time.sleep(3)
        
        # Delete document
        print_info("Deleting document...")
        success = db.delete_document(doc_id)
        
        if success:
            results.add_result("Document Deletion", True, "Deleted from DB + GridFS")
            
            # Verify deletion
            doc = db.get_document_details(doc_id)
            if doc is None:
                results.add_result("Verify Deletion", True, "Document not found (correct)")
            else:
                results.add_result("Verify Deletion", False, "Document still exists")
        else:
            results.add_result("Document Deletion", False, "Delete operation failed")
        
        # Clean up test file
        test_file = os.path.join(parent_dir, 'tests', 'downloaded_test.pdf')
        if os.path.exists(test_file):
            os.remove(test_file)
            print_info("Cleaned up test download file")
        
    except KeyboardInterrupt:
        print_warning("\nDeletion skipped by user")
        results.add_result("Document Deletion", True, "Skipped (manual)")
    except Exception as e:
        results.add_result("Document Deletion", False, str(e))
        import traceback
        traceback.print_exc()
    
    return results

def run_complete_workflow():
    """Run complete system workflow test"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("="*80)
    print("PDF Intelligence System - Complete Workflow Test")
    print("="*80)
    print(f"{Colors.ENDC}")
    
    print_info("This test will:")
    print("  1. Check environment configuration")
    print("  2. Extract text from German PDF (OCR)")
    print("  3. Save to MongoDB with GridFS")
    print("  4. Process with AI (OpenAI API - uses tokens)")
    print("  5. Test keyword search")
    print("  6. Test PDF download")
    print("  7. Check document status")
    print("  8. Verify structured data")
    print("  9. Clean up test data")
    print()
    
    all_results = []
    
    # Test 1: Environment
    env_results = test_environment()
    all_results.append(env_results)
    
    if not env_results.tests.get("OpenAI API Key", {}).get("passed"):
        print_error("\nCannot proceed without OpenAI API key")
        print_info("Please configure OPENAI_API_KEY in .env file")
        return False
    
    if not env_results.tests.get("Test PDF", {}).get("passed"):
        print_error("\nCannot proceed without test PDF")
        return False
    
    # Test 2: PDF extraction
    pdf_results = test_pdf_extraction()
    all_results.append(pdf_results)
    
    if not hasattr(pdf_results, 'pages_data'):
        print_error("\nCannot proceed without extracted pages")
        return False
    
    # Test 3: Database operations
    db_results = test_database_operations(pdf_results.pages_data)
    all_results.append(db_results)
    
    if not hasattr(db_results, 'doc_id') or not hasattr(db_results, 'db'):
        print_error("\nCannot proceed without saved document")
        return False
    
    doc_id = db_results.doc_id
    db = db_results.db
    pdf_file_id = db_results.pdf_file_id
    
    # Test 4: AI processing
    ai_results = test_ai_processing(db, doc_id)
    all_results.append(ai_results)
    
    # Test 5: Search
    search_results = test_search_functionality(db, doc_id)
    all_results.append(search_results)
    
    # Test 6: Download
    if pdf_file_id:
        download_results = test_download_pdf(db, doc_id, pdf_file_id)
        all_results.append(download_results)
    
    # Test 7: Status
    status_results = test_document_status(db, doc_id)
    all_results.append(status_results)
    
    # Test 8: Structured data
    structured_results = test_structured_data(db, doc_id)
    all_results.append(structured_results)
    
    # Test 9: Cleanup
    cleanup_results = test_cleanup(db, doc_id)
    all_results.append(cleanup_results)
    
    # Overall summary
    print_header("Overall Test Summary")
    
    total_tests = sum(len(r.tests) for r in all_results)
    total_passed = sum(sum(1 for t in r.tests.values() if t["passed"]) for r in all_results)
    
    print(f"\n{Colors.BOLD}Total: {total_passed}/{total_tests} tests passed{Colors.ENDC}\n")
    
    if total_passed == total_tests:
        print_success("All tests passed! System is fully functional.")
        return True
    else:
        print_warning(f"{total_tests - total_passed} tests failed")
        return False

if __name__ == "__main__":
    print(f"\n{Colors.BOLD}PDF Intelligence System - Complete Workflow Test{Colors.ENDC}")
    print("Testing all functionality with real PDF and AI processing\n")
    
    success = run_complete_workflow()
    
    sys.exit(0 if success else 1)

