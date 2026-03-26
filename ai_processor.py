import json
import logging
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from database import MongoDBManager
from typing import Dict, Any, Optional, List
import google.generativeai as genai

from prompts import (
    get_structure_text_prompt,
    get_document_summary_prompt,
    get_ask_question_prompt,
    get_extract_entities_prompt,
    ENTITY_TYPE_DESCRIPTIONS,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        """
        Initialize AI Processor for Google Gemini.
        :param api_key: Gemini API Key. If None, tries to read from env or os.
        :param model: Gemini model to use.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if not self.api_key:
            logger.error("="*70)
            logger.error("CRITICAL: No GEMINI_API_KEY provided or found in environment.")
            logger.error("AI processing will fail. Please set GEMINI_API_KEY in .env file")
            logger.error("="*70)
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.client = True # Marker that it works
                logger.info(f"Gemini client configured successfully (model: {model})")
                logger.info(f"API key configured: {self.api_key[:10]}...{self.api_key[-4:]}")
            except Exception as e:
                logger.error(f"Failed to configure Gemini client: {e}")
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
        Send raw text to Gemini to extract structure, summary, and keywords.
        """
        if not self.api_key or not self.client:
            logger.error("Cannot structure text: Gemini API Key not configured")
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
            mid_point = int(max_chars * 0.7)
            end_point = len(raw_text) - int(max_chars * 0.3)
            
            safe_mid = raw_text.rfind(' ', 0, mid_point)
            safe_end = raw_text.find(' ', end_point)
            
            if safe_mid == -1: safe_mid = mid_point
            if safe_end == -1: safe_end = end_point
            
            first_part = raw_text[:safe_mid]
            last_part = raw_text[safe_end:]
            text_to_process = f"{first_part}\n\n[...{len(raw_text) - len(first_part) - len(last_part)} chars truncated...]\n\n{last_part}"

        system_prompt = get_structure_text_prompt()

        try:
            logger.info(f"Sending {len(text_to_process)} characters to Gemini ({self.model})...")
            
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                    "max_output_tokens": 1000
                }
            )
            
            response = model.generate_content(f"Text to structure:\n\n{text_to_process}")
            content = response.text
            
            logger.info(f"Received response from Gemini ({len(content)} characters)")
            
            # Cleanup markdown if present
            clean_content = content.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_content)
                logger.info("Successfully parsed JSON response from Gemini")
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}")
                default = self._get_default_structure()
                default["processing_status"] = "json_error"
                return default

            if self._validate_structure(data):
                data["processing_status"] = "success"
                logger.info("✓ AI structuring completed successfully")
                return data
            else:
                logger.warning("AI output missing required keys, merging with default.")
                default = self._get_default_structure()
                default.update(data)
                default["processing_status"] = "partial_success"
                return default

        except Exception as e:
            logger.error(f"Error during AI processing: {e}")
            default = self._get_default_structure()
            default["processing_status"] = "unknown_error"
            return default

    def process_document(self, db_manager: MongoDBManager, doc_id: str):
        """
        Process all pages of a document and update MongoDB with structured data.
        """
        logger.info(f"Starting AI processing for document: {doc_id}")
        
        if not self.api_key or not self.client:
            logger.error("CRITICAL: Cannot process document - API key not configured")
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

        all_summaries = []
        all_keywords = []
        processed_count = 0
        failed_count = 0

        def process_single_page(page, idx):
            page_num = page.get("page_num")
            raw_text = page.get("raw_text", "")
            
            if page.get("status") == "structured" and page.get("page_summary"):
                logger.info(f"[{idx}/{len(pages)}] Page {page_num} already processed with summary, skipping...")
                return {
                    "success": True, "skipped": True, "page_num": page_num,
                    "summary": page.get("page_summary", ""), "keywords": page.get("keywords", [])
                }
            
            logger.info(f"[{idx}/{len(pages)}] Processing page {page_num}...")
            
            structured_data = self.structure_text(raw_text)
            processing_status = structured_data.get("processing_status", "unknown")
            
            page_summary = structured_data.get("summary", "")
            keywords = structured_data.get("keywords", [])
            
            success = db_manager.update_page_data(
                doc_id=doc_id,
                page_num=page_num,
                structured_data=structured_data,
                page_summary=page_summary,
                keywords=keywords
            )
            
            return {
                "success": success and processing_status == "success",
                "skipped": False,
                "page_num": page_num,
                "summary": page_summary,
                "keywords": keywords,
                "status": processing_status
            }

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda arg: process_single_page(*arg), [(page, idx) for idx, page in enumerate(pages, 1)]))

        for res in results:
            if res["success"] or res["skipped"]:
                processed_count += 1
                if res["summary"]:
                    all_summaries.append(res["summary"])
                if res["keywords"]:
                    all_keywords.extend(res["keywords"])
            else:
                failed_count += 1
                logger.error(f"  ✗ Page {res['page_num']} failed with status: {res.get('status', 'db_error')}")
        
        if all_summaries:
            self._update_document_metadata(db_manager, doc_id, all_summaries, all_keywords)
        
        logger.info(f"Processing complete for document {doc_id} ({processed_count}/{len(pages)} pages)")
    
    def generate_document_summary(self, page_summaries: List[str], existing_categories: List[str] = None) -> dict:
        """
        Generate a concise executive summary and automatically categorize the entire document.
        """
        if not page_summaries:
            return {"summary": "", "category": "Sonstiges"}

        context = "\n\n".join([f"Page {i+1}: {summary}" for i, summary in enumerate(page_summaries)])
        
        if len(context) > 12000:
             context = context[:6000] + "\n\n[...intermediate pages omitted...]\n\n" + context[-6000:]

        system_prompt = get_document_summary_prompt(existing_categories)

        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3,
                    "max_output_tokens": 500
                }
            )
            response = model.generate_content(f"Here are the summaries of the document pages:\n\n{context}")
            content = response.text.strip()
            
            result = json.loads(content)
            return {
                "summary": result.get("summary", ""),
                "category": result.get("category", "Sonstiges")
            }
        except Exception as e:
            logger.error(f"Failed to generate document summary and category: {e}")
            summary_text = f"Document with {len(page_summaries)} pages. " + page_summaries[0]
            return {"summary": summary_text, "category": "Sonstiges"}

    def _update_document_metadata(self, db_manager: MongoDBManager, doc_id: str, 
                                   page_summaries: List[str], all_keywords: List[str]):
        """
        Update document-level metadata with aggregated summaries, keywords and category.
        """
        try:
            existing_categories = db_manager.get_unique_categories() if db_manager else []
            doc_info = self.generate_document_summary(page_summaries, existing_categories)
            doc_summary = doc_info.get("summary", "")
            doc_category = doc_info.get("category", "Sonstiges")
            
            unique_keywords = list(dict.fromkeys(all_keywords))[:30]
            
            if db_manager.documents_collection is not None:
                db_manager.documents_collection.update_one(
                    {"doc_id": doc_id},
                    {
                        "$set": {
                            "document_summary": doc_summary,
                            "category": doc_category,
                            "keywords": unique_keywords,
                            "status": "structured",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Error updating document metadata: {e}")

    def create_embedding(self, text: str) -> List[float]:
        """
        Erstellt einen Embedding-Vektor für einen Text über Gemini.
        Modell: text-embedding-004 (768 Dimensionen)
        """
        if not self.client:
            logger.error("create_embedding: Gemini Client nicht initialisiert.")
            return []

        if not text or not text.strip():
            logger.warning("create_embedding: Leerer Text übergeben.")
            return []

        try:
            text_to_embed = text[:32000] if len(text) > 32000 else text

            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text_to_embed,
                task_type="retrieval_document"
            )
            embedding = response['embedding']
            return embedding

        except Exception as e:
            logger.error(f"create_embedding: Fehler: {e}")
            return []

    def create_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Erstellt Embeddings für mehrere Texte mit Throttling-Schutz über Gemini.
        """
        import time

        if not self.client:
            logger.error("create_embeddings_batch: Gemini Client nicht initialisiert.")
            return []

        if not texts:
            return []

        valid_texts = [t[:32000] if len(t) > 32000 else t for t in texts if t and t.strip()]

        if not valid_texts:
            return []

        all_embeddings = []
        total_batches = (len(valid_texts) + batch_size - 1) // batch_size

        logger.info(f"Starte Batch-Embedding: {len(valid_texts)} Chunks in {total_batches} Batches à {batch_size}...")

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, len(valid_texts))
            batch = valid_texts[batch_start:batch_end]

            try:
                response = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=batch,
                    task_type="retrieval_document"
                )
                batch_embeddings = response['embedding']
                all_embeddings.extend(batch_embeddings)
                logger.info(f"  ✓ Batch {batch_idx + 1}/{total_batches} fertig ({len(batch_embeddings)} Vektoren)")

            except Exception as e:
                logger.warning(f"  Rate Limit/Error bei Batch {batch_idx + 1}: {e}. Warte 10s und versuche einzeln...")
                time.sleep(10)
                # Fallback: einzeln verarbeiten
                for text in batch:
                    emb = self.create_embedding(text)
                    all_embeddings.append(emb)
                    time.sleep(0.5)

            if batch_idx < total_batches - 1:
                time.sleep(0.5)

        return all_embeddings


    def ask_question(self, question: str, context_chunks: List[str]) -> dict:
        """
        Beantwortet eine Frage basierend auf den übergebenen Text-Chunks (RAG).
        """
        if not self.client:
            logger.error("ask_question: Gemini Client nicht initialisiert.")
            return {"answer": "Fehler: KI-Service ist nicht verfügbar.", "follow_ups": []}
            
        if not context_chunks:
            return {"answer": "Ich konnte keine passenden Informationen finden.", "follow_ups": []}
            
        context_text = "\n\n---\n\n".join(context_chunks)
        
        system_prompt = get_ask_question_prompt()
        user_prompt = f"Hier ist der relevante Kontext:\n\n{context_text}\n\nFrage: {question}"

        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                    "max_output_tokens": 800
                }
            )
            response = model.generate_content(user_prompt)
            content = response.text.strip()
            result = json.loads(content)
            return {
                "answer": result.get("answer", "Keine Antwort generiert."),
                "follow_ups": result.get("follow_ups", [])
            }
            
        except Exception as e:
            logger.error(f"Fehler bei ask_question: {e}")
            return {
                "answer": f"KI-Verarbeitung Fehler: {str(e)}",
                "follow_ups": []
            }

    def extract_entities(self, text: str, entity_types: List[str]) -> dict:
        """
        Extrahiert benannte Entitäten aus einem Dokumenttext über Gemini.
        """
        if not self.client:
            return {"error": "KI-Service nicht verfügbar."}

        if not text or not text.strip():
            return {"error": "Kein Text zum Extrahieren vorhanden."}

        requested = {k: v for k, v in ENTITY_TYPE_DESCRIPTIONS.items() if k in entity_types}
        if not requested:
            return {"error": "Keine gültigen Entity-Typen."}

        max_chars = 24000
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + f"\n\n[...{len(text) - max_chars} Zeichen gekürzt...]\n\n" + text[-half:]

        system_prompt = get_extract_entities_prompt(requested)

        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "max_output_tokens": 3000
                }
            )
            response = model.generate_content(f"Dokumenttext:\n\n{text}")
            content = response.text.strip()
            result = json.loads(content)
            return result

        except Exception as e:
            logger.error(f"Fehler bei extract_entities: {e}")
            return {"error": f"KI-Verarbeitung fehlgeschlagen: {str(e)}"}

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    
    if len(sys.argv) > 1:
        processor = AIProcessor()
        text = sys.argv[1]
        print(json.dumps(processor.structure_text(text), indent=2))
    else:
        print("Usage: python ai_processor.py \"Some text to structure\"")
