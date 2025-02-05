from typing import Dict, List, Optional
import random
from datetime import datetime, timedelta

class ERPService:
    def __init__(self):
        # Mock ERP data store
        self.purchase_orders = self._generate_mock_pos()
        self.goods_receipts = self._generate_mock_receipts()
    
    def _generate_mock_pos(self) -> Dict[str, Dict]:
        """Generate mock purchase orders"""
        mock_pos = {}
        vendors = ["Tech Corp", "Office Supplies Inc", "Global Trading LLC"]
        items = [
            {"name": "Laptop", "unit_price": 1200.00},
            {"name": "Monitor", "unit_price": 300.00},
            {"name": "Keyboard", "unit_price": 80.00},
            {"name": "Mouse", "unit_price": 40.00}
        ]
        
        for i in range(100):
            po_number = f"PO-{random.randint(10000, 99999)}"
            vendor = random.choice(vendors)
            po_date = datetime.now() - timedelta(days=random.randint(1, 90))
            
            # Generate line items
            line_items = []
            for _ in range(random.randint(1, 4)):
                item = random.choice(items)
                quantity = random.randint(1, 10)
                line_items.append({
                    "item": item["name"],
                    "quantity": quantity,
                    "unit_price": item["unit_price"],
                    "total": quantity * item["unit_price"]
                })
            
            total_amount = sum(item["total"] for item in line_items)
            
            mock_pos[po_number] = {
                "po_number": po_number,
                "vendor": vendor,
                "date": po_date.strftime("%Y-%m-%d"),
                "line_items": line_items,
                "total_amount": total_amount,
                "currency": "USD",
                "status": "approved"
            }
        
        return mock_pos
    
    def _generate_mock_receipts(self) -> Dict[str, Dict]:
        """Generate mock goods receipts for existing POs"""
        mock_receipts = {}
        
        for po_number, po_data in self.purchase_orders.items():
            receipt_number = f"GR-{random.randint(10000, 99999)}"
            receipt_date = datetime.strptime(po_data["date"], "%Y-%m-%d") + timedelta(days=random.randint(1, 14))
            
            # Generate received items (might be partial delivery)
            received_items = []
            for item in po_data["line_items"]:
                received_qty = random.randint(0, item["quantity"])  # Might receive partial or full quantity
                if received_qty > 0:
                    received_items.append({
                        "item": item["item"],
                        "quantity_received": received_qty,
                        "quantity_ordered": item["quantity"]
                    })
            
            mock_receipts[receipt_number] = {
                "receipt_number": receipt_number,
                "po_number": po_number,
                "date": receipt_date.strftime("%Y-%m-%d"),
                "received_items": received_items,
                "status": "received"
            }
        
        return mock_receipts
    
    def get_purchase_order(self, po_number: str) -> Optional[Dict]:
        """Retrieve purchase order data"""
        return self.purchase_orders.get(po_number)
    
    def get_goods_receipt(self, po_number: str) -> Optional[Dict]:
        """Retrieve goods receipt data for a PO"""
        for receipt in self.goods_receipts.values():
            if receipt["po_number"] == po_number:
                return receipt
        return None
    
    def validate_invoice(self, invoice_data: Dict, po_number: str) -> Dict:
        """
        Perform 3-way matching between invoice, PO, and goods receipt
        Returns validation results with discrepancies if any
        """
        results = {
            "match_status": "no_match",
            "discrepancies": [],
            "po_match": False,
            "receipt_match": False,
            "amount_match": False
        }
        
        # Get PO and receipt data
        po_data = self.get_purchase_order(po_number)
        if not po_data:
            results["discrepancies"].append("PO not found in system")
            return results
        
        receipt_data = self.get_goods_receipt(po_number)
        if not receipt_data:
            results["discrepancies"].append("No goods receipt found for this PO")
            return results
        
        # Compare PO details
        if po_data["vendor"].lower() != invoice_data["vendor_name"].lower():
            results["discrepancies"].append(f"Vendor mismatch: PO: {po_data['vendor']} vs Invoice: {invoice_data['vendor_name']}")
        
        # Compare amounts
        po_amount = po_data["total_amount"]
        invoice_amount = float(invoice_data["total_amount"])
        if abs(po_amount - invoice_amount) > 0.01:  # Allow small difference due to floating point
            results["discrepancies"].append(f"Amount mismatch: PO: {po_amount} vs Invoice: {invoice_amount}")
        else:
            results["amount_match"] = True
        
        # Compare quantities with goods receipt
        received_quantities = {item["item"]: item["quantity_received"] for item in receipt_data["received_items"]}
        for item in invoice_data["line_items"]:
            if item["item"] in received_quantities:
                if item["quantity"] > received_quantities[item["item"]]:
                    results["discrepancies"].append(
                        f"Quantity mismatch for {item['item']}: Invoiced: {item['quantity']} vs Received: {received_quantities[item['item']]}"
                    )
        
        # Set overall match status
        if not results["discrepancies"]:
            results["match_status"] = "full_match"
            results["po_match"] = True
            results["receipt_match"] = True
        elif len(results["discrepancies"]) <= 2:  # Allow some minor discrepancies
            results["match_status"] = "partial_match"
            results["po_match"] = True
        
        return results 