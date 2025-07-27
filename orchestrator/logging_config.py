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
            "service": "orchestrator"
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

def setup_logging(service_name: str = "orchestrator", log_level: str = "INFO"):
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
                
            # Add extra fields if present - they are added directly to the record object
            # We need to filter out standard logging attributes and only include custom ones
            standard_attrs = {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 
                'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 
                'thread', 'threadName', 'processName', 'process', 'getMessage', 
                'exc_info', 'exc_text', 'stack_info', 'taskName'
            }
            
            for key, value in record.__dict__.items():
                if key not in standard_attrs:
                    log_entry[key] = value
                
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

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, logger: logging.Logger, extra_data: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.logger = logger
        self.extra_data = extra_data or {}
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation_name}", extra={
            "operation": self.operation_name,
            "event": "start",
            **self.extra_data
        })
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is None:
            self.logger.info(f"Completed {self.operation_name}", extra={
                "operation": self.operation_name,
                "event": "complete",
                "duration_ms": round(duration_ms, 2),
                **self.extra_data
            })
        else:
            self.logger.error(f"Failed {self.operation_name}", extra={
                "operation": self.operation_name,
                "event": "error",
                "duration_ms": round(duration_ms, 2),
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                **self.extra_data
            })
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get current duration in milliseconds"""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())[:8]

def log_request_details(logger: logging.Logger, method: str, path: str, client_ip: str, 
                       user_agent: Optional[str] = None, request_size: Optional[int] = None):
    """Log HTTP request details"""
    logger.info("HTTP request received", extra={
        "event": "http_request",
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "request_size_bytes": request_size
    })

def log_response_details(logger: logging.Logger, status_code: int, response_size: Optional[int] = None,
                        duration_ms: Optional[float] = None):
    """Log HTTP response details"""
    logger.info("HTTP response sent", extra={
        "event": "http_response", 
        "status_code": status_code,
        "response_size_bytes": response_size,
        "duration_ms": duration_ms
    })

def log_external_api_call(logger: logging.Logger, service: str, endpoint: str, method: str = "POST",
                         request_data: Optional[Dict] = None, response_status: Optional[int] = None,
                         duration_ms: Optional[float] = None, error: Optional[str] = None):
    """Log external API calls"""
    log_data = {
        "event": "external_api_call",
        "external_service": service,
        "endpoint": endpoint,
        "method": method,
        "response_status": response_status,
        "duration_ms": duration_ms
    }
    
    if request_data:
        # Log request data size instead of full data for privacy
        log_data["request_data_size"] = len(json.dumps(request_data)) if request_data else 0
        
    if error:
        log_data["error"] = error
        logger.error(f"External API call failed: {service}", extra=log_data)
    else:
        logger.info(f"External API call: {service}", extra=log_data)
