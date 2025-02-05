import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta
import uuid
import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os
from pathlib import Path
import json

# Initialize Faker with multiple locales
fake = Faker(['en_US', 'ja_JP', 'zh_CN', 'de_DE', 'es_ES'])

def generate_po_number(include_edge_cases=False):
    """Generate a PO number with possible edge cases"""
    if not include_edge_cases:
        # Standard format: PO-12345
        return f"PO-{fake.random_number(digits=5, fix_len=True)}"
    else:
        # Edge cases
        edge_cases = [
            "",  # Missing PO
            "PO-ABCD",  # Invalid format with letters
            "12345",  # Missing PO prefix
            "PO-" + "9" * 20,  # Overly long number
            "PO-00000",  # All zeros
            f"PO-{fake.random_number(digits=5, fix_len=True)}",  # Normal format
            None,  # Null value
            "Invalid-PO-Format",  # Completely wrong format
            " ",  # Just whitespace
            f"PO-{fake.random_number(digits=3, fix_len=True)}",  # Too short
        ]
        return random.choice(edge_cases)

def generate_company(locale=None):
    if locale:
        fake.locale = locale
    
    return {
        'name': fake.company(),
        'address': fake.address().replace('\n', ', '),
        'email': fake.company_email(),
        'tax_id': f"TAX{fake.random_number(digits=8, fix_len=True)}"
    }

def generate_line_items(num_items=None, include_edge_cases=False):
    if num_items is None:
        num_items = random.randint(1, 5)
    
    items = []
    for i in range(num_items):
        if include_edge_cases and i == 0:
            # Add edge cases like $0 amount or very large numbers
            quantity = random.choice([0, 1, 999999])
            unit_price = random.choice([0.0, 0.01, 999999.99])
            description = random.choice([
                "",  # Empty description
                "A" * 1000,  # Very long description
                "Special@#$%Characters",  # Special characters
                "\n\n\n",  # Multiple newlines
                fake.bs()  # Normal description
            ])
        else:
            quantity = random.randint(1, 10)
            unit_price = round(random.uniform(10, 1000), 2)
            description = fake.bs()
        
        items.append({
            'description': description,
            'quantity': quantity,
            'unit_price': unit_price,
            'amount': round(quantity * unit_price, 2)
        })
    return items

def calculate_totals(line_items, tax_rate=None, discount_rate=None):
    subtotal = sum(item['amount'] for item in line_items)
    
    if discount_rate is None:
        # Include edge case of 100% discount
        discount_rate = random.choice([0, 0, 0, 0.05, 0.1, 0.25, 1.0])
    
    if tax_rate is None:
        # Various international tax rates
        tax_rate = random.choice([0.0, 0.05, 0.08, 0.1, 0.19, 0.20, 0.21])
    
    discount_amount = round(subtotal * discount_rate, 2)
    taxable_amount = subtotal - discount_amount
    tax_amount = round(taxable_amount * tax_rate, 2)
    total = taxable_amount + tax_amount
    
    return {
        'subtotal': subtotal,
        'discount_rate': discount_rate,
        'discount_amount': discount_amount,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total': total
    }

