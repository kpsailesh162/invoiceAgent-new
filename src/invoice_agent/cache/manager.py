from typing import Any, Optional
import redis
from functools import wraps
import json
import pickle
from datetime import timedelta

class CacheManager:
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0
    ):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
    
    def cache(
        self,
        key_prefix: str,
        expire: timedelta = timedelta(minutes=5)
    ):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{key_prefix}:{self._generate_key(args, kwargs)}"
                
                # Try to get from cache
                cached_value = self.redis.get(cache_key)
                if cached_value:
                    return pickle.loads(cached_value)
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                self.redis.setex(
                    cache_key,
                    expire,
                    pickle.dumps(result)
                )
                return result
            return wrapper
        return decorator
    
    def _generate_key(self, args: tuple, kwargs: dict) -> str:
        """Generate a unique cache key based on function arguments"""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return ":".join(key_parts) 