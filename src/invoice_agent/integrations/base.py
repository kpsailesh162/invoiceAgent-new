from abc import ABC, abstractmethod
from typing import Dict, Any, List, AsyncGenerator, Optional
from datetime import datetime
import aiohttp
import asyncio
import logging
from pathlib import Path
import tempfile
import hashlib
from ..core.data_model import Invoice

class SourceIntegrationError(Exception):
    """Base exception for source integration errors"""
    pass

class AuthenticationError(SourceIntegrationError):
    """Authentication related errors"""
    pass

class RateLimitError(SourceIntegrationError):
    """Rate limit exceeded errors"""
    pass

class SourceIntegration(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(
            max_requests=config.get('rate_limit', {}).get('max_requests', 100),
            time_window=config.get('rate_limit', {}).get('time_window', 60)
        )
        
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
    
    @abstractmethod
    async def connect(self):
        """Establish connection to the source"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to the source"""
        pass
    
    @abstractmethod
    async def fetch_invoices(
        self,
        since: Optional[datetime] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch invoices from the source"""
        pass
    
    @abstractmethod
    async def mark_as_processed(self, invoice_id: str):
        """Mark invoice as processed in the source"""
        pass
    
    async def download_attachment(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Path:
        """Download attachment to temporary file"""
        try:
            async with self.rate_limiter:
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                async with self.session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    content = await response.read()
                    
                    # Create temp file with unique name
                    file_hash = hashlib.md5(content).hexdigest()
                    temp_dir = Path(tempfile.gettempdir())
                    temp_file = temp_dir / f"invoice_{file_hash}"
                    
                    # Save content
                    temp_file.write_bytes(content)
                    return temp_file
                    
        except aiohttp.ClientError as e:
            raise SourceIntegrationError(f"Failed to download attachment: {str(e)}")

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        async with self._lock:
            await self._wait_if_needed()
            self._add_request()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def _wait_if_needed(self):
        """Wait if rate limit is exceeded"""
        now = datetime.now()
        self.requests = [
            ts for ts in self.requests
            if (now - ts).total_seconds() < self.time_window
        ]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = (
                self.requests[0] +
                datetime.timedelta(seconds=self.time_window) -
                now
            ).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    def _add_request(self):
        """Add new request timestamp"""
        self.requests.append(datetime.now()) 