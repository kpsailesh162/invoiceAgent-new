from typing import Dict, Any, Type
from pathlib import Path
import logging
from .core.config_manager import ConfigManager
from .core.data_model import Invoice
from .connectors.base_connector import BaseConnector
from .connectors.sap_connector import SAPConnector
from .connectors.excel_connector import ExcelConnector
from .validation.rule_engine import RuleEngine

class InvoiceAgent:
    def __init__(self, config_path: str):
        self.config_manager = ConfigManager(config_path)
        self.rule_engine = RuleEngine(self.config_manager.get_validation_rules())
        self.connector = self._initialize_connector()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _initialize_connector(self) -> BaseConnector:
        erp_config = self.config_manager.get_erp_config()
        connector_type = erp_config.get('type', 'excel').lower()
        
        if connector_type == 'sap':
            return SAPConnector(erp_config)
        else:
            return ExcelConnector(erp_config)
    
    def process_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        self.logger.info(f"Processing invoice {invoice.invoice_number}")
        
        # Validate invoice
        validation_errors = self.rule_engine.validate_invoice(invoice)
        if validation_errors:
            self.logger.error(f"Validation errors: {validation_errors}")
            return {'success': False, 'errors': validation_errors}
        
        # Export to target system
        if not self.connector.connect():
            self.logger.error("Failed to connect to target system")
            return {'success': False, 'errors': ['Connection failed']}
        
        export_success = self.connector.export_invoice(invoice)
        if not export_success:
            self.logger.error("Failed to export invoice")
            return {'success': False, 'errors': ['Export failed']}
        
        self.logger.info(f"Successfully processed invoice {invoice.invoice_number}")
        return {'success': True} 