import openai
import json
import logging
import os
from datetime import datetime
from database import MongoDBManager
from typing import Dict, Any, Optional, List
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
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
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
            # Better truncation: Split by spaces to avoid cutting words
            mid_point = int(max_chars * 0.7)
            end_point = len(raw_text) - int(max_chars * 0.3)
            
            # Find nearest space to avoid cutting words
            safe_mid = raw_text.rfind(' ', 0, mid_point)
            safe_end = raw_text.find(' ', end_point)
            
            if safe_mid == -1: safe_mid = mid_point
            if safe_end == -1: safe_end = end_point
            
            first_part = raw_text[:safe_mid]
            last_part = raw_text[safe_end:]
            text_to_process = f"{first_part}\n\n[...{len(raw_text) - len(first_part) - len(last_part)} chars truncated...]\n\n{last_part}"

        system_prompt = get_structure_text_prompt()

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
    
    def generate_document_summary(self, page_summaries: List[str]) -> dict:
        """
        Generate a concise executive summary and automatically categorize the entire document based on page summaries.
        """
        if not page_summaries:
            return {"summary": "", "category": "Sonstiges"}

        # Combine page summaries into a context
        context = "\n\n".join([f"Page {i+1}: {summary}" for i, summary in enumerate(page_summaries)])
        
        # Truncate if too long (approx 12k chars to stay well within token limits for 4o-mini/3.5)
        if len(context) > 12000:
             context = context[:6000] + "\n\n[...intermediate pages omitted...]\n\n" + context[-6000:]

        system_prompt = get_document_summary_prompt()

        try:
            logger.info(f"Generating document summary and category from {len(page_summaries)} pages...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here are the summaries of the document pages:\n\n{context}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500
            )
            content = response.choices[0].message.content.strip()
            import json
            result = json.loads(content)
            return {
                "summary": result.get("summary", ""),
                "category": result.get("category", "Sonstiges")
            }
        except Exception as e:
            logger.error(f"Failed to generate document summary and category: {e}")
            # Fallback to simple concatenation
            summary_text = f"Document with {len(page_summaries)} pages. " + page_summaries[0]
            return {"summary": summary_text, "category": "Sonstiges"}

    def _update_document_metadata(self, db_manager: MongoDBManager, doc_id: str, 
                                   page_summaries: List[str], all_keywords: List[str]):
        """
        Update document-level metadata with aggregated summaries, keywords and category.
        
        :param db_manager: Database manager instance
        :param doc_id: Document ID
        :param page_summaries: List of page summaries
        :param all_keywords: List of all keywords from all pages
        """
        try:
            # Create document summary and category using AI
            doc_info = self.generate_document_summary(page_summaries)
            doc_summary = doc_info.get("summary", "")
            doc_category = doc_info.get("category", "Sonstiges")
            
            # Deduplicate and limit keywords
            unique_keywords = list(dict.fromkeys(all_keywords))[:30]  # Top 30 unique keywords
            
            # Update documents collection
            if db_manager.documents_collection is not None:
                logger.info(f"Updating document {doc_id} with category {doc_category}, {len(unique_keywords)} keywords and summary length {len(doc_summary)}")
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
                logger.info(f"Updated document-level metadata for {doc_id}")
        except Exception as e:
            logger.error(f"Error updating document metadata: {e}")

    def create_embedding(self, text: str) -> List[float]:
        """
        Erstellt einen Embedding-Vektor für einen Text.

        Was passiert hier?
        - Der Text wird an OpenAI gesendet
        - OpenAI gibt eine Liste von 1536 Zahlen zurück
        - Diese Zahlen repräsentieren die "Bedeutung" des Textes im Vektorraum
        - Ähnliche Texte → ähnliche Vektoren → semantische Suche wird möglich

        Modell: text-embedding-3-small (1536 Dimensionen, kosteneffizient)

        :param text: Text für den Embedding erstellt werden soll
        :return: Liste von 1536 Floats (der Vektor) oder leere Liste bei Fehler
        """
        if not self.client:
            logger.error("create_embedding: OpenAI Client nicht initialisiert.")
            return []

        if not text or not text.strip():
            logger.warning("create_embedding: Leerer Text übergeben.")
            return []

        try:
            # Text kürzen falls zu lang (max ~8000 Tokens ~ 32000 Zeichen)
            text_to_embed = text[:32000] if len(text) > 32000 else text

            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text_to_embed
            )
            embedding = response.data[0].embedding
            logger.info(f"Embedding erstellt: {len(embedding)} Dimensionen für {len(text)} Zeichen Text")
            return embedding

        except openai.AuthenticationError:
            logger.error("create_embedding: Ungültiger API-Key.")
            return []
        except openai.RateLimitError:
            logger.error("create_embedding: Rate Limit erreicht.")
            return []
        except Exception as e:
            logger.error(f"create_embedding: Unerwarteter Fehler: {e}")
            return []

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Erstellt Embeddings für mehrere Texte auf einmal.

        Effizienter als create_embedding() einzeln aufzurufen, weil
        OpenAI alle Texte in einem einzigen API-Call verarbeitet.

        Beispiel:
            texts = ["Chunk 1 Text", "Chunk 2 Text", "Chunk 3 Text"]
            embeddings = ai.create_embeddings_batch(texts)
            # embeddings[0] = Vektor für "Chunk 1 Text"
            # embeddings[1] = Vektor für "Chunk 2 Text"
            # embeddings[2] = Vektor für "Chunk 3 Text"

        :param texts: Liste von Texten
        :return: Liste von Vektoren (leere Liste bei Fehler)
        """
        if not self.client:
            logger.error("create_embeddings_batch: OpenAI Client nicht initialisiert.")
            return []

        if not texts:
            return []

        # Leere Texte filtern, aber Position merken für spätere Zuordnung
        valid_texts = [t[:32000] if len(t) > 32000 else t for t in texts if t and t.strip()]

        if not valid_texts:
            return []

        try:
            logger.info(f"Erstelle Batch-Embeddings für {len(valid_texts)} Texte...")
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=valid_texts
            )
            # OpenAI gibt die Embeddings in der gleichen Reihenfolge zurück
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Batch-Embeddings fertig: {len(embeddings)} Vektoren à {len(embeddings[0])} Dimensionen")
            return embeddings

        except openai.RateLimitError:
            logger.warning("Rate Limit bei Batch-Embeddings. Versuche einzeln...")
            # Fallback: einzeln verarbeiten
            results = []
            for text in valid_texts:
                emb = self.create_embedding(text)
                results.append(emb)
            return results
        except Exception as e:
            logger.error(f"create_embeddings_batch: Fehler: {e}")
            return []

    def ask_question(self, question: str, context_chunks: List[str]) -> dict:
        """
        Beantwortet eine Frage basierend auf den übergebenen Text-Chunks (RAG).
        
        :param question: Die Frage des Benutzers
        :param context_chunks: Liste der relevanten Textabschnitte aus Qdrant
        :return: Die Antwort des KI-Modells
        """
        if not self.client:
            logger.error("ask_question: OpenAI Client nicht initialisiert.")
            return "Fehler: KI-Service ist nicht verfügbar."
            
        if not context_chunks:
            return "Ich konnte keine passenden Informationen im Dokument finden, um diese Frage zu beantworten."
            
        # Kontext zusammenbauen
        context_text = "\n\n---\n\n".join(context_chunks)
        
        system_prompt = get_ask_question_prompt()
        user_prompt = f"""Hier ist der relevante Kontext aus dem Dokument:

