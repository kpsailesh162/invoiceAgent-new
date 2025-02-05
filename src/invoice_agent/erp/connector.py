from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime, timedelta

class ERPConnector(ABC):
    """Base class for ERP system connectors"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    async def check_connection(self) -> Dict[str, bool]:
        """Check connection to ERP system"""
        pass
    
    @abstractmethod
    async def get_purchase_order(self, po_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get purchase order data from ERP system"""
        pass
    
    @abstractmethod
    async def get_goods_receipt(self, po_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get goods receipt data from ERP system"""
        pass
    
    @abstractmethod
    async def post_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post invoice to ERP system"""
        pass
    
    @abstractmethod
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[float]:
        """Get exchange rate between currencies"""
        pass

    @abstractmethod
    async def schedule_payment(self, invoice_data: Dict[str, Any]) -> Optional[datetime]:
        """Schedule payment for an invoice"""
        pass

class MockERPConnector(ERPConnector):
    """Mock implementation of ERP connector for testing"""
    
    async def check_connection(self) -> Dict[str, bool]:
        """Check connection to ERP system"""
        try:
            self.logger.info("Checking ERP connection")
            return {"connected": True}
        except Exception as e:
            self.logger.error(f"Error checking connection: {str(e)}")
            return {"connected": False}
    
    async def get_purchase_order(self, po_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get purchase order data from ERP"""
        try:
            if not po_number:
                self.logger.error("No PO number provided")
                return None
                
            self.logger.info(f"Fetching PO data: {po_number}")
            
            # Return mock data
            return {
                "po_number": po_number,
                "vendor_id": "V001",
                "total_amount": 5000.00,
                "currency": "USD",
                "status": "completed",
                "line_items": [
                    {
                        "sku": "ITEM001",
                        "description": "Software License",
                        "quantity": 5,
                        "unit_price": 1000.00,
                        "total": 5000.00
                    }
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching PO data {po_number}: {str(e)}")
            raise
    
    async def get_goods_receipt(self, po_number: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get goods receipt data from ERP"""
        try:
            if not po_number:
                self.logger.error("No PO number provided")
                return None
                
            self.logger.info(f"Fetching GR data for PO: {po_number}")
            
            # Return mock data
            return {
                "gr_number": f"GR{po_number[2:]}",
                "po_number": po_number,
                "vendor_id": "V001",
                "status": "received",
                "line_items": [
                    {
                        "sku": "ITEM001",
                        "description": "Software License",
                        "quantity": 5,
                        "unit_price": 1000.00,
                        "total": 5000.00
                    }
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching GR data for PO {po_number}: {str(e)}")
            raise
    
    async def post_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post invoice data to ERP"""
        try:
            self.logger.info(f"Posting invoice: {invoice_data.get('invoice_number')}")
            
            # Return mock response
            return {
                "status": "success",
                "message": "Invoice posted successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Error posting invoice: {str(e)}")
            raise
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[float]:
        """Get exchange rate between currencies"""
        try:
            self.logger.info(f"Fetching exchange rate: {from_currency} to {to_currency}")
            
            # Return mock rate
            return 1.0 if from_currency == to_currency else 1.2
            
        except Exception as e:
            self.logger.error(f"Error fetching exchange rate: {str(e)}")
            raise
    
    async def schedule_payment(self, invoice_data: Dict[str, Any]) -> Optional[datetime]:
        """Schedule payment for an invoice"""
        try:
            self.logger.info(f"Scheduling payment for invoice: {invoice_data.get('invoice_number')}")
            
            # Return mock payment date (30 days from now)
            return datetime.now() + timedelta(days=30)
            
        except Exception as e:
            self.logger.error(f"Error scheduling payment: {str(e)}")
            raise 