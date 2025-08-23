"""
FastAPI error handling middleware for comprehensive error management
Implements requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""
import logging
import traceback
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, TimeoutError as SQLTimeoutError
from httpx import TimeoutException, ConnectError, HTTPStatusError
from pydantic import ValidationError

from app.models.enums import ErrorType
from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive error handling middleware for FastAPI application
    Provides centralized error processing, logging, and response formatting
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.error_handlers = self._setup_error_handlers()
        self.retry_config = {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "exponential_base": 2.0
        }
    
    def _setup_error_handlers(self) -> Dict[type, Callable]:
        """Setup specific error handlers for different exception types"""
        return {
            HTTPException: self._handle_http_exception,
            ValidationError: self._handle_validation_error,
            SQLAlchemyError: self._handle_database_error,
            DisconnectionError: self._handle_database_connection_error,
            SQLTimeoutError: self._handle_database_timeout_error,
            TimeoutException: self._handle_external_service_timeout,
            ConnectError: self._handle_external_service_connection_error,
            HTTPStatusError: self._handle_external_service_http_error,
            ValueError: self._handle_value_error,
            KeyError: self._handle_key_error,
            AttributeError: self._handle_attribute_error,
            Exception: self._handle_generic_error
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main middleware dispatch method
        Handles all requests and catches exceptions
        """
        start_time = datetime.now()
        request_id = self._generate_request_id()
        
        # Add request ID to request state for logging
        request.state.request_id = request_id
        
        try:
            # Log incoming request
            await self._log_request(request, request_id)
            
            # Process request
            response = await call_next(request)
            
            # Log successful response
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Request {request_id} completed successfully in {duration:.3f}s")
            
            return response
            
        except Exception as e:
            # Handle error and return appropriate response
            duration = (datetime.now() - start_time).total_seconds()
            return await self._handle_error(e, request, request_id, duration)
    
    async def _handle_error(self, error: Exception, request: Request, 
                          request_id: str, duration: float) -> JSONResponse:
        """
        Central error handling method
        Determines error type and applies appropriate handling strategy
        """
        try:
            # Classify error and get handler
            error_type = type(error)
            handler = self._get_error_handler(error_type)
            
            # Log error with context
            await self._log_error(error, request, request_id, duration)
            
            # Handle error and get response
            error_response = await handler(error, request, request_id)
            
            # Add monitoring metadata
            error_response.headers["X-Request-ID"] = request_id
            error_response.headers["X-Error-Type"] = self._classify_error_type(error).value
            
            return error_response
            
        except Exception as handler_error:
            # Fallback if error handler itself fails
            logger.critical(f"Error handler failed for request {request_id}: {handler_error}")
            return await self._get_fallback_response(request_id)
    
    def _get_error_handler(self, error_type: type) -> Callable:
        """Get appropriate error handler for exception type"""
        # Check for exact match first
        if error_type in self.error_handlers:
            return self.error_handlers[error_type]
        
        # Check for parent class matches
        for exception_type, handler in self.error_handlers.items():
            if issubclass(error_type, exception_type):
                return handler
        
        # Default to generic handler
        return self.error_handlers[Exception]
    
    def _classify_error_type(self, error: Exception) -> ErrorType:
        """Classify exception into application error type"""
        if isinstance(error, (SQLAlchemyError, DisconnectionError, SQLTimeoutError)):
            return ErrorType.DATABASE
        elif isinstance(error, (TimeoutException, ConnectError, HTTPStatusError)):
            return ErrorType.EXTERNAL_SERVICE
        elif isinstance(error, ValidationError):
            return ErrorType.VALIDATION
        elif isinstance(error, (ValueError, KeyError, AttributeError)):
            return ErrorType.BUSINESS_LOGIC
        else:
            return ErrorType.INPUT_PROCESSING
    
    async def _handle_http_exception(self, error: HTTPException, request: Request, 
                                   request_id: str) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "message": error.detail,
                    "status_code": error.status_code,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )
    
    async def _handle_validation_error(self, error: ValidationError, request: Request, 
                                     request_id: str) -> JSONResponse:
        """Handle Pydantic validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": "validation_error",
                    "message": "Invalid input data",
                    "details": error.errors(),
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "Check the format of your input data",
                        "Ensure all required fields are provided",
                        "Verify data types match expected formats"
                    ]
                }
            }
        )
    
    async def _handle_database_error(self, error: SQLAlchemyError, request: Request, 
                                   request_id: str) -> JSONResponse:
        """Handle SQLAlchemy database errors with retry suggestions"""
        logger.error(f"Database error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "type": "database_error",
                    "message": "Database operation failed",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "retry_after": 30,
                    "suggestions": [
                        "Please try again in a moment",
                        "If the problem persists, contact support"
                    ]
                }
            }
        )
    
    async def _handle_database_connection_error(self, error: DisconnectionError, 
                                              request: Request, request_id: str) -> JSONResponse:
        """Handle database connection errors"""
        logger.error(f"Database connection error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "type": "database_connection_error",
                    "message": "Database connection unavailable",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "retry_after": 60,
                    "suggestions": [
                        "The service is temporarily unavailable",
                        "Please try again in a few minutes"
                    ]
                }
            }
        )
    
    async def _handle_database_timeout_error(self, error: SQLTimeoutError, 
                                           request: Request, request_id: str) -> JSONResponse:
        """Handle database timeout errors"""
        logger.warning(f"Database timeout in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "type": "database_timeout",
                    "message": "Database operation timed out",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "retry_after": 30,
                    "suggestions": [
                        "The operation took too long to complete",
                        "Please try again with simpler data"
                    ]
                }
            }
        )
    
    async def _handle_external_service_timeout(self, error: TimeoutException, 
                                             request: Request, request_id: str) -> JSONResponse:
        """Handle external service timeout errors"""
        logger.warning(f"External service timeout in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "type": "external_service_timeout",
                    "message": "External service request timed out",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "retry_after": 60,
                    "fallback_available": True,
                    "suggestions": [
                        "Please try again in a moment",
                        "You can also try providing information in text format"
                    ]
                }
            }
        )
    
    async def _handle_external_service_connection_error(self, error: ConnectError, 
                                                      request: Request, request_id: str) -> JSONResponse:
        """Handle external service connection errors"""
        logger.error(f"External service connection error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "type": "external_service_unavailable",
                    "message": "External service is currently unavailable",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "retry_after": 120,
                    "fallback_available": True,
                    "suggestions": [
                        "Some AI features may be temporarily unavailable",
                        "Please try providing information in text format",
                        "Try again in a few minutes"
                    ]
                }
            }
        )
    
    async def _handle_external_service_http_error(self, error: HTTPStatusError, 
                                                request: Request, request_id: str) -> JSONResponse:
        """Handle external service HTTP errors"""
        logger.error(f"External service HTTP error in request {request_id}: {error}")
        
        status_code = 503 if error.response.status_code >= 500 else 502
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "type": "external_service_error",
                    "message": "External service returned an error",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "service_status": error.response.status_code,
                    "retry_after": 60,
                    "suggestions": [
                        "The external service is experiencing issues",
                        "Please try again later or use alternative input methods"
                    ]
                }
            }
        )
    
    async def _handle_value_error(self, error: ValueError, request: Request, 
                                request_id: str) -> JSONResponse:
        """Handle value errors with helpful guidance"""
        logger.warning(f"Value error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "value_error",
                    "message": "Invalid value provided",
                    "details": str(error),
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "Check the format of your input",
                        "Ensure numeric values are valid",
                        "Verify date and time formats"
                    ]
                }
            }
        )
    
    async def _handle_key_error(self, error: KeyError, request: Request, 
                              request_id: str) -> JSONResponse:
        """Handle key errors indicating missing required data"""
        logger.warning(f"Key error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "missing_data",
                    "message": f"Required field missing: {str(error)}",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "Ensure all required fields are provided",
                        "Check the request format",
                        "Refer to API documentation for required fields"
                    ]
                }
            }
        )
    
    async def _handle_attribute_error(self, error: AttributeError, request: Request, 
                                    request_id: str) -> JSONResponse:
        """Handle attribute errors indicating programming issues"""
        logger.error(f"Attribute error in request {request_id}: {error}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "internal_error",
                    "message": "Internal server error occurred",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "This appears to be a server-side issue",
                        "Please try again later",
                        "Contact support if the problem persists"
                    ]
                }
            }
        )
    
    async def _handle_generic_error(self, error: Exception, request: Request, 
                                  request_id: str) -> JSONResponse:
        """Handle any unclassified errors"""
        logger.error(f"Unhandled error in request {request_id}: {error}")
        
        # Include stack trace in debug mode
        error_details = {}
        if settings.debug:
            error_details["traceback"] = traceback.format_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "internal_error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "Please try again",
                        "If the problem persists, contact support",
                        "Include the request ID when reporting issues"
                    ],
                    **error_details
                }
            }
        )
    
    async def _get_fallback_response(self, request_id: str) -> JSONResponse:
        """Get fallback response when error handling itself fails"""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "critical_error",
                    "message": "Critical system error occurred",
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                    "suggestions": [
                        "Please try again later",
                        "Contact support immediately if this persists"
                    ]
                }
            }
        )
    
    async def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details"""
        try:
            logger.info(f"Request {request_id}: {request.method} {request.url.path}")
        except Exception as e:
            logger.warning(f"Failed to log request {request_id}: {e}")
    
    async def _log_error(self, error: Exception, request: Request, 
                        request_id: str, duration: float) -> None:
        """Log error with comprehensive context"""
        try:
            error_context = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration": f"{duration:.3f}s",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else "unknown"
            }
            
            # Add stack trace for critical errors
            if not isinstance(error, (HTTPException, ValidationError)):
                error_context["traceback"] = traceback.format_exc()
            
            logger.error(f"Request {request_id} failed: {error_context}")
            
        except Exception as log_error:
            logger.critical(f"Failed to log error for request {request_id}: {log_error}")
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for tracking"""
        import uuid
        return str(uuid.uuid4())[:8]


class DatabaseRetryMixin:
    """
    Mixin class providing database retry functionality with exponential backoff
    Implements requirement 7.2 for database operation retries
    """
    
    async def retry_database_operation(self, operation: Callable, 
                                     max_retries: int = 3,
                                     base_delay: float = 1.0,
                                     max_delay: float = 30.0,
                                     exponential_base: float = 2.0) -> Any:
        """
        Retry database operation with exponential backoff
        
        Args:
            operation: Async callable to retry
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff calculation
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation()
                
            except (DisconnectionError, SQLTimeoutError, SQLAlchemyError) as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
                    break
                
                # Calculate delay with exponential backoff
                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                
                logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                             f"retrying in {delay:.1f}s: {e}")
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # Non-retryable error, fail immediately
                logger.error(f"Non-retryable database error: {e}")
                raise
        
        # All retries exhausted
        raise last_exception


