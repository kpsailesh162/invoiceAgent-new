import pytest
import asyncio
from typing import Dict, Any
from pathlib import Path
import json
import shutil
import yaml
from datetime import datetime

@pytest.fixture
def test_config():
    """Load test configuration"""
    config_path = Path(__file__).parent / 'fixtures' / 'test_config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)['environments']['test']

@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for test files"""
    return tmp_path

@pytest.fixture
def sample_template():
    """Sample invoice template"""
    return {
        "name": "test_template",
        "fields": {
            "invoice_number": {"type": "string", "required": True},
            "date": {"type": "date", "required": True},
            "amount": {"type": "number", "required": True},
            "vendor": {"type": "string", "required": True},
            "description": {"type": "string", "required": False}
        }
    }

@pytest.fixture
def sample_workflow():
    """Sample workflow data"""
    return {
        "id": "test_workflow",
        "type": "single_invoice",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "steps": [],
        "metadata": {}
    }

@pytest.fixture
def sample_metrics():
    """Sample metrics data"""
    return {
        "processed_today": 10,
        "success_rate": 95.5,
        "processing_queue": 5,
        "avg_processing_time": 2.3
    }

def cleanup_test_files():
    """Clean up test files after tests"""
    dirs_to_cleanup = [
        'tests/fixtures/templates',
        'tests/fixtures/workflows',
        'tests/fixtures/metrics'
    ]
    for dir_path in dirs_to_cleanup:
        path = Path(dir_path)
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

@pytest.fixture(autouse=True)
def run_around_tests():
    """Setup and teardown for all tests"""
    cleanup_test_files()
    yield
    cleanup_test_files()

@pytest.fixture
def sample_invoice():
    return {
        'invoice_number': 'INV-2024-001',
        'vendor_name': 'CompuWorld',
        'vendor_id': 'VEN001',
        'po_number': 'PO-1234',
        'total_amount': '50000.00',
        'currency': 'USD',
        'line_items': [
            {
                'sku': 'LAPTOP-001',
                'description': 'Business Laptop',
                'quantity': 50,
                'unit_price': '1000.00',
                'total': '50000.00'
            }
        ]
    }

@pytest.fixture
def sample_po_data():
    return {
        'po_number': 'PO-1234',
        'vendor_id': 'VEN001',
        'total_amount': 50000.00,
        'currency': 'USD',
        'line_items': [
            {
                'sku': 'LAPTOP-001',
                'quantity': 50,
                'unit_price': 1000.00,
                'total': 50000.00
            }
        ]
    }

@pytest.fixture
def sample_gr_data():
    return {
        'gr_number': 'GR-001',
        'po_number': 'PO-1234',
        'posting_date': '2024-01-15',
        'line_items': [
            {
                'sku': 'LAPTOP-001',
                'quantity': 50,
                'unit': 'EA'
            }
        ]
    } 