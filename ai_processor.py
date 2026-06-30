import json
import logging
import os
import re
import time
from datetime import datetime
from database import MongoDBManager
from typing import Dict, Any, Optional, List
from openai import OpenAI

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
        Initialize AI Processor for OpenAI.
        :param api_key: OpenAI API Key. If None, tries to read from env.
        :param model: OpenAI chat model to use.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        
        if not self.api_key:
            logger.error("=" * 70)
            logger.error("CRITICAL: No OPENAI_API_KEY provided or found in environment.")
            logger.error("AI processing will fail. Please set OPENAI_API_KEY in .env file")
            logger.error("=" * 70)
        else:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"OpenAI client initialized successfully (model: {model})")
                logger.info(f"API key: {self.api_key[:10]}...{self.api_key[-4:]}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
        
        self.model = model

    def _clean_json(self, raw: str) -> str:
        """Strip markdown fences, trailing commas, and other common JSON issues."""
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        raw = raw.strip()
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        return raw

    def _parse_json_safe(self, raw: str) -> Optional[dict]:
        """Try to parse JSON, returning None if it fails even after cleanup."""
        cleaned = self._clean_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error after cleanup: {e}\nRaw snippet: {cleaned[:200]}")
            return None

    def _generate_with_retry(self, system_prompt: str, user_prompt: str,
                              config: dict, max_retries: int = 5, initial_delay: float = 8) -> Optional[str]:
        """
        Call OpenAI chat completions with exponential backoff for 429 quota errors.
        Returns the response text, or None if all retries are exhausted.
        """
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=config.get("temperature", 0.0),
                    max_completion_tokens=config.get("max_completion_tokens", 4000),
                    response_format=config.get("response_format", None)
                )
                
                # Token Tracking und Kostenkalkulation
                if response.usage:
                    p_tokens = response.usage.prompt_tokens
                    c_tokens = response.usage.completion_tokens
                    # gpt-4o-mini Preise (ca. $0.15 per 1M input, $0.60 per 1M output)
                    if "mini" in self.model:
                        cost = (p_tokens / 1000000) * 0.15 + (c_tokens / 1000000) * 0.60
                        logger.info(f"Token Usage: Prompt={p_tokens}, Completion={c_tokens} | Estimated Cost: ${cost:.6f}")
                    else:
                        logger.info(f"Token Usage: Prompt={p_tokens}, Completion={c_tokens}")

                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Rate limit hit. Waiting {delay:.0f}s before retry "
                            f"(attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(delay)
                        delay = min(delay * 1.5, 120)  # cap at 2 minutes
                    else:
                        logger.error("Max retries reached - giving up.")
                        raise
                else:
                    raise
        return None

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

    def _is_page_worth_analyzing(self, raw_text: str, min_chars: int = 40) -> bool:
        import re
        stripped = raw_text.strip()
        if not stripped:
            return False
        if re.fullmatch(r"\d{1,3}", stripped):
            return False
        content_chars = len(re.sub(r"\s+", "", stripped))
        if content_chars < min_chars:
            return False
        return True

    def structure_text(self, raw_text: str, max_chars: int = 8000) -> Dict[str, Any]:
        """Send raw text to OpenAI to extract structure, summary, and keywords."""
        if not self.client:
            logger.error("Cannot structure text: OpenAI client not initialized")
            default = self._get_default_structure()
            default["processing_status"] = "no_api_key"
            return default

        if not raw_text or len(raw_text.strip()) == 0:
            logger.warning("Empty text provided for structuring")
            default = self._get_default_structure()
            default["processing_status"] = "empty_text"
            return default

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
            text_to_process = (
                f"{first_part}\n\n"
                f"[...{len(raw_text) - len(first_part) - len(last_part)} chars truncated...]\n\n"
                f"{last_part}"
            )

        system_prompt = get_structure_text_prompt()

        try:
            logger.info(f"Sending {len(text_to_process)} chars to OpenAI ({self.model})...")
            raw = self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=f"Text to structure:\n\n{text_to_process}",
                config={
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_completion_tokens": 4000,
                }
            )

            if raw is None:
                default = self._get_default_structure()
                default["processing_status"] = "api_error"
                return default

            logger.info(f"Received response from OpenAI ({len(raw)} chars)")
            data = self._parse_json_safe(raw)

            if data is None:
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
            default["error_message"] = str(e)
            return default

    def structure_pages_batch(self, pages: List[Dict], max_chars_per_page: int = 3000) -> Dict[int, Dict[str, Any]]:
        """
        Process multiple pages in a single API call.
        Returns a dict mapping page_num -> structured_data.
        """
        if not self.client:
            return {}

        combined_parts = []
        for page in pages:
            page_num = page.get("page_num", "?")
            raw_text = page.get("raw_text", "").strip()
            if len(raw_text) > max_chars_per_page:
                half = max_chars_per_page // 2
                raw_text = raw_text[:half] + f"\n[...gekürzt...]\n" + raw_text[-half:]
            combined_parts.append(f"=== SEITE {page_num} ===\n{raw_text}")

        combined_text = "\n\n".join(combined_parts)
        page_nums = [p.get("page_num") for p in pages]

        system_prompt = (
            "Du bist ein Dokumentenanalyst. Du erhältst mehrere Seiten eines PDF-Dokuments. "
            "Für JEDE Seite erstellst du eine strukturierte Analyse. "
            "Antworte mit einem JSON-Objekt, dessen Schlüssel die Seitennummern (als Strings) sind. "
            "Jeder Wert hat folgende Felder: summary (string), keywords (array of strings), "
            "sections (array of strings), measurements (array of strings), "
            "key_fields (object with string values), tables (array of objects). "
            "Halte die Zusammenfassungen auf max. 2-3 Sätze pro Seite. "
            "Verwende die Sprache des Dokuments (Deutsch oder Englisch)."
        )

        try:
            raw = self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=f"Analysiere die folgenden Seiten:\n\n{combined_text}",
                config={
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_completion_tokens": 16000,
                }
            )

            if raw is None:
                return {}

            parsed = self._parse_json_safe(raw)
            if not isinstance(parsed, dict):
                return {}

            result = {}
            for page_num in page_nums:
                entry = parsed.get(str(page_num)) or parsed.get(page_num)
                if entry and isinstance(entry, dict):
                    entry["processing_status"] = "success"
                    result[page_num] = entry
                else:
                    result[page_num] = self._get_default_structure()
                    result[page_num]["processing_status"] = "missing_in_batch"

            return result

        except Exception as e:
            logger.error(f"Batch page processing failed: {e}")
            return {}

    def process_document(self, db_manager: MongoDBManager, doc_id: str,
                         batch_size: int = 10):
        logger.info(f"Starting AI processing for document: {doc_id}")
        
        if not self.client:
            logger.error("CRITICAL: Cannot process document - API client not initialized")
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

        pending_pages = []
        skipped_results = []
        empty_count = 0
        for page in pages:
            if page.get("status") == "structured" and page.get("page_summary"):
                skipped_results.append({
                    "success": True, "skipped": True,
                    "page_num": page.get("page_num"),
                    "summary": page.get("page_summary", ""),
                    "keywords": page.get("keywords", [])
                })
            elif not self._is_page_worth_analyzing(page.get("raw_text", "")):
                empty_count += 1
                empty_structure = self._get_default_structure()
                empty_structure["processing_status"] = "skipped_empty"
                db_manager.update_page_data(
                    doc_id=doc_id,
                    page_num=page.get("page_num"),
                    structured_data=empty_structure,
                    page_summary="[Seite ohne verwertbaren Inhalt]",
                    keywords=[]
                )
            else:
                pending_pages.append(page)

        logger.info(
            f"Document {doc_id}: {len(pages)} pages total — "
            f"{len(skipped_results)} already done, {empty_count} empty/skipped, "
            f"{len(pending_pages)} to analyse (batch_size={batch_size})"
        )

        all_summaries = [r["summary"] for r in skipped_results if r["summary"]]
        all_keywords: List[str] = []
        for r in skipped_results:
            all_keywords.extend(r["keywords"])

        processed_count = len(skipped_results)
        failed_count = 0

        total_batches = (len(pending_pages) + batch_size - 1) // batch_size if pending_pages else 0
        consecutive_failures = 0

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch = pending_pages[batch_start: batch_start + batch_size]
            page_nums_in_batch = [p.get("page_num") for p in batch]

            logger.info(f"  Batch {batch_idx + 1}/{total_batches}: pages {page_nums_in_batch}")

            batch_results = self.structure_pages_batch(batch)

            for page in batch:
                page_num = page.get("page_num")
                structured_data = batch_results.get(page_num)

                if structured_data is None:
                    logger.warning(f"    Page {page_num} missing from batch result – retrying individually")
                    structured_data = self.structure_text(page.get("raw_text", ""))
                    time.sleep(2)

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

                ok = success and processing_status in ("success", "partial_success")
                if ok:
                    processed_count += 1
                    consecutive_failures = 0
                    if page_summary:
                        all_summaries.append(page_summary)
                    all_keywords.extend(keywords)
                else:
                    failed_count += 1
                    consecutive_failures += 1
                    logger.error(f"    ✗ Page {page_num} failed (status={processing_status})")
                    
                    if consecutive_failures >= 3:
                        logger.error("Too many consecutive AI failures. Aborting document processing to prevent timeouts.")
                        raise RuntimeError("KI-Verarbeitung abgebrochen: 3 aufeinanderfolgende Seiten sind fehlgeschlagen (Rate Limit oder API-Fehler).")

            if batch_idx < total_batches - 1:
                time.sleep(5)

        if all_summaries:
            self._update_document_metadata(db_manager, doc_id, all_summaries, all_keywords)

        logger.info(
            f"Processing complete for document {doc_id}: "
            f"{processed_count}/{len(pages)} pages OK, {failed_count} failed."
        )
    
    def generate_document_summary(self, page_summaries: List[str], existing_categories: List[str] = None) -> dict:
        if not page_summaries:
            return {"summary": "", "category": "Sonstiges"}

        context = "\n\n".join([f"Page {i+1}: {summary}" for i, summary in enumerate(page_summaries)])
        if len(context) > 12000:
            context = context[:6000] + "\n\n[...intermediate pages omitted...]\n\n" + context[-6000:]

        system_prompt = get_document_summary_prompt(existing_categories)

        try:
            raw = self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=f"Here are the summaries of the document pages:\n\n{context}",
                config={
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_completion_tokens": 1500,
                }
            )
            if raw is None:
                raise ValueError("No response from API")
            result = self._parse_json_safe(raw)
            if result is None:
                raise ValueError("Could not parse JSON response")
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
        """Erstellt einen Embedding-Vektor über OpenAI."""
        if not self.client:
            logger.error("create_embedding: OpenAI Client nicht initialisiert.")
            return []

        if not text or not text.strip():
            logger.warning("create_embedding: Leerer Text übergeben.")
            return []

        try:
            text_to_embed = text[:32000] if len(text) > 32000 else text
            response = self.client.embeddings.create(
                input=text_to_embed,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"create_embedding: Fehler: {e}")
            return []

    def create_embeddings_batch(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        if not self.client:
            logger.error("create_embeddings_batch: OpenAI Client nicht initialisiert.")
            return []

        if not texts:
            return []

        valid_texts = [t[:32000] if len(t) > 32000 else t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        all_embeddings = []
        total_batches = (len(valid_texts) + batch_size - 1) // batch_size
        logger.info(f"Starte Batch-Embedding: {len(valid_texts)} Chunks in {total_batches} Batches...")

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch = valid_texts[batch_start:batch_start + batch_size]

            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-small"
                )
                batch_embeddings = [d.embedding for d in response.data]
                all_embeddings.extend(batch_embeddings)
                logger.info(f"  ✓ Batch {batch_idx + 1}/{total_batches} fertig ({len(batch_embeddings)} Vektoren)")

            except Exception as e:
                logger.warning(f"  Fehler bei Batch {batch_idx + 1}: {e}. Fallback auf Einzelverarbeitung...")
                time.sleep(10)
                for text in batch:
                    emb = self.create_embedding(text)
                    all_embeddings.append(emb)
                    time.sleep(1)

            if batch_idx < total_batches - 1:
                time.sleep(5)

        return all_embeddings

    def ask_question(self, question: str, context_chunks: List[str]) -> dict:
        if not self.client:
            logger.error("ask_question: OpenAI Client nicht initialisiert.")
            return {"answer": "Fehler: KI-Service ist nicht verfügbar.", "follow_ups": []}
            
        if not context_chunks:
            return {"answer": "Ich konnte keine passenden Informationen finden.", "follow_ups": []}
            
        context_text = "\n\n---\n\n".join(context_chunks)
        system_prompt = get_ask_question_prompt()
        user_prompt = f"Hier ist der relevante Kontext:\n\n{context_text}\n\nFrage: {question}"

        try:
            raw = self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config={
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_completion_tokens": 2000,
                }
            )
            if raw is None:
                raise ValueError("No response from API")
            result = self._parse_json_safe(raw)
            if result is None:
                raise ValueError("Could not parse JSON response")
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
            raw = self._generate_with_retry(
                system_prompt=system_prompt,
                user_prompt=f"Dokumenttext:\n\n{text}",
                config={
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                    "max_completion_tokens": 8000,
                }
            )
            if raw is None:
                raise ValueError("No response from API")
            result = self._parse_json_safe(raw)
            if result is None:
                raise ValueError("Could not parse JSON")
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
