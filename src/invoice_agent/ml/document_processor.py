from typing import Dict, Any
import logging
from .ocr_processor import OCRProcessor
from .nlp_processor import NLPProcessor

class DocumentProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.ocr = OCRProcessor(config)
        self.nlp = NLPProcessor(config)
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process document using OCR and NLP"""
        try:
            # Perform OCR
            ocr_results = await self.ocr.process_document(file_path)
            
            # Process with NLP
            extracted_data = self.nlp.process_ocr_results(ocr_results)
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Document processing failed: {str(e)}")
            raise 