class ExternalServiceRetryMixin:
    """
    Mixin class providing external service retry functionality
    Implements requirement 7.3 for external service failure handling
    """
    
    async def retry_external_service_operation(self, operation: Callable,
                                             service_name: str,
                                             max_retries: int = 2,
                                             base_delay: float = 2.0,
                                             timeout_multiplier: float = 1.5) -> Any:
        """
        Retry external service operation with appropriate backoff
        
        Args:
            operation: Async callable to retry
            service_name: Name of the external service for logging
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            timeout_multiplier: Multiplier for increasing timeout on retries
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation()
                
            except (TimeoutException, ConnectError) as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"{service_name} operation failed after {max_retries + 1} attempts: {e}")
                    break
                
                delay = base_delay * (attempt + 1)
                
                logger.warning(f"{service_name} operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                             f"retrying in {delay:.1f}s: {e}")
                
                await asyncio.sleep(delay)
            
            except HTTPStatusError as e:
                # Don't retry client errors (4xx), but retry server errors (5xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"{service_name} client error (no retry): {e}")
                    raise
                
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"{service_name} server error after {max_retries + 1} attempts: {e}")
                    break
                
                delay = base_delay * (attempt + 1)
                
                logger.warning(f"{service_name} server error (attempt {attempt + 1}/{max_retries + 1}), "
                             f"retrying in {delay:.1f}s: {e}")
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # Non-retryable error, fail immediately
                logger.error(f"Non-retryable {service_name} error: {e}")
                raise
        
        # All retries exhausted
        raise last_exception