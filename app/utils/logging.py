"""
Enhanced logging configuration for the application with structured logging support
Implements requirements 7.4, 7.5 for error logging and monitoring
"""
import logging
import sys
import json
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging with JSON output
    Provides consistent log format for monitoring and analysis
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        try:
            # Base log structure
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # Add exception information if present
            if record.exc_info:
                log_entry["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": self.formatException(record.exc_info) if record.exc_info else None
                }
            
            # Add extra fields from record
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                              'filename', 'module', 'lineno', 'funcName', 'created', 
                              'msecs', 'relativeCreated', 'thread', 'threadName', 
                              'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    extra_fields[key] = value
            
            if extra_fields:
                log_entry["extra"] = extra_fields
            
            return json.dumps(log_entry, default=str)
            
        except Exception as e:
            # Fallback to standard formatting if JSON formatting fails
            return f"LOGGING_ERROR: {e} | ORIGINAL: {super().format(record)}"


class ContextualFormatter(logging.Formatter):
    """
    Human-readable formatter with contextual information
    Used for development and console output
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with contextual information"""
        try:
            # Base format
            base_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            
            # Add request ID if available
            if hasattr(record, 'request_id'):
                base_format = f'%(asctime)s - [%(request_id)s] - %(name)s - %(levelname)s - %(message)s'
            
            # Add user ID if available
            if hasattr(record, 'user_id'):
                base_format = base_format.replace('%(levelname)s', '%(levelname)s [user:%(user_id)s]')
            
            formatter = logging.Formatter(base_format)
            return formatter.format(record)
            
        except Exception as e:
            # Fallback to standard formatting
            return f"FORMATTING_ERROR: {e} | ORIGINAL: {super().format(record)}"


def setup_logging():
    """Configure enhanced application logging with structured support"""
    
    # Determine if we should use structured logging
    use_structured = settings.environment == "production"
    
    # Create appropriate formatter
    if use_structured:
        formatter = StructuredFormatter()
    else:
        formatter = ContextualFormatter()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce access log noise
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Reduce HTTP client noise
    
    # Configure application-specific loggers
    logging.getLogger("app.services").setLevel(logging.INFO)
    logging.getLogger("app.middleware").setLevel(logging.INFO)
    logging.getLogger("app.api").setLevel(logging.INFO)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with consistent configuration
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter for adding contextual information to log records
    Useful for adding request IDs, user IDs, etc. to all log messages
    """
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]):
        super().__init__(logger, extra)
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add extra context"""
        # Merge extra context
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra.copy()
        
        return msg, kwargs


def get_contextual_logger(name: str, context: Dict[str, Any]) -> LoggerAdapter:
    """
    Get logger with contextual information
    
    Args:
        name: Logger name
        context: Context dictionary (e.g., {'request_id': '123', 'user_id': 'user456'})
    
    Returns:
        Logger adapter with context
    """
    base_logger = get_logger(name)
    return LoggerAdapter(base_logger, context)


def log_error_with_context(logger: logging.Logger, error: Exception, 
                          context: Dict[str, Any]) -> None:
    """
    Log error with comprehensive context information
    
    Args:
        logger: Logger instance
        error: Exception to log
        context: Additional context information
    """
    try:
        # Create error context
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            **context
        }
        
        # Log with context
        logger.error(
            f"Error occurred: {error}",
            extra=error_context,
            exc_info=True
        )
        
    except Exception as log_error:
        # Fallback logging if context logging fails
        logger.error(f"Error logging failed: {log_error}. Original error: {error}")


def log_performance_metric(logger: logging.Logger, operation: str, 
                          duration: float, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log performance metrics for monitoring
    
    Args:
        logger: Logger instance
        operation: Operation name
        duration: Duration in seconds
        context: Additional context
    """
    try:
        metric_context = {
            "metric_type": "performance",
            "operation": operation,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        if context:
            metric_context.update(context)
        
        logger.info(
            f"Performance metric: {operation} completed in {duration:.3f}s",
            extra=metric_context
        )
        
    except Exception as e:
        logger.warning(f"Failed to log performance metric: {e}")


def log_business_event(logger: logging.Logger, event: str, 
                      details: Dict[str, Any]) -> None:
    """
    Log business events for analytics and monitoring
    
    Args:
        logger: Logger instance
        event: Event name
        details: Event details
    """
    try:
        event_context = {
            "event_type": "business",
            "event_name": event,
            "timestamp": datetime.now().isoformat(),
            **details
        }
        
        logger.info(
            f"Business event: {event}",
            extra=event_context
        )
        
    except Exception as e:
        logger.warning(f"Failed to log business event: {e}")


# Setup logging on module import
setup_logging()