import requests
from typing import Dict, Any
from .base_connector import BaseConnector
from ..core.data_model import Invoice

class SAPConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config['base_url']
        self.api_key = config['api_key']
        self.company_code = config['company_code']
        
    def connect(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/connection_test",
                headers=self._get_headers()
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def export_invoice(self, invoice: Invoice) -> bool:
        payload = self._transform_to_sap_format(invoice)
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/invoices",
                headers=self._get_headers(),
                json=payload
            )
            return response.status_code in (200, 201)
        except Exception:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Company-Code': self.company_code
        }
    
    def _transform_to_sap_format(self, invoice: Invoice) -> Dict[str, Any]:
        return {
            'InvoiceHeader': {
                'DocNumber': invoice.invoice_number,
                'DocDate': invoice.date.strftime('%Y%m%d'),
                'VendorName': invoice.vendor_name,
                'VendorTaxID': invoice.vendor_tax_id,
                'TotalAmount': str(invoice.total_amount),
                'Currency': invoice.currency
            },
            'InvoiceItems': [
                {
                    'ItemNumber': idx + 1,
                    'Material': item.product_code,
                    'Description': item.description,
                    'Quantity': str(item.quantity),
                    'UnitPrice': str(item.unit_price),
                    'TotalPrice': str(item.total)
                }
                for idx, item in enumerate(invoice.line_items)
            ]
        } 