{context_text}

Frage: {question}"""

        try:
            logger.info(f"Generiere Antwort für Frage: '{question[:30]}...' (Kontext-Länge: {len(context_text)} Zeichen)")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2, # Niedrige Temperatur für fokussierte, faktenbasierte Antworten
                max_tokens=800
            )
            content = response.choices[0].message.content.strip()
            import json
            result = json.loads(content)
            return {
                "answer": result.get("answer", "Keine Antwort generiert."),
                "follow_ups": result.get("follow_ups", [])
            }
            
        except Exception as e:
            logger.error(f"Fehler bei ask_question: {e}")
            return {
                "answer": f"Es gab einen Fehler bei der KI-Verarbeitung: {str(e)}",
                "follow_ups": []
            }

    def extract_entities(self, text: str, entity_types: List[str]) -> dict:
        """
        Extrahiert benannte Entitäten aus einem Dokumenttext.
        
        Nutzt NICHT RAG, sondern den kompletten Text, da wir ALLE Entitäten finden wollen.
        
        :param text: Kompletter Dokumenttext (alle Seiten zusammen)
        :param entity_types: Liste der gewünschten Entity-Typen 
                            (z.B. ["personen", "firmen", "betraege"])
        :return: Dict mit Entity-Typ als Key und Liste von Rows als Value
        """
        if not self.client:
            logger.error("extract_entities: OpenAI Client nicht initialisiert.")
            return {"error": "KI-Service ist nicht verfügbar."}

        if not text or not text.strip():
            return {"error": "Kein Text zum Extrahieren vorhanden."}

        # Use centralized entity type definitions from prompts.py
        requested = {k: v for k, v in ENTITY_TYPE_DESCRIPTIONS.items() if k in entity_types}
        if not requested:
            return {"error": "Keine gültigen Entity-Typen angegeben."}

        # Truncate very long texts (keep beginning + end)
        max_chars = 24000
        if len(text) > max_chars:
            half = max_chars // 2
            text = text[:half] + f"\n\n[...{len(text) - max_chars} Zeichen gekürzt...]\n\n" + text[-half:]

        system_prompt = get_extract_entities_prompt(requested)

        try:
            logger.info(f"Entity Extraction: {len(text)} Zeichen, Typen: {list(requested.keys())}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Dokumenttext:\n\n{text}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=3000
            )
            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            logger.info(f"Entity Extraction erfolgreich: {', '.join(f'{k}={len(v)}' for k, v in result.items() if isinstance(v, list))}")
            return result

        except Exception as e:
            logger.error(f"Fehler bei extract_entities: {e}")
            return {"error": f"KI-Verarbeitung fehlgeschlagen: {str(e)}"}

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
