import pytest
from decimal import Decimal
from datetime import datetime
from src.invoice_agent.core.data_model import Invoice, LineItem

@pytest.fixture
def sample_line_item():
    return {
        'sku': 'LAPTOP-001',
        'description': 'Business Laptop',
        'quantity': 50,
        'unit_price': '1000.00',
        'total': '50000.00',
        'tax_rate': '0.10'
    }

@pytest.fixture
def sample_invoice_data(sample_line_item):
    return {
        'invoice_number': 'INV-2024-001',
        'vendor_name': 'CompuWorld',
        'vendor_id': 'VEN001',
        'po_number': 'PO-1234',
        'total_amount': '50000.00',
        'currency': 'USD',
        'line_items': [sample_line_item],
        'tax_amount': '5000.00',
        'shipping_amount': '500.00',
        'discount_amount': '1000.00',
        'file_path': '/path/to/invoice.pdf',
        'vendor_email': 'vendor@compuworld.com'
    }

def test_line_item_creation(sample_line_item):
    """Test creation of LineItem"""
    line_item = LineItem(
        sku=sample_line_item['sku'],
        description=sample_line_item['description'],
        quantity=int(sample_line_item['quantity']),
        unit_price=Decimal(sample_line_item['unit_price']),
        total=Decimal(sample_line_item['total']),
        tax_rate=Decimal(sample_line_item['tax_rate'])
    )
    
    assert line_item.sku == 'LAPTOP-001'
    assert line_item.description == 'Business Laptop'
    assert line_item.quantity == 50
    assert line_item.unit_price == Decimal('1000.00')
    assert line_item.total == Decimal('50000.00')
    assert line_item.tax_rate == Decimal('0.10')

def test_invoice_creation(sample_invoice_data):
    """Test creation of Invoice"""
    invoice = Invoice.from_dict(sample_invoice_data)
    
    assert invoice.invoice_number == 'INV-2024-001'
    assert invoice.vendor_name == 'CompuWorld'
    assert invoice.vendor_id == 'VEN001'
    assert invoice.po_number == 'PO-1234'
    assert invoice.total_amount == Decimal('50000.00')
    assert invoice.currency == 'USD'
    assert len(invoice.line_items) == 1
    assert invoice.tax_amount == Decimal('5000.00')
    assert invoice.shipping_amount == Decimal('500.00')
    assert invoice.discount_amount == Decimal('1000.00')
    assert invoice.status == 'received'
    assert isinstance(invoice.created_at, datetime)
    assert isinstance(invoice.updated_at, datetime)
    assert invoice.file_path == '/path/to/invoice.pdf'
    assert invoice.vendor_email == 'vendor@compuworld.com'

def test_invoice_optional_fields():
    """Test Invoice creation with minimal fields"""
    minimal_data = {
        'invoice_number': 'INV-2024-002',
        'vendor_name': 'TechCorp',
        'vendor_id': 'VEN002',
        'po_number': 'PO-5678',
        'total_amount': '25000.00',
        'currency': 'EUR',
        'line_items': [{
            'sku': 'MONITOR-001',
            'description': 'Monitor',
            'quantity': 10,
            'unit_price': '2500.00',
            'total': '25000.00'
        }]
    }
    
    invoice = Invoice.from_dict(minimal_data)
    
    assert invoice.tax_amount is None
    assert invoice.shipping_amount is None
    assert invoice.discount_amount is None
    assert invoice.status == 'received'
    assert invoice.line_items[0].tax_rate is None
    assert invoice.file_path is None
    assert invoice.vendor_email is None

def test_invoice_validation():
    """Test Invoice validation"""
    invalid_data = {
        'invoice_number': 'INV-2024-003',
        'vendor_name': 'TechCorp',
        'vendor_id': 'VEN003',
        'po_number': 'PO-9012',
        'total_amount': '30000.00',
        'currency': 'USD',
        'line_items': [{
            'sku': 'PRINTER-001',
            'description': 'Printer',
            'quantity': 'invalid',  # Should be integer
            'unit_price': '3000.00',
            'total': '30000.00'
        }]
    }
    
    with pytest.raises(ValueError):
        Invoice.from_dict(invalid_data)

def test_line_item_calculations():
    """Test LineItem calculations"""
    line_item = LineItem(
        sku='TEST-001',
        description='Test Item',
        quantity=5,
        unit_price=Decimal('100.00'),
        total=Decimal('500.00'),
        tax_rate=Decimal('0.20')
    )
    
    # Verify total matches quantity * unit_price
    assert line_item.total == line_item.quantity * line_item.unit_price
    
    # Calculate tax amount
    expected_tax = line_item.total * line_item.tax_rate
    assert expected_tax == Decimal('100.00')

def test_invoice_update():
    """Test Invoice update method"""
    # Create initial invoice
    invoice = Invoice.from_dict({
        'invoice_number': 'INV-2024-004',
        'vendor_name': 'TechCorp',
        'vendor_id': 'VEN004',
        'po_number': 'PO-1111',
        'total_amount': '10000.00',
        'currency': 'USD',
        'line_items': [{
            'sku': 'ITEM-001',
            'description': 'Test Item',
            'quantity': 1,
            'unit_price': '10000.00',
            'total': '10000.00'
        }]
    })
    
    # Update data
    update_data = {
        'total_amount': '15000.00',
        'tax_amount': '1500.00',
        'status': 'processing',
        'line_items': [{
            'sku': 'ITEM-001',
            'description': 'Updated Item',
            'quantity': 2,
            'unit_price': '7500.00',
            'total': '15000.00'
        }]
    }
    
    # Store original updated_at
    original_updated_at = invoice.updated_at
    
    # Perform update
    invoice.update(update_data)
    
    # Verify updates
    assert invoice.total_amount == Decimal('15000.00')
    assert invoice.tax_amount == Decimal('1500.00')
    assert invoice.status == 'processing'
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].description == 'Updated Item'
    assert invoice.line_items[0].quantity == 2
    assert invoice.line_items[0].unit_price == Decimal('7500.00')
    assert invoice.updated_at > original_updated_at 