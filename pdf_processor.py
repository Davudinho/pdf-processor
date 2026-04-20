import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum number of pages processed per OCR/extraction pass.
# Large PDFs are split into chunks of this size, processed separately,
# and then merged — avoiding tool and memory limits for big documents.
MAX_PAGES_PER_CHUNK = 25

class PDFProcessor:
    def __init__(self, tesseract_cmd=None, use_ocrmypdf=True):
        """
        Initialize PDF Processor with optional OCRmyPDF support.
        
        :param tesseract_cmd: Optional path to tesseract executable if not in PATH
        :param use_ocrmypdf: Use OCRmyPDF for better OCR quality (recommended)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self.use_ocrmypdf = use_ocrmypdf
        self._check_ocrmypdf_available()

    def _check_ocrmypdf_available(self):
        """Check if OCRmyPDF is installed and available."""
        if not self.use_ocrmypdf:
            return
        
        try:
            result = subprocess.run(
                ['ocrmypdf', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"OCRmyPDF available: {result.stdout.strip()}")
            else:
                logger.warning("OCRmyPDF not found, falling back to pytesseract")
                self.use_ocrmypdf = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("OCRmyPDF not installed, falling back to pytesseract")
            self.use_ocrmypdf = False
    
    def _preprocess_with_ocrmypdf(self, pdf_path: str) -> str:
        """
        Preprocess PDF with OCRmyPDF to add searchable text layer.
        Significantly improves OCR quality, especially for German/English documents.
        
        :param pdf_path: Path to input PDF
        :return: Path to OCR-processed PDF, or original path if failed
        """
        try:
            # Create temporary output file
            output_fd, output_path = tempfile.mkstemp(suffix='.pdf')
            os.close(output_fd)
            
            logger.info(f"Running OCRmyPDF on: {Path(pdf_path).name}")
            
            # Run OCRmyPDF with optimized settings
            # --skip-text: Preserve existing text, only OCR images
            # -l deu+eng: German and English languages
            # --deskew: Fix skewed pages
            # --optimize 1: Light optimization
            # Note: Removed --clean as it requires 'unpaper' which may not be installed
            cmd = [
                'ocrmypdf',
                '--skip-text',      # Keep existing text layers
                '-l', 'deu+eng',    # German + English
                '--deskew',         # Fix page skew
                '--optimize', '1',  # Light optimization
                '--quiet',          # Less verbose output
                pdf_path,
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900  # 15 minutes timeout for large PDFs (e.g. 80+ pages)
            )
            
            if result.returncode == 0:
                logger.info(f"OCRmyPDF completed successfully")
                return output_path
            else:
                logger.warning(f"OCRmyPDF failed: {result.stderr}")
                # Clean up failed output file
                if os.path.exists(output_path):
                    os.remove(output_path)
                return pdf_path  # Fallback to original
                
        except subprocess.TimeoutExpired:
            logger.error("OCRmyPDF timeout - PDF may be too large")
            if os.path.exists(output_path):
                os.remove(output_path)
            return pdf_path
        except Exception as e:
            logger.error(f"OCRmyPDF error: {e}")
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
            return pdf_path
    
    def _needs_ocr(self, pdf_path: str) -> bool:
        """
        Check if PDF needs OCR by sampling first few pages.
        
        :param pdf_path: Path to PDF file
        :return: True if OCR is needed
        """
        try:
            doc = fitz.open(pdf_path)
            # Check first 3 pages or all pages if less than 3
            sample_size = min(3, len(doc))
            
            for page_num in range(sample_size):
                page = doc[page_num]
                text = page.get_text().strip()
                # If any sampled page has very little text, assume OCR is needed
                if len(text) < 50:
                    doc.close()
                    logger.info(f"OCR needed: Page {page_num + 1} has only {len(text)} characters")
                    return True
            
            doc.close()
            logger.info("PDF already has text, OCR preprocessing skipped")
            return False
        except Exception as e:
            logger.warning(f"Error checking if OCR needed: {e}")
            return True  # When in doubt, apply OCR
    
    def _create_pdf_chunk(self, source_doc, start_page: int, end_page: int) -> str:
        """
        Save pages [start_page, end_page) from source_doc into a temporary PDF file.

        :param source_doc: Open fitz.Document (the full original PDF)
        :param start_page:  0-based index of the first page to include
        :param end_page:    0-based index AFTER the last page to include
        :return: Path to the newly created temporary PDF file
        """
        chunk_doc = fitz.open()  # empty PDF
        chunk_doc.insert_pdf(source_doc, from_page=start_page, to_page=end_page - 1)
        fd, chunk_path = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        chunk_doc.save(chunk_path)
        chunk_doc.close()
        return chunk_path

    def _extract_chunk(self, chunk_path: str, page_offset: int) -> list:
        """
        Extract text from a single PDF chunk (max MAX_PAGES_PER_CHUNK pages).

        Steps:
        1. OCRmyPDF preprocessing (if available and chunk needs OCR)
        2. Page-by-page text extraction via PyMuPDF
        3. Per-page pytesseract fallback when extracted text is too short

        :param chunk_path:   Path to the temporary chunk PDF
        :param page_offset:  How many pages come before this chunk in the original
                             document (used to compute the correct global page number)
        :return: List of page dicts with globally-correct page_num values
        """
        processed_path = chunk_path
        temp_ocr_file = None

        try:
            # Step 1: Preprocess with OCRmyPDF if available and needed
            if self.use_ocrmypdf and self._needs_ocr(chunk_path):
                logger.info(f"  OCRmyPDF: preprocessing chunk (pages {page_offset + 1}–{page_offset + MAX_PAGES_PER_CHUNK})...")
                ocr_path = self._preprocess_with_ocrmypdf(chunk_path)
                if ocr_path != chunk_path:
                    temp_ocr_file = ocr_path
                    processed_path = ocr_path

            # Step 2: Extract text page by page
            results = []
            doc = fitz.open(processed_path)

            for local_idx, page in enumerate(doc):
                global_page_num = page_offset + local_idx + 1  # 1-based
                text = page.get_text()

                # Step 3: pytesseract fallback for pages with too little text
                if self.is_text_scannable(len(text)):
                    logger.info(
                        f"  Page {global_page_num}: only {len(text)} chars — trying pytesseract..."
                    )
                    ocr_text = self._perform_ocr(page)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text

                results.append({
                    "page_num": global_page_num,
                    "raw_text": text,
                    "text_length": len(text)
                })

            doc.close()
            return results

        finally:
            # Always clean up the OCRmyPDF temp file for this chunk
            if temp_ocr_file and os.path.exists(temp_ocr_file):
                try:
                    os.remove(temp_ocr_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up OCR temp file: {e}")

    def extract_text_from_pdf(self, pdf_path: str) -> list:
        """
        Extract text from a PDF file — with automatic chunking for large documents.

        Strategy (Split → Process → Merge):
        1. Count total pages.
        2. If pages ≤ MAX_PAGES_PER_CHUNK → process the whole file at once.
        3. If pages > MAX_PAGES_PER_CHUNK → split into temporary PDF chunks
           of at most MAX_PAGES_PER_CHUNK pages each.
        4. Process every chunk independently (OCR + text extraction).
        5. Merge all chunk results, sorted by page number, and return.

        Example: 84-page PDF with MAX_PAGES_PER_CHUNK=25
          → chunk 1: pages  1–25
          → chunk 2: pages 26–50
          → chunk 3: pages 51–75
          → chunk 4: pages 76–84
          → merge all 84 page results into one list

        :param pdf_path: Path to the PDF file
        :return: List of dicts, one per page: {"page_num": int, "raw_text": str, "text_length": int}
        """
        chunk_temp_files = []  # track temp files so we always clean them up

        try:
            # ── Step 1: Count pages ──────────────────────────────────────────
            source_doc = fitz.open(pdf_path)
            total_pages = len(source_doc)
            logger.info(
                f"PDF '{Path(pdf_path).name}' has {total_pages} pages "
                f"(chunk limit: {MAX_PAGES_PER_CHUNK})"
            )

            # ── Step 2 & 3: Build list of (chunk_path, page_offset) ────────────
            if total_pages <= MAX_PAGES_PER_CHUNK:
                # Small PDF — no splitting needed
                source_doc.close()
                chunks = [(pdf_path, 0)]
            else:
                # Large PDF — split into chunks
                num_chunks = (total_pages + MAX_PAGES_PER_CHUNK - 1) // MAX_PAGES_PER_CHUNK
                logger.info(
                    f"Large PDF: splitting into {num_chunks} chunks of max "
                    f"{MAX_PAGES_PER_CHUNK} pages each..."
                )
                chunks = []
                for chunk_idx in range(num_chunks):
                    start = chunk_idx * MAX_PAGES_PER_CHUNK          # 0-based
                    end   = min(start + MAX_PAGES_PER_CHUNK, total_pages)  # exclusive
                    chunk_path = self._create_pdf_chunk(source_doc, start, end)
                    chunk_temp_files.append(chunk_path)
                    chunks.append((chunk_path, start))
                    logger.info(
                        f"  Chunk {chunk_idx + 1}/{num_chunks}: "
                        f"pages {start + 1}–{end} → {chunk_path}"
                    )
                source_doc.close()

            # ── Step 4: Process every chunk ────────────────────────────────
            all_results = []
            for i, (chunk_path, page_offset) in enumerate(chunks, 1):
                logger.info(f"Processing chunk {i}/{len(chunks)} (offset={page_offset})...")
                chunk_results = self._extract_chunk(chunk_path, page_offset)
                all_results.extend(chunk_results)

            # ── Step 5: Merge ───────────────────────────────────────────────
            all_results.sort(key=lambda x: x["page_num"])
            logger.info(
                f"Extraction complete: {len(all_results)}/{total_pages} pages extracted."
            )
            return all_results

        except Exception as e:
            logger.error(f"Error processing PDF '{pdf_path}': {e}")
            raise

        finally:
            # Always clean up any temporary chunk PDF files
            for tmp in chunk_temp_files:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception as e:
                    logger.warning(f"Failed to clean up chunk file '{tmp}': {e}")

    def is_text_scannable(self, text_length: int, threshold: int = 50) -> bool:
        """
        Determine if a page requires OCR based on extracted text length.
        """
        return text_length < threshold

    def _perform_ocr(self, page) -> str:
        """
        Render page to image and perform enhanced OCR using Tesseract.

        Pipeline:
        1. Adaptive DPI  — higher resolution for small/dense pages
        2. Grayscale conversion
        3. Contrast & sharpness enhancement
        4. Adaptive binarization (Otsu-style threshold)
        5. Tesseract with optimised config (PSM 6, OEM 3)
        6. Memory cleanup after each page
        """
        pix = None
        try:
            # ── 1. Adaptive DPI ────────────────────────────────────────────────
            # PyMuPDF pages are in points (1 pt = 1/72 inch).
            # Target 300 DPI for normal pages, 350 DPI for small/dense pages.
            page_width_pt = page.rect.width
            page_height_pt = page.rect.height
            target_dpi = 350 if (page_width_pt < 400 or page_height_pt < 400) else 300
            zoom = target_dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Free the pixmap immediately to avoid accumulating RAM over many pages
            pix = None

            # ── 2. Grayscale ───────────────────────────────────────────────────
            img = img.convert("L")

            # ── 3. Contrast + Sharpness enhancement ───────────────────────────
            img = ImageEnhance.Contrast(img).enhance(1.8)
            img = ImageEnhance.Sharpness(img).enhance(2.0)

            # ── 4. Adaptive binarization (Otsu-style via histogram) ────────────
            # Compute a simple histogram-based threshold
            histogram = img.histogram()
            total_pixels = img.width * img.height
            cumulative = 0
            threshold = 128  # sensible default
            for value, count in enumerate(histogram):
                cumulative += count
                if cumulative >= total_pixels * 0.5:
                    threshold = value
                    break
            # Clamp threshold to a useful range so we don't over-darken
            threshold = max(80, min(threshold, 200))
            img = img.point(lambda px: 255 if px > threshold else 0, "L")

            # ── 5. Tesseract OCR ───────────────────────────────────────────────
            # PSM 6 = assume a uniform block of text (good for full pages)
            # OEM 3 = default engine (LSTM neural net + legacy fallback)
            custom_config = r"--psm 6 --oem 3"
            text = pytesseract.image_to_string(img, lang="deu+eng", config=custom_config)

            # ── 6. Cleanup ─────────────────────────────────────────────────────
            img.close()
            return text

        except MemoryError:
            logger.error("OCR MemoryError — page skipped to avoid crash")
            return "[OCR SKIPPED: Nicht genug RAM]"
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return "[OCR FAILED]"
        finally:
            # Ensure pixmap memory is always released
            if pix is not None:
                pix = None

if __name__ == "__main__":
    # Test script
    import sys
    if len(sys.argv) > 1:
        processor = PDFProcessor()
        try:
            data = processor.extract_text_from_pdf(sys.argv[1])
            for page in data:
                print(f"--- Page {page['page_num']} ---")
                print(page['raw_text'][:200] + "...")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python pdf_processor.py <path_to_pdf>")
