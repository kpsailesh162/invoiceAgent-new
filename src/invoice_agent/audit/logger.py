from typing import Dict, Any, Optional
import logging
from datetime import datetime
import json
from pathlib import Path
import asyncio
import aiofiles
from ..core.data_model import Invoice

class AuditLogger:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.audit_dir = Path(config['audit']['directory'])
        self.audit_dir.mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def log_event(
        self,
        event_type: str,
        invoice: Invoice,
        details: Dict[str, Any],
        user: Optional[str] = None
    ):
        """Log audit event"""
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'invoice_number': invoice.invoice_number,
                'vendor_name': invoice.vendor_name,
                'amount': str(invoice.total_amount),
                'currency': invoice.currency,
                'user': user or 'system',
                'details': details
            }
            
            # Write to audit log file
            async with aiofiles.open(
                self.audit_dir / f"{datetime.now():%Y-%m-%d}.jsonl",
                'a'
            ) as f:
                await f.write(json.dumps(event) + '\n')
            
            # If configured, send to external audit system
            if self.config['audit'].get('external_system'):
                await self._send_to_external_system(event)
                
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {str(e)}")
    
    async def _send_to_external_system(self, event: Dict[str, Any]):
        """Send audit event to external system"""
        try:
            # Implement external system integration
            pass
        except Exception as e:
            self.logger.error(
                f"Failed to send audit event to external system: {str(e)}"
            ) 