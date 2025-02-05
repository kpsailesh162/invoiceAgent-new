from fastapi import Request, HTTPException
import time
from collections import defaultdict
from typing import Dict, Tuple
import asyncio

class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 100,
        burst_size: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.requests: Dict[str, list] = defaultdict(list)
        self._cleanup_task = asyncio.create_task(self._cleanup_old_requests())
    
    async def check_rate_limit(self, request: Request):
        client_ip = request.client.host
        current_time = time.time()
        
        # Remove old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests"
            )
        
        self.requests[client_ip].append(current_time)
    
    async def _cleanup_old_requests(self):
        while True:
            await asyncio.sleep(60)
            current_time = time.time()
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    req_time for req_time in self.requests[ip]
                    if current_time - req_time < 60
                ]
                if not self.requests[ip]:
                    del self.requests[ip] 