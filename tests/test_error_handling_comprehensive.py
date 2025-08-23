"""
Comprehensive tests for error handling middleware and recovery systems
Tests requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, TimeoutError as SQLTimeoutError
from httpx import TimeoutException, ConnectError, HTTPStatusError
from pydantic import ValidationError

from app.middleware.error_middleware import ErrorHandlingMiddleware, DatabaseRetryMixin, ExternalServiceRetryMixin
from app.services.error_monitoring import ErrorMonitor, ErrorMetrics, ErrorEvent, ErrorSeverity, HealthChecker
from app.services.error_recovery import ErrorRecoveryService, RecoveryStrategy, CircuitBreaker
from app.models.enums import ErrorType, MessageType
from app.models.schemas import Message, Response


class TestErrorHandlingMiddleware:
    """Test error handling middleware functionality"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing"""
        from starlette.applications import Starlette
        app = Starlette()
        return ErrorHandlingMiddleware(app)
    
    def test_error_classification(self, middleware):
        """Test error classification into appropriate types"""
        # Database errors
        db_error = SQLAlchemyError("Database connection failed")
        assert middleware._classify_error_type(db_error) == ErrorType.DATABASE
        
        # External service errors
        timeout_error = TimeoutException("Request timed out")
        assert middleware._classify_error_type(timeout_error) == ErrorType.EXTERNAL_SERVICE
        
        # Validation errors
        validation_error = ValidationError([], Mock)
        assert middleware._classify_error_type(validation_error) == ErrorType.VALIDATION
        
        # Business logic errors
        value_error = ValueError("Invalid value")
        assert middleware._classify_error_type(value_error) == ErrorType.BUSINESS_LOGIC
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, middleware):
        """Test database error handling with appropriate response"""
        error = DisconnectionError("Database connection lost")
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test"}
        
        response = await middleware._handle_database_connection_error(error, request, "test123")
        
        assert response.status_code == 503
        content = response.body.decode()
        assert "database_connection_error" in content
        assert "retry_after" in content
    
    @pytest.mark.asyncio
    async def test_external_service_error_handling(self, middleware):
        """Test external service error handling with fallback suggestions"""
        mock_response = Mock()
        mock_response.status_code = 503
        error = HTTPStatusError("Service unavailable", request=Mock(), response=mock_response)
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/test"
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test"}
        
        response = await middleware._handle_external_service_http_error(error, request, "test123")
        
        assert response.status_code == 503
        content = response.body.decode()
        assert "external_service_error" in content
        assert "suggestions" in content


class TestDatabaseRetryMixin:
    """Test database retry functionality"""
    
    @pytest.fixture
    def retry_mixin(self):
        """Create retry mixin instance"""
        return DatabaseRetryMixin()
    
    @pytest.mark.asyncio
    async def test_successful_retry_after_failure(self, retry_mixin):
        """Test successful operation after initial failure"""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DisconnectionError("Connection failed")
            return "success"
        
        result = await retry_mixin.retry_database_operation(
            failing_operation, max_retries=2, base_delay=0.01
        )
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, retry_mixin):
        """Test behavior when all retries are exhausted"""
        async def always_failing_operation():
            raise SQLTimeoutError("Timeout", None, None)
        
        with pytest.raises(SQLTimeoutError):
            await retry_mixin.retry_database_operation(
                always_failing_operation, max_retries=2, base_delay=0.01
            )
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self, retry_mixin):
        """Test that non-retryable errors fail immediately"""
        async def non_retryable_operation():
            raise ValueError("Invalid value")
        
        with pytest.raises(ValueError):
            await retry_mixin.retry_database_operation(
                non_retryable_operation, max_retries=2, base_delay=0.01
            )


