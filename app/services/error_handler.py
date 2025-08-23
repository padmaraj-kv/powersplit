"""
Enhanced error handling and recovery mechanisms for conversation state management
Implements requirements 7.1, 7.2, 7.3 for comprehensive error handling
"""
import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from app.models.enums import ConversationStep, MessageType, ErrorType
from app.models.schemas import Message, Response, ConversationState, ErrorResponse
from app.services.error_monitoring import error_monitor, ErrorSeverity
from app.services.error_recovery import error_recovery_service
from app.utils.logging import get_logger, log_error_with_context

logger = get_logger(__name__)


class ConversationErrorHandler:
    """
    Handles errors and implements recovery mechanisms for conversation management
    Provides graceful degradation and retry logic
    """
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]  # Exponential backoff in seconds
        self.error_recovery_strategies = self._setup_recovery_strategies()
    
    def _setup_recovery_strategies(self) -> Dict[ErrorType, Callable]:
        """Setup error recovery strategies for different error types"""
        return {
            ErrorType.INPUT_PROCESSING: self._handle_input_processing_error,
            ErrorType.EXTERNAL_SERVICE: self._handle_external_service_error,
            ErrorType.BUSINESS_LOGIC: self._handle_business_logic_error,
            ErrorType.DATABASE: self._handle_database_error,
            ErrorType.VALIDATION: self._handle_validation_error
        }
    
    async def handle_conversation_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """
        Enhanced main error handler for conversation processing
        Integrates with error monitoring and recovery systems
        """
        try:
            error_type = self._classify_error(error)
            
            # Log error with comprehensive context
            error_context = {
                "service": "conversation_manager",
                "user_id": user_id,
                "message_type": message.message_type.value if message else "unknown",
                "error_type": error_type.value,
                "user_facing": True
            }
            
            # Log to monitoring system
            error_id = await error_monitor.log_error(error, error_context)
            
            # Attempt recovery using recovery service
            recovery_response = await error_recovery_service.recover_from_error(error, error_context)
            
            if recovery_response:
                logger.info(f"Error recovery successful for user {user_id}, error_id: {error_id}")
                return recovery_response
            
            # Fallback to original recovery strategies
            recovery_strategy = self.error_recovery_strategies.get(error_type)
            if recovery_strategy:
                response = await recovery_strategy(error, user_id, message)
                response.metadata = response.metadata or {}
                response.metadata["error_id"] = error_id
                return response
            else:
                return await self._handle_unknown_error(error, user_id, message, error_id)
                
        except Exception as e:
            log_error_with_context(logger, e, {
                "service": "error_handler",
                "user_id": user_id,
                "original_error": str(error),
                "critical": True
            })
            return self._get_fallback_response()
    
    async def retry_operation(self, operation: Callable, max_retries: int = None) -> Any:
        """
        Retry operation with exponential backoff
        Implements requirement 7.2 for retry mechanisms
        """
        max_retries = max_retries or self.max_retries
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Operation failed after {max_retries} attempts: {e}")
        
        raise last_exception
    
    async def handle_state_validation_error(self, state: ConversationState, error: str) -> ConversationState:
        """
        Handle conversation state validation errors
        Reset state to a valid configuration
        """
        logger.warning(f"State validation error for user {state.user_id}: {error}")
        
        # Reset to initial state with error context
        state.current_step = ConversationStep.INITIAL
        state.context = {
            "validation_error": error,
            "reset_timestamp": datetime.now().isoformat(),
            "previous_step": state.current_step.value if state.current_step else "unknown"
        }
        state.retry_count = 0
        state.last_error = None
        
        return state
    
    async def handle_step_transition_error(self, from_step: ConversationStep, 
                                         to_step: ConversationStep, 
                                         user_id: str) -> Response:
        """Handle invalid step transition errors"""
        logger.error(f"Invalid step transition for user {user_id}: {from_step} -> {to_step}")
        
        return Response(
            content="I got a bit confused about where we are in our conversation. Let's start fresh. Please send me your bill information.",
            message_type=MessageType.TEXT,
            metadata={
                "error_type": "invalid_transition",
                "from_step": from_step.value,
                "to_step": to_step.value
            }
        )
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error into appropriate error type"""
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Database-related errors
        if any(keyword in error_str for keyword in ["database", "connection", "sqlalchemy", "psycopg"]):
            return ErrorType.DATABASE
        
        # External service errors
        if any(keyword in error_str for keyword in ["timeout", "connection", "http", "api", "service"]):
            return ErrorType.EXTERNAL_SERVICE
        
        # Validation errors
        if any(keyword in error_str for keyword in ["validation", "invalid", "format", "required"]):
            return ErrorType.VALIDATION
        
        # Input processing errors
        if any(keyword in error_str for keyword in ["parse", "extract", "process", "decode"]):
            return ErrorType.INPUT_PROCESSING
        
        # Default to business logic error
        return ErrorType.BUSINESS_LOGIC
    
    async def _handle_input_processing_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """Handle input processing errors with fallback options"""
        logger.warning(f"Input processing error for user {user_id}: {error}")
        
        # Provide specific guidance based on message type
        if message.message_type == MessageType.IMAGE:
            return Response(
                content="I had trouble reading your bill image. Please try sending a clearer photo or type the bill details manually.",
                message_type=MessageType.TEXT,
                metadata={"error_type": "image_processing", "fallback": "manual_input"}
            )
        elif message.message_type == MessageType.VOICE:
            return Response(
                content="I couldn't understand your voice message clearly. Please try typing your bill information instead.",
                message_type=MessageType.TEXT,
                metadata={"error_type": "voice_processing", "fallback": "text_input"}
            )
        else:
            return Response(
                content="I had trouble understanding your message. Please try rephrasing or provide more details about your bill.",
                message_type=MessageType.TEXT,
                metadata={"error_type": "text_processing"}
            )
    
    async def _handle_external_service_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """Handle external service failures with graceful degradation"""
        logger.error(f"External service error for user {user_id}: {error}")
        
        return Response(
            content="I'm having trouble connecting to some services right now. Please try again in a moment, or provide your bill information in text format.",
            message_type=MessageType.TEXT,
            metadata={
                "error_type": "external_service",
                "fallback": "manual_processing",
                "retry_suggested": True
            }
        )
    
    async def _handle_business_logic_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """Handle business logic errors with helpful guidance"""
        logger.error(f"Business logic error for user {user_id}: {error}")
        
        return Response(
            content="I encountered an issue processing your request. Please check your bill information and try again, or type 'help' for assistance.",
            message_type=MessageType.TEXT,
            metadata={"error_type": "business_logic", "help_available": True}
        )
    
    async def _handle_database_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """Handle database errors with retry suggestion"""
        logger.error(f"Database error for user {user_id}: {error}")
        
        return Response(
            content="I'm having trouble saving your information right now. Please try again in a moment.",
            message_type=MessageType.TEXT,
            metadata={
                "error_type": "database",
                "retry_suggested": True,
                "temporary": True
            }
        )
    
    async def _handle_validation_error(self, error: Exception, user_id: str, message: Message) -> Response:
        """Handle validation errors with specific guidance"""
        logger.warning(f"Validation error for user {user_id}: {error}")
        
        return Response(
            content="There seems to be an issue with the information provided. Please check the format and try again.",
            message_type=MessageType.TEXT,
            metadata={"error_type": "validation", "format_help": True}
        )
    
    async def _handle_unknown_error(self, error: Exception, user_id: str, message: Message, error_id: str = None) -> Response:
        """Handle unknown errors with generic recovery and error tracking"""
        log_error_with_context(logger, error, {
            "service": "conversation_manager",
            "user_id": user_id,
            "error_id": error_id,
            "unknown_error": True
        })
        
        return Response(
            content="I encountered an unexpected error. Please try again or type 'reset' to start over.",
            message_type=MessageType.TEXT,
            metadata={
                "error_type": "unknown", 
                "reset_suggested": True,
                "error_id": error_id,
                "support_contact": True
            }
        )
    
    def _get_fallback_response(self) -> Response:
        """Get fallback response when error handler itself fails"""
        return Response(
            content="I'm experiencing technical difficulties. Please try again later.",
            message_type=MessageType.TEXT,
            metadata={"error_type": "critical", "fallback": True}
        )
    
    async def log_error_context(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error with full context for debugging"""
        try:
            error_context = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now().isoformat(),
                **context
            }
            logger.error(f"Error context: {error_context}")
        except Exception as e:
            logger.critical(f"Failed to log error context: {e}")
    
    def get_error_recovery_suggestions(self, error_type: ErrorType) -> Dict[str, Any]:
        """Get recovery suggestions for different error types"""
        suggestions = {
            ErrorType.INPUT_PROCESSING: {
                "retry": True,
                "alternative_input": True,
                "manual_entry": True
            },
            ErrorType.EXTERNAL_SERVICE: {
                "retry": True,
                "wait_time": "1-2 minutes",
                "fallback_mode": True
            },
            ErrorType.BUSINESS_LOGIC: {
                "check_input": True,
                "help_available": True,
                "reset_option": True
            },
            ErrorType.DATABASE: {
                "retry": True,
                "temporary": True,
                "wait_time": "30 seconds"
            },
            ErrorType.VALIDATION: {
                "check_format": True,
                "examples_available": True,
                "help_available": True
            }
        }
        return suggestions.get(error_type, {"retry": True, "reset_option": True})