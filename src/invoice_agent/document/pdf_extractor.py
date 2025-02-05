from typing import Dict, List
import re
from datetime import datetime
import random
from pathlib import Path

class PDFExtractor:
    def __init__(self):
        self.common_fields = [
            "invoice_number",
            "po_number",
            "invoice_date",
            "due_date",
            "vendor_name",
            "total_amount",
            "tax_amount",
            "currency"
        ]
    
    def extract_data(self, pdf_path: str) -> Dict:
        """
        Simulate AI-based data extraction from PDF invoice
        In a real implementation, this would use OCR and ML models
        """
        # For demo purposes, we'll generate plausible data
        # In reality, this would use OCR and ML to extract actual data
        
        extracted_data = {
            "invoice_number": f"INV-{random.randint(10000, 99999)}",
            "po_number": f"PO-{random.randint(10000, 99999)}",
            "invoice_date": (datetime.now().date()).strftime("%Y-%m-%d"),
            "due_date": (datetime.now().date()).strftime("%Y-%m-%d"),
            "vendor_name": random.choice(["Tech Corp", "Office Supplies Inc", "Global Trading LLC"]),
            "confidence_scores": {}
        }
        
        # Generate line items
        items = [
            {"name": "Laptop", "unit_price": 1200.00},
            {"name": "Monitor", "unit_price": 300.00},
            {"name": "Keyboard", "unit_price": 80.00},
            {"name": "Mouse", "unit_price": 40.00}
        ]
        
        line_items = []
        total_amount = 0
        
        for _ in range(random.randint(1, 4)):
            item = random.choice(items)
            quantity = random.randint(1, 5)
            amount = quantity * item["unit_price"]
            total_amount += amount
            
            line_items.append({
                "item": item["name"],
                "quantity": quantity,
                "unit_price": item["unit_price"],
                "amount": amount
            })
        
        # Add tax
        tax_rate = 0.1  # 10% tax
        tax_amount = total_amount * tax_rate
        
        extracted_data.update({
            "line_items": line_items,
            "subtotal": total_amount,
            "tax_amount": tax_amount,
            "total_amount": total_amount + tax_amount,
            "currency": "USD"
        })
        
        # Generate confidence scores for each field
        for field in self.common_fields:
            extracted_data["confidence_scores"][field] = random.uniform(0.85, 0.99)
        
        return extracted_data
    
    def validate_extraction(self, extracted_data: Dict) -> Dict:
        """
        Validate the extracted data for completeness and format
        Returns validation results with any issues found
        """
        validation_results = {
            "is_valid": True,
            "missing_fields": [],
            "low_confidence_fields": [],
            "format_issues": []
        }
        
        # Check required fields
        for field in self.common_fields:
            if field not in extracted_data:
                validation_results["missing_fields"].append(field)
                validation_results["is_valid"] = False
        
        # Check confidence scores
        for field, score in extracted_data.get("confidence_scores", {}).items():
            if score < 0.90:
                validation_results["low_confidence_fields"].append({
                    "field": field,
                    "confidence": score
                })
        
        # Validate formats
        if "invoice_date" in extracted_data:
            try:
                datetime.strptime(extracted_data["invoice_date"], "%Y-%m-%d")
            except ValueError:
                validation_results["format_issues"].append("Invalid invoice_date format")
                validation_results["is_valid"] = False
        
        if "total_amount" in extracted_data:
            if not isinstance(extracted_data["total_amount"], (int, float)):
                validation_results["format_issues"].append("Invalid total_amount format")
                validation_results["is_valid"] = False
        
        return validation_results 