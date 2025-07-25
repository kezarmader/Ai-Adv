import logging
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
import uuid
from contextvars import ContextVar

# Context variable to track request IDs across async operations
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "poster-service"
        }
        
        # Add request ID if available
        req_id = request_id.get()
        if req_id:
            log_entry["request_id"] = req_id
            
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
            
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def setup_logging(service_name: str = "poster-service", log_level: str = "INFO"):
    """Setup structured logging for the service"""
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with custom structured formatter
    handler = logging.StreamHandler()
    
    # Create formatter with service name
    class ServiceFormatter(StructuredFormatter):
        def format(self, record):
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": service_name
            }
            
            # Add request ID if available
            req_id = request_id.get()
            if req_id:
                log_entry["request_id"] = req_id
                
            # Add extra fields if present
            if hasattr(record, 'extra'):
                log_entry.update(record.extra)
                
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
                
            return json.dumps(log_entry)
    
    formatter = ServiceFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())[:8]
