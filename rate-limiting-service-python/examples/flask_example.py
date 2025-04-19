"""
Example Flask application with rate limiting.
"""

from flask import Flask, jsonify, request
from rate_limiter import RateLimiter, create_limiter


app = Flask(__name__)

limiter = create_limiter({
    "default_limits": {
        "anonymous": {
            "rate": 10, 
            "interval": "minute"
        }
    },
    "endpoint_overrides": {
        "/api/high-load": {
            "rate": 3,
            "interval": "minute"
        }
    }
})

app.before_request(limiter.limit())


@app.route('/')
def index():
    """Simple home page."""
    return jsonify({
        "message": "Welcome to the rate-limited API",
        "endpoints": [
            "/api/public",
            "/api/high-load"
        ]
    })


@app.route('/api/public')
def public_api():
    """
    Public API endpoint with default rate limit (10 requests per minute).
    """
    return jsonify({
        "message": "This is a public API endpoint",
        "rate_limit": "10 requests per minute"
    })


@app.route('/api/high-load')
@limiter.limit(rate=3, interval='minute') 
def high_load_api():
    """
    High-load API endpoint with stricter rate limit (3 requests per minute).
    """
    return jsonify({
        "message": "This is a high-load API endpoint",
        "rate_limit": "3 requests per minute",
        "data": "Processing intensive operation..."
    })


@app.route('/api/custom')
def custom_api():
    """
    Custom API endpoint that manually checks rate limits.
    """

    user_ip = request.remote_addr
    
    return jsonify({
        "message": "This is a custom API endpoint",
        "user_ip": user_ip
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000) 