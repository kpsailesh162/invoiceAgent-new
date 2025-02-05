from typing import Optional, Callable, Dict, Any
import time
import redis
from functools import wraps
from datetime import datetime
import json
from ..config.enterprise_config import EnterpriseConfig

class RateLimiter:
    """Enterprise rate limiting with Redis backend."""
    
    def __init__(
        self,
        redis_url: str,
        config: EnterpriseConfig,
        default_limit: int = 60,
        default_window: int = 60
    ):
        self.redis = redis.from_url(redis_url)
        self.config = config
        self.default_limit = default_limit
        self.default_window = default_window
    
    def get_limit_key(self, tenant_id: str, user_id: str, action: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"rate_limit:{tenant_id}:{user_id}:{action}"
    
    def is_allowed(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> bool:
        """Check if action is allowed under rate limits."""
        key = self.get_limit_key(tenant_id, user_id, action)
        
        # Get tenant-specific limits
        if limit is None:
            limit = self.config.get_rate_limit(
                tenant_id,
                f"{action}_per_minute"
            ) or self.default_limit
        
        window = window or self.default_window
        now = int(time.time())
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Clean up old entries
        pipe.zremrangebyscore(key, 0, now - window)
        
        # Count recent requests
        pipe.zcard(key)
        
        # Add new request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry on the key
        pipe.expire(key, window)
        
        # Execute pipeline
        _, current_count, *_ = pipe.execute()
        
        return current_count < limit
    
    def get_remaining(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get remaining rate limit information."""
        key = self.get_limit_key(tenant_id, user_id, action)
        
        if limit is None:
            limit = self.config.get_rate_limit(
                tenant_id,
                f"{action}_per_minute"
            ) or self.default_limit
        
        window = window or self.default_window
        now = int(time.time())
        
        # Use pipeline for atomic operations
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        _, current_count = pipe.execute()
        
        reset_time = now + window
        
        return {
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "reset": reset_time,
            "window": window
        }

def rate_limit(
    action: str,
    limit: Optional[int] = None,
    window: Optional[int] = None
):
    """Decorator for rate limiting functions."""
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get rate limiter instance
            rate_limiter = kwargs.get('rate_limiter')
            if not rate_limiter:
                raise ValueError("Rate limiter instance required")
            
            # Get tenant and user info
            tenant_id = kwargs.get('tenant_id')
            user_id = kwargs.get('user_id')
            
            if not tenant_id or not user_id:
                raise ValueError("tenant_id and user_id required for rate limiting")
            
            # Check rate limit
            if not rate_limiter.is_allowed(tenant_id, user_id, action, limit, window):
                remaining = rate_limiter.get_remaining(tenant_id, user_id, action, limit, window)
                raise RateLimitExceeded(
                    action=action,
                    limit=remaining["limit"],
                    reset=remaining["reset"]
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, action: str, limit: int, reset: int):
        self.action = action
        self.limit = limit
        self.reset = reset
        self.message = (
            f"Rate limit exceeded for action '{action}'. "
            f"Limit is {limit} requests. "
            f"Resets at {datetime.fromtimestamp(reset).isoformat()}"
        )
        super().__init__(self.message) 