import openai
import json
import logging
import os
from datetime import datetime
from database import MongoDBManager
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-5-mini"):
        """
        Initialize AI Processor.
        :param api_key: OpenAI API Key. If None, tries to read from env or os.
        :param model: OpenAI model to use.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        
        if not self.api_key:
            logger.error("="*70)
            logger.error("CRITICAL: No OPENAI_API_KEY provided or found in environment.")
            logger.error("AI processing will fail. Please set OPENAI_API_KEY in .env file")
            logger.error("="*70)
            # We don't raise error here to allow app instantiation, but methods will fail gracefully
        else:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI client initialized successfully (model: {model})")
                logger.info(f"API key configured: {self.api_key[:10]}...{self.api_key[-4:]}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                logger.error("Check if your API key is valid")
        
        self.model = model

    def _get_default_structure(self) -> Dict[str, Any]:
        """Return a default empty structure for fallbacks."""
        return {
            "summary": "",
            "keywords": [],
            "sections": [],
            "measurements": [],
            "key_fields": {},
            "tables": [],
            "processing_status": "failed"
        }

    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """Check if the data has the required top-level keys."""
        required_keys = ["summary", "keywords", "sections", "measurements", "key_fields", "tables"]
        return all(key in data for key in required_keys)

    def structure_text(self, raw_text: str, max_chars: int = 8000) -> Dict[str, Any]:
        """
        Send raw text to OpenAI to extract structure, summary, and keywords.
        
        For large texts, intelligently truncate or use chunking strategy.
        
        :param raw_text: Raw text from PDF page
        :param max_chars: Maximum characters to send to LLM
        :return: Structured data including summary and keywords
        """
        if not self.api_key or not self.client:
            logger.error("="*70)
            logger.error("Cannot structure text: OpenAI API Key not configured")
            logger.error("Please set OPENAI_API_KEY in your .env file")
            logger.error("Example: OPENAI_API_KEY=sk-proj-...")
            logger.error("="*70)
            default = self._get_default_structure()
            default["processing_status"] = "no_api_key"
            return default

        if not raw_text or len(raw_text.strip()) == 0:
            logger.warning("Empty text provided for structuring")
            default = self._get_default_structure()
            default["processing_status"] = "empty_text"
            return default

        # Intelligent text truncation for large pages
        text_to_process = raw_text
        if len(raw_text) > max_chars:
            logger.info(f"Text too long ({len(raw_text)} chars), truncating to {max_chars}")
            # Take first 70% and last 30% to preserve context
            first_part = raw_text[:int(max_chars * 0.7)]
            last_part = raw_text[-int(max_chars * 0.3):]
            text_to_process = first_part + "\n\n[...middle content truncated...]\n\n" + last_part

        system_prompt = """
You are a highly capable document extraction assistant. 
Analyze the provided text (German or English) and extract structured data into a valid JSON object.

REQUIRED OUTPUT STRUCTURE:
{
  "summary": "A concise 50-100 word summary of the page content",
  "keywords": ["keyword1", "keyword2", ...],  // 5-15 relevant keywords for search
  "sections": [{"title": "Section Title", "content": "Section content summary..."}],
  "measurements": [{"value": 12.5, "unit": "mm", "context": "description of measurement"}],
  "key_fields": {"invoice_date": "YYYY-MM-DD", "document_number": "...", "names": ["..."]},
  "tables": [[{"col1": "val1", "col2": "val2"}]]
}

