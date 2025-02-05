import pytest
from src.invoice_agent.monitoring.metrics import MetricsCollector
from unittest.mock import patch
import time

@pytest.fixture
def metrics():
    return MetricsCollector(app_name="test")

def test_invoice_processing_metrics(metrics):
    # Test counter
    metrics.record_invoice_processed('matched')
    assert metrics.invoice_processed._value.get() == 1
    
    # Test error counter
    metrics.record_error('processing_error')
    assert metrics.invoice_errors._value.get() == 1
    
    # Test queue size
    metrics.update_queue_size(5)
    assert metrics.queue_size._value.get() == 5

def test_processing_time_tracking(metrics):
    @metrics.track_time(metrics.processing_time)
    def slow_function():
        time.sleep(0.1)
        return True
    
    result = slow_function()
    assert result is True
    assert metrics.processing_time._sum.get() > 0

def test_amount_distribution(metrics):
    amounts = [1000, 5000, 10000, 50000]
    for amount in amounts:
        metrics.observe_amount(amount)
    
    assert metrics.amount_distribution._sum.get() == sum(amounts) 