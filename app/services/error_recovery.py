"""
Error recovery service for graceful degradation and automatic recovery
Implements requirements 7.1, 7.3 for graceful degradation and external service failures
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from app.models.enums import ErrorType, MessageType
from app.models.schemas import Response, Message
from app.services.error_monitoring import error_monitor, ErrorSeverity
from app.utils.logging import get_logger, log_error_with_context

logger = get_logger(__name__)


class RecoveryStrategy(str, Enum):
    """Recovery strategies for different types of failures"""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    SKIP = "skip"
    MANUAL = "manual"


@dataclass
class RecoveryAction:
    """Defines a recovery action for a specific error scenario"""
    strategy: RecoveryStrategy
    max_attempts: int = 3
    delay_seconds: float = 1.0
    fallback_function: Optional[Callable] = None
    degraded_response: Optional[str] = None
    skip_condition: Optional[Callable] = None


class ErrorRecoveryService:
    """
    Service for implementing error recovery strategies and graceful degradation
    Provides automatic recovery mechanisms for various failure scenarios
    """
    
    def __init__(self):
        self.recovery_strategies = self._setup_recovery_strategies()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.fallback_responses = self._setup_fallback_responses()
        self.degraded_services: Dict[str, datetime] = {}
    
    def _setup_recovery_strategies(self) -> Dict[ErrorType, RecoveryAction]:
        """Setup recovery strategies for different error types"""
        return {
            ErrorType.EXTERNAL_SERVICE: RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                max_attempts=2,
                delay_seconds=2.0,
                fallback_function=self._external_service_fallback
            ),
            ErrorType.DATABASE: RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=1.0,
                fallback_function=self._database_fallback
            ),
            ErrorType.INPUT_PROCESSING: RecoveryAction(
                strategy=RecoveryStrategy.DEGRADE,
                max_attempts=1,
                degraded_response="I had trouble processing your input. Please try providing the information in text format."
            ),
            ErrorType.VALIDATION: RecoveryAction(
                strategy=RecoveryStrategy.MANUAL,
                max_attempts=1,
                degraded_response="There's an issue with the data format. Please check your input and try again."
            ),
            ErrorType.BUSINESS_LOGIC: RecoveryAction(
                strategy=RecoveryStrategy.SKIP,
                max_attempts=1,
                skip_condition=lambda: True
            )
        }
    
    def _setup_fallback_responses(self) -> Dict[str, str]:
        """Setup fallback responses for different service failures"""
        return {
            "sarvam_ai": "I couldn't process your voice message. Please type your bill information instead.",
            "gemini_vision": "I had trouble reading your bill image. Please type the bill details or send a clearer photo.",
            "litellm": "I'm having trouble with text processing. Please provide simple, clear bill information.",
            "siren_whatsapp": "WhatsApp messaging is temporarily unavailable. Trying SMS instead.",
            "siren_sms": "Both WhatsApp and SMS are temporarily unavailable. Please try again later.",
            "database": "I'm having trouble saving your information. Please try again in a moment.",
            "upi_service": "Payment link generation is temporarily unavailable. I'll provide manual payment instructions."
        }
    
    async def recover_from_error(self, error: Exception, context: Dict[str, Any]) -> Optional[Response]:
        """
        Main recovery method that attempts to recover from errors
        
        Args:
            error: The exception that occurred
            context: Context information including service, user_id, etc.
        
        Returns:
            Recovery response if successful, None if recovery not possible
        """
        try:
            # Classify error and get recovery strategy
            error_type = self._classify_error(error)
            recovery_action = self.recovery_strategies.get(error_type)
            
            if not recovery_action:
                logger.warning(f"No recovery strategy for error type: {error_type}")
                return None
            
            # Log recovery attempt
            await error_monitor.log_error(error, {
                **context,
                "recovery_attempted": True,
                "recovery_strategy": recovery_action.strategy.value
            })
            
            # Execute recovery strategy
            if recovery_action.strategy == RecoveryStrategy.RETRY:
                return await self._retry_recovery(error, context, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.FALLBACK:
                return await self._fallback_recovery(error, context, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.DEGRADE:
                return await self._degrade_recovery(error, context, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.SKIP:
                return await self._skip_recovery(error, context, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.MANUAL:
                return await self._manual_recovery(error, context, recovery_action)
            
            return None
            
        except Exception as recovery_error:
            log_error_with_context(logger, recovery_error, {
                **context,
                "original_error": str(error),
                "recovery_failed": True
            })
            return None
    
    async def _retry_recovery(self, error: Exception, context: Dict[str, Any], 
                            action: RecoveryAction) -> Optional[Response]:
        """Implement retry recovery strategy with exponential backoff"""
        service_name = context.get("service", "unknown")
        operation = context.get("operation")
        
        if not operation:
            logger.warning("No operation provided for retry recovery")
            return None
        
        for attempt in range(action.max_attempts):
            try:
                # Wait before retry (except first attempt)
                if attempt > 0:
                    delay = action.delay_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                
                logger.info(f"Retry attempt {attempt + 1}/{action.max_attempts} for {service_name}")
                
                # Execute the operation again
                result = await operation()
                
                logger.info(f"Retry successful for {service_name} after {attempt + 1} attempts")
                return result
                
            except Exception as retry_error:
                if attempt == action.max_attempts - 1:
                    logger.error(f"All retry attempts failed for {service_name}: {retry_error}")
                    # Try fallback if available
                    if action.fallback_function:
                        return await action.fallback_function(error, context)
                else:
                    logger.warning(f"Retry attempt {attempt + 1} failed for {service_name}: {retry_error}")
        
        return None
    
    async def _fallback_recovery(self, error: Exception, context: Dict[str, Any], 
                               action: RecoveryAction) -> Optional[Response]:
        """Implement fallback recovery strategy"""
        service_name = context.get("service", "unknown")
        
        logger.info(f"Attempting fallback recovery for {service_name}")
        
        if action.fallback_function:
            try:
                return await action.fallback_function(error, context)
            except Exception as fallback_error:
                log_error_with_context(logger, fallback_error, {
                    **context,
                    "fallback_failed": True,
                    "original_error": str(error)
                })
        
        # Use default fallback response
        fallback_message = self.fallback_responses.get(service_name, 
                                                      "Service temporarily unavailable. Please try again later.")
        
        return Response(
            content=fallback_message,
            message_type=MessageType.TEXT,
            metadata={
                "recovery_type": "fallback",
                "original_service": service_name,
                "fallback_used": True
            }
        )
    
    async def _degrade_recovery(self, error: Exception, context: Dict[str, Any], 
                              action: RecoveryAction) -> Optional[Response]:
        """Implement graceful degradation recovery strategy"""
        service_name = context.get("service", "unknown")
        
        logger.info(f"Implementing graceful degradation for {service_name}")
        
        # Mark service as degraded
        self.degraded_services[service_name] = datetime.now()
        
        # Return degraded response
        degraded_message = action.degraded_response or self.fallback_responses.get(
            service_name, "Service is running in limited mode. Some features may be unavailable."
        )
        
        return Response(
            content=degraded_message,
            message_type=MessageType.TEXT,
            metadata={
                "recovery_type": "degraded",
                "service": service_name,
                "degraded_since": datetime.now().isoformat(),
                "suggestions": self._get_degradation_suggestions(service_name)
            }
        )
    
    async def _skip_recovery(self, error: Exception, context: Dict[str, Any], 
                           action: RecoveryAction) -> Optional[Response]:
        """Implement skip recovery strategy"""
        service_name = context.get("service", "unknown")
        
        logger.info(f"Skipping failed operation for {service_name}")
        
        # Check skip condition if provided
        if action.skip_condition and not action.skip_condition():
            return None
        
        return Response(
            content="I encountered an issue with that step, but let's continue. Please provide the next piece of information.",
            message_type=MessageType.TEXT,
            metadata={
                "recovery_type": "skip",
                "skipped_service": service_name,
                "continue_flow": True
            }
        )
    
    async def _manual_recovery(self, error: Exception, context: Dict[str, Any], 
                             action: RecoveryAction) -> Optional[Response]:
        """Implement manual recovery strategy"""
        service_name = context.get("service", "unknown")
        
        logger.info(f"Manual recovery required for {service_name}")
        
        manual_message = action.degraded_response or "I need your help to continue. Please provide the information manually."
        
        return Response(
            content=manual_message,
            message_type=MessageType.TEXT,
            metadata={
                "recovery_type": "manual",
                "service": service_name,
                "manual_intervention_required": True,
                "help_available": True
            }
        )
    
    async def _external_service_fallback(self, error: Exception, context: Dict[str, Any]) -> Response:
        """Fallback for external service failures"""
        service_name = context.get("service", "unknown")
        message_type = context.get("message_type", MessageType.TEXT)
        
        # Provide specific fallback based on service and message type
        if service_name == "sarvam_ai" and message_type == MessageType.VOICE:
            return Response(
                content="I couldn't process your voice message. Please type your bill information instead.",
                message_type=MessageType.TEXT,
                metadata={"fallback_from": "voice_to_text", "alternative": "text_input"}
            )
        elif service_name == "gemini_vision" and message_type == MessageType.IMAGE:
            return Response(
                content="I had trouble reading your bill image. Please type the bill details or send a clearer photo.",
                message_type=MessageType.TEXT,
                metadata={"fallback_from": "image_processing", "alternative": "manual_entry"}
            )
        else:
            return Response(
                content="I'm having trouble with some services. Please provide your information in simple text format.",
                message_type=MessageType.TEXT,
                metadata={"fallback_from": service_name, "alternative": "text_processing"}
            )
    
    async def _database_fallback(self, error: Exception, context: Dict[str, Any]) -> Response:
        """Fallback for database failures"""
        return Response(
            content="I'm having trouble saving your information right now. Please try again in a moment, and I'll remember where we left off.",
            message_type=MessageType.TEXT,
            metadata={
                "fallback_from": "database",
                "retry_suggested": True,
                "temporary_issue": True
            }
        )
    
    def _get_degradation_suggestions(self, service_name: str) -> List[str]:
        """Get suggestions for users when service is degraded"""
        suggestions = {
            "sarvam_ai": [
                "Try typing your message instead of voice",
                "Speak more clearly if using voice messages"
            ],
            "gemini_vision": [
                "Take a clearer photo of your bill",
                "Type the bill information manually",
                "Ensure good lighting when taking photos"
            ],
            "litellm": [
                "Use simple, clear language",
                "Break down complex requests into smaller parts"
            ],
            "siren": [
                "Messages may be delayed",
                "Try again in a few minutes"
            ]
        }
        
        return suggestions.get(service_name, ["Please try again later"])
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error into application error type"""
        error_str = str(error).lower()
        
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
    
    def is_service_degraded(self, service_name: str, degradation_timeout: timedelta = timedelta(minutes=10)) -> bool:
        """Check if a service is currently in degraded state"""
        if service_name not in self.degraded_services:
            return False
        
        degraded_since = self.degraded_services[service_name]
        return datetime.now() - degraded_since < degradation_timeout
    
    def clear_service_degradation(self, service_name: str) -> None:
        """Clear degradation status for a service"""
        if service_name in self.degraded_services:
            del self.degraded_services[service_name]
            logger.info(f"Cleared degradation status for {service_name}")
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery status and degraded services"""
        return {
            "degraded_services": {
                service: {
                    "degraded_since": degraded_since.isoformat(),
                    "duration_minutes": (datetime.now() - degraded_since).total_seconds() / 60
                }
                for service, degraded_since in self.degraded_services.items()
            },
            "circuit_breakers": {
                name: breaker.get_status()
                for name, breaker in self.circuit_breakers.items()
            },
            "timestamp": datetime.now().isoformat()
        }


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service protection
    Prevents cascading failures by temporarily disabling failing services
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, operation: Callable) -> Any:
        """Execute operation through circuit breaker"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = await operation()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful operation"""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


# Global error recovery service instance
error_recovery_service = ErrorRecoveryService()