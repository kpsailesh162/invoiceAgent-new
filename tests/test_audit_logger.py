import pytest
import json
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from decimal import Decimal
from invoice_agent.audit.logger import AuditLogger
from invoice_agent.core.data_model import Invoice, LineItem
import aiofiles

@pytest.fixture
def test_config():
    return {
        'audit': {
            'directory': 'test_audit_logs',
            'external_system': False
        }
    }

@pytest.fixture
def test_invoice():
    return Invoice(
        invoice_number="INV-001",
        vendor_name="Test Vendor",
        vendor_id="V123",
        po_number="PO123",
        total_amount=Decimal('100.00'),
        currency="USD",
        line_items=[
            LineItem(
                sku="SKU123",
                description="Test Item",
                quantity=1,
                unit_price=Decimal('100.00'),
                total=Decimal('100.00')
            )
        ]
    )

@pytest.fixture
def audit_logger(test_config, tmp_path):
    test_config['audit']['directory'] = str(tmp_path / 'audit_logs')
    return AuditLogger(test_config)

@pytest.mark.asyncio
async def test_log_event_basic(audit_logger, test_invoice):
    event_type = "INVOICE_RECEIVED"
    details = {"source": "email"}
    
    await audit_logger.log_event(event_type, test_invoice, details)
    
    # Check log file
    log_dir = Path(audit_logger.audit_dir)
    log_files = list(log_dir.glob('*.jsonl'))
    assert len(log_files) == 1
    
    # Verify log content
    async with aiofiles.open(log_files[0], 'r') as f:
        content = await f.read()
        log_entry = json.loads(content.strip())
        
        assert log_entry['event_type'] == event_type
        assert log_entry['invoice_number'] == test_invoice.invoice_number
        assert log_entry['vendor_name'] == test_invoice.vendor_name
        assert float(log_entry['amount']) == test_invoice.total_amount
        assert log_entry['currency'] == test_invoice.currency
        assert log_entry['user'] == 'system'
        assert log_entry['details'] == details

@pytest.mark.asyncio
async def test_log_event_with_user(audit_logger, test_invoice):
    event_type = "INVOICE_APPROVED"
    details = {"approver_role": "manager"}
    user = "john.doe"
    
    await audit_logger.log_event(event_type, test_invoice, details, user)
    
    log_dir = Path(audit_logger.audit_dir)
    log_files = list(log_dir.glob('*.jsonl'))
    async with aiofiles.open(log_files[0], 'r') as f:
        content = await f.read()
        log_entry = json.loads(content.strip())
        assert log_entry['user'] == user

@pytest.mark.asyncio
async def test_log_event_error_handling(audit_logger, test_invoice):
    with patch('aiofiles.open', side_effect=Exception("Test error")):
        # Should not raise exception but log error
        await audit_logger.log_event("TEST", test_invoice, {})

@pytest.mark.asyncio
async def test_external_system_integration(test_config, test_invoice):
    test_config['audit']['external_system'] = True
    logger = AuditLogger(test_config)
    
    with patch.object(logger, '_send_to_external_system') as mock_send:
        await logger.log_event("TEST", test_invoice, {})
        assert mock_send.called

@pytest.mark.asyncio
async def test_external_system_error(test_config, test_invoice):
    test_config['audit']['external_system'] = True
    logger = AuditLogger(test_config)
    
    with patch.object(logger, '_send_to_external_system', 
                     side_effect=Exception("External system error")):
        # Should not raise exception but log error
        await logger.log_event("TEST", test_invoice, {})

@pytest.mark.asyncio
async def test_multiple_log_events(audit_logger, test_invoice):
    events = [
        ("RECEIVED", {"source": "email"}),
        ("VALIDATED", {"status": "success"}),
        ("PROCESSED", {"result": "approved"})
    ]
    
    for event_type, details in events:
        await audit_logger.log_event(event_type, test_invoice, details)
    
    log_dir = Path(audit_logger.audit_dir)
    log_files = list(log_dir.glob('*.jsonl'))
    assert len(log_files) == 1
    
    async with aiofiles.open(log_files[0], 'r') as f:
        content = await f.read()
        log_entries = [json.loads(line) for line in content.strip().split('\n')]
        assert len(log_entries) == len(events)
        for i, (event_type, details) in enumerate(events):
            assert log_entries[i]['event_type'] == event_type
            assert log_entries[i]['details'] == details 