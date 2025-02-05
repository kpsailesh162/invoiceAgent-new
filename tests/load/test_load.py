import pytest
import asyncio
import aiohttp
from src.invoice_agent.workflow.processor import EnhancedInvoiceWorkflowProcessor
from src.invoice_agent.core.data_model import Invoice
import time
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_users(test_config, sample_invoice):
    """Test system under concurrent user load"""
    async def simulate_user(user_id: int):
        processor = EnhancedInvoiceWorkflowProcessor(test_config)
        invoice = Invoice(**sample_invoice)
        invoice.invoice_number = f"{invoice.invoice_number}-{user_id}"
        
        try:
            await processor.process_single_invoice(invoice)
            return True
        except Exception as e:
            return False
    
    # Simulate 50 concurrent users
    tasks = [simulate_user(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    # Assert success rate
    success_rate = sum(results) / len(results)
    assert success_rate >= 0.95  # 95% success rate threshold

@pytest.mark.load
@pytest.mark.asyncio
async def test_sustained_load():
    """Test system under sustained load"""
    processor = EnhancedInvoiceWorkflowProcessor(test_config)
    
    async def process_batch(batch_id: int):
        invoices = [
            Invoice(**{**sample_invoice, 'invoice_number': f"INV-{batch_id}-{i}"})
            for i in range(10)
        ]
        start_time = time.time()
        await processor.process_new_invoices()
        return time.time() - start_time
    
    # Process 10 batches of 10 invoices each
    processing_times = []
    for i in range(10):
        batch_time = await process_batch(i)
        processing_times.append(batch_time)
        
    # Assert processing time remains stable
    time_variance = max(processing_times) - min(processing_times)
    assert time_variance < 1.0  # Maximum 1 second variance

@pytest.mark.load
async def test_error_rates_under_load():
    """Test error rates under heavy load"""
    processor = EnhancedInvoiceWorkflowProcessor(test_config)
    total_errors = 0
    total_requests = 1000
    
    async def process_with_error_tracking(invoice_id: int):
        try:
            invoice = Invoice(**{
                **sample_invoice,
                'invoice_number': f"INV-LOAD-{invoice_id}"
            })
            await processor.process_single_invoice(invoice)
            return None
        except Exception as e:
            return str(e)
    
    # Process 1000 invoices
    tasks = [process_with_error_tracking(i) for i in range(total_requests)]
    results = await asyncio.gather(*tasks)
    
    # Count errors
    total_errors = sum(1 for r in results if r is not None)
    error_rate = total_errors / total_requests
    
    # Assert error rate is below threshold
    assert error_rate < 0.05  # Maximum 5% error rate 