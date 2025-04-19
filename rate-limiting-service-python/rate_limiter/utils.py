"""
Utility functions for rate limiting service.
"""

from typing import Dict, Any, Optional, Union


def get_interval_in_seconds(interval: str) -> int:
    """
    Convert a time interval string to seconds.
    
    Args:
        interval: Time interval (second, minute, hour, day, week, month)
        
    Returns:
        Interval in seconds
    """
    interval = interval.lower()
    if interval == 'second':
        return 1
    elif interval == 'minute':
        return 60
    elif interval == 'hour':
        return 60 * 60
    elif interval == 'day':
        return 24 * 60 * 60
    elif interval == 'week':
        return 7 * 24 * 60 * 60
    elif interval == 'month':
        return 30 * 24 * 60 * 60
    else:
        # Default to minute if unknown
        return 60


def generate_key(prefix: str, identifier: str, resource: Optional[str] = None) -> str:
    """
    Generate a unique key for rate limiting.
    
    Args:
        prefix: Key prefix
        identifier: Unique identifier
        resource: Optional resource identifier
        
    Returns:
        Unique key
    """
    if resource:
        return f"{prefix}:{identifier}:{resource}"
    return f"{prefix}:{identifier}"


def calculate_reset(window_size: int) -> int:
    """
    Calculate the time until a window resets.
    
    Args:
        window_size: Window size in seconds
        
    Returns:
        Seconds until window reset
    """
    import time
    now = int(time.time())
    return window_size - (now % window_size)


def format_error_response(limit: int, interval: str, reset: int) -> Dict[str, Any]:
    """
    Format error response for rate limiting.
    
    Args:
        limit: Rate limit
        interval: Time interval
        reset: Seconds until reset
        
    Returns:
        Error response object
    """
    return {
        'error': 'Rate limit exceeded',
        'message': f'Вы превысили лимит запросов: {limit} запросов в {interval}',
        'retry_after': reset
    }


def normalize_client_info(request) -> Dict[str, Any]:
    """
    Normalize client information from request.
    
    Args:
        request: Request object (Flask, FastAPI, etc.)
        
    Returns:
        Normalized client info
    """
    # Try to handle different web frameworks
    headers = getattr(request, 'headers', {})
    
    # Extract IP address
    if hasattr(request, 'client') and hasattr(request.client, 'host'):  # FastAPI
        ip = request.client.host
    elif getattr(request, 'remote_addr', None):  # Flask
        ip = request.remote_addr
    else:
        ip = headers.get('x-forwarded-for', headers.get('x-real-ip', 'unknown'))
        if ip and ',' in ip:  # Handle multiple IPs in X-Forwarded-For
            ip = ip.split(',')[0].strip()
    
    # Extract user ID
    user_id = None
    user = getattr(request, 'user', None)
    if user:
        user_id = getattr(user, 'id', None)
    
    # Extract path
    path = getattr(request, 'path', getattr(request, 'url', '/'))
    if hasattr(path, 'path'):  # Handle URL objects
        path = path.path
    
    return {
        'ip': ip,
        'user_id': user_id,
        'api_key': headers.get('x-api-key'),
        'user_agent': headers.get('user-agent', 'unknown'),
        'path': path
    }


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse configuration values to ensure correct types.
    
    Args:
        config: Configuration object
        
    Returns:
        Normalized configuration
    """
    rate = config.get('rate')
    if rate is not None:
        try:
            rate = int(rate)
        except (ValueError, TypeError):
            rate = 60
    else:
        rate = 60
    
    return {
        **config,
        'rate': rate,
        'interval': config.get('interval', 'minute'),
        'enabled': config.get('enabled', True)
    }


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to the config file
        
    Returns:
        Configuration dictionary
    """
    import json
    import os
    
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {} 