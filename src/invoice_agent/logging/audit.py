import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, JSON
from ..database.models import Base

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String(50))
    user_id = Column(String(50))
    resource_type = Column(String(50))
    resource_id = Column(String(50))
    changes = Column(JSON)
    ip_address = Column(String(50))

class AuditLogger:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def log_action(
        self,
        action: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any] = None,
        ip_address: str = None
    ):
        try:
            audit_log = AuditLog(
                action=action,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                changes=changes,
                ip_address=ip_address
            )
            
            self.session.add(audit_log)
            self.session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to create audit log: {str(e)}")
            self.session.rollback()
            raise 