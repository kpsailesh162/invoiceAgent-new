"""
Invoice Agent package initialization.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Version of the invoice_agent package
__version__ = "0.1.0"

# Import main components for easier access
from invoice_agent.core.invoice_processor import InvoiceAgent
from invoice_agent.security.auth import AuthManager
from invoice_agent.template.template_manager import TemplateManager
from invoice_agent.workflow.workflow_manager import WorkflowManager
from invoice_agent.monitoring.metrics import MetricsManager

__all__ = [
    'InvoiceAgent',
    'AuthManager',
    'TemplateManager',
    'WorkflowManager',
    'MetricsManager',
]
