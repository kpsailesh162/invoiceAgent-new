from quickbooks import QuickBooks
from quickbooks.objects.bill import Bill, BillLine
from typing import Dict, Any
from .base_connector import BaseConnector
from ..core.data_model import Invoice

class QuickBooksConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.refresh_token = config['refresh_token']
        self.company_id = config['company_id']
        self.client = None
        
    def connect(self) -> bool:
        try:
            self.client = QuickBooks(
                client_id=self.client_id,
                client_secret=self.client_secret,
                refresh_token=self.refresh_token,
                company_id=self.company_id
            )
            return True
        except Exception:
            return False
    
    def export_invoice(self, invoice: Invoice) -> bool:
        try:
            bill = Bill()
            bill.DocNumber = invoice.invoice_number
            bill.TxnDate = invoice.date
            
            for item in invoice.line_items:
                line = BillLine()
                line.Amount = float(item.total)
                line.Description = item.description
                line.DetailType = "ItemBasedExpenseLineDetail"
                bill.Line.append(line)
            
            bill.save()
            return True
        except Exception:
            return False 