"""
Storage adapters for rate limiting.
"""

from .redis_storage import RedisStorage
from .memory_storage import MemoryStorage

__all__ = ['RedisStorage', 'MemoryStorage'] 