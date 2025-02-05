from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import logging
from .base import SourceIntegration, SourceIntegrationError
from .email import EmailIntegration
from .api_source import APISourceIntegration
from ..core.data_model import Invoice
from ..ml.document_processor import DocumentProcessor

class SourceManager:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.sources: Dict[str, SourceIntegration] = {}
        self.document_processor = DocumentProcessor(config)
        self._initialize_sources()
    
    def _initialize_sources(self):
        """Initialize configured source integrations"""
        source_mapping = {
            'email': EmailIntegration,
            'api': APISourceIntegration
        }
        
        for source_config in self.config.get('sources', []):
            source_type = source_config['type']
            if source_type in source_mapping:
                try:
                    source = source_mapping[source_type](source_config)
                    self.sources[source_config['name']] = source
                except Exception as e:
                    self.logger.error(
                        f"Failed to initialize {source_type} source "
                        f"'{source_config['name']}': {str(e)}"
                    )
    
    async def fetch_all_invoices(
        self,
        since: Optional[datetime] = None
    ) -> List[Invoice]:
        """Fetch and process invoices from all sources"""
        tasks = []
        async with asyncio.TaskGroup() as group:
            for source_name, source in self.sources.items():
                task = group.create_task(
                    self._fetch_from_source(source_name, source, since)
                )
                tasks.append(task)
        
        # Collect results
        invoices = []
        for task in tasks:
            try:
                result = task.result()
                invoices.extend(result)
            except Exception as e:
                self.logger.error(f"Source fetch error: {str(e)}")
        
        return invoices
    
    async def _fetch_from_source(
        self,
        source_name: str,
        source: SourceIntegration,
        since: Optional[datetime]
    ) -> List[Invoice]:
        """Fetch and process invoices from a single source"""
        invoices = []
        
        try:
            async with source:  # Use context manager
                async for invoice_data in source.fetch_invoices(since):
                    try:
                        # Process document
                        file_path = invoice_data.get('file_path')
                        if not file_path:
                            continue
                        
                        extracted_data = await self.document_processor.process_document(
                            file_path
                        )
                        
                        # Create Invoice object
                        invoice = Invoice(
                            source=source_name,
                            source_id=invoice_data.get('id'),
                            raw_data=invoice_data,
                            **extracted_data
                        )
                        
                        # Validate invoice
                        if self._validate_invoice(invoice):
                            invoices.append(invoice)
                            await source.mark_as_processed(invoice.source_id)
                        
                    except Exception as e:
                        self.logger.error(
                            f"Failed to process invoice from {source_name}: {str(e)}"
                        )
                        
        except SourceIntegrationError as e:
            self.logger.error(f"Error fetching from {source_name}: {str(e)}")
        
        return invoices
    
    def _validate_invoice(self, invoice: Invoice) -> bool:
        """Validate processed invoice"""
        # Add your validation logic here
        required_fields = ['invoice_number', 'date', 'total_amount']
        
        for field in required_fields:
            if not getattr(invoice, field, None):
                self.logger.warning(
                    f"Missing required field '{field}' in invoice {invoice.source_id}"
                )
                return False
        
        return True 