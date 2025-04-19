"""
Example FastAPI application with rate limiting.
"""

from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import JSONResponse
from rate_limiter.fastapi import RateLimiterMiddleware, rate_limit


app = FastAPI(
    title="Rate-Limited API",
    description="Example API with rate limiting",
    version="1.0.0"
)

app.add_middleware(
    RateLimiterMiddleware,
    options={
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
    }
)


@app.get("/")
async def index():
    """Simple home page."""
    return {
        "message": "Welcome to the rate-limited API",
        "endpoints": [
            "/api/public",
            "/api/high-load",
            "/api/custom"
        ]
    }


@app.get("/api/public")
async def public_api():
    """
    Public API endpoint with default rate limit (10 requests per minute).
    """
    return {
        "message": "This is a public API endpoint",
        "rate_limit": "10 requests per minute"
    }


@app.get("/api/high-load")
@rate_limit(rate=3, interval="minute") 
async def high_load_api():
    """
    High-load API endpoint with stricter rate limit (3 requests per minute).
    """
    return {
        "message": "This is a high-load API endpoint",
        "rate_limit": "3 requests per minute",
        "data": "Processing intensive operation..."
    }


@app.get("/api/custom")
async def custom_api(request: Request):
    """
    Custom API endpoint that manually performs additional checks.
    """
    client_host = request.client.host
    
    return {
        "message": "This is a custom API endpoint",
        "client_ip": client_host
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_example:app", host="0.0.0.0", port=8000, reload=True) 