from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta
import json
import csv
from pathlib import Path
import logging
from ..erp.erp_data import erp_mock_data
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('invoice_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InvoiceGenerator:
    def __init__(self):
        self.output_dir = Path("src/invoice_agent/data/mock_invoices")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for different formats
        (self.output_dir / "pdf").mkdir(exist_ok=True)
        (self.output_dir / "csv").mkdir(exist_ok=True)
        (self.output_dir / "xlsx").mkdir(exist_ok=True)
        
        self.invoice_counter = 1000
        
        # Set up PDF styles
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )
        self.header_style = ParagraphStyle(
            'CustomHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=20
        )
        self.normal_style = self.styles['Normal']
    
    def generate_invoice_data(self, po: dict, introduce_errors: bool = False) -> dict:
        """Generate invoice data based on a purchase order"""
        invoice_data = {
            "invoice_number": f"INV{self.invoice_counter:04d}",
            "po_number": po["po_number"],
            "vendor_info": po["vendor_info"].copy(),
            "invoice_date": self._generate_invoice_date(po["order_date"]),
            "due_date": None,  # Will be set based on payment terms
            "payment_terms": "Net 30",
            "items": self._generate_line_items(po["items"], introduce_errors),
            "subtotal": 0,  # Will be calculated
            "tax_amount": 0,  # Will be calculated
            "total_amount": 0,  # Will be calculated
            "currency": "USD",
            "status": "pending"
        }
        
        # Calculate totals
        invoice_data["subtotal"] = sum(item["total"] for item in invoice_data["items"])
        invoice_data["tax_amount"] = round(invoice_data["subtotal"] * 0.1, 2)  # 10% tax
        invoice_data["total_amount"] = invoice_data["subtotal"] + invoice_data["tax_amount"]
        
        # Set due date based on payment terms
        invoice_date = datetime.strptime(invoice_data["invoice_date"], "%Y-%m-%d")
        invoice_data["due_date"] = (invoice_date + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Introduce random errors if requested
        if introduce_errors:
            self._introduce_random_errors(invoice_data)
        
        self.invoice_counter += 1
        return invoice_data
    
    def _generate_invoice_date(self, po_date: str) -> str:
        """Generate invoice date after PO date"""
        po_datetime = datetime.strptime(po_date, "%Y-%m-%d")
        days_after = random.randint(1, 5)  # Invoice 1-5 days after PO
        invoice_date = po_datetime + timedelta(days=days_after)
        return invoice_date.strftime("%Y-%m-%d")
    
    def _generate_line_items(self, po_items: List[dict], introduce_errors: bool) -> List[dict]:
        """Generate line items based on PO items"""
        invoice_items = []
        for po_item in po_items:
            item = {
                "description": po_item["description"],
                "quantity": po_item["quantity"],
                "unit_price": po_item["unit_price"],
                "total": po_item["quantity"] * po_item["unit_price"]
            }
            
            if introduce_errors:
                # Small random variations in quantity or price
                if random.random() < 0.3:
                    variation = random.uniform(-0.05, 0.05)  # ±5%
                    if random.choice([True, False]):
                        item["quantity"] = round(item["quantity"] * (1 + variation))
                    else:
                        item["unit_price"] = round(item["unit_price"] * (1 + variation), 2)
                    item["total"] = item["quantity"] * item["unit_price"]
            
            invoice_items.append(item)
        return invoice_items
    
    def _introduce_random_errors(self, invoice_data: dict):
        """Introduce random errors in invoice data"""
        error_types = [
            self._error_wrong_po_number,
            self._error_wrong_payment_terms,
            self._error_wrong_tax_calculation,
            self._error_wrong_total_calculation,
            self._error_missing_field
        ]
        
        # Apply 1-2 random errors
        for _ in range(random.randint(1, 2)):
            error_func = random.choice(error_types)
            error_func(invoice_data)
    
    def _error_wrong_po_number(self, invoice_data: dict):
        """Modify PO number slightly"""
        po_num = invoice_data["po_number"]
        new_num = str(int(po_num[2:]) + random.randint(1, 10)).zfill(4)
        invoice_data["po_number"] = f"PO{new_num}"
    
    def _error_wrong_payment_terms(self, invoice_data: dict):
        """Change payment terms"""
        terms = ["Net 15", "Net 45", "Net 60", "2% 10 Net 30"]
        invoice_data["payment_terms"] = random.choice(terms)
    
    def _error_wrong_tax_calculation(self, invoice_data: dict):
        """Apply wrong tax rate"""
        wrong_rates = [0.08, 0.09, 0.11, 0.12]  # Instead of 0.10
        rate = random.choice(wrong_rates)
        invoice_data["tax_amount"] = round(invoice_data["subtotal"] * rate, 2)
        invoice_data["total_amount"] = invoice_data["subtotal"] + invoice_data["tax_amount"]
    
    def _error_wrong_total_calculation(self, invoice_data: dict):
        """Make total amount incorrect"""
        variation = random.uniform(-0.03, 0.03)  # ±3%
        invoice_data["total_amount"] = round(invoice_data["total_amount"] * (1 + variation), 2)
    
    def _error_missing_field(self, invoice_data: dict):
        """Remove a non-critical field"""
        fields = ["payment_terms", "currency"]
        field_to_remove = random.choice(fields)
        invoice_data.pop(field_to_remove, None)
    
    def generate_csv_invoice(self, invoice_data: dict, output_path: Path):
        """Generate a CSV format invoice file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header information
            writer.writerow(["Invoice Information"])
            writer.writerow(["Invoice Number:", invoice_data["invoice_number"]])
            writer.writerow(["PO Number:", invoice_data.get("po_number", "N/A")])
            writer.writerow(["Invoice Date:", invoice_data["invoice_date"]])
            writer.writerow(["Due Date:", invoice_data.get("due_date", "N/A")])
            writer.writerow([])
            
            # Write vendor information
            writer.writerow(["Vendor Information"])
            writer.writerow(["Name:", invoice_data["vendor_info"]["name"]])
            writer.writerow(["ID:", invoice_data["vendor_info"]["id"]])
            writer.writerow([])
            
            # Write line items
            writer.writerow(["Line Items"])
            writer.writerow(["Description", "Quantity", "Unit Price", "Total"])
            for item in invoice_data["items"]:
                writer.writerow([
                    item["description"],
                    item["quantity"],
                    f"${item['unit_price']:.2f}",
                    f"${item['total']:.2f}"
                ])
            writer.writerow([])
            
            # Write totals
            writer.writerow(["", "", "Subtotal:", f"${invoice_data.get('subtotal', 0):.2f}"])
            writer.writerow(["", "", "Tax Amount:", f"${invoice_data.get('tax_amount', 0):.2f}"])
            writer.writerow(["", "", "Total Amount:", f"${invoice_data.get('total_amount', 0):.2f}"])
            
            # Write additional information
            if "payment_terms" in invoice_data:
                writer.writerow([])
                writer.writerow(["Payment Terms:", invoice_data["payment_terms"]])
            if "currency" in invoice_data:
                writer.writerow(["Currency:", invoice_data["currency"]])
    
    def generate_pdf_invoice(self, invoice_data: dict, output_path: Path):
        """Generate a PDF format invoice file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = SimpleDocTemplate(
            str(output_path),  # Convert Path to string
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Create the story (content) for the PDF
        story = []
        
        # Add title
        story.append(Paragraph(f"Invoice {invoice_data['invoice_number']}", self.title_style))
        
        # Add invoice information
        invoice_info = [
            ["Invoice Information", ""],
            ["Invoice Number:", invoice_data["invoice_number"]],
            ["PO Number:", invoice_data.get("po_number", "N/A")],
            ["Invoice Date:", invoice_data["invoice_date"]],
            ["Due Date:", invoice_data.get("due_date", "N/A")]
        ]
        t = Table(invoice_info, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))
        
        # Add vendor information
        vendor_info = [
            ["Vendor Information", ""],
            ["Name:", invoice_data["vendor_info"]["name"]],
            ["ID:", invoice_data["vendor_info"]["id"]]
        ]
        t = Table(vendor_info, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))
        
        # Add line items
        story.append(Paragraph("Line Items", self.header_style))
        line_items = [["Description", "Quantity", "Unit Price", "Total"]]
        for item in invoice_data["items"]:
            line_items.append([
                item["description"],
                str(item["quantity"]),
                f"${item['unit_price']:.2f}",
                f"${item['total']:.2f}"
            ])
        
        # Add totals
        line_items.extend([
            ["", "", "Subtotal:", f"${invoice_data.get('subtotal', 0):.2f}"],
            ["", "", "Tax Amount:", f"${invoice_data.get('tax_amount', 0):.2f}"],
            ["", "", "Total Amount:", f"${invoice_data.get('total_amount', 0):.2f}"]
        ])
        
        t = Table(line_items, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('GRID', (0,0), (-1,0), 1, colors.black),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
            ('LINEBELOW', (0,-4), (-1,-4), 1, colors.black),
        ]))
        story.append(t)
        
        # Add additional information
        if "payment_terms" in invoice_data or "currency" in invoice_data:
            story.append(Spacer(1, 20))
            additional_info = []
            if "payment_terms" in invoice_data:
                additional_info.append(["Payment Terms:", invoice_data["payment_terms"]])
            if "currency" in invoice_data:
                additional_info.append(["Currency:", invoice_data["currency"]])
            
            t = Table(additional_info, colWidths=[2*inch, 4*inch])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ]))
            story.append(t)
        
        # Build the PDF
        doc.build(story)
    
    def generate_xlsx_invoice(self, invoice_data: dict, output_path: Path):
        """Generate an Excel format invoice file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a list of rows for the Excel file
        rows = []
        
        # Add invoice information
        rows.extend([
            ["Invoice Information"],
            ["Invoice Number:", invoice_data["invoice_number"]],
            ["PO Number:", invoice_data.get("po_number", "N/A")],
            ["Invoice Date:", invoice_data["invoice_date"]],
            ["Due Date:", invoice_data.get("due_date", "N/A")],
            []
        ])
        
        # Add vendor information
        rows.extend([
            ["Vendor Information"],
            ["Name:", invoice_data["vendor_info"]["name"]],
            ["ID:", invoice_data["vendor_info"]["id"]],
            []
        ])
        
        # Add line items
        rows.extend([
            ["Line Items"],
            ["Description", "Quantity", "Unit Price", "Total"]
        ])
        
        for item in invoice_data["items"]:
            rows.append([
                item["description"],
                item["quantity"],
                item["unit_price"],
                item["total"]
            ])
        
        rows.extend([
            [],
            ["", "", "Subtotal:", invoice_data.get("subtotal", 0)],
            ["", "", "Tax Amount:", invoice_data.get("tax_amount", 0)],
            ["", "", "Total Amount:", invoice_data.get("total_amount", 0)]
        ])
        
        # Add additional information
        if "payment_terms" in invoice_data:
            rows.extend([[], ["Payment Terms:", invoice_data["payment_terms"]]])
        if "currency" in invoice_data:
            rows.extend([["Currency:", invoice_data["currency"]]])
        
        # Convert to DataFrame and save as Excel
        df = pd.DataFrame(rows)
        writer = pd.ExcelWriter(output_path, engine='openpyxl')
        df.to_excel(writer, index=False, header=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Sheet1']
        for idx, col in enumerate(df):
            max_length = max(df[col].astype(str).apply(len).max(), 20)
            worksheet.column_dimensions[chr(65 + idx)].width = max_length
        
        writer.close()
    
    def generate_invoice_files(self, invoice_data: dict, base_path: Path):
        """Generate invoice in all formats"""
        # Extract the base filename without extension
        base_filename = base_path.name
        parent_dir = base_path.parent
        
        # Generate CSV
        self.generate_csv_invoice(
            invoice_data,
            parent_dir / "csv" / f"{base_filename}.csv"
        )
        
        # Generate PDF
        self.generate_pdf_invoice(
            invoice_data,
            parent_dir / "pdf" / f"{base_filename}.pdf"
        )
        
        # Generate XLSX
        self.generate_xlsx_invoice(
            invoice_data,
            parent_dir / "xlsx" / f"{base_filename}.xlsx"
        )
    
    def generate_all_test_cases(self):
        """Generate test invoices for all scenarios"""
        logger.info("Starting test invoice generation")
        
        # Get completed POs for invoice generation
        completed_pos = [po for po in erp_mock_data.purchase_orders if po["status"] == "completed"]
        
        for po in completed_pos:
            # Generate normal invoice
            invoice_data = self.generate_invoice_data(po, introduce_errors=False)
            self.generate_invoice_files(
                invoice_data,
                Path(f"invoice_{invoice_data['invoice_number']}_normal")
            )
            
            # Generate invoice with errors
            invoice_data_with_errors = self.generate_invoice_data(po, introduce_errors=True)
            self.generate_invoice_files(
                invoice_data_with_errors,
                Path(f"invoice_{invoice_data_with_errors['invoice_number']}_with_errors")
            )
            
            logger.info(f"Generated invoices for PO: {po['po_number']}")
        
        logger.info("Completed test invoice generation")

# Key fields for matching
MATCHING_FIELDS = {
    "required": [
        "invoice_number",
        "po_number",
        "vendor_info.tax_id",
        "total_amount",
        "currency"
    ],
    "optional": [
        "payment_terms",
        "vendor_info.address"
    ],
    "line_items": [
        "id",
        "quantity",
        "unit_price",
        "total"
    ]
}

# Initialize generator
invoice_generator = InvoiceGenerator() 