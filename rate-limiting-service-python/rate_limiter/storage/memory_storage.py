"""
In-memory storage adapter for rate limiting.
"""

from typing import Dict, Any, Optional, Union
import time
import asyncio
from collections import defaultdict


class MemoryStorage:
    """
    In-memory storage adapter for rate limiting.
    """
    
    def __init__(self, options: Dict[str, Any] = None):
        """
        Initialize memory storage adapter.
        
        Args:
            options: Storage options (unused for memory storage)
        """
        self.options = options or {}
        self._data = {}
        self._expirations = {}  # Map of key to expiration time
        
        # Start background task to clean expired keys
        self._setup_expiration_cleaner()
    
    def _setup_expiration_cleaner(self):
        """
        Set up background task to clean expired keys.
        """
        async def clean_expired_keys():
            while True:
                now = time.time()
                # Find expired keys
                expired_keys = [key for key, expires_at in self._expirations.items() 
                                if expires_at <= now]
                
                # Remove expired keys
                for key in expired_keys:
                    del self._data[key]
                    del self._expirations[key]
                
                # Sleep for 1 second
                await asyncio.sleep(1)
        
        # Schedule the background task
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(clean_expired_keys())
        except RuntimeError:
            # Handle case when there's no event loop
            pass
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from memory.
        
        Args:
            key: Storage key
            
        Returns:
            Value or None if not found
        """
        # Check if key exists and is not expired
        if key in self._data:
            if key in self._expirations and self._expirations[key] <= time.time():
                # Key is expired
                del self._data[key]
                del self._expirations[key]
                return None
            return self._data[key]
        return None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set a value in memory with optional expiration.
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time-to-live in seconds
            
        Returns:
            Success indicator
        """
        self._data[key] = value
        
        if ttl:
            self._expirations[key] = time.time() + ttl
        elif key in self._expirations:
            # Remove expiration if ttl is None
            del self._expirations[key]
            
        return True
    
    async def incr(self, key: str) -> int:
        """
        Increment a counter in memory.
        
        Args:
            key: Storage key
            
        Returns:
            New counter value
        """
        # Check if key exists
        value = await self.get(key)
        if value is None:
            value = "0"
        
        try:
            # Try to convert to int and increment
            new_value = int(value) + 1
            await self.set(key, str(new_value))
            return new_value
        except (ValueError, TypeError):
            # If value is not an integer, set to 1
            await self.set(key, "1")
            return 1
    
    async def expire(self, key: str, ttl: int) -> int:
        """
        Set expiration time on a key.
        
        Args:
            key: Storage key
            ttl: Time-to-live in seconds
            
        Returns:
            1 if the timeout was set, 0 if key doesn't exist
        """
        if key in self._data:
            self._expirations[key] = time.time() + ttl
            return 1
        return 0
    
    async def delete(self, key: str) -> int:
        """
        Delete a key from memory.
        
        Args:
            key: Storage key
            
        Returns:
            Number of keys removed
        """
        if key in self._data:
            del self._data[key]
            if key in self._expirations:
                del self._expirations[key]
            return 1
        return 0
    
    async def execute_lua(self, script: str, keys: list, args: list) -> Any:
        """
        Execute a Lua script (not supported in memory storage).
        
        Args:
            script: Lua script
            keys: List of keys
            args: List of arguments
            
        Returns:
            Script result
        """
        raise NotImplementedError("Lua scripts are not supported in memory storage")
    
    async def close(self):
        """
        Close the memory storage (no-op).
        """
        # Nothing to close for in-memory storage
        pass 