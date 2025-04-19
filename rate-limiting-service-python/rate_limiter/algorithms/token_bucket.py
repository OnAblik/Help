import time
from typing import Dict, Any, Optional, Tuple

from ..utils import get_interval_in_seconds


class TokenBucket:
    
    def __init__(self, storage, options: Dict[str, Any] = None):
        self.storage = storage
        self.options = options or {}
        
    async def check(self, identifier: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        options = options or {}
        rate = options.get('rate', 60)
        interval = options.get('interval', 'minute')
        interval_seconds = get_interval_in_seconds(interval)
        
        bucket_key = f"tb:{identifier}"
        last_update_key = f"tb:{identifier}:last"
        
        current_tokens, last_update = await self._get_bucket_state(bucket_key, last_update_key, rate)
        
        now = int(time.time() * 1000)
        elapsed_ms = now - last_update
        refill_rate = rate / interval_seconds
        refill_tokens = (elapsed_ms / 1000) * refill_rate
        
        new_tokens = min(current_tokens + refill_tokens, rate)
        
        allowed = new_tokens >= 1
        if allowed:
            new_tokens -= 1
            
        await self._store_bucket_state(bucket_key, last_update_key, new_tokens, now, interval_seconds)
        
        ms_until_refill = ((rate - new_tokens) / refill_rate) * 1000 if allowed else ((1 - new_tokens) / refill_rate) * 1000
        
        return {
            'allowed': allowed,
            'limit': rate,
            'remaining': int(new_tokens),
            'reset': int(ms_until_refill / 1000),
            'retry_after': 0 if allowed else int(ms_until_refill / 1000)
        }
    
    async def _get_bucket_state(self, bucket_key: str, last_update_key: str, rate: int) -> Tuple[float, int]:
        current_tokens = await self.storage.get(bucket_key)
        last_update = await self.storage.get(last_update_key)
        
        if current_tokens is None:
            current_tokens = float(rate)
        else:
            current_tokens = float(current_tokens)
            
        if last_update is None:
            last_update = int(time.time() * 1000)
        else:
            last_update = int(last_update)
            
        return current_tokens, last_update
    
    async def _store_bucket_state(self, bucket_key: str, last_update_key: str, 
                                 tokens: float, update_time: int, ttl: int) -> None:
        await self.storage.set(bucket_key, str(tokens), ttl)
        await self.storage.set(last_update_key, str(update_time), ttl)
    
    async def reset(self, identifier: str, options: Dict[str, Any] = None) -> bool:
        options = options or {}
        rate = options.get('rate', 60)
        
        bucket_key = f"tb:{identifier}"
        last_update_key = f"tb:{identifier}:last"
        
        await self.storage.set(bucket_key, str(rate))
        await self.storage.set(last_update_key, str(int(time.time() * 1000)))
        
        return True