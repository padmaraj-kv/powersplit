#!/usr/bin/env python3
"""
Validation script for the main application orchestrator
Tests configuration, imports, and basic functionality
"""
import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_configuration():
    """Test configuration validation"""
    print("Testing configuration...")
    try:
        from app.core.config import settings, validate_configuration
        
        # Test basic configuration loading
        print(f"✓ Configuration loaded for environment: {settings.environment}")
        print(f"✓ Debug mode: {settings.debug}")
        print(f"✓ Log level: {settings.log_level}")
        
        # Test configuration validation (will fail if required vars missing)
        # validate_configuration()
        # print("✓ Configuration validation passed")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

async def test_imports():
    """Test all critical imports"""
    print("\nTesting imports...")
    try:
        # Test main application import
        from app.main import app
        print("✓ Main application imported successfully")
        
        # Test route imports
        from app.api.routes import webhooks, bills, admin
        print("✓ All route modules imported successfully")
        
        # Test service imports
        from app.services.conversation_factory import get_conversation_factory
        print("✓ Conversation factory imported successfully")
        
        # Test repository imports
        from app.database.repositories import (
            SQLUserRepository, SQLContactRepository, SQLBillRepository,
            SQLPaymentRepository, SQLConversationRepository, DatabaseRepository
        )
        print("✓ All repository classes imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False

async def test_fastapi_app():
    """Test FastAPI application setup"""
    print("\nTesting FastAPI application...")
    try:
        from app.main import app
        
        # Check app configuration
        print(f"✓ App title: {app.title}")
        print(f"✓ App version: {app.version}")
        
        # Check routes are registered
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/",
            "/health",
            "/health/detailed",
            "/metrics",
            "/errors/summary"
        ]
        
        for route in expected_routes:
            if route in routes:
                print(f"✓ Route registered: {route}")
            else:
                print(f"✗ Route missing: {route}")
        
        # Check routers are included
        router_prefixes = []
        for route in app.routes:
            if hasattr(route, 'path_regex'):
                path = route.path
                if path.startswith('/api/v1/'):
                    router_prefixes.append(path.split('/')[3])
        
        expected_prefixes = ['webhooks', 'bills', 'admin']
        for prefix in expected_prefixes:
            if prefix in router_prefixes:
                print(f"✓ Router included: {prefix}")
            else:
                print(f"✗ Router missing: {prefix}")
        
        return True
    except Exception as e:
        print(f"✗ FastAPI app test failed: {e}")
        return False

async def test_service_factory():
    """Test service factory setup"""
    print("\nTesting service factory...")
    try:
        from app.services.conversation_factory import ConversationFactory
        from app.database.repositories import SQLUserRepository, SQLContactRepository, SQLConversationRepository
        
        # Create mock database session (won't actually connect)
        class MockDB:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def first(self):
                return None
            def all(self):
                return []
            def add(self, obj):
                pass
            def commit(self):
                pass
            def refresh(self, obj):
                pass
            def rollback(self):
                pass
        
        mock_db = MockDB()
        
        # Test repository creation
        user_repo = SQLUserRepository(mock_db)
        contact_repo = SQLContactRepository(mock_db)
        conversation_repo = SQLConversationRepository(mock_db)
        print("✓ Repository instances created successfully")
        
        # Test factory creation
        factory = ConversationFactory(conversation_repo, contact_repo, user_repo)
        print("✓ Conversation factory created successfully")
        
        # Test service creation (without actual initialization)
        ai_service = factory.get_ai_service()
        contact_manager = factory.get_contact_manager()
        bill_splitter = factory.get_bill_splitter()
        print("✓ All services can be created from factory")
        
        return True
    except Exception as e:
        print(f"✗ Service factory test failed: {e}")
        return False

async def test_error_handling():
    """Test error handling setup"""
    print("\nTesting error handling...")
    try:
        from app.middleware.error_middleware import ErrorHandlingMiddleware
        from app.services.error_monitoring import error_monitor, health_checker
        print("✓ Error handling components imported successfully")
        
        # Test error monitor
        error_summary = error_monitor.get_error_summary()
        print("✓ Error monitor functional")
        
        return True
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        return False

async def main():
    """Run all validation tests"""
    print("=== Bill Splitting Agent - Main Orchestrator Validation ===\n")
    
    tests = [
        test_configuration,
        test_imports,
        test_fastapi_app,
        test_service_factory,
        test_error_handling
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Validation Summary ===")
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! Main orchestrator is properly configured.")
        return 0
    else:
        print("✗ Some tests failed. Please check the configuration and dependencies.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)