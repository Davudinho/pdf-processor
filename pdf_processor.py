import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                timeout=300  # 5 minutes timeout for large PDFs
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
    
    def extract_text_from_pdf(self, pdf_path: str) -> list:
        """
        Extract text from a PDF file with enhanced OCR support.
        
        Process:
        1. Check if PDF needs OCR (scanned document detection)
        2. If needed and OCRmyPDF available: preprocess entire PDF with OCRmyPDF
        3. Extract text from all pages using PyMuPDF
        4. Fallback to pytesseract OCR for individual pages if needed
        
        :param pdf_path: Path to the PDF file
        :return: List of dicts for each page: {"page_num": int, "raw_text": str, "text_length": int}
        """
        processed_path = pdf_path
        temp_file_created = False
        
        try:
            # Step 1: Preprocess with OCRmyPDF if available and needed
            if self.use_ocrmypdf and self._needs_ocr(pdf_path):
                logger.info("Preprocessing PDF with OCRmyPDF for better OCR quality...")
                processed_path = self._preprocess_with_ocrmypdf(pdf_path)
                temp_file_created = (processed_path != pdf_path)
            
            # Step 2: Extract text from all pages
            results = []
            doc = fitz.open(processed_path)
            
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                
                # Step 3: Fallback to pytesseract for individual pages if still insufficient
                if self.is_text_scannable(len(text)) and not self.use_ocrmypdf:
                    logger.info(f"Page {page_num} needs additional OCR (pytesseract)...")
                    text = self._perform_ocr(page)
                
                results.append({
                    "page_num": page_num,
                    "raw_text": text,
                    "text_length": len(text)
                })
            
            doc.close()
            
            # Clean up temporary file
            if temp_file_created and os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                    logger.debug(f"Cleaned up temporary file: {processed_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            # Clean up on error
            if temp_file_created and processed_path != pdf_path and os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                except:
                    pass
            raise

    def is_text_scannable(self, text_length: int, threshold: int = 50) -> bool:
        """
        Determine if a page requires OCR based on extracted text length.
        """
        return text_length < threshold

    def _perform_ocr(self, page) -> str:
        """
        Render page to image and perform OCR using Tesseract.
        """
        try:
            # Render page to image (pixmap)
            # matrix=fitz.Matrix(2, 2) increases resolution for better OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            img = Image.open(io.BytesIO(img_data))
            
            # Run Tesseract
            # lang='deu+eng' for German and English support
            text = pytesseract.image_to_string(img, lang='deu+eng')
            return text
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return "[OCR FAILED]"

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
