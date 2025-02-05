import pytest
import time
import asyncio
from src.invoice_agent.workflow.processor import EnhancedInvoiceWorkflowProcessor, InvoiceStatus
from src.invoice_agent.core.data_model import Invoice, LineItem
from decimal import Decimal
from datetime import datetime
from invoice_agent.erp.sap_connector import SAPConnector
from invoice_agent.notifications.manager import NotificationManager
from invoice_agent.audit.logger import AuditLogger
import aiohttp
from redis.asyncio import Redis
import statistics
import psutil
import os

@pytest.fixture
def test_config():
    """Test configuration fixture"""
    return {
        'sap': {
            'base_url': 'http://mock-sap-server:8080',
            'username': 'test_user',
            'password': 'test_pass',
            'timeout': 5
        },
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        'processing': {
            'batch_size': 10,
            'max_retries': 3,
            'retry_delay': 1
        }
    }

@pytest.mark.performance
@pytest.mark.asyncio
async def test_processing_time(test_config):
    """Test processing time for single invoice"""
    # Setup components
    source_manager = MockSourceManager()
    document_processor = MockDocumentProcessor()
    erp_connector = SAPConnector(test_config)
    notification_manager = MockNotificationManager()
    audit_logger = MockAuditLogger()
    metrics = MockMetrics()
    
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=source_manager,
        document_processor=document_processor,
        erp_connector=erp_connector,
        notification_manager=notification_manager,
        audit_logger=audit_logger,
        metrics=metrics,
        config=test_config
    )
    
    invoice = create_test_invoice("INV-PERF-TIME-001")
    
    start_time = time.time()
    await processor._process_single_invoice(invoice)
    processing_time = time.time() - start_time
    
    # Assert processing time is under threshold
    assert processing_time < 2.0  # 2 seconds threshold

@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage(test_config):
    """Test memory usage during processing"""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Setup components
    source_manager = MockSourceManager()
    document_processor = MockDocumentProcessor()
    erp_connector = SAPConnector(test_config)
    notification_manager = MockNotificationManager()
    audit_logger = MockAuditLogger()
    metrics = MockMetrics()
    
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=source_manager,
        document_processor=document_processor,
        erp_connector=erp_connector,
        notification_manager=notification_manager,
        audit_logger=audit_logger,
        metrics=metrics,
        config=test_config
    )
    
    # Process multiple invoices
    batch_size = 50
    invoices = [create_test_invoice(f"INV-PERF-MEM-{i+1:03d}") for i in range(batch_size)]
    
    await asyncio.gather(*(processor._process_single_invoice(invoice) for invoice in invoices))
    
    final_memory = process.memory_info().rss
    memory_increase = (final_memory - initial_memory) / 1024 / 1024  # Convert to MB
    
    # Assert memory increase is reasonable (less than 100MB)
    assert memory_increase < 100.0

@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_usage(test_config):
    """Test CPU usage during processing"""
    process = psutil.Process()
    initial_cpu_percent = process.cpu_percent()
    
    # Setup components
    source_manager = MockSourceManager()
    document_processor = MockDocumentProcessor()
    erp_connector = SAPConnector(test_config)
    notification_manager = MockNotificationManager()
    audit_logger = MockAuditLogger()
    metrics = MockMetrics()
    
    processor = EnhancedInvoiceWorkflowProcessor(
        source_manager=source_manager,
        document_processor=document_processor,
        erp_connector=erp_connector,
        notification_manager=notification_manager,
        audit_logger=audit_logger,
        metrics=metrics,
        config=test_config
    )
    
    # Process multiple invoices
    batch_size = 50
    invoices = [create_test_invoice(f"INV-PERF-CPU-{i+1:03d}") for i in range(batch_size)]
    
    await asyncio.gather(*(processor._process_single_invoice(invoice) for invoice in invoices))
    
    final_cpu_percent = process.cpu_percent()
    
    # Assert CPU usage is reasonable (less than 80%)
    assert final_cpu_percent < 80.0

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

