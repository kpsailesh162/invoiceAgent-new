import requests
from typing import Dict, Any, AsyncGenerator
from datetime import datetime
import aiohttp
import tempfile
from pathlib import Path

class SAPIntegration(SourceIntegration):
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config['base_url']
        self.api_key = config['api_key']
        self.company_code = config['company_code']
        self.session = None
    
    async def connect(self) -> bool:
        try:
            self.session = aiohttp.ClientSession(
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
            )
            async with self.session.get(f"{self.base_url}/api/v1/connection_test") as response:
                return response.status == 200
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SAP: {str(e)}")
    
    async def fetch_invoices(self, since: datetime = None) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.session:
            await self.connect()
        
        params = {
            'company_code': self.company_code,
            'from_date': since.isoformat() if since else None
        }
        
        async with self.session.get(
            f"{self.base_url}/api/v1/invoices",
            params=params
        ) as response:
            if response.status == 200:
                invoices = await response.json()
                
                for invoice in invoices:
                    # Download invoice document
                    doc_path = await self._download_document(invoice['document_url'])
                    if doc_path:
                        yield {
                            'source': 'sap',
                            'invoice_id': invoice['id'],
                            'document_id': invoice['document_id'],
                            'vendor_id': invoice['vendor_id'],
                            'file_path': doc_path,
                            'file_type': 'pdf',
                            'metadata': invoice
                        }
    
    async def _download_document(self, url: str) -> str:
        async with self.session.get(url) as response:
            if response.status == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    tmp.write(await response.read())
                    return tmp.name
        return None
    
    async def mark_as_processed(self, invoice_id: str) -> bool:
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/invoices/{invoice_id}/process"
            ) as response:
                return response.status == 200
        except Exception:
            return False 