from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBManager:
    def __init__(self, uri="mongodb://localhost:27017/", db_name="pdf_intelligence_db"):
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
            self.collection.create_index("doc_id", unique=True)
            self.collection.create_index("filename")
            self.collection.create_index("created_at")
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise

    def save_pdf_pages(self, filename: str, pages_data: list) -> str:
        """
        Save PDF pages to the database.
        
        :param filename: Original filename
        :param pages_data: List of dictionaries containing page extraction data
        :return: doc_id (UUID string)
        """
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
                raise
        return None

    def get_document_status(self, doc_id: str) -> dict:
        """
        Get the overall status of a document.
        """
        try:
            # Check if any page is still 'raw'
            doc = self.collection.find_one({"doc_id": doc_id})
            if not doc:
                return None
            
            total_pages = self.collection.count_documents({"doc_id": doc_id})
            processed_pages = self.collection.count_documents({"doc_id": doc_id, "status": "structured"})
            
            return {
                "doc_id": doc_id,
                "filename": doc["filename"],
                "total_pages": total_pages,
                "processed_pages": processed_pages,
                "is_complete": total_pages == processed_pages
            }
        except Exception as e:
            logger.error(f"Error getting status for {doc_id}: {e}")
            return None

    def get_raw_text(self, doc_id: str, page_num: int = None):
        """
        Retrieve raw text for a document or specific page.
        """
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

    def update_structured_text(self, doc_id: str, page_num: int, structured_data: dict):
        """
        Update a specific page with structured data.
        """
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

    def get_all_documents(self):
        """
        Get a list of all unique documents with basic metadata.
        """
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
                is_processed = all(s == "structured" for s in doc["status_counts"])
                doc["status"] = "structured" if is_processed else "processing"
                del doc["status_counts"]
                
            return results
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def get_document_details(self, doc_id: str):
        """
        Get full details for a document including structured data.
        """
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

    def delete_document(self, doc_id: str):
        """
        Delete all pages associated with a document ID.
        """
        try:
            result = self.collection.delete_many({"doc_id": doc_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
