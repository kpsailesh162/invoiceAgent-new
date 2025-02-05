from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.data_model import Invoice

class BaseConnector(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def export_invoice(self, invoice: Invoice) -> bool:
        pass
    
    @abstractmethod
    def get_status(self, invoice_id: str) -> Dict[str, Any]:
        pass 