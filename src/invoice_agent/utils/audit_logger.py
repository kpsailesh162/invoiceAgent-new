import logging
from typing import Dict, Any, Optional
import asyncio

class AuditLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def log_event(
        self,
        event_type: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
        user_id: Optional[str] = None
    ):
        """Log an audit event"""
        try:
            event_data = {
                "event_type": event_type,
                "user_id": user_id,
                "data": data,
                "metadata": metadata
            }
            
            self.logger.log(level, f"Audit event: {event_data}")
            
        except Exception as e:
            self.logger.error(f"Error logging audit event: {str(e)}")
            raise
    
    async def log_workflow_event(
        self,
        workflow_id: str,
        event_type: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        """Log a workflow-specific audit event"""
        try:
            event_data = {
                "workflow_id": workflow_id,
                "event_type": event_type,
                "user_id": user_id,
                "data": data,
                "metadata": metadata
            }
            
            self.logger.info(f"Workflow event: {event_data}")
            
        except Exception as e:
            self.logger.error(f"Error logging workflow event: {str(e)}")
            raise
    
    async def log_data_access(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        """Log a data access event"""
        try:
            event_data = {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "user_id": user_id,
                "metadata": metadata
            }
            
            self.logger.info(f"Data access: {event_data}")
            
        except Exception as e:
            self.logger.error(f"Error logging data access: {str(e)}")
            raise

# Initialize global audit logger
audit_logger = AuditLogger() 