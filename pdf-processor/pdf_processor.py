import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, tesseract_cmd=None):
        """
        Initialize PDF Processor.
        :param tesseract_cmd: Optional path to tesseract executable if not in PATH
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text_from_pdf(self, pdf_path: str) -> list:
        """
        Extract text from a PDF file. Uses OCR if the text layer is insufficient.
        
        :param pdf_path: Path to the PDF file
        :return: List of dicts for each page: {"page_num": int, "raw_text": str, "text_length": int}
        """
        results = []
        try:
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                
                # Check if we need OCR
                if self.is_text_scannable(len(text)):
                    logger.info(f"Page {page_num} seems scanned/empty. Attempting OCR...")
                    text = self._perform_ocr(page)
                
                results.append({
                    "page_num": page_num,
                    "raw_text": text,
                    "text_length": len(text)
                })
            doc.close()
            return results
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
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
