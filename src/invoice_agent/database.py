from typing import List, Dict, Any, Optional
import asyncpg
from datetime import datetime

from .models import Invoice, InvoiceStatus, WorkflowStatus

class Database:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pool = None
    
    async def connect(self):
        """Create database connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(**self.config)
            
            # Create tables if they don't exist
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS invoices (
                        workflow_id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        status TEXT NOT NULL,
                        upload_time TIMESTAMP NOT NULL,
                        error_message TEXT,
                        metadata JSONB
                    )
                ''')
    
    async def create_invoice_entry(self, invoice_data: Dict[str, Any]) -> None:
        """Create a new invoice entry"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO invoices (
                    workflow_id, filename, file_path, status, 
                    upload_time, error_message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''', invoice_data['workflow_id'],
                invoice_data['filename'],
                invoice_data['file_path'],
                invoice_data['status'].value,
                invoice_data['upload_time'],
                invoice_data.get('error_message'),
                invoice_data.get('metadata'))
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """Get the status of a workflow"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                'SELECT status, error_message FROM invoices WHERE workflow_id = $1',
                workflow_id
            )
            
            if record:
                return WorkflowStatus(record['status'])
            return None
    
    async def update_workflow_status(
        self, 
        workflow_id: str, 
        status: WorkflowStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update the status of a workflow"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE invoices 
                SET status = $1, error_message = $2
                WHERE workflow_id = $3
            ''', status.value, error_message, workflow_id)
    
    async def get_invoices_by_status(self, status: InvoiceStatus) -> List[Invoice]:
        """Get all invoices with a specific status"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                'SELECT * FROM invoices WHERE status = $1',
                status.value
            )
            
            return [
                Invoice(
                    workflow_id=r['workflow_id'],
                    filename=r['filename'],
                    file_path=r['file_path'],
                    status=InvoiceStatus(r['status']),
                    upload_time=r['upload_time'],
                    error_message=r['error_message'],
                    metadata=r['metadata']
                )
                for r in records
            ]
    
    async def get_all_invoices(self) -> List[Invoice]:
        """Get all invoices"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            records = await conn.fetch('SELECT * FROM invoices ORDER BY upload_time DESC')
            
            return [
                Invoice(
                    workflow_id=r['workflow_id'],
                    filename=r['filename'],
                    file_path=r['file_path'],
                    status=InvoiceStatus(r['status']),
                    upload_time=r['upload_time'],
                    error_message=r['error_message'],
                    metadata=r['metadata']
                )
                for r in records
            ] 