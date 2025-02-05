import pytest
from unittest.mock import Mock, patch, AsyncMock, call
from datetime import datetime, timedelta
from decimal import Decimal
from src.invoice_agent.workflow.processor import (
    EnhancedInvoiceWorkflowProcessor,
    InvoiceStatus
)
from src.invoice_agent.core.data_model import Invoice, LineItem
import asyncio
from unittest.mock import ANY

@pytest.fixture
def test_config():
    """Fixture providing test configuration"""
    return {
        'max_retries': 3,
        'timeout_seconds': 30,
        'batch_size': 10,
        'default_currency': 'USD',
        'supported_currencies': ['USD', 'EUR', 'GBP'],
        'notification_settings': {
            'enabled': True,
            'channels': ['email', 'slack']
        }
    }

@pytest.fixture
def mock_dependencies():
    """Fixture providing mocked dependencies"""
    dependencies = {
        'source_manager': AsyncMock(),
        'document_processor': AsyncMock(),
        'erp_connector': AsyncMock(),
        'notification_manager': AsyncMock(),
        'audit_logger': AsyncMock(),
        'metrics': AsyncMock()
    }
    
    # Configure default return values
    dependencies['erp_connector'].get_exchange_rate.return_value = {
        'rate': 1.0,
        'date': datetime.now().date().isoformat()
    }
    
    # Configure document processor to return dictionary
    dependencies['document_processor'].process_document.return_value = {}
    
    return dependencies

@pytest.fixture
def sample_invoice():
    """Fixture providing a sample invoice data"""
    return {
        'invoice_number': 'INV-001',
        'vendor_name': 'Tech Solutions Inc.',
        'vendor_id': 'VENDOR-001',
        'po_number': 'PO-001',
        'total_amount': '50000.00',
        'currency': 'USD',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'description': 'Business Laptop',
            'quantity': 20,
            'unit_price': '2500.00',
            'total': '50000.00'
        }],
        'shipping_amount': '100.00',
        'discount_amount': '0.00',
        'status': InvoiceStatus.NEW.value
    }

@pytest.fixture
def sample_po_data():
    """Fixture providing sample purchase order data"""
    return {
        'po_number': 'PO-001',
        'vendor_id': 'VENDOR-001',
        'total_amount': '50000.00',
        'currency': 'USD',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'description': 'Business Laptop',
            'quantity': 20,
            'unit_price': '2500.00',
            'total': '50000.00'
        }]
    }

@pytest.fixture
def sample_gr_data():
    """Fixture providing sample goods receipt data"""
    return {
        'gr_number': 'GR-001',
        'po_number': 'PO-001',
        'vendor_id': 'VENDOR-001',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'quantity_received': 20,
            'date_received': datetime.now().date().isoformat()
        }]
    }

@pytest.fixture
def complex_invoice():
    """Fixture providing a complex invoice with multiple line items"""
    return {
        'invoice_number': 'INV-002',
        'vendor_name': 'Tech Solutions Inc.',
        'vendor_id': 'VENDOR-001',
        'po_number': 'PO-002',
        'total_amount': '75000.00',
        'currency': 'USD',
        'line_items': [
            {
                'sku': 'LAPTOP-001',
                'description': 'Business Laptop',
                'quantity': 20,
                'unit_price': '2500.00',
                'total': '50000.00'
            },
            {
                'sku': 'DOCK-001',
                'description': 'Docking Station',
                'quantity': 50,
                'unit_price': '500.00',
                'total': '25000.00'
            }
        ],
        'shipping_amount': '200.00',
        'discount_amount': '1000.00',
        'status': InvoiceStatus.NEW.value
    }

@pytest.fixture
def international_invoice():
    """Fixture providing an international invoice in EUR"""
    return {
        'invoice_number': 'INV-003',
        'vendor_name': 'European Tech GmbH',
        'vendor_id': 'VENDOR-EU-001',
        'po_number': 'PO-003',
        'total_amount': '42000.00',
        'currency': 'EUR',
        'line_items': [{
            'sku': 'SERVER-001',
            'description': 'Enterprise Server',
            'quantity': 2,
            'unit_price': '21000.00',
            'total': '42000.00'
        }],
        'shipping_amount': '500.00',
        'discount_amount': '0.00',
        'status': InvoiceStatus.NEW.value
    }

