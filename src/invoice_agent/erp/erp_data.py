from pathlib import Path
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class ERPMockData:
    def __init__(self):
        self.data_dir = Path("src/invoice_agent/erp/mock_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.vendors: List[dict] = []
        self.purchase_orders: List[dict] = []
        self.goods_receipts: List[dict] = []
        
        self._generate_master_data()
    
    def _generate_master_data(self):
        """Generate all master data"""
        self._generate_vendors()
        self._generate_purchase_orders()
        self._generate_goods_receipts()
        
        # Save all data to files
        self._save_data()
    
    def _generate_vendors(self):
        """Generate vendor master data"""
        vendor_names = [
            "Tech Solutions Inc.",
            "Global Supply Co.",
            "Office Essentials Ltd.",
            "Industrial Parts Corp.",
            "Digital Systems LLC",
            "Hardware Wholesale Inc.",
            "Software Solutions Pro",
            "Electronics Depot Corp.",
            "Manufacturing Supplies Co.",
            "IT Equipment Direct"
        ]
        
        for i, name in enumerate(vendor_names, 1):
            vendor = {
                "id": f"V{i:03d}",
                "name": name,
                "tax_id": f"TAX{random.randint(100000, 999999)}",
                "payment_terms": random.choice(["Net 30", "Net 45", "2% 10 Net 30"]),
                "currency": "USD",
                "status": "active",
                "contact": {
                    "email": f"accounts@{name.lower().replace(' ', '')}.com",
                    "phone": f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
                }
            }
            self.vendors.append(vendor)
    
    def _generate_purchase_orders(self):
        """Generate purchase order data"""
        items_catalog = [
            {"description": "Desktop Computer", "unit_price": 899.99},
            {"description": "Laptop", "unit_price": 1299.99},
            {"description": "Monitor", "unit_price": 299.99},
            {"description": "Keyboard", "unit_price": 79.99},
            {"description": "Mouse", "unit_price": 49.99},
            {"description": "Docking Station", "unit_price": 199.99},
            {"description": "Printer", "unit_price": 399.99},
            {"description": "Network Switch", "unit_price": 299.99},
            {"description": "Server Rack", "unit_price": 899.99},
            {"description": "UPS Battery", "unit_price": 599.99}
        ]
        
        start_date = datetime(2023, 1, 1)
        for i in range(1, 51):  # Generate 50 POs
            po_date = start_date + timedelta(days=random.randint(0, 364))
            vendor = random.choice(self.vendors)
            
            # Generate 1-5 items for this PO
            num_items = random.randint(1, 5)
            items = []
            subtotal = 0
            
            for _ in range(num_items):
                item = random.choice(items_catalog).copy()
                item["quantity"] = random.randint(1, 10)
                item["total"] = round(item["quantity"] * item["unit_price"], 2)
                items.append(item)
                subtotal += item["total"]
            
            tax_amount = round(subtotal * 0.1, 2)  # 10% tax
            total_amount = subtotal + tax_amount
            
            po = {
                "po_number": f"PO{i:04d}",
                "vendor_info": {
                    "id": vendor["id"],
                    "name": vendor["name"]
                },
                "order_date": po_date.strftime("%Y-%m-%d"),
                "items": items,
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
                "currency": vendor["currency"],
                "status": random.choice(["completed", "completed", "completed", "pending", "cancelled"]),
                "payment_terms": vendor["payment_terms"]
            }
            
            self.purchase_orders.append(po)
    
    def _generate_goods_receipts(self):
        """Generate goods receipt data for completed POs"""
        for po in self.purchase_orders:
            if po["status"] == "completed":
                po_date = datetime.strptime(po["order_date"], "%Y-%m-%d")
                receipt_date = po_date + timedelta(days=random.randint(1, 10))
                
                gr = {
                    "gr_number": f"GR{po['po_number'][2:]}",
                    "po_number": po["po_number"],
                    "vendor_info": po["vendor_info"].copy(),
                    "receipt_date": receipt_date.strftime("%Y-%m-%d"),
                    "items": []
                }
                
                # Generate received quantities (might be partial)
                for po_item in po["items"]:
                    received_qty = po_item["quantity"]
                    if random.random() < 0.1:  # 10% chance of partial delivery
                        received_qty = round(received_qty * random.uniform(0.8, 0.95))
                    
                    gr_item = {
                        "description": po_item["description"],
                        "ordered_quantity": po_item["quantity"],
                        "received_quantity": received_qty,
                        "unit_price": po_item["unit_price"]
                    }
                    gr["items"].append(gr_item)
                
                self.goods_receipts.append(gr)
    
    def _save_data(self):
        """Save all generated data to JSON files"""
        data_files = {
            "vendors.json": self.vendors,
            "purchase_orders.json": self.purchase_orders,
            "goods_receipts.json": self.goods_receipts
        }
        
        for filename, data in data_files.items():
            with open(self.data_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
    
    def get_vendor_by_id(self, vendor_id: str) -> Optional[dict]:
        """Get vendor by ID"""
        for vendor in self.vendors:
            if vendor["id"] == vendor_id:
                return vendor
        return None
    
    def get_po_by_number(self, po_number: str) -> Optional[dict]:
        """Get purchase order by number"""
        for po in self.purchase_orders:
            if po["po_number"] == po_number:
                return po
        return None
    
    def get_gr_by_po_number(self, po_number: str) -> Optional[dict]:
        """Get goods receipt by PO number"""
        for gr in self.goods_receipts:
            if gr["po_number"] == po_number:
                return gr
        return None
    
    def get_gr_by_number(self, gr_number: str) -> Optional[dict]:
        """Get goods receipt by GR number"""
        for gr in self.goods_receipts:
            if gr["gr_number"] == gr_number:
                return gr
        return None

# Create a singleton instance
erp_mock_data = ERPMockData() 