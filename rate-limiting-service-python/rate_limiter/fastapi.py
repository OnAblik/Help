"""
FastAPI integration for the rate limiter.
"""

from typing import Dict, Any, Optional, Callable, Union
import functools

from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .limiter import RateLimiter, create_limiter
from .utils import format_error_response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    """
    
    def __init__(self, app, config_path: Optional[str] = None, 
                options: Dict[str, Any] = None):
        """
        Initialize the middleware.
        
        Args:
            app: FastAPI application
            config_path: Path to configuration file
            options: Rate limiter options
        """
        super().__init__(app)
        self.limiter = create_limiter(config_path, options)
    
    async def dispatch(self, request: Request, call_next):
        """
        Process the request through rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware
            
        Returns:
            Response
        """
        # Check rate limit
        result = await self.limiter.check(request)
        
        # Add rate limit headers to all responses
        response = await call_next(request)
        
        response.headers['X-RateLimit-Limit'] = str(result['limit'])
        response.headers['X-RateLimit-Remaining'] = str(result['remaining'])
        response.headers['X-RateLimit-Reset'] = str(result['reset'])
        
        if not result['allowed']:
            # Rate limit exceeded
            return JSONResponse(
                content=format_error_response(
                    result['limit'],
                    'minute',  # TODO: Get from options
                    result['reset']
                ),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    'X-RateLimit-Limit': str(result['limit']),
                    'X-RateLimit-Remaining': str(result['remaining']),
                    'X-RateLimit-Reset': str(result['reset']),
                    'Retry-After': str(result['retry_after'])
                }
            )
        
        return response


def rate_limit(rate: Optional[int] = None, interval: Optional[str] = None,
              limiter: Optional[RateLimiter] = None):
    """
    Rate limiting decorator for FastAPI endpoints.
    
    Args:
        rate: Request rate (requests per interval)
        interval: Time interval
        limiter: Optional custom rate limiter instance
        
    Returns:
        FastAPI dependency callable
    """
    options = {}
    if rate is not None:
        options['rate'] = rate
    if interval is not None:
        options['interval'] = interval
    
    # Use provided limiter or create a new one
    rate_limiter = limiter or RateLimiter(options)
    
    async def rate_limit_dependency(request: Request):
        result = await rate_limiter.check(request, options)
        
        if not result['allowed']:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=format_error_response(
                    result['limit'],
                    options.get('interval', 'minute'),
                    result['reset']
                ),
                headers={
                    'X-RateLimit-Limit': str(result['limit']),
                    'X-RateLimit-Remaining': str(result['remaining']),
                    'X-RateLimit-Reset': str(result['reset']),
                    'Retry-After': str(result['retry_after'])
                }
            )
    
    return Depends(rate_limit_dependency) 