@pytest.fixture
def processor(test_config, mock_dependencies):
    """Fixture providing the workflow processor instance"""
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=mock_dependencies['source_manager'],
        document_processor=mock_dependencies['document_processor'],
        erp_connector=mock_dependencies['erp_connector'],
        notification_manager=mock_dependencies['notification_manager'],
        audit_logger=mock_dependencies['audit_logger'],
        metrics=mock_dependencies['metrics'],
        config=test_config
    )
    return processor

@pytest.mark.asyncio
async def test_successful_invoice_processing(
    processor,
    mock_dependencies,
    sample_invoice,
    sample_po_data,
    sample_gr_data
):
    """Test successful invoice processing flow"""
    # Setup mocks
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    mock_dependencies['erp_connector'].get_purchase_order.return_value = sample_po_data
    mock_dependencies['erp_connector'].get_goods_receipt.return_value = {
        'gr_number': 'GR-001',
        'po_number': 'PO-001',
        'vendor_id': 'VENDOR-001',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'quantity': 20,
            'date_received': datetime.now().date().isoformat()
        }]
    }
    mock_dependencies['erp_connector'].schedule_payment.return_value = datetime.now()
    
    # Execute
    await processor.process_new_invoices()
    
    # Verify
    assert invoice.status == InvoiceStatus.SCHEDULED.value
    mock_dependencies['metrics'].record_invoice_processed.assert_called_with('matched')
    mock_dependencies['notification_manager'].send_notification.assert_called()
    mock_dependencies['audit_logger'].log_event.assert_called()

@pytest.mark.asyncio
async def test_invoice_exception_handling(
    processor,
    mock_dependencies,
    sample_invoice,
    sample_po_data
):
    """Test handling of invoice exceptions"""
    # Setup mocks with mismatched amount
    invoice = Invoice.from_dict(sample_invoice)
    sample_po_data['total_amount'] = 45000.00  # Create mismatch
    
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    mock_dependencies['erp_connector'].get_purchase_order.return_value = sample_po_data
    
    # Execute
    await processor.process_new_invoices()
    
    # Verify
    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_invoice_processed.assert_called_with('exception')
    mock_dependencies['notification_manager'].send_notification.assert_called()

@pytest.mark.asyncio
async def test_retry_logic(processor, mock_dependencies, sample_invoice):
    """Test retry logic for temporary failures"""
    # Setup mocks
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.side_effect = [
        Exception("Temporary error"),
        Exception("Temporary error"),
        sample_invoice
    ]
    mock_dependencies['erp_connector'].get_purchase_order.return_value = sample_invoice
    mock_dependencies['erp_connector'].get_goods_receipt.return_value = {
        'gr_number': 'GR-001',
        'po_number': 'PO-001',
        'vendor_id': 'VENDOR-001',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'quantity': 20,
            'date_received': datetime.now().date().isoformat()
        }]
    }
    
    # Execute
    await processor.process_new_invoices()
    
    # Verify
    assert mock_dependencies['document_processor'].process_document.call_count == 3
    assert invoice.status == InvoiceStatus.SCHEDULED.value

@pytest.mark.asyncio
async def test_max_retries_exceeded(processor, mock_dependencies, sample_invoice):
    """Test handling of max retries exceeded"""
    # Setup mock to consistently raise Exception
    mock_dependencies['document_processor'].process_document.side_effect = Exception("Persistent error")
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [Invoice.from_dict(sample_invoice)]
    
    # Process invoice
    with pytest.raises(Exception):
        await processor.process_new_invoices()
    
    # Verify error handling
    mock_dependencies['metrics'].record_error.assert_called_with("max_retries_exceeded")
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        ANY,
        {'exception_type': ['MAX_RETRIES'], 'description': ['Persistent error']}
    )

@pytest.mark.asyncio
async def test_empty_invoice_list(processor, mock_dependencies):
    """Test handling of empty invoice list"""
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = []
    
    await processor.process_new_invoices()
    
    mock_dependencies['metrics'].update_queue_size.assert_called_with(0)
    mock_dependencies['document_processor'].process_document.assert_not_called()

