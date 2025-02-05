import cx_Oracle
from typing import Dict, Any
from .base_connector import BaseConnector
from ..core.data_model import Invoice

class OracleConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        self.connection_string = config['connection_string']
        self.username = config['username']
        self.password = config['password']
        self.connection = None
        
    def connect(self) -> bool:
        try:
            self.connection = cx_Oracle.connect(
                self.username,
                self.password,
                self.connection_string
            )
            return True
        except Exception:
            return False
    
    def export_invoice(self, invoice: Invoice) -> bool:
        try:
            cursor = self.connection.cursor()
            # Insert invoice header
            cursor.execute("""
                INSERT INTO AP_INVOICES (
                    INVOICE_NUMBER, INVOICE_DATE, VENDOR_NAME,
                    TOTAL_AMOUNT, CURRENCY_CODE
                ) VALUES (:1, :2, :3, :4, :5)
            """, (
                invoice.invoice_number,
                invoice.date,
                invoice.vendor_name,
                float(invoice.total_amount),
                invoice.currency
            ))
            
            # Insert line items
            for item in invoice.line_items:
                cursor.execute("""
                    INSERT INTO AP_INVOICE_LINES (
                        INVOICE_NUMBER, DESCRIPTION, QUANTITY,
                        UNIT_PRICE, TOTAL_AMOUNT
                    ) VALUES (:1, :2, :3, :4, :5)
                """, (
                    invoice.invoice_number,
                    item.description,
                    float(item.quantity),
                    float(item.unit_price),
                    float(item.total)
                ))
            
            self.connection.commit()
            return True
        except Exception:
            self.connection.rollback()
            return False 