def generate_invoice(invoice_number=None, include_edge_cases=False):
    if invoice_number is None:
        invoice_number = f"INV-{fake.random_number(digits=6, fix_len=True)}"
    
    # Spread dates over last 12 months
    if include_edge_cases:
        issue_date = random.choice([
            fake.date_between(start_date='-1y', end_date='today'),
            datetime.now().date(),  # Today
            (datetime.now() + timedelta(days=1)).date(),  # Future date (invalid)
            datetime(2000, 1, 1).date(),  # Very old date
            None,  # Missing date
        ])
    else:
        issue_date = fake.date_between(start_date='-1y', end_date='today')
    
    payment_terms = random.choice([0, 15, 30, 45, 60, 90])
    due_date = issue_date + timedelta(days=payment_terms) if issue_date else None
    
    # Mix of domestic and international companies
    locale = random.choice(['en_US', 'ja_JP', 'zh_CN', 'de_DE', 'es_ES'])
    seller = generate_company(locale)
    buyer = generate_company(random.choice(['en_US', locale]))  # Sometimes same locale, sometimes US
    
    line_items = generate_line_items(include_edge_cases=include_edge_cases)
    totals = calculate_totals(line_items)
    
    # More varied payment statuses and currencies
    payment_status = random.choice([
        'Paid', 'Unpaid', 'Partial', 'Overdue', 'Cancelled',
        'Disputed', 'Refunded', 'Payment Failed', 'Pending',
        'Draft', 'Void', 'Written Off'
    ])
    
    currency = random.choice([
        'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD', 
        'CHF', 'HKD', 'SGD', 'INR', 'BRL', 'RUB'
    ])
    
    # Generate PO number (about 66% of invoices have PO numbers)
    has_po = random.choice([True, True, False])
    po_number = generate_po_number(include_edge_cases) if has_po else ""
    
    return {
        'invoice_id': str(uuid.uuid4()),
        'invoice_number': invoice_number,
        'po_number': po_number,
        'issue_date': issue_date,
        'due_date': due_date,
        'payment_terms': f"Net {payment_terms}",
        'payment_status': payment_status,
        'currency': currency,
        
        'seller_name': seller['name'],
        'seller_address': seller['address'],
        'seller_email': seller['email'],
        'seller_tax_id': seller['tax_id'],
        
        'buyer_name': buyer['name'],
        'buyer_address': buyer['address'],
        'buyer_email': buyer['email'],
        'buyer_tax_id': buyer['tax_id'],
        
        'line_items': line_items,
        'subtotal': totals['subtotal'],
        'discount_rate': totals['discount_rate'],
        'discount_amount': totals['discount_amount'],
        'tax_rate': totals['tax_rate'],
        'tax_amount': totals['tax_amount'],
        'total_amount': totals['total']
    }

def create_pdf_invoice(invoice_data, output_path):
    """Generate a PDF version of the invoice"""
    # Convert Path to string for reportlab
    if isinstance(output_path, Path):
        output_path = str(output_path)
        
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header
    elements.append(Paragraph(f"Invoice #{invoice_data['invoice_number']}", styles['Heading1']))
    if invoice_data['po_number']:
        elements.append(Paragraph(f"PO #: {invoice_data['po_number']}", styles['Normal']))
    elements.append(Paragraph(f"Date: {invoice_data['issue_date']}", styles['Normal']))
    elements.append(Paragraph(f"Due Date: {invoice_data['due_date']}", styles['Normal']))
    
    # Company Information
    elements.append(Paragraph("From:", styles['Heading2']))
    elements.append(Paragraph(invoice_data['seller_name'], styles['Normal']))
    elements.append(Paragraph(invoice_data['seller_address'], styles['Normal']))
    
    elements.append(Paragraph("To:", styles['Heading2']))
    elements.append(Paragraph(invoice_data['buyer_name'], styles['Normal']))
    elements.append(Paragraph(invoice_data['buyer_address'], styles['Normal']))
    
    # Line Items
    data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
    for item in invoice_data['line_items']:
        data.append([
            item['description'],
            str(item['quantity']),
            f"{invoice_data['currency']} {item['unit_price']:.2f}",
            f"{invoice_data['currency']} {item['amount']:.2f}"
        ])
    
    # Totals
    data.extend([
        ['Subtotal', '', '', f"{invoice_data['currency']} {invoice_data['subtotal']:.2f}"],
        ['Discount', '', f"{invoice_data['discount_rate']*100:.1f}%", f"{invoice_data['currency']} {invoice_data['discount_amount']:.2f}"],
        ['Tax', '', f"{invoice_data['tax_rate']*100:.1f}%", f"{invoice_data['currency']} {invoice_data['tax_amount']:.2f}"],
        ['Total', '', '', f"{invoice_data['currency']} {invoice_data['total_amount']:.2f}"]
    ])
    
    table = Table(data)
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