@pytest.mark.asyncio
async def test_network_timeout(processor, mock_dependencies, sample_invoice):
    """Test handling of network timeouts"""
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['erp_connector'].get_purchase_order.side_effect = asyncio.TimeoutError("Network timeout")
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    
    with pytest.raises(asyncio.TimeoutError):
        await processor.process_new_invoices()
    
    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_error.assert_called_with('timeout_error')
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice,
        {'exception_type': ['TIMEOUT'], 'description': ['Network timeout']}
    )

@pytest.mark.asyncio
async def test_concurrent_processing(processor, mock_dependencies, sample_invoice):
    """Test concurrent processing of multiple invoices"""
    invoices = [Invoice.from_dict(sample_invoice) for _ in range(5)]
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = invoices
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    
    await processor.process_new_invoices()
    
    assert mock_dependencies['document_processor'].process_document.call_count == 5

@pytest.mark.asyncio
async def test_invoice_validation(processor, mock_dependencies, sample_invoice):
    """Test comprehensive invoice validation"""
    # Test case: Missing required fields
    invalid_invoice = {'vendor_name': 'Test Vendor'}  # Invalid invoice data
    
    invoice = Invoice.from_dict(sample_invoice)  # Create a valid invoice first
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = invalid_invoice
    mock_dependencies['erp_connector'].get_purchase_order.return_value = None
    
    await processor.process_new_invoices()
    
    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_error.assert_called_with('processing_error')
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice,
        {'exception_type': ['PO_MISMATCH'], 'description': ['Purchase order details do not match']}
    )

@pytest.mark.asyncio
async def test_complex_invoice_processing(
    processor,
    mock_dependencies,
    complex_invoice,
    sample_po_data
):
    """Test processing of complex invoice with multiple line items"""
    invoice = Invoice.from_dict(complex_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = complex_invoice

    # Modify PO data to match complex invoice
    sample_po_data['line_items'] = complex_invoice['line_items']
    sample_po_data['total_amount'] = complex_invoice['total_amount']
    mock_dependencies['erp_connector'].get_purchase_order.return_value = sample_po_data
    
    # Add matching goods receipt
    mock_dependencies['erp_connector'].get_goods_receipt.return_value = {
        'gr_number': 'GR-002',
        'po_number': 'PO-002',
        'vendor_id': 'VENDOR-001',
        'line_items': [
            {
                'sku': 'LAPTOP-001',
                'quantity': 20,
                'date_received': datetime.now().date().isoformat()
            },
            {
                'sku': 'DOCK-001',
                'quantity': 50,
                'date_received': datetime.now().date().isoformat()
            }
        ]
    }

    await processor.process_new_invoices()

    assert invoice.status == InvoiceStatus.SCHEDULED.value
    mock_dependencies['metrics'].record_invoice_processed.assert_called_with('matched')

@pytest.mark.asyncio
async def test_international_invoice(
    processor,
    mock_dependencies,
    international_invoice
):
    """Test processing of international invoice"""
    invoice = Invoice.from_dict(international_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = international_invoice

    # Mock exchange rate service
    mock_dependencies['erp_connector'].get_exchange_rate.return_value = {
        'rate': 1.2,
        'date': datetime.now().date().isoformat()
    }

    # Mock PO and GR data
    mock_dependencies['erp_connector'].get_purchase_order.return_value = {
        'po_number': 'PO-003',
        'vendor_id': 'VENDOR-EU-001',
        'total_amount': '42000.00',
        'currency': 'EUR',
        'line_items': international_invoice['line_items']
    }
    
    mock_dependencies['erp_connector'].get_goods_receipt.return_value = {
        'gr_number': 'GR-003',
        'po_number': 'PO-003',
        'vendor_id': 'VENDOR-EU-001',
        'line_items': [{
            'sku': 'SERVER-001',
            'quantity': 2,
            'date_received': datetime.now().date().isoformat()
        }]
    }

    await processor.process_new_invoices()

    assert invoice.status == InvoiceStatus.SCHEDULED.value
    mock_dependencies['erp_connector'].get_exchange_rate.assert_called_once()
    mock_dependencies['metrics'].record_invoice_processed.assert_called_with('matched')

@pytest.mark.asyncio
async def test_duplicate_invoice_handling(processor, mock_dependencies, sample_invoice):
    """Test handling of duplicate invoices"""
    # Create duplicate invoices
    invoice1 = Invoice.from_dict(sample_invoice)
    invoice2 = Invoice.from_dict(sample_invoice)  # Same invoice number
    
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice1, invoice2]
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    
    # Mock duplicate detection
    async def is_duplicate(invoice):
        return invoice == invoice2
    processor._is_duplicate_invoice = is_duplicate

    await processor.process_new_invoices()

    assert invoice2.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_error.assert_called_with('duplicate_invoice')
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice2,
        {'exception_type': ['DUPLICATE'], 'description': ['Duplicate invoice detected']}
    )