class TestExternalServiceRetryMixin:
    """Test external service retry functionality"""
    
    @pytest.fixture
    def retry_mixin(self):
        """Create external service retry mixin instance"""
        return ExternalServiceRetryMixin()
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, retry_mixin):
        """Test retry behavior on timeout errors"""
        call_count = 0
        
        async def timeout_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutException("Request timed out")
            return "success"
        
        result = await retry_mixin.retry_external_service_operation(
            timeout_operation, "test_service", max_retries=2, base_delay=0.01
        )
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, retry_mixin):
        """Test that client errors (4xx) are not retried"""
        mock_response = Mock()
        mock_response.status_code = 400
        
        async def client_error_operation():
            raise HTTPStatusError("Bad request", request=Mock(), response=mock_response)
        
        with pytest.raises(HTTPStatusError):
            await retry_mixin.retry_external_service_operation(
                client_error_operation, "test_service", max_retries=2, base_delay=0.01
            )
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, retry_mixin):
        """Test retry behavior on server errors (5xx)"""
        call_count = 0
        mock_response = Mock()
        mock_response.status_code = 503
        
        async def server_error_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise HTTPStatusError("Service unavailable", request=Mock(), response=mock_response)
            return "success"
        
        result = await retry_mixin.retry_external_service_operation(
            server_error_operation, "test_service", max_retries=2, base_delay=0.01
        )
        
        assert result == "success"
        assert call_count == 2


class TestErrorMonitoring:
    """Test error monitoring and metrics collection"""
    
    @pytest.fixture
    def error_monitor(self):
        """Create error monitor instance"""
        return ErrorMonitor()
    
    @pytest.fixture
    def error_metrics(self):
        """Create error metrics instance"""
        return ErrorMetrics(window_size=100)
    
    def test_error_metrics_collection(self, error_metrics):
        """Test error metrics collection and analysis"""
        # Add some test errors
        error1 = ErrorEvent(
            id="test1",
            timestamp=datetime.now(),
            error_type=ErrorType.DATABASE,
            severity=ErrorSeverity.HIGH,
            message="Database error",
            service="test_service"
        )
        
        error2 = ErrorEvent(
            id="test2",
            timestamp=datetime.now(),
            error_type=ErrorType.EXTERNAL_SERVICE,
            severity=ErrorSeverity.MEDIUM,
            message="Service error",
            service="test_service"
        )
        
        error_metrics.add_error(error1)
        error_metrics.add_error(error2)
        
        # Test metrics
        assert error_metrics.error_counts[ErrorType.DATABASE] == 1
        assert error_metrics.error_counts[ErrorType.EXTERNAL_SERVICE] == 1
        assert error_metrics.service_errors["test_service"] == 2
        
        # Test top error types
        top_errors = error_metrics.get_top_error_types(limit=2)
        assert len(top_errors) == 2
    
    def test_error_rate_calculation(self, error_metrics):
        """Test error rate calculation within time windows"""
        # Add errors with different timestamps
        now = datetime.now()
        
        for i in range(5):
            error = ErrorEvent(
                id=f"test{i}",
                timestamp=now - timedelta(minutes=i * 10),
                error_type=ErrorType.BUSINESS_LOGIC,
                severity=ErrorSeverity.LOW,
                message=f"Error {i}",
                service="test_service"
            )
            error_metrics.add_error(error)
        
        # Test error rate calculation
        rate_1h = error_metrics.get_error_rate(timedelta(hours=1))
        assert rate_1h > 0
    
    @pytest.mark.asyncio
    async def test_error_logging_with_context(self, error_monitor):
        """Test error logging with comprehensive context"""
        error = ValueError("Test error")
        context = {
            "service": "test_service",
            "user_id": "test_user",
            "request_id": "test_request",
            "user_facing": True
        }
        
        error_id = await error_monitor.log_error(error, context)
        
        assert error_id is not None
        assert error_id != "monitoring_failed"
        
        # Check that error was added to metrics
        assert len(error_monitor.metrics.error_events) > 0
    
    @pytest.mark.asyncio
    async def test_error_resolution(self, error_monitor):
        """Test error resolution tracking"""
        error = Exception("Test error")
        context = {"service": "test_service"}
        
        error_id = await error_monitor.log_error(error, context)
        
        # Resolve the error
        resolved = await error_monitor.resolve_error(error_id, "Fixed by restart")
        assert resolved is True
        
        # Check resolution status
        for event in error_monitor.metrics.error_events:
            if event.id == error_id:
                assert event.resolved is True
                assert event.resolution_time is not None
                break
        else:
            pytest.fail("Error event not found")


