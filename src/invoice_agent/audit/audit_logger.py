from typing import Any, Dict, Optional
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading
from queue import Queue
import uuid
from ..config.settings import config

class AuditLogger:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.log_dir = config.LOG_DIR / "audit"
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Set up file handler
            self.file_handler = logging.FileHandler(
                self.log_dir / f"audit_{datetime.now().strftime('%Y%m')}.log"
            )
            self.file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(levelname)s - %(message)s'
                )
            )
            
            # Set up logger
            self.logger = logging.getLogger("audit")
            self.logger.setLevel(logging.INFO)
            self.logger.addHandler(self.file_handler)
            
            # Initialize async logging queue
            self.log_queue = Queue()
            self.async_thread = threading.Thread(target=self._process_log_queue, daemon=True)
            self.async_thread.start()
            
            self.initialized = True
    
    def _process_log_queue(self):
        """Process logs asynchronously"""
        while True:
            log_entry = self.log_queue.get()
            if log_entry is None:
                break
            
            level, event_type, details = log_entry
            self._write_log(level, event_type, details)
    
    def _write_log(self, level: int, event_type: str, details: Dict[str, Any]):
        """Write log entry"""
        try:
            # Add metadata
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "environment": config.environment,
                **details
            }
            
            # Mask sensitive data
            self._mask_sensitive_data(log_data)
            
            # Write to log file
            self.logger.log(
                level,
                json.dumps(log_data, default=str)
            )
            
            # Write to separate file for critical events
            if level >= logging.ERROR:
                self._write_critical_event(log_data)
        
        except Exception as e:
            # Fallback logging for logging failures
            self.logger.error(f"Logging failure: {str(e)}")
    
    def _write_critical_event(self, log_data: Dict):
        """Write critical events to separate file"""
        critical_log_path = self.log_dir / "critical_events.log"
        try:
            with open(critical_log_path, "a") as f:
                f.write(json.dumps(log_data, default=str) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write critical event: {str(e)}")
    
    def _mask_sensitive_data(self, data: Dict):
        """Mask sensitive fields in log data"""
        sensitive_fields = config.security.SENSITIVE_FIELDS
        
        def mask_value(value: str) -> str:
            if len(value) <= 4:
                return "*" * len(value)
            return value[:4] + "*" * (len(value) - 4)
        
        def recursive_mask(obj: Any):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in sensitive_fields and isinstance(value, str):
                        obj[key] = mask_value(value)
                    else:
                        recursive_mask(value)
            elif isinstance(obj, list):
                for item in obj:
                    recursive_mask(item)
        
        recursive_mask(data)
    
    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        level: int = logging.INFO,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """Log an audit event"""
        if not config.security.AUDIT_LOGGING_ENABLED:
            return
        
        log_details = {
            "user_id": user_id,
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "details": details
        }
        
        # Add to async queue
        self.log_queue.put((level, event_type, log_details))
    
    def log_security_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log security-related events"""
        self.log_event(
            event_type,
            details,
            level=logging.WARNING,
            user_id=user_id
        )
    
    def log_data_access(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        user_id: str,
        details: Optional[Dict] = None
    ):
        """Log data access events"""
        self.log_event(
            "data_access",
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                **(details or {})
            },
            user_id=user_id
        )
    
    def log_workflow_event(
        self,
        workflow_id: str,
        status: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log workflow state changes"""
        self.log_event(
            "workflow_state_change",
            {
                "workflow_id": workflow_id,
                "status": status,
                **details
            },
            user_id=user_id
        )
    
    def cleanup_old_logs(self):
        """Clean up logs older than retention period"""
        retention_days = config.security.DATA_RETENTION_DAYS
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for log_file in self.log_dir.glob("audit_*.log"):
            try:
                file_date = datetime.strptime(log_file.stem[6:], "%Y%m")
                if file_date < cutoff_date:
                    log_file.unlink()
            except Exception as e:
                self.logger.error(f"Failed to cleanup log file {log_file}: {str(e)}")

# Initialize audit logger
audit_logger = AuditLogger() 