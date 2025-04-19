"""
Sliding Window Rate Limiting Algorithm

The sliding window algorithm tracks requests in smaller time buckets and provides a 
weighted calculation across window boundaries. This prevents the "burst at the edge" 
problem that can occur with fixed window rate limiting.
"""

import time
from typing import Dict, Any, Tuple

from ..utils import get_interval_in_seconds


class SlidingWindow:
    """
    Implementation of the Sliding Window rate limiting algorithm.
    """
    
    def __init__(self, storage, options: Dict[str, Any] = None):
        """
        Initialize the Sliding Window algorithm with storage and options.
        
        Args:
            storage: Storage interface for persisting window state
            options: Configuration options
        """
        self.storage = storage
        self.options = options or {}
        
    async def check(self, identifier: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check if a request is allowed and update window counters.
        
        Args:
            identifier: Client identifier
            options: Rate limit options for this check
            
        Returns:
            Dict containing the check result and metadata
        """
        options = options or {}
        rate = options.get('rate', 60)
        interval = options.get('interval', 'minute')
        interval_seconds = get_interval_in_seconds(interval)
        
        now = int(time.time())
        current_window = now // interval_seconds * interval_seconds
        previous_window = current_window - interval_seconds
        
        current_window_key = f"sw:{identifier}:{current_window}"
        previous_window_key = f"sw:{identifier}:{previous_window}"
        
        # Get the current counts for both windows
        current_count, previous_count = await self._get_window_counts(
            current_window_key, previous_window_key)
        
        # Calculate window position (0 at start, 1 at end)
        window_position = (now % interval_seconds) / interval_seconds
        
        # Calculate weighted count using rolling window
        weighted_count = current_count + previous_count * (1 - window_position)
        
        allowed = weighted_count < rate
        
        if allowed:
            await self.storage.incr(current_window_key)
            # Store for 2x interval to ensure we keep previous window
            await self.storage.expire(current_window_key, interval_seconds * 2)
        
        remaining = max(0, int(rate - weighted_count - (1 if allowed else 0)))
        reset = interval_seconds - (now % interval_seconds)
        
        return {
            'allowed': allowed,
            'limit': rate,
            'remaining': remaining,
            'reset': reset,
            'retry_after': 0 if allowed else reset
        }
    
    async def _get_window_counts(self, current_key: str, previous_key: str) -> Tuple[int, int]:
        """
        Get the request counts for current and previous windows.
        
        Args:
            current_key: Redis/memory key for current window
            previous_key: Redis/memory key for previous window
            
        Returns:
            Tuple of (current_count, previous_count)
        """
        current_count = await self.storage.get(current_key)
        previous_count = await self.storage.get(previous_key)
        
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
            
        if previous_count is None:
            previous_count = 0
        else:
            previous_count = int(previous_count)
            
        return current_count, previous_count
    
    async def reset(self, identifier: str, options: Dict[str, Any] = None) -> bool:
        """
        Reset a window counter.
        
        Args:
            identifier: Client identifier
            options: Rate limit options
            
        Returns:
            Success indicator
        """
        options = options or {}
        interval = options.get('interval', self.options.get('interval', 'minute'))
        interval_seconds = get_interval_in_seconds(interval)
        
        now = int(time.time())
        current_window = now // interval_seconds * interval_seconds
        previous_window = current_window - interval_seconds
        
        current_window_key = f"sw:{identifier}:{current_window}"
        previous_window_key = f"sw:{identifier}:{previous_window}"
        
        await self.storage.set(current_window_key, "0")
        await self.storage.set(previous_window_key, "0")
        
        return True
    
    async def get_current_count(self, identifier: str) -> float:
        """
        Get the current count for an identifier.
        
        Args:
            identifier: Client identifier
            
        Returns:
            Current weighted count
        """
        interval = self.options.get('interval', 'minute')
        interval_seconds = get_interval_in_seconds(interval)
        
        now = int(time.time())
        current_window = now // interval_seconds * interval_seconds
        previous_window = current_window - interval_seconds
        
        current_window_key = f"sw:{identifier}:{current_window}"
        previous_window_key = f"sw:{identifier}:{previous_window}"
        
        current_count, previous_count = await self._get_window_counts(
            current_window_key, previous_window_key)
        
        window_position = (now % interval_seconds) / interval_seconds
        
        return current_count + previous_count * (1 - window_position) 