@pytest.mark.asyncio
async def test_partial_matching(
    processor,
    mock_dependencies,
    sample_invoice,
    sample_po_data
):
    """Test partial matching of invoices"""
    # Modify invoice to have multiple line items
    invoice_data = sample_invoice.copy()
    invoice_data['line_items'].append({
        'sku': 'DOCK-001',
        'description': 'Docking Station',
        'quantity': 50,
        'unit_price': '200.00',
        'total': '10000.00'
    })

    invoice = Invoice.from_dict(invoice_data)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = invoice_data
    mock_dependencies['erp_connector'].get_purchase_order.return_value = sample_po_data

    await processor.process_new_invoices()

    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice,
        {'exception_type': ['PO_MISMATCH'], 'description': ['Purchase order details do not match']}
    )

@pytest.mark.asyncio
async def test_timeout_handling(processor, mock_dependencies, sample_invoice):
    """Test handling of timeout errors"""
    # Setup mock to raise TimeoutError
    mock_dependencies['erp_connector'].get_purchase_order.side_effect = asyncio.TimeoutError("Network timeout")
    
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    
    # Process invoice
    with pytest.raises(asyncio.TimeoutError):
        await processor.process_new_invoices()
    
    # Verify error handling
    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_error.assert_called_with("timeout_error")
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice,
        {'exception_type': ['TIMEOUT'], 'description': ['Network timeout']}
    )

@pytest.mark.asyncio
async def test_data_consistency(processor, mock_dependencies, sample_invoice):
    """Test data consistency during invoice processing"""
    # Setup mock to return valid data
    mock_dependencies['document_processor'].process_document.return_value = sample_invoice
    mock_dependencies['erp_connector'].get_purchase_order.return_value = {
        'po_number': 'PO-001',
        'total_amount': '50000.00',
        'vendor_id': 'VENDOR-001',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'description': 'Business Laptop',
            'quantity': 20,
            'unit_price': '2500.00',
            'total': '50000.00'
        }]
    }
    mock_dependencies['erp_connector'].get_goods_receipt.return_value = {
        'gr_number': 'GR-001',
        'po_number': 'PO-001',
        'vendor_id': 'VENDOR-001',
        'line_items': [{
            'sku': 'LAPTOP-001',
            'quantity': 20,
            'date_received': datetime.now().date().isoformat()
        }]
    }
    mock_dependencies['erp_connector'].schedule_payment.return_value = datetime.now()
    
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    
    # Process invoice
    await processor.process_new_invoices()
    
    # Verify status transitions
    mock_dependencies['audit_logger'].log_event.assert_any_call(
        'invoice_status_change',
        invoice,
        {'status': InvoiceStatus.PROCESSING.value}
    )
    assert invoice.status == InvoiceStatus.SCHEDULED.value

@pytest.mark.asyncio
async def test_concurrent_error_handling(processor, mock_dependencies, sample_invoice):
    """Test handling of concurrent errors during invoice processing"""
    # Setup mock to raise TimeoutError
    mock_dependencies['document_processor'].process_document.side_effect = asyncio.TimeoutError("Network timeout")
    
    invoice = Invoice.from_dict(sample_invoice)
    mock_dependencies['source_manager'].fetch_all_invoices.return_value = [invoice]
    
    # Process invoice
    with pytest.raises(asyncio.TimeoutError):
        await processor.process_new_invoices()
    
    # Verify error handling
    assert invoice.status == InvoiceStatus.EXCEPTION.value
    mock_dependencies['metrics'].record_error.assert_called_with("timeout_error")
    mock_dependencies['audit_logger'].log_event.assert_called_with(
        'invoice_exception',
        invoice,
        {'exception_type': ['TIMEOUT'], 'description': ['Network timeout']}
    ) 