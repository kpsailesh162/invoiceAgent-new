import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from invoice_agent.workflow.processor import EnhancedInvoiceWorkflowProcessor, InvoiceStatus
from invoice_agent.core.data_model import Invoice, LineItem
from invoice_agent.erp.sap_connector import SAPConnector
from invoice_agent.notifications.manager import NotificationManager
from invoice_agent.audit.logger import AuditLogger
import aiohttp
from redis.asyncio import Redis

class MockSourceManager:
    async def fetch_all_invoices(self):
        return []

class MockDocumentProcessor:
    async def process_document(self, file_path):
        return {
            'po_number': 'PO-1234',
            'vendor_id': 'VEN001',
            'total_amount': '50000.00'
        }

class MockMetrics:
    async def update_queue_size(self, size):
        pass
    
    async def record_error(self, error_type):
        pass
    
    async def record_invoice_processed(self, status):
        pass
    
    async def observe_processing_time(self, start_time):
        pass
    
    async def observe_amount(self, amount):
        pass

class MockNotificationManager:
    async def send_notification(self, notification_type: str, data: dict, recipients: list = None):
        pass

class MockRedis:
    def __init__(self):
        self.data = {}
    
    async def get(self, key):
        return self.data.get(key)
    
    async def set(self, key, value):
        self.data[key] = value
    
    async def flushall(self):
        self.data = {}
    
    async def aclose(self):
        pass

class MockAuditLogger:
    def __init__(self):
        self.logs = []
    
    async def log_event(self, event_type: str, invoice: Invoice, details: dict, user: str = None):
        self.logs.append({
            'event_type': event_type,
            'invoice_number': invoice.invoice_number,
            'details': details
        })
    
    async def get_logs_for_invoice(self, invoice_number: str):
        return [log for log in self.logs if log['invoice_number'] == invoice_number]

@pytest.fixture
async def integration_setup(test_config):
    """Setup integration test environment"""
    # Setup Redis
    redis = MockRedis()
    await redis.flushall()
    
    # Setup components
    source_manager = MockSourceManager()
    document_processor = MockDocumentProcessor()
    erp_connector = SAPConnector(test_config)
    notification_manager = MockNotificationManager()
    audit_logger = MockAuditLogger()
    metrics = MockMetrics()
    
    # Setup HTTP client
    session = aiohttp.ClientSession()
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=source_manager,
        document_processor=document_processor,
        erp_connector=erp_connector,
        notification_manager=notification_manager,
        audit_logger=audit_logger,
        metrics=metrics,
        config=test_config
    )
    processor.redis = redis
    
    yield processor
    
    # Cleanup
    await redis.aclose()
    await session.close()

@pytest.mark.asyncio
async def test_process_single_invoice(integration_setup):
    """Test processing a single invoice through the workflow"""
    async for processor in integration_setup:
        # Create a test invoice with exact match to PO data
        line_items = [
            LineItem(
                sku="LAPTOP-001",
                description="Test Laptop",
                quantity=50,
                unit_price=Decimal("1000.00"),
                total=Decimal("50000.00")
            )
        ]
        
        invoice = Invoice(
            invoice_number="INV123",
            vendor_name="CompuWorld",
            vendor_id="VEN001",
            po_number="PO-1234",
            total_amount=Decimal("50000.00"),
            currency="USD",
            line_items=line_items,
            status="received"
        )
        
        # Process the invoice
        await processor._process_single_invoice(invoice)
        
        # Verify the invoice status
        assert invoice.status == InvoiceStatus.SCHEDULED.value
        
        # Verify Redis cache
        cached_data = await processor.redis.get(f"invoice:{invoice.invoice_number}")
        assert cached_data is not None

@pytest.mark.asyncio
async def test_end_to_end_processing(integration_setup, sample_invoice):
    """Test complete invoice processing flow"""
    async for processor in integration_setup:
        # Create line items from sample invoice with exact match to PO data
        line_items = [
            LineItem(
                sku="LAPTOP-001",
                description="Test Laptop",
                quantity=50,
                unit_price=Decimal("1000.00"),
                total=Decimal("50000.00")
            )
        ]
        
        # Create invoice with proper fields
        invoice = Invoice(
            invoice_number=sample_invoice['invoice_number'],
            vendor_name=sample_invoice['vendor_name'],
            vendor_id=sample_invoice['vendor_id'],
            po_number=sample_invoice['po_number'],
            total_amount=Decimal("50000.00"),
            currency=sample_invoice['currency'],
            line_items=line_items,
            status=sample_invoice['status']
        )
        
        # Process invoice
        await processor._process_single_invoice(invoice)
        
        # Verify invoice status
        assert invoice.status == InvoiceStatus.SCHEDULED.value
        
        # Verify Redis cache
        cached_data = await processor.redis.get(f"invoice:{invoice.invoice_number}")
        assert cached_data is not None
        
        # Verify audit logs
        audit_logs = await processor.audit_logger.get_logs_for_invoice(invoice.invoice_number)
        assert len(audit_logs) > 0

@pytest.mark.asyncio
async def test_erp_integration(integration_setup, sample_invoice):
    """Test integration with ERP system"""
    async for processor in integration_setup:
        # Test ERP connection
        erp_status = await processor.erp_connector.check_connection()
        assert erp_status['connected'] is True
        
        # Test PO fetch
        po_data = await processor.erp_connector.get_purchase_order(sample_invoice['po_number'])
        assert po_data is not None
        assert po_data['po_number'] == sample_invoice['po_number']
        assert po_data['vendor_id'] == sample_invoice['vendor_id'] 