import logging
import json
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any

# Context variable to store request ID across async calls
request_id: ContextVar[str] = ContextVar('request_id', default='')

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": getattr(record, 'service', 'video-generator'),
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id.get('')
        }
        
        # Add any extra fields from the log record
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 
                              'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 
                              'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
                              'exc_text', 'stack_info', 'message', 'service']:
                    if not key.startswith('_'):
                        log_entry[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)

def setup_logging(service_name: str, log_level: str = "INFO") -> logging.Logger:
    """Setup structured logging for the service"""
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with structured formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(StructuredFormatter())
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Set service name on all records
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = service_name
        return record
    
    logging.setLogRecordFactory(record_factory)
    
    return logger

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, logger: logging.Logger, extra_context: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.logger = logger
        self.extra_context = extra_context or {}
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation_name}", extra={
            "event": "operation_start", 
            "operation": self.operation_name,
            **self.extra_context
        })
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            self.logger.info(f"Completed {self.operation_name}", extra={
                "event": "operation_complete",
                "operation": self.operation_name,
                "duration_ms": round(self.duration_ms, 2),
                **self.extra_context
            })
        else:
            self.logger.error(f"Failed {self.operation_name}", extra={
                "event": "operation_failed",
                "operation": self.operation_name, 
                "duration_ms": round(self.duration_ms, 2),
                "error": str(exc_val),
                "error_type": exc_type.__name__ if exc_type else None,
                **self.extra_context
            })

def log_video_generation_metrics(logger: logging.Logger, width: int, height: int, fps: int, duration: int, effect_type: str):
    """Log video generation metrics"""
    logger.info("Video generation metrics", extra={
        "event": "video_metrics",
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration,
        "effect_type": effect_type,
        "total_frames": fps * duration
    })
