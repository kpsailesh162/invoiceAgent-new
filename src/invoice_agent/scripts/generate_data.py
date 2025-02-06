import os
from pathlib import Path
import sqlite3
import json
import random
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class DataGenerator:
    def __init__(self):
        load_dotenv()
        self.db_config = {
            'dbname': os.getenv('POSTGRES_DB', 'invoice_agent'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432')
        }
        self.conn = psycopg2.connect(**self.db_config)
        self.cur = self.conn.cursor()
        
        # Create base directories for generated files
        self.base_path = Path("src/invoice_agent/data/generated_invoices")
        for folder in ["pdf", "csv", "xlsx"]:
            (self.base_path / folder).mkdir(parents=True, exist_ok=True)
        
        # Initialize data containers
        self.vendors = []
        self.purchase_orders = []
        self.goods_receipts = []
    
    def generate_vendors(self):
        """Generate vendor data and store in database"""
        vendor_names = [
            "Tech Solutions Inc.",
            "Global Supply Co.",
            "Office Essentials Ltd.",
            "Industrial Parts Corp.",
            "Digital Systems LLC",
            "Hardware Wholesale Inc.",
            "Software Solutions Pro",
            "Electronics Depot Corp.",
            "Manufacturing Supplies Co.",
            "IT Equipment Direct"
        ]
        
        for i, name in enumerate(vendor_names, 1):
            vendor = {
                "id": f"V{i:03d}",
                "name": name,
                "tax_id": f"TAX{random.randint(100000, 999999)}",
                "payment_terms": random.choice(["Net 30", "Net 45", "2% 10 Net 30"]),
                "currency": "USD",
                "status": "active",
                "contact_email": f"accounts@{name.lower().replace(' ', '')}.com",
                "contact_phone": f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
            }
            
            # Insert into database
            self.cur.execute("""
                INSERT INTO vendors (
                    id, name, tax_id, payment_terms, currency, status,
                    contact_email, contact_phone
                ) VALUES (
                    %(id)s, %(name)s, %(tax_id)s, %(payment_terms)s,
                    %(currency)s, %(status)s, %(contact_email)s, %(contact_phone)s
                )
            """, vendor)
            
            self.vendors.append(vendor)
        
        self.conn.commit()
        print(f"Generated {len(self.vendors)} vendors")
    
    def generate_purchase_orders(self):
        """Generate purchase order data and store in database"""
        items_catalog = [
            {"description": "Desktop Computer", "unit_price": 899.99},
            {"description": "Laptop", "unit_price": 1299.99},
            {"description": "Monitor", "unit_price": 299.99},
            {"description": "Keyboard", "unit_price": 79.99},
            {"description": "Mouse", "unit_price": 49.99},
            {"description": "Docking Station", "unit_price": 199.99},
            {"description": "Printer", "unit_price": 399.99},
            {"description": "Network Switch", "unit_price": 299.99},
            {"description": "Server Rack", "unit_price": 899.99},
            {"description": "UPS Battery", "unit_price": 599.99}
        ]
        
        # Define specific test cases
        test_cases = [
            # Case 1: Normal PO with multiple items (completed)
            {
                "items_count": 3,
                "status": "completed",
                "special": None
            },
            # Case 2: Single item PO (completed)
            {
                "items_count": 1,
                "status": "completed",
                "special": None
            },
            # Case 3: Maximum items PO (completed)
            {
                "items_count": 5,
                "status": "completed",
                "special": None
            },
            # Case 4: Pending PO
            {
                "items_count": 2,
                "status": "pending",
                "special": None
            },
            # Case 5: Cancelled PO
            {
                "items_count": 2,
                "status": "cancelled",
                "special": None
            },
            # Case 6: High value PO (completed)
            {
                "items_count": 4,
                "status": "completed",
                "special": "high_value"
            },
            # Case 7: Low value PO (completed)
            {
                "items_count": 1,
                "status": "completed",
                "special": "low_value"
            },
            # Case 8: Zero tax PO (completed)
            {
                "items_count": 2,
                "status": "completed",
                "special": "zero_tax"
            },
            # Case 9: High tax PO (completed)
            {
                "items_count": 2,
                "status": "completed",
                "special": "high_tax"
            },
            # Case 10: Bulk order PO (completed)
            {
                "items_count": 3,
                "status": "completed",
                "special": "bulk_order"
            }
        ]
        
        start_date = datetime(2023, 1, 1)
        
        # Generate specific test cases first
        for i, test_case in enumerate(test_cases, 1):
            vendor = random.choice(self.vendors)
            po_date = start_date + timedelta(days=random.randint(0, 364))
            
            # Generate items based on test case
            items = []
            subtotal = 0
            
            if test_case["special"] == "high_value":
                # Select expensive items with high quantities
                selected_items = sorted(items_catalog, key=lambda x: x["unit_price"], reverse=True)[:test_case["items_count"]]
                for item in selected_items:
                    quantity = random.randint(5, 10)
                    total = round(quantity * item["unit_price"], 2)
                    items.append({
                        "description": item["description"],
                        "quantity": quantity,
                        "unit_price": item["unit_price"],
                        "total": total
                    })
                    subtotal += total
            elif test_case["special"] == "low_value":
                # Select cheapest items with low quantities
                selected_items = sorted(items_catalog, key=lambda x: x["unit_price"])[:test_case["items_count"]]
                for item in selected_items:
                    quantity = random.randint(1, 3)
                    total = round(quantity * item["unit_price"], 2)
                    items.append({
                        "description": item["description"],
                        "quantity": quantity,
                        "unit_price": item["unit_price"],
                        "total": total
                    })
                    subtotal += total
            elif test_case["special"] == "bulk_order":
                # High quantities of random items
                selected_items = random.sample(items_catalog, test_case["items_count"])
                for item in selected_items:
                    quantity = random.randint(20, 50)
                    total = round(quantity * item["unit_price"], 2)
                    items.append({
                        "description": item["description"],
                        "quantity": quantity,
                        "unit_price": item["unit_price"],
                        "total": total
                    })
                    subtotal += total
            else:
                # Normal item generation
                selected_items = random.sample(items_catalog, test_case["items_count"])
                for item in selected_items:
                    quantity = random.randint(1, 10)
                    total = round(quantity * item["unit_price"], 2)
                    items.append({
                        "description": item["description"],
                        "quantity": quantity,
                        "unit_price": item["unit_price"],
                        "total": total
                    })
                    subtotal += total
            
            # Calculate tax based on special cases
            if test_case["special"] == "zero_tax":
                tax_amount = 0
            elif test_case["special"] == "high_tax":
                tax_amount = round(subtotal * 0.20, 2)  # 20% tax
            else:
                tax_amount = round(subtotal * 0.10, 2)  # 10% tax
            
            total_amount = subtotal + tax_amount
            
            po = {
                "po_number": f"PO{i:04d}",
                "vendor_id": vendor["id"],
                "order_date": po_date.date(),
                "items": Json(items),
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
                "currency": vendor["currency"],
                "status": test_case["status"],
                "payment_terms": vendor["payment_terms"]
            }
            
            # Insert into database
            self.cur.execute("""
                INSERT INTO purchase_orders (
                    po_number, vendor_id, order_date, items, subtotal,
                    tax_amount, total_amount, currency, status, payment_terms
                ) VALUES (
                    %(po_number)s, %(vendor_id)s, %(order_date)s, %(items)s,
                    %(subtotal)s, %(tax_amount)s, %(total_amount)s,
                    %(currency)s, %(status)s, %(payment_terms)s
                )
            """, po)
            
            self.purchase_orders.append(po)
        
        # Generate additional random POs
        for i in range(len(test_cases) + 1, 51):
            vendor = random.choice(self.vendors)
            po_date = start_date + timedelta(days=random.randint(0, 364))
            
            # Generate 1-5 items
            num_items = random.randint(1, 5)
            items = []
            subtotal = 0
            
            for _ in range(num_items):
                item = random.choice(items_catalog).copy()
                quantity = random.randint(1, 10)
                total = round(quantity * item["unit_price"], 2)
                items.append({
                    "description": item["description"],
                    "quantity": quantity,
                    "unit_price": item["unit_price"],
                    "total": total
                })
                subtotal += total
            
            tax_amount = round(subtotal * 0.1, 2)  # 10% tax
            total_amount = subtotal + tax_amount
            
            po = {
                "po_number": f"PO{i:04d}",
                "vendor_id": vendor["id"],
                "order_date": po_date.date(),
                "items": Json(items),
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
                "currency": vendor["currency"],
                "status": random.choices(
                    ["completed", "pending", "cancelled"],
                    weights=[0.6, 0.3, 0.1]
                )[0],
                "payment_terms": vendor["payment_terms"]
            }
            
            # Insert into database
            self.cur.execute("""
                INSERT INTO purchase_orders (
                    po_number, vendor_id, order_date, items, subtotal,
                    tax_amount, total_amount, currency, status, payment_terms
                ) VALUES (
                    %(po_number)s, %(vendor_id)s, %(order_date)s, %(items)s,
                    %(subtotal)s, %(tax_amount)s, %(total_amount)s,
                    %(currency)s, %(status)s, %(payment_terms)s
                )
            """, po)
            
            self.purchase_orders.append(po)
        
        self.conn.commit()
        print(f"Generated {len(self.purchase_orders)} purchase orders")
    
    def generate_goods_receipts(self):
        """Generate goods receipt data for completed POs and store in database"""
        # Get all completed POs
        self.cur.execute("""
            SELECT po_number, vendor_id, order_date, items::json as items
            FROM purchase_orders 
            WHERE status = 'completed'
        """)
        completed_pos = self.cur.fetchall()
        
        for po in completed_pos:
            po_date = po[2]  # order_date
            receipt_date = po_date + timedelta(days=random.randint(1, 10))
            
            items = []
            for po_item in po[3]:  # items as JSON
                received_qty = po_item["quantity"]
                if random.random() < 0.1:  # 10% chance of partial delivery
                    received_qty = round(received_qty * random.uniform(0.8, 0.95))
                
                items.append({
                    "description": po_item["description"],
                    "ordered_quantity": po_item["quantity"],
                    "received_quantity": received_qty,
                    "unit_price": po_item["unit_price"]
                })
            
            gr = {
                "gr_number": f"GR{po[0][2:]}",  # Convert PO0001 to GR0001
                "po_number": po[0],  # po_number
                "vendor_id": po[1],  # vendor_id
                "receipt_date": receipt_date,
                "items": Json(items)
            }
            
            # Insert into database
            self.cur.execute("""
                INSERT INTO goods_receipts (
                    gr_number, po_number, vendor_id, receipt_date, items
                ) VALUES (
                    %(gr_number)s, %(po_number)s, %(vendor_id)s,
                    %(receipt_date)s, %(items)s
                )
            """, gr)
            
            self.goods_receipts.append(gr)
        
        self.conn.commit()
        print(f"Generated {len(self.goods_receipts)} goods receipts")
    
    def generate_invoice_files(self):
        """Generate invoice files in PDF, CSV, and XLSX formats"""
        # Get all completed POs with their GR data
        self.cur.execute("""
            SELECT 
                po.po_number,
                po.order_date,
                po.items::json as items,
                po.subtotal,
                po.tax_amount,
                po.total_amount,
                v.name as vendor_name,
                v.id as vendor_id,
                gr.items::json as gr_items
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.id
            LEFT JOIN goods_receipts gr ON po.po_number = gr.po_number
            WHERE po.status = 'completed'
        """)
        completed_pos = self.cur.fetchall()
        
        for po_data in completed_pos:
            invoice_number = f"INV{po_data[0][2:]}"  # Convert PO0001 to INV0001
            
            po = {
                "po_number": po_data[0],
                "order_date": po_data[1],
                "items": po_data[2],
                "subtotal": po_data[3],
                "tax_amount": po_data[4],
                "total_amount": po_data[5]
            }
            
            vendor = {
                "name": po_data[6],
                "id": po_data[7]
            }

            # Check if this is a green invoice (all quantities match)
            is_green = False
            if po_data[8]:  # If GR items exist
                gr_items = po_data[8]
                is_green = all(gr_item["received_quantity"] == gr_item["ordered_quantity"] for gr_item in gr_items)
            
            # Generate invoice files in different formats
            self._generate_pdf_invoice(invoice_number, po, vendor, is_green)
            self._generate_csv_invoice(invoice_number, po, vendor, is_green)
            self._generate_xlsx_invoice(invoice_number, po, vendor, is_green)
        
        print(f"\nGenerated invoice files for {len(completed_pos)} completed POs")
    
    def _generate_pdf_invoice(self, invoice_number, po, vendor, is_green):
        """Generate PDF format invoice"""
        filename = f"{invoice_number}_green.pdf" if is_green else f"{invoice_number}.pdf"
        pdf_path = self.base_path / "pdf" / filename
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add green watermark if applicable
        if is_green:
            green_style = ParagraphStyle(
                'GreenInvoice',
                parent=styles['Heading1'],
                textColor=colors.green,
                fontSize=24,
                spaceAfter=30
            )
            elements.append(Paragraph("GREEN INVOICE", green_style))
        
        # Header
        elements.append(Paragraph(f"INVOICE #{invoice_number}", styles["Title"]))
        elements.append(Paragraph(f"Date: {po['order_date']}", styles["Normal"]))
        elements.append(Paragraph(f"PO Number: {po['po_number']}", styles["Normal"]))
        elements.append(Paragraph(f"Vendor: {vendor['name']}", styles["Normal"]))
        
        # Items table
        table_data = [["Description", "Quantity", "Unit Price", "Total"]]
        for item in po['items']:
            table_data.append([
                item["description"],
                str(item["quantity"]),
                f"${item['unit_price']:.2f}",
                f"${item['total']:.2f}"
            ])
        
        # Add totals
        table_data.extend([
            ["", "", "Subtotal:", f"${po['subtotal']:.2f}"],
            ["", "", "Tax:", f"${po['tax_amount']:.2f}"],
            ["", "", "Total:", f"${po['total_amount']:.2f}"]
        ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
    
    def _generate_csv_invoice(self, invoice_number, po, vendor, is_green):
        """Generate CSV format invoice"""
        filename = f"{invoice_number}_green.csv" if is_green else f"{invoice_number}.csv"
        csv_path = self.base_path / "csv" / filename
        
        # Prepare data
        rows = [
            ["Invoice Number", invoice_number],
            ["Date", po["order_date"]],
            ["PO Number", po["po_number"]],
            ["Vendor", vendor["name"]],
            [],
            ["Description", "Quantity", "Unit Price", "Total"]
        ]
        
        for item in po['items']:
            rows.append([
                item["description"],
                item["quantity"],
                item["unit_price"],
                item["total"]
            ])
        
        rows.extend([
            [],
            ["Subtotal", "", "", po["subtotal"]],
            ["Tax", "", "", po["tax_amount"]],
            ["Total", "", "", po["total_amount"]]
        ])
        
        # Write to CSV
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False, header=False)
    
    def _generate_xlsx_invoice(self, invoice_number, po, vendor, is_green):
        """Generate XLSX format invoice"""
        filename = f"{invoice_number}_green.xlsx" if is_green else f"{invoice_number}.xlsx"
        xlsx_path = self.base_path / "xlsx" / filename
        
        # Create Excel writer
        writer = pd.ExcelWriter(xlsx_path, engine='openpyxl')
        
        # Header data
        header_data = {
            "Invoice Details": [
                ["Invoice Number", invoice_number],
                ["Date", po["order_date"]],
                ["PO Number", po["po_number"]],
                ["Vendor", vendor["name"]]
            ]
        }
        
        # Items data
        items_data = {
            "Description": [],
            "Quantity": [],
            "Unit Price": [],
            "Total": []
        }
        
        for item in po['items']:
            items_data["Description"].append(item["description"])
            items_data["Quantity"].append(item["quantity"])
            items_data["Unit Price"].append(item["unit_price"])
            items_data["Total"].append(item["total"])
        
        # Create DataFrames and write to Excel
        pd.DataFrame(header_data["Invoice Details"]).to_excel(
            writer, sheet_name="Invoice", index=False, header=False
        )
        
        pd.DataFrame(items_data).to_excel(
            writer, sheet_name="Invoice", startrow=6, index=False
        )
        
        # Add totals
        totals_data = {
            "": ["", "Subtotal", "Tax", "Total"],
            "Amount": [
                "",
                po["subtotal"],
                po["tax_amount"],
                po["total_amount"]
            ]
        }
        
        pd.DataFrame(totals_data).to_excel(
            writer,
            sheet_name="Invoice",
            startrow=len(items_data["Description"]) + 8,
            index=False
        )
        
        writer.close()
    
    def generate_all(self):
        """Generate all data and files"""
        print("Starting data generation process...")
        
        # Generate ERP data
        self.generate_vendors()
        self.generate_purchase_orders()
        self.generate_goods_receipts()
        
        # Generate invoice files
        print("\nGenerating invoice files...")
        self.generate_invoice_files()
        
        print("\nData generation completed successfully")
    
    def close(self):
        """Close database connection"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

def main():
    generator = DataGenerator()
    try:
        generator.generate_all()
    finally:
        generator.close()

if __name__ == "__main__":
    main() 