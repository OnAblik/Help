"""
Redis storage adapter for rate limiting.
"""

from typing import Dict, Any, Optional, Union
import aioredis


class RedisStorage:
    """
    Redis storage adapter for rate limiting.
    """
    
    def __init__(self, options: Dict[str, Any] = None):
        """
        Initialize Redis storage adapter.
        
        Args:
            options: Redis connection options
        """
        self.options = options or {}
        self.redis = None
        self.connected = False
        
    async def connect(self):
        """
        Connect to Redis server.
        """
        if self.connected:
            return
        
        host = self.options.get('host', 'localhost')
        port = self.options.get('port', 6379)
        password = self.options.get('password')
        db = self.options.get('db', 0)
        
        connection_string = f"redis://"
        
        if password:
            connection_string += f":{password}@"
            
        connection_string += f"{host}:{port}/{db}"
        
        self.redis = await aioredis.from_url(
            connection_string,
            encoding="utf-8",
            decode_responses=True
        )
        
        self.connected = True
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis.
        
        Args:
            key: Redis key
            
        Returns:
            Value or None if not found
        """
        if not self.connected:
            await self.connect()
            
        key_prefix = self.options.get('key_prefix', '')
        prefixed_key = f"{key_prefix}{key}"
        
        return await self.redis.get(prefixed_key)
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set a value in Redis with optional expiration.
        
        Args:
            key: Redis key
            value: Value to store
            ttl: Time-to-live in seconds
            
        Returns:
            Success indicator
        """
        if not self.connected:
            await self.connect()
            
        key_prefix = self.options.get('key_prefix', '')
        prefixed_key = f"{key_prefix}{key}"
        
        if ttl:
            await self.redis.setex(prefixed_key, ttl, value)
        else:
            await self.redis.set(prefixed_key, value)
            
        return True
    
    async def incr(self, key: str) -> int:
        """
        Increment a counter in Redis.
        
        Args:
            key: Redis key
            
        Returns:
            New counter value
        """
        if not self.connected:
            await self.connect()
            
        key_prefix = self.options.get('key_prefix', '')
        prefixed_key = f"{key_prefix}{key}"
        
        return await self.redis.incr(prefixed_key)
    
    async def expire(self, key: str, ttl: int) -> int:
        """
        Set expiration time on a key.
        
        Args:
            key: Redis key
            ttl: Time-to-live in seconds
            
        Returns:
            1 if the timeout was set, 0 if key doesn't exist
        """
        if not self.connected:
            await self.connect()
            
        key_prefix = self.options.get('key_prefix', '')
        prefixed_key = f"{key_prefix}{key}"
        
        return await self.redis.expire(prefixed_key, ttl)
    
    async def delete(self, key: str) -> int:
        """
        Delete a key from Redis.
        
        Args:
            key: Redis key
            
        Returns:
            Number of keys removed
        """
        if not self.connected:
            await self.connect()
            
        key_prefix = self.options.get('key_prefix', '')
        prefixed_key = f"{key_prefix}{key}"
        
        return await self.redis.delete(prefixed_key)
    
    async def execute_lua(self, script: str, keys: list, args: list) -> Any:
        """
        Execute a Lua script.
        
        Args:
            script: Lua script
            keys: List of keys
            args: List of arguments
            
        Returns:
            Script result
        """
        if not self.connected:
            await self.connect()
            
        # Add prefix to keys
        key_prefix = self.options.get('key_prefix', '')
        prefixed_keys = [f"{key_prefix}{key}" for key in keys]
        
        # Create a script object
        script_obj = self.redis.register_script(script)
        
        return await script_obj(keys=prefixed_keys, args=args)
    
    async def close(self):
        """
        Close the Redis connection.
        """
        if self.connected and self.redis:
            await self.redis.close()
            self.connected = False 