class TestErrorRecovery:
    """Test error recovery service functionality"""
    
    @pytest.fixture
    def recovery_service(self):
        """Create error recovery service instance"""
        return ErrorRecoveryService()
    
    @pytest.mark.asyncio
    async def test_external_service_fallback_recovery(self, recovery_service):
        """Test fallback recovery for external service failures"""
        error = TimeoutException("Service timeout")
        context = {
            "service": "sarvam_ai",
            "message_type": MessageType.VOICE,
            "user_id": "test_user"
        }
        
        response = await recovery_service.recover_from_error(error, context)
        
        assert response is not None
        assert "voice message" in response.content.lower()
        assert "type" in response.content.lower()
        assert response.metadata["recovery_type"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_degradation_recovery(self, recovery_service):
        """Test graceful degradation recovery"""
        error = Exception("Processing failed")
        context = {
            "service": "gemini_vision",
            "message_type": MessageType.IMAGE,
            "user_id": "test_user"
        }
        
        # Mock the recovery action to use degradation
        recovery_service.recovery_strategies[ErrorType.INPUT_PROCESSING].strategy = RecoveryStrategy.DEGRADE
        
        response = await recovery_service.recover_from_error(error, context)
        
        assert response is not None
        assert response.metadata["recovery_type"] == "degraded"
        assert "gemini_vision" in recovery_service.degraded_services
    
    def test_service_degradation_tracking(self, recovery_service):
        """Test service degradation status tracking"""
        service_name = "test_service"
        
        # Initially not degraded
        assert not recovery_service.is_service_degraded(service_name)
        
        # Mark as degraded
        recovery_service.degraded_services[service_name] = datetime.now()
        assert recovery_service.is_service_degraded(service_name)
        
        # Clear degradation
        recovery_service.clear_service_degradation(service_name)
        assert not recovery_service.is_service_degraded(service_name)


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance"""
        return CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_on_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures"""
        async def failing_operation():
            raise Exception("Operation failed")
        
        # Trigger failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_operation)
        
        assert circuit_breaker.state == "open"
        
        # Next call should fail immediately
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await circuit_breaker.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through half-open state"""
        async def failing_operation():
            raise Exception("Operation failed")
        
        async def successful_operation():
            return "success"
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_operation)
        
        assert circuit_breaker.state == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Successful operation should close circuit
        result = await circuit_breaker.call(successful_operation)
        assert result == "success"
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 0


class TestHealthChecker:
    """Test health checking functionality"""
    
    @pytest.fixture
    def health_checker(self):
        """Create health checker instance"""
        return HealthChecker()
    
    @pytest.mark.asyncio
    async def test_health_check_registration_and_execution(self, health_checker):
        """Test health check registration and execution"""
        async def test_health_check():
            return {"status": "healthy", "details": "All good"}
        
        def sync_health_check():
            return {"status": "healthy", "sync": True}
        
        # Register health checks
        health_checker.register_health_check("async_test", test_health_check)
        health_checker.register_health_check("sync_test", sync_health_check)
        
        # Run health checks
        results = await health_checker.run_health_checks()
        
        assert results["overall_status"] == "healthy"
        assert "async_test" in results["checks"]
        assert "sync_test" in results["checks"]
        assert results["checks"]["async_test"]["status"] == "healthy"
        assert results["checks"]["sync_test"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_failure_handling(self, health_checker):
        """Test health check failure handling"""
        async def failing_health_check():
            raise Exception("Health check failed")
        
        health_checker.register_health_check("failing_test", failing_health_check)
        
        results = await health_checker.run_health_checks()
        
        assert results["overall_status"] == "degraded"
        assert results["checks"]["failing_test"]["status"] == "unhealthy"
        assert "error" in results["checks"]["failing_test"]


@pytest.mark.asyncio
async def test_integration_error_handling_flow():
    """Test complete error handling flow integration"""
    from app.services.error_handler import ConversationErrorHandler
    
    error_handler = ConversationErrorHandler()
    
    # Create test message
    message = Message(
        id="test_msg",
        user_id="test_user",
        content="test content",
        message_type=MessageType.TEXT,
        timestamp=datetime.now()
    )
    
    # Test error handling with monitoring integration
    error = ValueError("Test integration error")
    
    response = await error_handler.handle_conversation_error(error, "test_user", message)
    
    assert response is not None
    assert response.message_type == MessageType.TEXT
    assert "error" in response.content.lower() or "try again" in response.content.lower()
    
    # Check that error was logged to monitoring system
    # This would be verified by checking the error_monitor.metrics in a real scenario


if __name__ == "__main__":
    pytest.main([__file__, "-v"])