def generate_invoice_dataset(num_invoices=100, include_edge_cases=True):
    # Create output directories
    output_dir = Path('generated_invoices')
    output_dir.mkdir(exist_ok=True)
    (output_dir / 'pdf').mkdir(exist_ok=True)
    (output_dir / 'excel').mkdir(exist_ok=True)
    
    invoices = []
    num_edge_cases = num_invoices // 10 if include_edge_cases else 0  # 10% edge cases
    
    # Track PO numbers to create some duplicates
    used_po_numbers = []
    
    for i in range(num_invoices):
        is_edge_case = i < num_edge_cases
        invoice = generate_invoice(
            f"INV-{str(i+1).zfill(6)}", 
            include_edge_cases=is_edge_case
        )
        
        # Sometimes create duplicate PO numbers (for edge cases)
        if is_edge_case and used_po_numbers and random.random() < 0.2:
            invoice['po_number'] = random.choice(used_po_numbers)
        elif invoice['po_number']:
            used_po_numbers.append(invoice['po_number'])
        
        # Store line items as string for CSV
        invoice_for_csv = invoice.copy()
        invoice_for_csv['line_items'] = str(invoice['line_items'])
        invoices.append(invoice_for_csv)
        
        # Generate PDF
        if random.random() < 0.5:  # 50% of invoices get PDFs
            pdf_path = output_dir / 'pdf' / f"{invoice['invoice_number']}.pdf"
            create_pdf_invoice(invoice, pdf_path)
    
    # Save to CSV
    df = pd.DataFrame(invoices)
    csv_path = output_dir / 'invoices.csv'
    df.to_csv(str(csv_path), index=False)  # Convert Path to string
    
    # Save to Excel with multiple sheets
    excel_path = output_dir / 'excel' / 'invoices.xlsx'
    with pd.ExcelWriter(str(excel_path), engine='openpyxl') as writer:  # Convert Path to string
        # All invoices
        df.to_excel(writer, sheet_name='All Invoices', index=False)
        
        # Paid invoices
        df[df['payment_status'] == 'Paid'].to_excel(
            writer, sheet_name='Paid Invoices', index=False
        )
        
        # Unpaid invoices
        df[df['payment_status'].isin(['Unpaid', 'Overdue'])].to_excel(
            writer, sheet_name='Unpaid Invoices', index=False
        )
        
        # By currency
        for currency in df['currency'].unique():
            sheet_name = f'{currency} Invoices'[:31]  # Excel sheet name length limit
            df[df['currency'] == currency].to_excel(
                writer, sheet_name=sheet_name, index=False
            )
        
        # PO analysis
        po_analysis = df[['po_number', 'total_amount']].copy()
        po_analysis['has_po'] = po_analysis['po_number'].notna() & (po_analysis['po_number'] != '')
        po_stats = pd.DataFrame({
            'Metric': ['Total Invoices', 'With PO', 'Without PO', 'Unique POs', 'Duplicate POs'],
            'Value': [
                len(df),
                po_analysis['has_po'].sum(),
                (~po_analysis['has_po']).sum(),
                po_analysis['po_number'].nunique(),
                len(df) - po_analysis['po_number'].nunique()
            ]
        })
        po_stats.to_excel(writer, sheet_name='PO Analysis', index=False)
    
    # Save one sample invoice in JSON format for template reference
    sample_invoice = generate_invoice(include_edge_cases=True)
    with open(str(output_dir / 'sample_invoice_template.json'), 'w') as f:  # Convert Path to string
        json.dump(sample_invoice, f, indent=2, default=str)
    
    print(f"Generated {len(df)} invoices:")
    print(f"- CSV file: {csv_path}")
    print(f"- Excel file: {excel_path}")
    print(f"- PDF files: {len(list((output_dir / 'pdf').glob('*.pdf')))} files in {output_dir / 'pdf'}")
    print(f"- Sample template: {output_dir / 'sample_invoice_template.json'}")
    
    # Print PO number statistics
    print("\nPO Number Statistics:")
    print(f"- Invoices with PO: {po_analysis['has_po'].sum()} ({po_analysis['has_po'].mean()*100:.1f}%)")
    print(f"- Unique PO numbers: {po_analysis['po_number'].nunique()}")
    print(f"- Duplicate PO numbers: {len(df) - po_analysis['po_number'].nunique()}")
    
    return df

if __name__ == "__main__":
    # Generate 100 sample invoices with edge cases
    df = generate_invoice_dataset(100, include_edge_cases=True) 