def create_test_invoice(invoice_number: str) -> Invoice:
    """Create a test invoice with valid data"""
    line_items = [
        LineItem(
            sku="LAPTOP-001",
            description="Test Laptop",
            quantity=50,
            unit_price=Decimal("1000.00"),
            total=Decimal("50000.00")
        )
    ]
    
    return Invoice(
        invoice_number=invoice_number,
        vendor_name="CompuWorld",
        vendor_id="VEN001",
        po_number="PO-1234",
        total_amount=Decimal("50000.00"),
        currency="USD",
        line_items=line_items,
        status="received"
    )

@pytest.fixture
async def performance_setup(test_config):
    """Setup performance test environment"""
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
async def test_single_invoice_performance(performance_setup):
    """Test performance of processing a single invoice"""
    async for processor in performance_setup:
        # Create test invoice
        invoice = create_test_invoice("INV-PERF-001")
        
        # Measure processing time
        start_time = time.time()
        await processor._process_single_invoice(invoice)
        processing_time = time.time() - start_time
        
        # Log performance metrics
        print(f"\nSingle invoice processing time: {processing_time:.3f} seconds")
        
        # Verify successful processing
        assert invoice.status == InvoiceStatus.SCHEDULED.value
        assert processing_time < 1.0  # Should process within 1 second

@pytest.mark.asyncio
async def test_batch_processing_performance(performance_setup):
    """Test performance of batch invoice processing"""
    async for processor in performance_setup:
        # Create batch of test invoices
        batch_size = 10
        invoices = [
            create_test_invoice(f"INV-PERF-BATCH-{i+1:03d}")
            for i in range(batch_size)
        ]
        
        # Measure batch processing time
        start_time = time.time()
        await asyncio.gather(*(
            processor._process_single_invoice(invoice)
            for invoice in invoices
        ))
        total_time = time.time() - start_time
        
        # Calculate metrics
        avg_time_per_invoice = total_time / batch_size
        throughput = batch_size / total_time
        
        # Log performance metrics
        print(f"\nBatch processing metrics:")
        print(f"Total time for {batch_size} invoices: {total_time:.3f} seconds")
        print(f"Average time per invoice: {avg_time_per_invoice:.3f} seconds")
        print(f"Throughput: {throughput:.2f} invoices/second")
        
        # Verify successful processing
        assert all(inv.status == InvoiceStatus.SCHEDULED.value for inv in invoices)
        assert avg_time_per_invoice < 1.0  # Each invoice should average under 1 second

@pytest.mark.asyncio
async def test_concurrent_load_performance(performance_setup):
    """Test performance under concurrent load"""
    async for processor in performance_setup:
        # Test parameters
        num_concurrent = 5  # Number of concurrent batches
        batch_size = 5      # Invoices per batch
        total_invoices = num_concurrent * batch_size
        
        # Create batches of test invoices
        all_invoices = [
            create_test_invoice(f"INV-PERF-CONC-{i+1:03d}")
            for i in range(total_invoices)
        ]
        
        # Split into batches
        batches = [
            all_invoices[i:i + batch_size]
            for i in range(0, total_invoices, batch_size)
        ]
        
        # Process batches concurrently and measure times
        processing_times = []
        start_time = time.time()
        
        async def process_batch(batch):
            batch_start = time.time()
            await asyncio.gather(*(
                processor._process_single_invoice(invoice)
                for invoice in batch
            ))
            processing_times.append(time.time() - batch_start)
        
        await asyncio.gather(*(
            process_batch(batch)
            for batch in batches
        ))
        
        total_time = time.time() - start_time
        
        # Calculate metrics
        avg_batch_time = statistics.mean(processing_times)
        std_dev = statistics.stdev(processing_times)
        throughput = total_invoices / total_time
        
        # Log performance metrics
        print(f"\nConcurrent load metrics:")
        print(f"Total time for {total_invoices} invoices: {total_time:.3f} seconds")
        print(f"Average batch time: {avg_batch_time:.3f} seconds")
        print(f"Standard deviation: {std_dev:.3f} seconds")
        print(f"Throughput: {throughput:.2f} invoices/second")
        
        # Verify successful processing
        assert all(inv.status == InvoiceStatus.SCHEDULED.value for inv in all_invoices)
        assert avg_batch_time < 2.0  # Each batch should complete within 2 seconds 