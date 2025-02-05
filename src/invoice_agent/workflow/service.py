import asyncio
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config.settings import config
from .processor import EnhancedInvoiceWorkflowProcessor
from ..database import Database
from ..models import InvoiceStatus, WorkflowStatus

logger = logging.getLogger(__name__)

class WorkflowProcessorService:
    def __init__(self):
        self.processor = EnhancedInvoiceWorkflowProcessor()
        self.db = Database(config.DB_CONFIG)
        self.running = False
        self._setup_logging()
    
    def _setup_logging(self):
        logging.basicConfig(
            filename=config.LOG_FILE,
            format=config.LOG_FORMAT,
            level=getattr(logging, config.LOG_LEVEL)
        )
    
    async def start(self):
        """Start the workflow processor service"""
        logger.info("Starting workflow processor service")
        self.running = True
        
        while self.running:
            try:
                # Get pending invoices from database
                pending_invoices = await self.db.get_invoices_by_status(InvoiceStatus.PENDING)
                
                for invoice in pending_invoices[:config.PROCESSING['batch_size']]:
                    try:
                        # Update workflow status to processing
                        await self.db.update_workflow_status(
                            invoice.workflow_id,
                            WorkflowStatus.PROCESSING
                        )
                        
                        # Process the invoice
                        result = await self.processor.process_invoice(invoice)
                        
                        # Update workflow status based on result
                        if result.success:
                            await self.db.update_workflow_status(
                                invoice.workflow_id,
                                WorkflowStatus.COMPLETED
                            )
                        else:
                            await self.db.update_workflow_status(
                                invoice.workflow_id,
                                WorkflowStatus.FAILED,
                                error_message=result.error_message
                            )
                    
                    except Exception as e:
                        logger.error(f"Error processing invoice {invoice.id}: {str(e)}")
                        await self.db.update_workflow_status(
                            invoice.workflow_id,
                            WorkflowStatus.FAILED,
                            error_message=str(e)
                        )
                
                # Wait before next batch
                await asyncio.sleep(config.PROCESSING['poll_interval'])
            
            except Exception as e:
                logger.error(f"Service error: {str(e)}")
                await asyncio.sleep(config.PROCESSING['retry_delay'])
    
    async def stop(self):
        """Stop the workflow processor service"""
        logger.info("Stopping workflow processor service")
        self.running = False
    
    @classmethod
    async def create_and_start(cls):
        """Factory method to create and start the service"""
        service = cls()
        asyncio.create_task(service.start())
        return service 