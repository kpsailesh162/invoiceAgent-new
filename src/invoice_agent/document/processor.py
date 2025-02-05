import logging
from typing import Dict, Any
import asyncio
from decimal import Decimal
import re
from pathlib import Path
import json
import os

class DocumentProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process an invoice document and extract data"""
        try:
            self.logger.info(f"Processing document: {file_path}")
            
            # Ensure file exists
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Invoice file not found: {file_path}")
            
            # Extract data from the uploaded file
            # This would typically involve OCR and data extraction
            # For now, we'll read from a JSON sidecar if it exists, otherwise extract from filename
            json_sidecar = Path(file_path + '.json')
            
            if json_sidecar.exists():
                # Read extracted data from JSON sidecar
                with open(json_sidecar, 'r') as f:
                    extracted_data = json.load(f)
                    
                # Convert numeric values to Decimal
                if 'total_amount' in extracted_data:
                    extracted_data['total_amount'] = Decimal(str(extracted_data['total_amount']))
                if 'line_items' in extracted_data:
                    for item in extracted_data['line_items']:
                        if 'unit_price' in item:
                            item['unit_price'] = Decimal(str(item['unit_price']))
                        if 'total' in item:
                            item['total'] = Decimal(str(item['total']))
                
                return extracted_data
            else:
                # Extract basic info from filename as fallback
                invoice_number = self._extract_invoice_number_from_filename(file_path)
                
                # Return minimal extracted data
                return {
                    "invoice_number": invoice_number,
                    "invoice_date": None,
                    "vendor_info": None,
                    "po_number": None,
                    "total_amount": Decimal("0"),
                    "currency": "USD",
                    "line_items": []
                }
            
        except Exception as e:
            self.logger.error(f"Error processing document {file_path}: {str(e)}")
            raise 

    def _extract_invoice_number_from_filename(self, file_path: str) -> str:
        """Extract invoice number from filename."""
        file_name = os.path.basename(file_path)
        # Remove file extension
        file_name = os.path.splitext(file_name)[0]
        # Remove 'invoice_' prefix if present
        if file_name.startswith('invoice_'):
            file_name = file_name[8:]
        # Remove '_normal' suffix if present
        if file_name.endswith('_normal'):
            file_name = file_name[:-7]
        # The remaining string is the invoice number, whether it contains hyphens or not
        return file_name 