RULES:
1. Output valid JSON only. NO markdown blocks (e.g. ```json).
2. 'summary' should be concise but informative (50-100 words).
3. 'keywords' should include important terms, names, technical terms (5-15 keywords).
4. If a field is empty, return an empty list [] or empty dict {}.
5. 'tables' should be a list of lists (rows) or list of list of dicts.
6. Extract all dates, numbers, and important entity names into 'key_fields'.
7. Be robust against OCR errors.
8. Focus on accuracy over completeness for large documents.
"""

        try:
            logger.info(f"Sending {len(text_to_process)} characters to OpenAI ({self.model})...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text to structure:\n\n{text_to_process}"} 
                ],
                temperature=0,
                max_tokens=2500,  # Increased for summary + keywords
                timeout=45
            )
            
            content = response.choices[0].message.content
            logger.info(f"Received response from OpenAI ({len(content)} characters)")
            
            # Cleanup markdown if present
            clean_content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_content)
                logger.info("Successfully parsed JSON response from OpenAI")
            except json.JSONDecodeError as e:
                logger.error("="*70)
                logger.error(f"JSON Parse Error: {e}")
                logger.error(f"Raw Response (truncated): {content[:500]}")
                logger.error("OpenAI returned invalid JSON format")
                logger.error("="*70)
                default = self._get_default_structure()
                default["processing_status"] = "json_error"
                return default

            if self._validate_structure(data):
                data["processing_status"] = "success"
                logger.info("✓ AI structuring completed successfully")
                return data
            else:
                logger.warning("AI output missing required keys, merging with default.")
                logger.warning(f"Expected keys: summary, keywords, sections, measurements, key_fields, tables")
                logger.warning(f"Received keys: {list(data.keys())}")
                default = self._get_default_structure()
                default.update(data) # Keep what we got
                default["processing_status"] = "partial_success"
                return default

        except openai.AuthenticationError as e:
            logger.error("="*70)
            logger.error(f"OpenAI Authentication Error: {e}")
            logger.error("Your API key is invalid or expired")
            logger.error("Please check OPENAI_API_KEY in .env file")
            logger.error("="*70)
            default = self._get_default_structure()
            default["processing_status"] = "auth_error"
            return default
        except openai.RateLimitError as e:
            logger.error("="*70)
            logger.error(f"OpenAI Rate Limit Error: {e}")
            logger.error("You have exceeded your API rate limit")
            logger.error("Please wait or upgrade your OpenAI plan")
            logger.error("="*70)
            default = self._get_default_structure()
            default["processing_status"] = "rate_limit_error"
            return default
        except openai.APIError as e:
            logger.error("="*70)
            logger.error(f"OpenAI API Error: {e}")
            logger.error("OpenAI service may be experiencing issues")
            logger.error("="*70)
            default = self._get_default_structure()
            default["processing_status"] = "api_error"
            return default
        except Exception as e:
            logger.error("="*70)
            logger.error(f"Unexpected Error during AI processing: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error("="*70)
            import traceback
            logger.error(traceback.format_exc())
            default = self._get_default_structure()
            default["processing_status"] = "unknown_error"
            return default

    def process_document(self, db_manager: MongoDBManager, doc_id: str):
        """
        Process all pages of a document and update MongoDB with structured data.
        Generates summary, keywords, and structured fields for each page.
        """
        logger.info("="*70)
        logger.info(f"Starting AI processing for document: {doc_id}")
        logger.info("="*70)
        
        # Check API key first
        if not self.api_key or not self.client:
            logger.error("="*70)
            logger.error("CRITICAL: Cannot process document - OpenAI API key not configured")
            logger.error("Please set OPENAI_API_KEY in your .env file")
            logger.error("Processing will continue but metadata will be empty")
            logger.error("="*70)
            # Mark all pages as processed with empty metadata
            pages = db_manager.get_raw_text(doc_id)
            for page in pages:
                db_manager.update_page_data(
                    doc_id=doc_id,
                    page_num=page.get("page_num"),
                    structured_data=self._get_default_structure(),
                    page_summary="[No API key - processing skipped]",
                    keywords=[]
                )
            return
        
        pages = db_manager.get_raw_text(doc_id)
        if not pages:
            logger.warning(f"No pages found for document {doc_id}")
            return

        logger.info(f"Document has {len(pages)} pages to process")

        all_summaries = []
        all_keywords = []
        processed_count = 0
        failed_count = 0

        for idx, page in enumerate(pages, 1):
            page_num = page.get("page_num")
            raw_text = page.get("raw_text", "")
            
            # Skip already processed pages (optional optimization)
            # CRITICAL CHANGE: Only skip if we actually HAVE a summary. 
            # If status is "structured" but summary is empty, it means previous processing failed or was empty.
            if page.get("status") == "structured" and page.get("page_summary"):
                logger.info(f"[{idx}/{len(pages)}] Page {page_num} already processed with summary, skipping...")
                
                # Collect existing data for document-level aggregation
                existing_summary = page.get("page_summary", "")
                existing_keywords = page.get("keywords", [])
                
                if existing_summary:
                    all_summaries.append(existing_summary)
                if existing_keywords:
                    all_keywords.extend(existing_keywords)
                
                processed_count += 1
                continue
            
            # If we are here, we are (re)processing the page
            if page.get("status") == "structured":
                 logger.info(f"[{idx}/{len(pages)}] Retrying page {page_num} (was 'structured' but missing summary)...")
            else:
                 logger.info(f"[{idx}/{len(pages)}] Processing page {page_num}...")
            logger.info(f"  Text length: {len(raw_text)} characters")
            
            structured_data = self.structure_text(raw_text)
            
            # Check processing status
            processing_status = structured_data.get("processing_status", "unknown")
            
            if processing_status == "no_api_key":
                logger.error(f"  ✗ Page {page_num} failed: No API key")
                failed_count += 1
            elif processing_status == "success":
                logger.info(f"  ✓ Page {page_num} processed successfully")
                processed_count += 1
            else:
                logger.warning(f"  ⚠ Page {page_num} processed with status: {processing_status}")
                processed_count += 1
            
            # Extract summary and keywords from structured data
            page_summary = structured_data.get("summary", "")
            keywords = structured_data.get("keywords", [])
            
            if page_summary:
                logger.info(f"  Summary: {page_summary[:80]}...")
            if keywords:
                logger.info(f"  Keywords: {', '.join(keywords[:5])}")
            
            # Update page with all extracted data
            success = db_manager.update_page_data(
                doc_id=doc_id,
                page_num=page_num,
                structured_data=structured_data,
                page_summary=page_summary,
                keywords=keywords
            )
            
            if not success:
                logger.error(f"  ✗ Failed to save to database for page {page_num}")
                failed_count += 1
            else:
                logger.info(f"  ✓ Saved to database")
                all_summaries.append(page_summary)
                all_keywords.extend(keywords)
        
        # Generate document-level summary
        if all_summaries:
            logger.info("Generating document-level metadata...")
            self._update_document_metadata(db_manager, doc_id, all_summaries, all_keywords)
        
        logger.info("="*70)
        logger.info(f"Processing complete for document {doc_id}")
        logger.info(f"  Successfully processed: {processed_count}/{len(pages)} pages")
        if failed_count > 0:
            logger.warning(f"  Failed: {failed_count} pages")
        logger.info("="*70)
    
    def generate_document_summary(self, page_summaries: List[str]) -> str:
        """
        Generate a concise executive summary for the entire document based on page summaries.
        """
        if not page_summaries:
            return ""
            
        # If only one page, just return that page's summary
        if len(page_summaries) == 1:
            return page_summaries[0]

        # Combine page summaries into a context
        context = "\n\n".join([f"Page {i+1}: {summary}" for i, summary in enumerate(page_summaries)])
        
        # Truncate if too long (approx 12k chars to stay well within token limits for 4o-mini/3.5)
        if len(context) > 12000:
             context = context[:6000] + "\n\n[...intermediate pages omitted...]\n\n" + context[-6000:]

        system_prompt = """
        You are an expert executive assistant. 
        Create a coherent, concise executive summary (100-200 words) of the ENTIRE document based on the provided page summaries.
        
        GUIDELINES:
        1. Synthesize the information, do not just list what is on each page.
        2. Identify the core purpose, main results, and key dates/entities.
        3. Write in the same language as the document (German or English).
        4. Focus on the "Big Picture".
        """

        try:
            logger.info(f"Generating document summary from {len(page_summaries)} pages...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here are the summaries of the document pages:\n\n{context}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate document summary: {e}")
            # Fallback to simple concatenation
            return f"Document with {len(page_summaries)} pages. " + page_summaries[0]

    def _update_document_metadata(self, db_manager: MongoDBManager, doc_id: str, 
                                   page_summaries: List[str], all_keywords: List[str]):
        """
        Update document-level metadata with aggregated summaries and keywords.
        
        :param db_manager: Database manager instance
        :param doc_id: Document ID
        :param page_summaries: List of page summaries
        :param all_keywords: List of all keywords from all pages
        """
        try:
            # Create document summary using AI
            doc_summary = self.generate_document_summary(page_summaries)
            
            # Deduplicate and limit keywords
            unique_keywords = list(dict.fromkeys(all_keywords))[:30]  # Top 30 unique keywords
            
            # Update documents collection
            if db_manager.documents_collection is not None:
                logger.info(f"Updating document {doc_id} with {len(unique_keywords)} keywords and summary length {len(doc_summary)}")
                db_manager.documents_collection.update_one(
                    {"doc_id": doc_id},
                    {
                        "$set": {
                            "document_summary": doc_summary,
                            "keywords": unique_keywords,
                            "status": "structured",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"Updated document-level metadata for {doc_id}")
        except Exception as e:
            logger.error(f"Error updating document metadata: {e}")

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
