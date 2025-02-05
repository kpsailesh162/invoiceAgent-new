from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import asyncio
from ..core.data_model import Invoice
from ..agent import InvoiceAgent
from ..database.models import ProcessedInvoice
from sqlalchemy.orm import Session

class BatchProcessor:
    def __init__(self, db_session: Session, max_workers: int = 4):
        self.db_session = db_session
        self.max_workers = max_workers
        self.agent = InvoiceAgent("config.yaml")
    
    async def process_batch(
        self,
        invoices: List[Invoice]
    ) -> Dict[str, Any]:
        results = []
        failed = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create tasks for each invoice
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor,
                    self._process_single_invoice,
                    invoice
                )
                for invoice in invoices
            ]
            
            # Wait for all tasks to complete
            completed = await asyncio.gather(*tasks)
            
            # Process results
            for invoice, result in zip(invoices, completed):
                if result['success']:
                    results.append(invoice.invoice_number)
                else:
                    failed.append({
                        'invoice_number': invoice.invoice_number,
                        'errors': result['errors']
                    })
        
        return {
            'processed': len(results),
            'failed': len(failed),
            'successful_invoices': results,
            'failed_invoices': failed
        }
    
    def _process_single_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        try:
            # Process invoice
            result = self.agent.process_invoice(invoice)
            
            # Store result in database
            processed_invoice = ProcessedInvoice(
                invoice_number=invoice.invoice_number,
                date=invoice.date,
                vendor_name=invoice.vendor_name,
                total_amount=invoice.total_amount,
                status='processed' if result['success'] else 'failed',
                connector_type=self.agent.connector.__class__.__name__,
                raw_data=invoice.__dict__
            )
            
            self.db_session.add(processed_invoice)
            self.db_session.commit()
            
            return result
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            } 