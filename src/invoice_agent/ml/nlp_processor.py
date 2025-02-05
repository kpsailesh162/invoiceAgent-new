from typing import Dict, Any, List
import spacy
from transformers import pipeline
import re
from datetime import datetime
import logging
from .ocr_processor import OCRResult

class NLPProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.nlp = spacy.load("en_core_web_lg")
        self.ner = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english")
        
        # Load custom patterns and rules
        self.patterns = self._load_patterns()
    
    def process_ocr_results(
        self,
        ocr_results: List[OCRResult]
    ) -> Dict[str, Any]:
        """Process OCR results with NLP"""
        try:
            # Combine text while preserving layout
            processed_text = self._combine_text(ocr_results)
            
            # Extract key fields
            extracted_data = self._extract_fields(processed_text)
            
            # Validate and normalize
            normalized_data = self._normalize_data(extracted_data)
            
            return normalized_data
            
        except Exception as e:
            self.logger.error(f"NLP processing failed: {str(e)}")
            raise
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load custom patterns for field extraction"""
        return {
            'invoice_number': [
                r'(?i)invoice\s*(?:#|number|num|no)?[:.]?\s*([A-Z0-9-]+)',
                r'(?i)inv\s*(?:#|number|num|no)?[:.]?\s*([A-Z0-9-]+)'
            ],
            'date': [
                r'(?i)date[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                r'(?i)dated[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
            ],
            'amount': [
                r'(?i)total\s*amount[:.]?\s*[\$£€]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'(?i)grand\s*total[:.]?\s*[\$£€]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'tax_id': [
                r'(?i)tax\s*id[:.]?\s*([A-Z0-9-]+)',
                r'(?i)vat\s*number[:.]?\s*([A-Z0-9-]+)'
            ]
        }
    
    def _combine_text(self, ocr_results: List[OCRResult]) -> str:
        """Combine OCR results while preserving layout"""
        # Sort by page and position
        sorted_results = sorted(
            ocr_results,
            key=lambda x: (x.page_number, x.bounding_box[1], x.bounding_box[0])
        )
        
        # Combine text with layout preservation
        current_y = None
        combined_text = []
        line_buffer = []
        
        for result in sorted_results:
            if current_y is None:
                current_y = result.bounding_box[1]
            
            # Check if new line
            if abs(result.bounding_box[1] - current_y) > 10:
                combined_text.append(' '.join(line_buffer))
                line_buffer = []
                current_y = result.bounding_box[1]
            
            line_buffer.append(result.text)
        
        if line_buffer:
            combined_text.append(' '.join(line_buffer))
        
        return '\n'.join(combined_text)
    
    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract key fields using patterns and NLP"""
        # Basic pattern matching
        extracted = {}
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    extracted[field] = match.group(1)
                    break
        
        # NLP-based extraction
        doc = self.nlp(text)
        
        # Extract organizations (vendor/customer)
        orgs = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
        if orgs:
            extracted['vendor_name'] = orgs[0]  # Usually first org is vendor
        
        # Extract money amounts
        amounts = [ent.text for ent in doc.ents if ent.label_ == 'MONEY']
        if amounts and 'amount' not in extracted:
            extracted['amount'] = amounts[-1]  # Usually last amount is total
        
        # Extract dates
        dates = [ent.text for ent in doc.ents if ent.label_ == 'DATE']
        if dates and 'date' not in extracted:
            extracted['date'] = dates[0]
        
        return extracted
    
    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize extracted data"""
        normalized = {}
        
        # Normalize date
        if 'date' in data:
            try:
                date_str = data['date']
                # Try different date formats
                for fmt in ('%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        normalized['date'] = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                self.logger.warning(f"Failed to normalize date: {data['date']}")
        
        # Normalize amount
        if 'amount' in data:
            try:
                amount_str = re.sub(r'[^\d.,]', '', data['amount'])
                if ',' in amount_str and '.' in amount_str:
                    # European format (1.234,56)
                    amount_str = amount_str.replace('.', '').replace(',', '.')
                else:
                    amount_str = amount_str.replace(',', '')
                normalized['amount'] = float(amount_str)
            except Exception:
                self.logger.warning(f"Failed to normalize amount: {data['amount']}")
        
        # Copy other fields
        for field in ('invoice_number', 'vendor_name', 'tax_id'):
            if field in data:
                normalized[field] = data[field]
        
        return normalized 