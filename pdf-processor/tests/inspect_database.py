#!/usr/bin/env python
"""
Inspect MongoDB Database
Shows what data is currently in the database.
"""

import sys
import os
import json

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, '.env'))

from database import MongoDBManager
from bson import json_util

def main():
    print("\n" + "="*80)
    print("MongoDB Database Inspector")
    print("="*80 + "\n")
    
    # Connect to database
    db = MongoDBManager(
        uri=os.getenv('MONGO_URI', 'mongodb://localhost:27017/'),
        db_name='pdf_intelligence_db'
    )
    
    if not db.client:
        print("ERROR: Cannot connect to MongoDB")
        return
    
    print(f"Connected to database: pdf_intelligence_db\n")
    
    # Count collections
    print("=" * 80)
    print("COLLECTION COUNTS")
    print("=" * 80)
    
    doc_count = db.documents_collection.count_documents({})
    page_count = db.pages_collection.count_documents({})
    file_count = db.db['fs.files'].count_documents({})
    chunk_count = db.db['fs.chunks'].count_documents({})
    
    print(f"documents collection:  {doc_count} documents")
    print(f"pages collection:      {page_count} pages")
    print(f"fs.files (GridFS):     {file_count} files")
    print(f"fs.chunks (GridFS):    {chunk_count} chunks")
    print()
    
    if doc_count == 0:
        print("⚠ Database is empty!")
        print()
        print("Run this to upload test data:")
        print("  python test_and_keep_data.py")
        return
    
    # Show documents
    print("=" * 80)
    print("DOCUMENTS")
    print("=" * 80)
    
    documents = list(db.documents_collection.find().sort("created_at", -1).limit(5))
    
    for idx, doc in enumerate(documents, 1):
        print(f"\nDocument {idx}:")
        print(f"  doc_id:           {doc.get('doc_id')}")
        print(f"  filename:         {doc.get('filename')}")
        print(f"  total_pages:      {doc.get('total_pages')}")
        print(f"  pdf_file_id:      {doc.get('pdf_file_id')}")
        print(f"  status:           {doc.get('status')}")
        print(f"  created_at:       {doc.get('created_at')}")
        
        if doc.get('document_summary'):
            print(f"  summary:          {doc.get('document_summary')[:80]}...")
        else:
            print(f"  summary:          (not generated yet)")
        
        if doc.get('keywords'):
            print(f"  keywords:         {', '.join(doc.get('keywords', [])[:5])}")
        else:
            print(f"  keywords:         (not generated yet)")
    
    print()
    
    # Show sample pages
    print("=" * 80)
    print("SAMPLE PAGES (first 3)")
    print("=" * 80)
    
    if doc_count > 0:
        first_doc_id = documents[0].get('doc_id')
        pages = list(db.pages_collection.find({"doc_id": first_doc_id}).sort("page_num", 1).limit(3))
        
        for page in pages:
            print(f"\nPage {page.get('page_num')}:")
            print(f"  text_length:      {page.get('text_length')} characters")
            print(f"  status:           {page.get('status')}")
            
            if page.get('page_summary'):
                print(f"  summary:          {page.get('page_summary')[:60]}...")
            else:
                print(f"  summary:          (not generated yet)")
            
            if page.get('keywords'):
                print(f"  keywords:         {', '.join(page.get('keywords', [])[:5])}")
            else:
                print(f"  keywords:         (not generated yet)")
            
            # Show text sample
            raw_text = page.get('raw_text', '')
            sample = raw_text[:150].replace('\n', ' ')
            print(f"  text_sample:      {sample}...")
    
    print()
    
    # Show GridFS files
    print("=" * 80)
    print("GRIDFS FILES")
    print("=" * 80)
    
    gridfs_files = list(db.db['fs.files'].find().limit(5))
    
    for idx, gf in enumerate(gridfs_files, 1):
        print(f"\nGridFS File {idx}:")
        print(f"  _id:              {gf.get('_id')}")
        print(f"  filename:         {gf.get('filename')}")
        print(f"  length:           {gf.get('length') / (1024*1024):.2f} MB")
        print(f"  uploadDate:       {gf.get('uploadDate')}")
        print(f"  contentType:      {gf.get('contentType')}")
    
    print()
    
    # Test search
    print("=" * 80)
    print("SEARCH TEST")
    print("=" * 80)
    
    search_results = db.search_documents("Genehmigung", limit=3)
    
    print(f"\nSearch for 'Genehmigung': {len(search_results)} results\n")
    
    for idx, result in enumerate(search_results, 1):
        print(f"Result {idx}:")
        print(f"  filename:         {result.get('filename')}")
        print(f"  page_num:         {result.get('page_num')}")
        print(f"  search_score:     {result.get('search_score', 0):.2f}")
        
        if result.get('page_summary'):
            print(f"  summary:          {result.get('page_summary')[:60]}...")
        else:
            print(f"  summary:          (not yet generated)")
        
        snippet = result.get('text_snippet', '')[:100]
        print(f"  text_snippet:     {snippet}...")
        print()
    
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)
    print()
    print(f"[OK] Total documents: {doc_count}")
    print(f"[OK] Total pages: {page_count}")
    print(f"[OK] GridFS files: {file_count} files, {chunk_count} chunks")
    print()
    
    if documents:
        latest_doc = documents[0]
        print(f"Latest document ID: {latest_doc.get('doc_id')}")
        print()
        print("To delete this document:")
        print(f"  python -c \"from database import MongoDBManager; db = MongoDBManager(db_name='pdf_intelligence_db'); db.delete_document('{latest_doc.get('doc_id')}')\"")
    
    print()

if __name__ == "__main__":
    main()

