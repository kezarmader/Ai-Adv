from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from logging_config import setup_logging, generate_request_id, request_id

# Setup structured logging
logger = setup_logging("poster-service", "INFO")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate and set request ID
        req_id = generate_request_id()
        request_id.set(req_id)
        
        # Log request details
        client_ip = request.client.host if request.client else "unknown"
        logger.info("HTTP request received", extra={
            "method": request.method,
            "path": str(request.url.path),
            "client_ip": client_ip,
            "event": "http_request"
        })
        
        # Start timing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response details
        logger.info("HTTP response sent", extra={
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "event": "http_response"
        })
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id
        
        return response

app = FastAPI(title="AI Advertisement Generator - Poster Service", version="1.0.0")
app.add_middleware(LoggingMiddleware)

logger.info("Poster service starting up")

@app.post("/post")
async def mock_post(req: Request):
    """Mock posting service for advertisements"""
    try:
        data = await req.json()
        
        # Log the posting request details
        logger.info("Advertisement post request received", extra={
            "has_text": "text" in data and bool(data["text"]),
            "has_image_url": "image_url" in data and bool(data["image_url"]),
            "text_preview": str(data.get("text", {}))[:100] + "..." if len(str(data.get("text", {}))) > 100 else str(data.get("text", {})),
            "image_url": data.get("image_url", "")
        })
        
        # Simulate posting delay
        time.sleep(0.1)
        
        logger.info("Advertisement posted successfully (mock)", extra={
            "status": "success",
            "message": "Simulated post to advertising platform"
        })
        
        return {
            "status": "success", 
            "message": "Advertisement posted successfully to mock platform",
            "platform": "mock-platform",
            "post_id": generate_request_id()
        }
        
    except Exception as e:
        logger.error("Error processing post request", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        return {
            "status": "error",
            "message": f"Failed to post advertisement: {str(e)}"
        }

@app.get("/")
def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy", 
        "service": "poster-service",
        "description": "Mock advertisement posting service"
    }

@app.get("/status")
def service_status():
    """Service status endpoint"""
    return {
        "service": "poster-service",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": ["/post", "/", "/status"]
    }

logger.info("Poster service ready")

