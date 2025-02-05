import pandas as pd
from pathlib import Path
from typing import Dict, Any
from .base_connector import BaseConnector
from ..core.data_model import Invoice

class ExcelConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        self.output_dir = Path(config['output_directory'])
        self.template_path = Path(config['template_path'])
        self.field_mapping = config['field_mapping']
        
    def connect(self) -> bool:
        return (
            self.output_dir.exists() and 
            self.template_path.exists() and 
            self.template_path.suffix in ('.xlsx', '.xls')
        )
    
    def export_invoice(self, invoice: Invoice) -> bool:
        try:
            df = self._convert_invoice_to_dataframe(invoice)
            output_path = self.output_dir / f"invoice_{invoice.invoice_number}.xlsx"
            df.to_excel(output_path, index=False)
            return True
        except Exception:
            return False
    
    def _convert_invoice_to_dataframe(self, invoice: Invoice) -> pd.DataFrame:
        # Create line items dataframe
        items_data = []
        for item in invoice.line_items:
            items_data.append({
                'Invoice Number': invoice.invoice_number,
                'Date': invoice.date,
                'Vendor': invoice.vendor_name,
                'Description': item.description,
                'Quantity': item.quantity,
                'Unit Price': item.unit_price,
                'Total': item.total,
                'Tax Amount': item.tax_amount
            })
        
        return pd.DataFrame(items_data) 