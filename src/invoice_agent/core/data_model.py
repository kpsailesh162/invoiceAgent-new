from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

@dataclass
class VendorInfo:
    id: str
    name: str
    email: str
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['VendorInfo']:
        """Create VendorInfo instance from dictionary"""
        if not data:
            return None
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            email=data.get('email', '')
        )

@dataclass
class LineItem:
    sku: str
    description: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LineItem':
        """Create LineItem instance from dictionary"""
        return cls(
            sku=data.get('sku', ''),
            description=data.get('description', ''),
            quantity=int(data.get('quantity', 0)),
            unit_price=Decimal(str(data.get('unit_price', '0'))),
            total=Decimal(str(data.get('total', '0')))
        )

@dataclass
class Invoice:
    invoice_number: str
    file_path: str
    invoice_date: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    vendor_info: Optional[VendorInfo] = None
    po_number: Optional[str] = None
    total_amount: Decimal = Decimal('0')
    currency: str = 'USD'
    status: str = 'new'
    line_items: List[LineItem] = field(default_factory=list)
    additional_fields: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def vendor_id(self) -> Optional[str]:
        """Get vendor ID"""
        return self.vendor_info.id if self.vendor_info else None
    
    @property
    def vendor_name(self) -> Optional[str]:
        """Get vendor name"""
        return self.vendor_info.name if self.vendor_info else None
    
    @property
    def vendor_email(self) -> Optional[str]:
        """Get vendor email"""
        return self.vendor_info.email if self.vendor_info else None
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update invoice with extracted data"""
        for key, value in data.items():
            if key == 'line_items' and isinstance(value, list):
                self.line_items = [
                    LineItem.from_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif key == 'vendor_info':
                self.vendor_info = VendorInfo.from_dict(value)
            elif key == 'invoice_date' and isinstance(value, str):
                self.invoice_date = datetime.fromisoformat(value)
            elif key == 'due_date' and isinstance(value, str):
                self.due_date = datetime.fromisoformat(value)
            elif key == 'total_amount':
                self.total_amount = Decimal(str(value))
            elif hasattr(self, key):
                setattr(self, key, value)
            else:
                self.additional_fields[key] = value
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Invoice':
        """Create Invoice instance from dictionary"""
        return cls(
            invoice_number=data['invoice_number'],
            file_path=data['file_path'],
            invoice_date=datetime.fromisoformat(data['invoice_date']) if 'invoice_date' in data else datetime.now(),
            due_date=datetime.fromisoformat(data['due_date']) if 'due_date' in data else None,
            vendor_info=VendorInfo.from_dict(data.get('vendor_info')),
            po_number=data.get('po_number'),
            total_amount=Decimal(str(data.get('total_amount', '0'))),
            currency=data.get('currency', 'USD'),
            status=data.get('status', 'new'),
            line_items=[LineItem.from_dict(item) for item in data.get('line_items', [])],
            additional_fields=data.get('additional_fields', {})
        )

    def to_json(self) -> str:
        """Convert invoice to JSON string"""
        import json
        
        def default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, (Invoice, VendorInfo, LineItem)):
                return obj.__dict__
            return str(obj)
        
        return json.dumps(self, default=default, indent=2) 