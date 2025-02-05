import logging
from typing import List
import asyncio
from pathlib import Path
from ..core.data_model import Invoice

class SourceManager:
    def __init__(self, upload_dir: str = "uploads"):
        self.logger = logging.getLogger(__name__)
        # Convert to absolute path
        self.upload_dir = Path(upload_dir).resolve()
        
        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def fetch_all_invoices(self) -> List[Invoice]:
        """Fetch all pending invoices from the upload directory"""
        try:
            self.logger.info("Fetching pending invoices")
            
            # Get all PDF files in upload directory
            invoice_files = list(self.upload_dir.glob("*.pdf"))
            
            if not invoice_files:
                self.logger.info("No pending invoices found")
                return []
            
            # Create Invoice objects for each file
            invoices = []
            for file_path in invoice_files:
                # Check if a .processed flag file exists
                processed_flag = file_path.with_suffix('.processed')
                if not processed_flag.exists():
                    # Use absolute path for file_path
                    invoice = Invoice(
                        invoice_number=file_path.stem,  # Will be updated by document processor
                        file_path=str(file_path)
                    )
                    invoices.append(invoice)
            
            return invoices
            
        except Exception as e:
            self.logger.error(f"Error fetching invoices: {str(e)}")
            raise
            
    async def mark_as_processed(self, invoice: Invoice):
        """Mark an invoice as processed"""
        try:
            # Create a .processed flag file
            file_path = Path(invoice.file_path)
            processed_flag = file_path.with_suffix('.processed')
            processed_flag.touch()
            
            # Save processing results
            results_file = file_path.with_suffix('.json')
            with open(results_file, 'w') as f:
                f.write(invoice.to_json())
                
        except Exception as e:
            self.logger.error(f"Error marking invoice as processed: {str(e)}")
            raise 