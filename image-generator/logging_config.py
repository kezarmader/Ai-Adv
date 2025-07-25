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
            "service": "image-generator"
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

def setup_logging(service_name: str = "image-generator", log_level: str = "INFO"):
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

def log_gpu_usage(logger: logging.Logger, operation: str = None):
    """Log GPU memory usage if available"""
    try:
        import torch
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated()
            memory_reserved = torch.cuda.memory_reserved()
            logger.info("GPU memory usage", extra={
                "operation": operation,
                "memory_allocated_mb": round(memory_allocated / 1024 / 1024, 2),
                "memory_reserved_mb": round(memory_reserved / 1024 / 1024, 2)
            })
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Could not log GPU usage: {e}")

def log_image_generation_metrics(logger: logging.Logger, width: int, height: int, 
                                num_inference_steps: int, guidance_scale: float,
                                model_name: str = None):
    """Log image generation parameters"""
    logger.info("Image generation parameters", extra={
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "model_name": model_name
    })
