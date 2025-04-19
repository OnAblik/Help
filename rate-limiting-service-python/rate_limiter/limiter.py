"""
Main rate limiter implementation.
"""

from typing import Dict, Any, Optional, Union, Callable
import inspect
import functools
import json
import os

from .algorithms import TokenBucket, SlidingWindow
from .storage import RedisStorage, MemoryStorage
from .utils import (
    normalize_client_info,
    normalize_config,
    format_error_response,
    load_config_from_file
)


class RateLimiter:
    """
    Main rate limiter class that provides the core functionality.
    """
    
    def __init__(self, options: Dict[str, Any] = None):
        """
        Initialize the rate limiter with configuration.
        
        Args:
            options: Configuration options
        """
        self.options = options or {}
        self._setup_storage()
        self._setup_algorithms()
        self.metrics = {
            'requests_total': 0,
            'throttled_total': 0
        }
    
    def _setup_storage(self):
        """
        Set up the appropriate storage backend.
        """
        storage_type = self.options.get('storage', {}).get('type', 'memory')
        storage_options = self.options.get('storage', {}).get('options', {})
        
        if storage_type == 'redis':
            self.storage = RedisStorage(storage_options)
        else:
            # Default to in-memory storage
            self.storage = MemoryStorage(storage_options)
    
    def _setup_algorithms(self):
        """
        Initialize rate limiting algorithms.
        """
        self.algorithms = {
            'token_bucket': TokenBucket(self.storage, self.options),
            'sliding_window': SlidingWindow(self.storage, self.options)
        }
        
        # Default algorithm
        self.algorithm = self.options.get('algorithm', 'token_bucket')
    
    def get_client_identifier(self, request) -> str:
        """
        Get client identifier based on request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Client identifier string
        """
        client_info = normalize_client_info(request)
        
        # Check for user ID in authenticated requests
        user_id = client_info.get('user_id')
        if user_id and self.options.get('client_identifier') == 'user_id':
            return f"user:{user_id}"
        
        # Check for API key
        api_key = client_info.get('api_key')
        if api_key:
            return f"apikey:{api_key}"
        
        # Fall back to IP address
        ip = client_info.get('ip', 'unknown')
        return f"ip:{ip}"
    
    async def check(self, request, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check if a request is allowed based on rate limits.
        
        Args:
            request: HTTP request object
            options: Optional rate limit options
            
        Returns:
            Rate limit check result
        """
        self.metrics['requests_total'] += 1
        
        # Get client identifier
        identifier = self.get_client_identifier(request)
        
        # Get request path
        client_info = normalize_client_info(request)
        path = client_info.get('path', '/')
        
        # Check for endpoint-specific override
        endpoint_overrides = self.options.get('endpoint_overrides', {})
        effective_options = endpoint_overrides.get(path, options or self.options)
        
        # Select algorithm and perform check
        result = None
        if self.algorithm == 'sliding_window':
            result = await self.algorithms['sliding_window'].check(identifier, effective_options)
        else:
            # Default to token bucket
            result = await self.algorithms['token_bucket'].check(identifier, effective_options)
        
        if not result['allowed']:
            self.metrics['throttled_total'] += 1
        
        return result
    
    async def reset(self, identifier: str, options: Dict[str, Any] = None) -> bool:
        """
        Reset rate limit for a client.
        
        Args:
            identifier: Client identifier
            options: Optional rate limit options
            
        Returns:
            Success indicator
        """
        algorithm_name = (options or {}).get('algorithm', self.algorithm)
        return await self.algorithms[algorithm_name].reset(identifier, options)
    
    def limit(self, rate: Optional[int] = None, interval: Optional[str] = None) -> Callable:
        """
        Create a rate limiting decorator/middleware.
        
        Args:
            rate: Request rate (requests per interval)
            interval: Time interval
            
        Returns:
            Decorator function
        """
        options = {}
        if rate is not None:
            options['rate'] = rate
        if interval is not None:
            options['interval'] = interval
        
        def decorator(func_or_endpoint):
            if callable(func_or_endpoint):
                # Function decorator
                @functools.wraps(func_or_endpoint)
                async def wrapper(*args, **kwargs):
                    # Find request object in args or kwargs
                    request = None
                    for arg in args:
                        if hasattr(arg, 'headers') or hasattr(arg, 'cookies'):
                            request = arg
                            break
                    
                    if not request:
                        for arg_name, arg_value in kwargs.items():
                            if arg_name in ('request', 'req') or \
                               hasattr(arg_value, 'headers') or \
                               hasattr(arg_value, 'cookies'):
                                request = arg_value
                                break
                    
                    if not request:
                        # Can't find request object, skip rate limiting
                        return await func_or_endpoint(*args, **kwargs)
                    
                    # Check rate limit
                    result = await self.check(request, options)
                    
                    if not result['allowed']:
                        # Rate limit exceeded
                        # Handle different web frameworks
                        response_func = None
                        for arg in args:
                            if hasattr(arg, 'json') and callable(arg.json):
                                response_func = arg.json
                                break
                        
                        if response_func:
                            # Return JSON response
                            return response_func(
                                format_error_response(
                                    result['limit'],
                                    options.get('interval', 'minute'),
                                    result['reset']
                                ),
                                status_code=429,
                                headers={
                                    'X-RateLimit-Limit': str(result['limit']),
                                    'X-RateLimit-Remaining': str(result['remaining']),
                                    'X-RateLimit-Reset': str(result['reset']),
                                    'Retry-After': str(result['retry_after'])
                                }
                            )
                        
                        # If we can't find a way to return a response, raise an exception
                        error_msg = f"Rate limit exceeded: {result['limit']} requests per {options.get('interval', 'minute')}"
                        raise RateLimitExceeded(error_msg, result)
                    
                    # Rate limit not exceeded, proceed to original function
                    return await func_or_endpoint(*args, **kwargs)
                
                # Handle both async and sync functions
                if not inspect.iscoroutinefunction(func_or_endpoint):
                    # For sync functions
                    @functools.wraps(func_or_endpoint)
                    def sync_wrapper(*args, **kwargs):
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        return loop.run_until_complete(wrapper(*args, **kwargs))
                    
                    return sync_wrapper
                
                return wrapper
            else:
                # Framework-specific middleware (e.g., for Flask)
                async def middleware():
                    from flask import request, jsonify, make_response
                    
                    # Check rate limit
                    result = await self.check(request, options)
                    
                    if not result['allowed']:
                        # Rate limit exceeded
                        response = make_response(jsonify(
                            format_error_response(
                                result['limit'],
                                options.get('interval', 'minute'),
                                result['reset']
                            )
                        ), 429)
                        
                        response.headers['X-RateLimit-Limit'] = str(result['limit'])
                        response.headers['X-RateLimit-Remaining'] = str(result['remaining'])
                        response.headers['X-RateLimit-Reset'] = str(result['reset'])
                        response.headers['Retry-After'] = str(result['retry_after'])
                        
                        return response
                    
                    # Rate limit not exceeded, continue to next middleware/handler
                    return None
                
                # For Flask before_request
                def flask_middleware():
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    return loop.run_until_complete(middleware())
                
                return flask_middleware
        
        return decorator
    
    def get_metrics(self) -> Dict[str, int]:
        """
        Get current metrics.
        
        Returns:
            Current metrics
        """
        return dict(self.metrics)


class RateLimitExceeded(Exception):
    """
    Exception raised when rate limit is exceeded.
    """
    
    def __init__(self, message: str, result: Dict[str, Any]):
        super().__init__(message)
        self.result = result


def create_limiter(config_path: Optional[str] = None, options: Dict[str, Any] = None) -> RateLimiter:
    """
    Create a rate limiter instance with configuration.
    
    Args:
        config_path: Path to configuration file
        options: Configuration options
        
    Returns:
        RateLimiter instance
    """
    # Load config from file if provided
    config = {}
    if config_path:
        config = load_config_from_file(config_path)
    
    # Merge with provided options
    if options:
        config.update(options)
    
    return RateLimiter(config) 