from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Invoice(BaseModel):
    workflow_id: str
    filename: str
    file_path: str
    status: InvoiceStatus
    upload_time: datetime
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class WorkflowResult(BaseModel):
    success: bool
    error_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None 