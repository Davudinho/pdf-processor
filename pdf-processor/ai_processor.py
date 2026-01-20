import openai
import json
import logging
import os
from database import MongoDBManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self, api_key=None, model="gpt-3.5-turbo"):
        """
        Initialize AI Processor.
        :param api_key: OpenAI API Key. If None, tries to read from env or os.
        :param model: OpenAI model to use.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OPENAI_API_KEY provided or found in environment.")
        
        self.client = openai.OpenAI(api_key=self.api_key)
        self.model = model

    def structure_text(self, raw_text: str) -> dict:
        """
        Send raw text to OpenAI to extract structure.
        """
        if not raw_text or len(raw_text.strip()) == 0:
            return {}

        system_prompt = """
        You are a document extraction assistant. Convert the given text into a structured JSON object.
        Focus on extracting:
        1. 'sections': Key sections or headings with their content.
        2. 'measurements': Any numerical values with units.
        3. 'key_fields': Dates, names, invoice numbers, specific identifiers.
        4. 'tables': If there is tabular data, represent it as a list of dictionaries or list of lists.
        
        Output valid JSON only. Do not add markdown formatting like ```json ... ```.
        Support German and English text.
        If a field is not found, omit it or return empty.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text to structure:\n\n{raw_text[:3000]}"} # Truncate to avoid token limits if necessary
                ],
                temperature=0,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # Basic cleanup if the model outputs markdown code blocks despite instructions
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {content}")
            return {"error": "Failed to parse AI output", "raw_response": content}
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return {"error": str(e)}

    def process_document(self, db_manager: MongoDBManager, doc_id: str):
        """
        Process all pages of a document and update MongoDB with structured data.
        """
        pages = db_manager.get_raw_text(doc_id)
        if not pages:
            logger.warning(f"No pages found for document {doc_id}")
            return

        for page in pages:
            page_num = page["page_num"]
            raw_text = page.get("raw_text", "")
            
            if not raw_text:
                continue
                
            logger.info(f"Structuring page {page_num} of document {doc_id}...")
            structured_data = self.structure_text(raw_text)
            
            db_manager.update_structured_text(doc_id, page_num, structured_data)
        
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
