#!/usr/bin/env python3
"""
Simple test script for error handling functionality
"""
import asyncio
import sys
from datetime import datetime

# Add app to path
sys.path.insert(0, '.')

def test_error_monitoring():
    """Test basic error monitoring functionality"""
    try:
        from app.services.error_monitoring import ErrorMonitor, ErrorSeverity, ErrorEvent
        from app.models.enums import ErrorType
        
        monitor = ErrorMonitor()
        
        # Test error event creation
        error_event = ErrorEvent(
            id="test_001",
            timestamp=datetime.now(),
            error_type=ErrorType.DATABASE,
            severity=ErrorSeverity.HIGH,
            message="Test error",
            service="test_service"
        )
        
        # Test metrics
        monitor.metrics.add_error(error_event)
        assert len(monitor.metrics.error_events) > 0
        
        print("✅ Error monitoring basic functionality works")
        return True
        
    except Exception as e:
        print(f"❌ Error monitoring test failed: {e}")
        return False

def test_error_recovery():
    """Test basic error recovery functionality"""
    try:
        from app.services.error_recovery import ErrorRecoveryService
        from app.models.enums import MessageType
        
        recovery_service = ErrorRecoveryService()
        
        # Test service degradation tracking
        service_name = "test_service"
        recovery_service.degraded_services[service_name] = datetime.now()
        
        assert recovery_service.is_service_degraded(service_name)
        
        recovery_service.clear_service_degradation(service_name)
        assert not recovery_service.is_service_degraded(service_name)
        
        print("✅ Error recovery basic functionality works")
        return True
        
    except Exception as e:
        print(f"❌ Error recovery test failed: {e}")
        return False

def test_error_middleware():
    """Test basic error middleware functionality"""
    try:
        from app.middleware.error_middleware import ErrorHandlingMiddleware
        from starlette.applications import Starlette
        from sqlalchemy.exc import SQLAlchemyError
        from app.models.enums import ErrorType
        
        app = Starlette()
        middleware = ErrorHandlingMiddleware(app)
        
        # Test error classification
        db_error = SQLAlchemyError("Database error")
        error_type = middleware._classify_error_type(db_error)
        assert error_type == ErrorType.DATABASE
        
        print("✅ Error middleware basic functionality works")
        return True
        
    except Exception as e:
        print(f"❌ Error middleware test failed: {e}")
        return False

async def test_conversation_error_handler():
    """Test conversation error handler"""
    try:
        from app.services.error_handler import ConversationErrorHandler
        from app.models.schemas import Message
        from app.models.enums import MessageType
        
        handler = ConversationErrorHandler()
        
        # Create test message
        message = Message(
            id="test_msg",
            user_id="test_user",
            content="test content",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        # Test error handling
        error = ValueError("Test error")
        response = await handler.handle_conversation_error(error, "test_user", message)
        
        assert response is not None
        assert response.message_type == MessageType.TEXT
        assert len(response.content) > 0
        
        print("✅ Conversation error handler basic functionality works")
        return True
        
    except Exception as e:
        print(f"❌ Conversation error handler test failed: {e}")
        return False

async def main():
    """Run all basic tests"""
    print("🧪 Running Basic Error Handling Tests")
    print("=" * 50)
    
    tests = [
        ("Error Monitoring", test_error_monitoring),
        ("Error Recovery", test_error_recovery),
        ("Error Middleware", test_error_middleware),
        ("Conversation Error Handler", test_conversation_error_handler)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All basic error handling tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)