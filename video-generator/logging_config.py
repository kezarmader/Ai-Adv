import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
import json

# Context variable for request ID
request_id: ContextVar[str] = ContextVar('request_id', default='')

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())[:8]

def setup_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    """Setup structured logging for the service"""
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatting
    handler = logging.StreamHandler()
    formatter = StructuredFormatter(service_name)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": request_id.get(''),
        }
        
        # Add extra fields if present
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                              'filename', 'module', 'lineno', 'funcName', 'created', 
                              'msecs', 'relativeCreated', 'thread', 'threadName', 
                              'processName', 'process', 'getMessage', 'exc_info', 
                              'exc_text', 'stack_info']:
                    log_entry[key] = value
        
        return json.dumps(log_entry)

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, logger: logging.Logger, extra_data: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.logger = logger
        self.extra_data = extra_data or {}
        self.start_time = None
        self.duration_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"{self.operation_name} started", extra={
            "event": "operation_start",
            "operation": self.operation_name,
            **self.extra_data
        })
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            self.duration_ms = (time.time() - self.start_time) * 1000
            
            if exc_type is None:
                self.logger.debug(f"{self.operation_name} completed", extra={
                    "event": "operation_complete",
                    "operation": self.operation_name,
                    "duration_ms": round(self.duration_ms, 2),
                    **self.extra_data
                })
            else:
                self.logger.error(f"{self.operation_name} failed", extra={
                    "event": "operation_error",
                    "operation": self.operation_name,
                    "duration_ms": round(self.duration_ms, 2),
                    "error_type": exc_type.__name__ if exc_type else None,
                    "error_message": str(exc_val) if exc_val else None,
                    **self.extra_data
                })

def log_gpu_usage(logger: logging.Logger, stage: str):
    """Log GPU usage information if available"""
    try:
        import torch
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated() / 1024**3  # GB
            memory_reserved = torch.cuda.memory_reserved() / 1024**3   # GB
            
            logger.info("GPU memory usage", extra={
                "stage": stage,
                "memory_allocated_gb": round(memory_allocated, 2),
                "memory_reserved_gb": round(memory_reserved, 2),
                "gpu_name": torch.cuda.get_device_name(),
                "event": "gpu_usage"
            })
    except ImportError:
        # torch not available, skip GPU logging
        pass
    except Exception as e:
        logger.warning("Could not log GPU usage", extra={
            "stage": stage,
            "error": str(e)
        })

def log_video_generation_metrics(logger: logging.Logger, width: int, height: int, 
                                duration: int, fps: int, animation_type: str):
    """Log video generation metrics"""
    total_frames = duration * fps
    logger.info("Video generation metrics", extra={
        "video_width": width,
        "video_height": height,
        "duration_seconds": duration,
        "fps": fps,
        "total_frames": total_frames,
        "animation_type": animation_type,
        "event": "video_metrics"
    })