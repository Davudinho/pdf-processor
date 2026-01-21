from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime
import uuid
import logging
from typing import List, Dict, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBManager:
    def __init__(self, uri: str = "mongodb://localhost:27017/", db_name: str = "pdf_intelligence_db"):
        """
        Initialize MongoDB connection.
        
        :param uri: MongoDB connection string
        :param db_name: Name of the database
        """
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.collection = None
        self._connect()

    def _connect(self):
        """Establish connection to MongoDB and set up collection."""
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Check if the connection is successful
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.collection = self.db["pdf_documents"]
            
            # Create indexes for performance
            self.collection.create_index("doc_id", unique=False) # doc_id is NOT unique across collection because multiple pages share it
            self.collection.create_index([("doc_id", 1), ("page_num", 1)], unique=True)
            self.collection.create_index("filename")
            self.collection.create_index("created_at")
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            pass 
        except Exception as e:
             # Handle IndexKeySpecsConflict by attempting to drop and recreate
             if "IndexKeySpecsConflict" in str(e) or (hasattr(e, 'code') and e.code == 86):
                 logger.warning("Index conflict detected. Attempting to fix by dropping indexes...")
                 try:
                     self.collection.drop_indexes()
                     logger.info("Indexes dropped. Recreating...")
                     self.collection.create_index("doc_id", unique=False)
                     self.collection.create_index([("doc_id", 1), ("page_num", 1)], unique=True)
                     self.collection.create_index("filename")
                     self.collection.create_index("created_at")
                     logger.info("Indexes recreated successfully.")
                 except Exception as re:
                     logger.error(f"Failed to Fix indexes: {re}")
             else:
                logger.error(f"Unexpected error connecting to MongoDB: {e}")

    def save_pdf_pages(self, filename: str, pages_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Save PDF pages to the database.
        
        :param filename: Original filename
        :param pages_data: List of dictionaries containing page extraction data
        :return: doc_id (UUID string) or None if failed
        """
        if self.collection is None:
            logger.error("Database not connected")
            return None

        doc_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        documents = []
        for page in pages_data:
            doc = {
                "doc_id": doc_id,
                "filename": filename,
                "page_num": page.get("page_num"),
                "raw_text": page.get("raw_text", ""),
                "text_length": page.get("text_length", 0),
                "created_at": created_at,
                "status": "raw",
                "structured_data": {}
            }
            documents.append(doc)
        
        if documents:
            try:
                self.collection.insert_many(documents)
                logger.info(f"Saved {len(documents)} pages for document {doc_id}")
                return doc_id
            except OperationFailure as e:
                logger.error(f"Failed to save documents: {e}")
                return None
        return None

    def get_document_status(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the overall status of a document.
        """
        if self.collection is None:
            return None

        try:
            # Check if any page exists
            first_page = self.collection.find_one({"doc_id": doc_id})
            if not first_page:
                return None
            
            total_pages = self.collection.count_documents({"doc_id": doc_id})
            processed_pages = self.collection.count_documents({"doc_id": doc_id, "status": "structured"})
            
            return {
                "doc_id": doc_id,
                "filename": first_page["filename"],
                "total_pages": total_pages,
                "processed_pages": processed_pages,
                "is_complete": total_pages > 0 and total_pages == processed_pages
            }
        except Exception as e:
            logger.error(f"Error getting status for {doc_id}: {e}")
            return None

    def get_raw_text(self, doc_id: str, page_num: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve raw text for a document or specific page.
        """
        if self.collection is None:
            return []

        query = {"doc_id": doc_id}
        if page_num is not None:
            query["page_num"] = page_num
            
        try:
            cursor = self.collection.find(query).sort("page_num", 1)
            results = list(cursor)
            return results
        except Exception as e:
            logger.error(f"Error retrieving raw text for {doc_id}: {e}")
            return []

    def update_structured_text(self, doc_id: str, page_num: int, structured_data: dict) -> bool:
        """
        Update a specific page with structured data.
        """
        if self.collection is None:
            return False

        try:
            result = self.collection.update_one(
                {"doc_id": doc_id, "page_num": page_num},
                {
                    "$set": {
                        "structured_data": structured_data,
                        "status": "structured",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating structured text for {doc_id} page {page_num}: {e}")
            return False

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Get a list of all unique documents with basic metadata.
        """
        if self.collection is None:
            return []

        try:
            pipeline = [
                {"$sort": {"created_at": -1}},
                {"$group": {
                    "_id": "$doc_id",
                    "filename": {"$first": "$filename"},
                    "created_at": {"$first": "$created_at"},
                    "page_count": {"$sum": 1},
                    "status_counts": {"$push": "$status"}
                }}
            ]
            results = list(self.collection.aggregate(pipeline))
            
            # Post-process to determine overall status
            for doc in results:
                doc["doc_id"] = doc["_id"]
                del doc["_id"]
                # A document is complete if all pages are structured
                is_processed = all(s == "structured" for s in doc["status_counts"])
                doc["status"] = "structured" if is_processed and doc["page_count"] > 0 else "processing"
                del doc["status_counts"]
                
            return results
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def get_document_details(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a document including structured data for all pages.
        """
        if self.collection is None:
            return None

        try:
            cursor = self.collection.find({"doc_id": doc_id}).sort("page_num", 1)
            pages = list(cursor)
            if not pages:
                return None
            
            # Remove MongoDB _id
            for page in pages:
                if "_id" in page:
                    del page["_id"]
            
            return {
                "doc_id": doc_id,
                "filename": pages[0]["filename"],
                "created_at": pages[0]["created_at"],
                "pages": pages
            }
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
                "pages": doc_details["pages"]
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
        Delete all pages associated with a document ID.
        """
        if self.collection is None:
            return False

        try:
            result = self.collection.delete_many({"doc_id": doc_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
