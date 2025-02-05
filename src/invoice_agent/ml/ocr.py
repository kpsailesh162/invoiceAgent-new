import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
from PIL import Image
import torch
from typing import Dict, Any

class InvoiceOCR:
    def __init__(self):
        self.processor = LayoutLMv3Processor.from_pretrained(
            "microsoft/layoutlmv3-base"
        )
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(
            "microsoft/layoutlmv3-base"
        )
        
    async def extract_invoice_data(self, file) -> Dict[str, Any]:
        # Convert PDF to images if needed
        if file.filename.endswith('.pdf'):
            images = convert_from_path(file.filename)
            image = images[0]  # Process first page
        else:
            image = Image.open(file.file)
        
        # Preprocess image
        image = self._preprocess_image(image)
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(image)
        
        # Get layout information
        encoding = self.processor(
            image,
            text,
            return_tensors="pt",
            truncation=True
        )
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**encoding)
        
        # Process predictions
        predictions = outputs.logits.argmax(-1).squeeze().tolist()
        
        # Extract structured data
        return self._extract_structured_data(text, predictions)
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply thresholding
        _, binary = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary)
        
        return Image.fromarray(denoised)
    
    def _extract_structured_data(
        self,
        text: str,
        predictions: list
    ) -> Dict[str, Any]:
        # Implement extraction logic based on model predictions
        # This is a simplified example
        import re
        
        data = {
            'invoice_number': None,
            'date': None,
            'total_amount': None,
            'vendor_name': None
        }
        
        # Extract invoice number (example pattern)
        invoice_match = re.search(r'Invoice[:#]\s*([A-Z0-9-]+)', text)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1)
        
        # Extract date (example pattern)
        date_match = re.search(
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            text
        )
        if date_match:
            data['date'] = date_match.group(0)
        
        # Extract amount (example pattern)
        amount_match = re.search(
            r'Total:?\s*[\$£€]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            text
        )
        if amount_match:
            data['total_amount'] = amount_match.group(1)
        
        return data 