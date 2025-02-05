import pytest
import asyncio
from typing import Dict, Any
from pathlib import Path
import json

@pytest.fixture
def test_config() -> Dict[str, Any]:
    return {
        'notifications': {
            'email': {
                'sender': 'test@example.com',
                'smtp_host': 'smtp.test.com',
                'smtp_port': 587,
                'username': 'test',
                'password': 'test'
            },
            'slack': {
                'token': 'xoxb-test',
                'channel': '#test'
            }
        },
        'audit': {
            'directory': '/tmp/invoice-agent-test/audit',
            'external_system': {
                'type': 'test',
                'url': 'http://test.com'
            }
        },
        'sap': {
            'ashost': 'test.sap.com',
            'sysnr': '00',
            'client': '100',
            'user': 'test',
            'passwd': 'test'
        },
        'amount_tolerance': 0.01,
        'price_tolerance': 0.01,
        'max_retries': 3,
        'retry_delay': 1
    }

@pytest.fixture
def sample_invoice():
    return {
        'invoice_number': 'INV-2024-001',
        'vendor_name': 'CompuWorld',
        'vendor_id': 'VEN001',
        'po_number': 'PO-1234',
        'total_amount': '50000.00',
        'currency': 'USD',
        'due_date': '2024-03-31',
        'status': 'NEW'
    } 