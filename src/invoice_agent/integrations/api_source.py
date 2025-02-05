from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime
import aiohttp
import asyncio
import jwt
import json
from .base import (
    SourceIntegration,
    SourceIntegrationError,
    AuthenticationError,
    RateLimitError
)

class APISourceIntegration(SourceIntegration):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config['base_url']
        self.auth_token = None
        self.token_expiry = None
    
    async def connect(self):
        """Connect to API and authenticate"""
        try:
            self.session = aiohttp.ClientSession(
                base_url=self.base_url,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            await self._authenticate()
            
        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Failed to connect to API: {str(e)}")
    
    async def disconnect(self):
        """Close API connection"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_invoices(
        self,
        since: Optional[datetime] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch invoices from API"""
        try:
            # Check token expiry
            if self._should_refresh_token():
                await self._authenticate()
            
            # Build query parameters
            params = {}
            if since:
                params['since'] = since.isoformat()
            
            async with self.rate_limiter:
                async with self.session.get(
                    '/invoices',
                    params=params,
                    headers=self._get_headers()
                ) as response:
                    if response.status == 429:
                        raise RateLimitError("API rate limit exceeded")
                    
                    response.raise_for_status()
                    data = await response.json()
                    
                    for invoice in data['invoices']:
                        # Download attachments if any
                        if 'attachment_url' in invoice:
                            file_path = await self.download_attachment(
                                invoice['attachment_url'],
                                headers=self._get_headers()
                            )
                            invoice['file_path'] = str(file_path)
                        
                        yield invoice
                        
        except aiohttp.ClientError as e:
            raise SourceIntegrationError(f"Failed to fetch invoices: {str(e)}")
    
    async def mark_as_processed(self, invoice_id: str):
        """Mark invoice as processed in API"""
        try:
            async with self.rate_limiter:
                async with self.session.post(
                    f'/invoices/{invoice_id}/process',
                    headers=self._get_headers()
                ) as response:
                    response.raise_for_status()
                    
        except aiohttp.ClientError as e:
            raise SourceIntegrationError(
                f"Failed to mark invoice as processed: {str(e)}"
            )
    
    async def _authenticate(self):
        """Authenticate with API"""
        try:
            auth_data = {
                'client_id': self.config['client_id'],
                'client_secret': self.config['client_secret']
            }
            
            async with self.session.post(
                '/auth/token',
                json=auth_data
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                self.auth_token = data['access_token']
                self.token_expiry = datetime.now() + datetime.timedelta(
                    seconds=data['expires_in']
                )
                
        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    def _should_refresh_token(self) -> bool:
        """Check if token needs refresh"""
        if not self.auth_token or not self.token_expiry:
            return True
        
        # Refresh if token expires in less than 5 minutes
        return datetime.now() + datetime.timedelta(minutes=5) >= self.token_expiry
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        } 