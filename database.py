from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime
import uuid
import logging
import gridfs
from bson import ObjectId
from typing import List, Dict, Optional, Any, BinaryIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBManager:
    def __init__(self, uri: str = "mongodb://localhost:27017/", db_name: str = "pdf_intelligence_db"):
        """
        Initialize MongoDB connection with GridFS support.
        
        Architecture:
        - documents collection: Document-level metadata and PDF file references
        - pages collection: Page-level raw text, summaries, and structured data
        - GridFS (fs.files, fs.chunks): Original PDF binary storage
        
        :param uri: MongoDB connection string
        :param db_name: Name of the database
        """
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.documents_collection = None  # Document-level metadata
        self.pages_collection = None      # Page-level data
        self.fs = None                    # GridFS for PDF storage
        self._connect()

    def _connect(self):
        """
        Establish connection to MongoDB and set up collections with indexes.
        Creates separate collections for documents and pages, plus GridFS.
        """
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Check if the connection is successful
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            
            # Initialize collections
            self.documents_collection = self.db["documents"]  # Document-level metadata
            self.pages_collection = self.db["pages"]          # Page-level data
            
            # Initialize GridFS for PDF storage
            self.fs = gridfs.GridFS(self.db)
            
            # Legacy compatibility: keep reference to pages as 'collection'
            self.collection = self.pages_collection
            
            # Create indexes for documents collection
            self.documents_collection.create_index("doc_id", unique=True)
            self.documents_collection.create_index("filename")
            self.documents_collection.create_index("created_at")
            
            # Create indexes for pages collection
            self.pages_collection.create_index("doc_id")
            self.pages_collection.create_index([("doc_id", 1), ("page_num", 1)], unique=True)
            
            # Create text index for keyword search on pages
            self.pages_collection.create_index([("raw_text", "text"), ("keywords", "text")])
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
            logger.info("Collections initialized: documents, pages, GridFS")
            
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise  # Fail fast! App should not start without DB. 
        except Exception as e:
             # Handle IndexKeySpecsConflict by attempting to drop and recreate
             if "IndexKeySpecsConflict" in str(e) or (hasattr(e, 'code') and e.code == 86):
                 logger.warning("Index conflict detected. Attempting to fix by dropping indexes...")
                 try:
                     self.documents_collection.drop_indexes()
                     self.pages_collection.drop_indexes()
                     logger.info("Indexes dropped. Recreating...")
                     
                     # Recreate document indexes
                     self.documents_collection.create_index("doc_id", unique=True)
                     self.documents_collection.create_index("filename")
                     self.documents_collection.create_index("created_at")
                     
                     # Recreate page indexes
                     self.pages_collection.create_index("doc_id")
                     self.pages_collection.create_index([("doc_id", 1), ("page_num", 1)], unique=True)
                     self.pages_collection.create_index([("raw_text", "text"), ("keywords", "text")])
                     
                     logger.info("Indexes recreated successfully.")
                 except Exception as re:
                     logger.error(f"Failed to fix indexes: {re}")
             else:
                logger.error(f"Unexpected error connecting to MongoDB: {e}")
                raise # Re-raise unexpected connection errors

    def save_pdf_with_pages(self, pdf_path: str, filename: str, pages_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Save PDF file to GridFS and page data to collections.
        
        New architecture:
        1. Store original PDF in GridFS
        2. Create document-level metadata in documents collection
        3. Create page-level data in pages collection
        
        :param pdf_path: Path to the PDF file on disk
        :param filename: Original filename
        :param pages_data: List of dictionaries containing page extraction data
        :return: doc_id (UUID string) or None if failed
        """
        if self.pages_collection is None or self.documents_collection is None:
            logger.error("Database not connected")
            return None

        doc_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        try:
            # Step 1: Upload PDF to GridFS
            pdf_file_id = None
            try:
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_file_id = self.fs.put(
                        pdf_file,
                        filename=filename,
                        content_type='application/pdf',
                        metadata={"doc_id": doc_id, "uploaded_at": created_at}
                    )
                logger.info(f"PDF stored in GridFS with file_id: {pdf_file_id}")
            except Exception as e:
                logger.error(f"Failed to upload PDF to GridFS: {e}")
                # Continue without PDF file - we still want to save extracted text
            
            # Step 2: Create document-level metadata
            document_record = {
                "doc_id": doc_id,
                "filename": filename,
                "pdf_file_id": str(pdf_file_id) if pdf_file_id else None,
                "total_pages": len(pages_data),
                "created_at": created_at,
                "status": "raw",  # Will be updated to "structured" after AI processing
                "document_summary": "",  # Will be populated by AI
                "keywords": []  # Will be populated by AI
            }
            self.documents_collection.insert_one(document_record)
            
            # Step 3: Create page-level records
            page_records = []
            for page in pages_data:
                page_record = {
                    "doc_id": doc_id,
                    "page_num": page.get("page_num"),
                    "raw_text": page.get("raw_text", ""),
                    "text_length": page.get("text_length", 0),
                    "created_at": created_at,
                    "status": "raw",
                    "page_summary": "",  # Will be populated by AI
                    "keywords": [],      # Will be populated by AI
                    "structured_data": {}
                }
                page_records.append(page_record)
            
            if page_records:
                self.pages_collection.insert_many(page_records)
                logger.info(f"Saved document {doc_id}: {len(page_records)} pages")
                return doc_id
            else:
                logger.error("No pages to save")
                return None
                
        except OperationFailure as e:
            logger.error(f"Failed to save document: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving document: {e}")
            return None
    
    def save_pdf_pages(self, filename: str, pages_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Legacy method for backward compatibility.
        Note: This does NOT save the original PDF file.
        Use save_pdf_with_pages() instead for full functionality.
        
        :param filename: Original filename
        :param pages_data: List of dictionaries containing page extraction data
        :return: doc_id (UUID string) or None if failed
        """
        logger.warning("Using legacy save_pdf_pages method - PDF file will not be stored")
        if self.pages_collection is None or self.documents_collection is None:
            logger.error("Database not connected")
            return None

        doc_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        try:
            # Create document-level metadata (without PDF file)
            document_record = {
                "doc_id": doc_id,
                "filename": filename,
                "pdf_file_id": None,
                "total_pages": len(pages_data),
                "created_at": created_at,
                "status": "raw",
                "document_summary": "",
                "keywords": []
            }
            self.documents_collection.insert_one(document_record)
            
            # Create page records
            page_records = []
            for page in pages_data:
                page_record = {
                    "doc_id": doc_id,
                    "page_num": page.get("page_num"),
                    "raw_text": page.get("raw_text", ""),
                    "text_length": page.get("text_length", 0),
                    "created_at": created_at,
                    "status": "raw",
                    "page_summary": "",
                    "keywords": [],
                    "structured_data": {}
                }
                page_records.append(page_record)
            
            if page_records:
                self.pages_collection.insert_many(page_records)
                logger.info(f"Saved {len(page_records)} pages for document {doc_id}")
                return doc_id
            return None
            
        except OperationFailure as e:
            logger.error(f"Failed to save documents: {e}")
            return None

    def get_pdf_file(self, file_id: str) -> Optional[gridfs.GridOut]:
        """
        Retrieve PDF file from GridFS.
        
        :param file_id: GridFS file ID (string)
        :return: GridFS file object or None if not found
        """
        if self.fs is None:
            logger.error("GridFS not initialized")
            return None
        
        try:
            grid_out = self.fs.get(ObjectId(file_id))
            return grid_out
        except gridfs.errors.NoFile:
            logger.error(f"PDF file not found in GridFS: {file_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving PDF from GridFS: {e}")
            return None
    
    def delete_pdf_file(self, file_id: str) -> bool:
        """
        Delete PDF file from GridFS.
        
        :param file_id: GridFS file ID (string)
        :return: True if deleted successfully, False otherwise
        """
        if self.fs is None:
            return False
        
        try:
            self.fs.delete(ObjectId(file_id))
            logger.info(f"Deleted PDF file from GridFS: {file_id}")
            return True
        except gridfs.errors.NoFile:
            logger.warning(f"PDF file not found for deletion: {file_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting PDF from GridFS: {e}")
            return False

    def get_document_status(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the overall status of a document.
        Now uses the documents collection for metadata.
        """
        if self.documents_collection is None or self.pages_collection is None:
            return None

        try:
            # Get document metadata
            doc = self.documents_collection.find_one({"doc_id": doc_id})
            if not doc:
                return None
            
            # Count page processing status
            total_pages = self.pages_collection.count_documents({"doc_id": doc_id})
            processed_pages = self.pages_collection.count_documents({"doc_id": doc_id, "status": "structured"})
            
            return {
                "doc_id": doc_id,
                "filename": doc["filename"],
                "total_pages": total_pages,
                "processed_pages": processed_pages,
                "is_complete": total_pages > 0 and total_pages == processed_pages,
                "has_pdf_file": doc.get("pdf_file_id") is not None
            }
        except Exception as e:
            logger.error(f"Error getting status for {doc_id}: {e}")
            return None

    def get_raw_text(self, doc_id: str, page_num: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve raw text for a document or specific page.
        Uses pages collection.
        """
        if self.pages_collection is None:
            return []

        query = {"doc_id": doc_id}
        if page_num is not None:
            query["page_num"] = page_num
            
        try:
            cursor = self.pages_collection.find(query).sort("page_num", 1)
            results = list(cursor)
            return results
        except Exception as e:
            logger.error(f"Error retrieving raw text for {doc_id}: {e}")
            return []

    def update_page_data(self, doc_id: str, page_num: int, 
                         structured_data: dict = None,
                         page_summary: str = None, 
                         keywords: List[str] = None) -> bool:
        """
        Update a specific page with AI-generated data.
        
        :param doc_id: Document ID
        :param page_num: Page number
        :param structured_data: Structured extraction (sections, tables, etc.)
        :param page_summary: Short summary of the page
        :param keywords: List of keywords extracted from the page
        :return: True if updated successfully
        """
        if self.pages_collection is None:
            return False

        try:
            update_fields = {
                "status": "structured",
                "updated_at": datetime.utcnow()
            }
            
            if structured_data is not None:
                update_fields["structured_data"] = structured_data
            if page_summary is not None:
                update_fields["page_summary"] = page_summary
            if keywords is not None:
                update_fields["keywords"] = keywords
            
            result = self.pages_collection.update_one(
                {"doc_id": doc_id, "page_num": page_num},
                {"$set": update_fields}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating page data for {doc_id} page {page_num}: {e}")
            return False
    
    def update_structured_text(self, doc_id: str, page_num: int, structured_data: dict) -> bool:
        """
        Legacy method for backward compatibility.
        Use update_page_data() for new implementations.
        """
        return self.update_page_data(doc_id, page_num, structured_data=structured_data)

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Get a list of all documents with metadata.
        Now uses the documents collection directly.
        """
        if self.documents_collection is None or self.pages_collection is None:
            return []

        try:
            # Get all documents
            documents = list(self.documents_collection.find().sort("created_at", -1))
            
            # Enhance with processing status
            for doc in documents:
                doc_id = doc["doc_id"]
                
                # Count processed pages
                total_pages = self.pages_collection.count_documents({"doc_id": doc_id})
                processed_pages = self.pages_collection.count_documents(
                    {"doc_id": doc_id, "status": "structured"}
                )
                
                # Determine overall status
                is_processed = total_pages > 0 and total_pages == processed_pages
                doc["status"] = "structured" if is_processed else "processing"
                doc["processed_pages"] = processed_pages
                doc["page_count"] = total_pages
                
                # Remove MongoDB internal _id
                if "_id" in doc:
                    del doc["_id"]
                
            return documents
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def get_document_details(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a document including metadata and all pages.
        """
        if self.documents_collection is None or self.pages_collection is None:
            return None

        try:
            # Get document metadata
            doc = self.documents_collection.find_one({"doc_id": doc_id})
            if not doc:
                return None
            
            # Get all pages
            cursor = self.pages_collection.find({"doc_id": doc_id}).sort("page_num", 1)
            pages = list(cursor)
            
            # Remove MongoDB _id from all records
            if "_id" in doc:
                del doc["_id"]
            for page in pages:
                if "_id" in page:
                    del page["_id"]
            
            # Combine document metadata and pages
            doc["pages"] = pages
            
            return doc
        except Exception as e:
            logger.error(f"Error getting details for {doc_id}: {e}")
            return None

    def create_document_structure(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Aggregates structured data from all pages into a single document-level structure.
        
        Merges:
        - sections: Collected list
        - measurements: Collected list
        - key_fields: Merged dictionary (later pages update earlier ones)
        - tables: Collected list
        """
        try:
            doc_details = self.get_document_details(doc_id)
            if not doc_details:
                return None

            unified_doc = {
                "doc_id": doc_id,
                "filename": doc_details["filename"],
                "total_pages": len(doc_details["pages"]),
                "all_sections": [],
                "all_measurements": [],
                "all_key_fields": {},
                "all_tables": [],
                "pages": doc_details["pages"],
                "document_summary": doc_details.get("document_summary", ""),
                "document_keywords": doc_details.get("keywords", [])
            }

            for page in doc_details["pages"]:
                s_data = page.get("structured_data")
                if not s_data or not isinstance(s_data, dict):
                    continue

                # Collect sections
                sections = s_data.get("sections", [])
                if isinstance(sections, list):
                    unified_doc["all_sections"].extend(sections)

                # Collect measurements
                measurements = s_data.get("measurements", [])
                if isinstance(measurements, list):
                    unified_doc["all_measurements"].extend(measurements)

                # Merge key_fields
                key_fields = s_data.get("key_fields", {})
                if isinstance(key_fields, dict):
                    unified_doc["all_key_fields"].update(key_fields)

                # Collect tables
                tables = s_data.get("tables", [])
                if isinstance(tables, list):
                    unified_doc["all_tables"].extend(tables)

            return unified_doc

        except Exception as e:
            logger.error(f"Error creating document structure for {doc_id}: {e}")
            return None

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document and all associated data.
        Deletes from: documents collection, pages collection, and GridFS.
        """
        if self.documents_collection is None or self.pages_collection is None:
            return False

        try:
            # Get document to find PDF file ID
            doc = self.documents_collection.find_one({"doc_id": doc_id})
            if not doc:
                logger.warning(f"Document not found: {doc_id}")
                return False
            
            # Delete PDF file from GridFS if exists
            if doc.get("pdf_file_id"):
                self.delete_pdf_file(doc["pdf_file_id"])
            
            # Delete pages
            pages_result = self.pages_collection.delete_many({"doc_id": doc_id})
            logger.info(f"Deleted {pages_result.deleted_count} pages for document {doc_id}")
            
            # Delete document metadata
            doc_result = self.documents_collection.delete_one({"doc_id": doc_id})
            
            return doc_result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    def search_documents(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search documents by keyword using MongoDB text index.
        Searches through raw_text and keywords fields in pages collection.
        
        :param query: Search query string
        :param limit: Maximum number of results to return
        :return: List of matching pages with document metadata
        """
        if self.pages_collection is None or self.documents_collection is None:
            return []
        
        try:
            # Perform text search on pages
            search_results = list(
                self.pages_collection.find(
                    {"$text": {"$search": query}},
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            )
            
            # Enhance results with document metadata
            enhanced_results = []
            for page in search_results:
                doc_id = page["doc_id"]
                
                # Get document metadata
                doc = self.documents_collection.find_one({"doc_id": doc_id})
                
                # Remove MongoDB _id
                if "_id" in page:
                    del page["_id"]
                if doc and "_id" in doc:
                    del doc["_id"]
                
                result = {
                    "doc_id": doc_id,
                    "filename": doc.get("filename") if doc else "Unknown",
                    "page_num": page.get("page_num"),
                    "page_summary": page.get("page_summary", ""),
                    "keywords": page.get("keywords", []),
                    "text_snippet": page.get("raw_text", "")[:300] + "...",
                    "search_score": page.get("score", 0)
                }
                enhanced_results.append(result)
            
            logger.info(f"Search for '{query}' returned {len(enhanced_results)} results")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
