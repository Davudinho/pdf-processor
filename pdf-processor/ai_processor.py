import openai
import json
import logging
import os
from database import MongoDBManager
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize AI Processor.
        :param api_key: OpenAI API Key. If None, tries to read from env or os.
        :param model: OpenAI model to use.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("CRITICAL: No OPENAI_API_KEY provided or found in environment.")
            # We don't raise error here to allow app instantiation, but methods will fail gracefully
        else:
            self.client = openai.OpenAI(api_key=self.api_key)
        
        self.model = model

    def _get_default_structure(self) -> Dict[str, Any]:
        """Return a default empty structure for fallbacks."""
        return {
            "sections": [],
            "measurements": [],
            "key_fields": {},
            "tables": [],
            "processing_status": "failed" # Using processing_status to distinguish from DB status
        }

    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """Check if the data has the required top-level keys."""
        required_keys = ["sections", "measurements", "key_fields", "tables"]
        # We only check for existence. Types are checked implicitly by consumption or could be added here.
        return all(key in data for key in required_keys)

    def structure_text(self, raw_text: str) -> Dict[str, Any]:
        """
        Send raw text to OpenAI to extract structure.
        """
        if not self.api_key:
            logger.error("Cannot structure text: Missing API Key")
            return self._get_default_structure()

        if not raw_text or len(raw_text.strip()) == 0:
            default = self._get_default_structure()
            default["processing_status"] = "empty_text"
            return default

        system_prompt = """
You are a highly capable document extraction assistant. 
Your task is to analyze the provided text (German or English) and extract structured data into a valid JSON object.

REQUIRED OUTPUT STRUCTURE:
{
  "sections": [{"title": "Section Title", "content": "Section content summary..."}],
  "measurements": [{"value": 12.5, "unit": "mm", "context": "description of measurement"}],
  "key_fields": {"invoice_date": "YYYY-MM-DD", "document_number": "...", "names": ["..."]},
  "tables": [[{"col1": "val1", "col2": "val2"}]] 
}

RULES:
1. Output valid JSON only. NO markdown blocks (e.g. ```json).
2. If a field is empty, return an empty list [] or empty dict {}.
3. 'tables' should be a list of lists (rows) or list of list of dicts.
4. Extract all dates, numbers, and important entity names into 'key_fields'.
5. Be robust against OCR errors.
"""

        try:
            # Added timeout=30 to prevent blocking indefinitely
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text to structure:\n\n{raw_text[:3500]}"} 
                ],
                temperature=0,
                max_tokens=2000,
                timeout=30
            )
            
            content = response.choices[0].message.content
            
            # Cleanup markdown if present
            clean_content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}")
                logger.error(f"Raw Response (truncated): {content[:500]}")
                default = self._get_default_structure()
                default["processing_status"] = "json_error"
                return default

            if self._validate_structure(data):
                data["processing_status"] = "success"
                return data
            else:
                logger.warning("AI output missing required keys, merging with default.")
                default = self._get_default_structure()
                default.update(data) # Keep what we got
                default["processing_status"] = "partial_success"
                return default

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            default = self._get_default_structure()
            default["processing_status"] = "api_error"
            return default

    def process_document(self, db_manager: MongoDBManager, doc_id: str):
        """
        Process all pages of a document and update MongoDB with structured data.
        """
        pages = db_manager.get_raw_text(doc_id)
        if not pages:
            logger.warning(f"No pages found for document {doc_id}")
            return

        logger.info(f"Starting processing for document {doc_id} with {len(pages)} pages.")

        for page in pages:
            page_num = page.get("page_num")
            raw_text = page.get("raw_text", "")
            
            # Skip if already processed? The user didn't explicitly ask for resume capability 
            # but it is good practice. However, "process_document" usually implies a fresh run or 
            # run on what's raw. For simplicity, we process everything.
            
            logger.info(f"Structuring page {page_num} of document {doc_id}...")
            structured_data = self.structure_text(raw_text)
            
            success = db_manager.update_structured_text(doc_id, page_num, structured_data)
            if not success:
                logger.error(f"Failed to save structured data for {doc_id} page {page_num}")
        
        logger.info(f"Finished processing document {doc_id}")

if __name__ == "__main__":
    # Test script
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    
    if len(sys.argv) > 1:
        processor = AIProcessor()
        text = sys.argv[1]
        print(json.dumps(processor.structure_text(text), indent=2))
    else:
        print("Usage: python ai_processor.py \"Some text to structure\"")
