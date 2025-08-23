#!/usr/bin/env python3
"""
Validation script for conversation state management implementation
Tests the core functionality without requiring pytest
"""
import sys
import asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

# Add app to path
sys.path.insert(0, '.')

try:
    from app.models.enums import ConversationStep, MessageType
    from app.models.schemas import Message, ConversationState
    from app.services.conversation_manager import ConversationManager
    from app.services.state_machine import ConversationStateMachine
    from app.services.error_handler import ConversationErrorHandler
    from app.services.step_handlers import InitialStepHandler
    from app.services.conversation_factory import ConversationFactory
    from app.interfaces.repositories import ConversationRepository
    
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


async def test_conversation_state_creation():
    """Test basic conversation state creation"""
    print("\n🧪 Testing conversation state creation...")
    
    try:
        state = ConversationState(
            user_id=str(uuid4()),
            session_id="test_session",
            current_step=ConversationStep.INITIAL,
            context={"test": "data"}
        )
        
        assert state.current_step == ConversationStep.INITIAL
        assert state.context["test"] == "data"
        assert state.retry_count == 0
        
        print("✅ Conversation state creation works")
        return True
    except Exception as e:
        print(f"❌ Conversation state creation failed: {e}")
        return False


async def test_state_machine_transitions():
    """Test state machine transition validation"""
    print("\n🧪 Testing state machine transitions...")
    
    try:
        # Create mock step handlers
        step_handlers = {
            ConversationStep.INITIAL: InitialStepHandler()
        }
        
        state_machine = ConversationStateMachine(step_handlers)
        
        # Test valid transition
        is_valid = await state_machine._is_valid_transition(
            ConversationStep.INITIAL, 
            ConversationStep.EXTRACTING_BILL
        )
        assert is_valid is True
        
        # Test invalid transition
        is_valid = await state_machine._is_valid_transition(
            ConversationStep.INITIAL, 
            ConversationStep.COMPLETED
        )
        assert is_valid is False
        
        print("✅ State machine transitions work")
        return True
    except Exception as e:
        print(f"❌ State machine transitions failed: {e}")
        return False


async def test_error_handler():
    """Test error handler functionality"""
    print("\n🧪 Testing error handler...")
    
    try:
        error_handler = ConversationErrorHandler()
        
        # Test error classification
        from app.models.enums import ErrorType
        
        db_error = Exception("database connection failed")
        error_type = error_handler._classify_error(db_error)
        assert error_type == ErrorType.DATABASE
        
        # Test retry mechanism
        call_count = 0
        
        async def test_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"
        
        result = await error_handler.retry_operation(test_operation, max_retries=3)
        assert result == "success"
        assert call_count == 2
        
        print("✅ Error handler works")
        return True
    except Exception as e:
        print(f"❌ Error handler failed: {e}")
        return False


async def test_conversation_manager():
    """Test conversation manager with mocked dependencies"""
    print("\n🧪 Testing conversation manager...")
    
    try:
        # Create mock repository
        mock_repo = Mock(spec=ConversationRepository)
        mock_repo.get_conversation_state = AsyncMock(return_value=None)
        mock_repo.create_conversation_state = AsyncMock()
        mock_repo.update_conversation_state = AsyncMock()
        mock_repo.delete_conversation_state = AsyncMock(return_value=True)
        
        # Create conversation factory
        factory = ConversationFactory(mock_repo)
        conversation_manager = factory.create_conversation_manager()
        
        # Test getting conversation state
        user_id = str(uuid4())
        session_id = "test_session"
        
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        
        assert state.user_id == user_id
        assert state.session_id == session_id
        assert state.current_step == ConversationStep.INITIAL
        
        # Test state validation
        is_valid = await conversation_manager._validate_state(state)
        assert is_valid is True
        
        print("✅ Conversation manager works")
        return True
    except Exception as e:
        print(f"❌ Conversation manager failed: {e}")
        return False


async def test_step_handlers():
    """Test step handlers"""
    print("\n🧪 Testing step handlers...")
    
    try:
        handler = InitialStepHandler()
        
        # Create test state and message
        state = ConversationState(
            user_id=str(uuid4()),
            session_id="test_session",
            current_step=ConversationStep.INITIAL,
            context={}
        )
        
        message = Message(
            id="test_msg",
            user_id=state.user_id,
            content="I have a bill for ₹500",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        # Test message handling
        result = await handler.handle_message(state, message)
        
        assert result.response.content
        assert result.response.message_type == MessageType.TEXT
        
        print("✅ Step handlers work")
        return True
    except Exception as e:
        print(f"❌ Step handlers failed: {e}")
        return False


async def test_conversation_factory():
    """Test conversation factory"""
    print("\n🧪 Testing conversation factory...")
    
    try:
        # Create mock repository
        mock_repo = Mock(spec=ConversationRepository)
        
        factory = ConversationFactory(mock_repo)
        
        # Test component creation
        state_machine = factory.get_state_machine()
        assert isinstance(state_machine, ConversationStateMachine)
        
        error_handler = factory.get_error_handler()
        assert isinstance(error_handler, ConversationErrorHandler)
        
        step_handlers = factory.get_step_handlers()
        assert ConversationStep.INITIAL in step_handlers
        
        conversation_manager = factory.create_conversation_manager()
        assert isinstance(conversation_manager, ConversationManager)
        
        print("✅ Conversation factory works")
        return True
    except Exception as e:
        print(f"❌ Conversation factory failed: {e}")
        return False


async def main():
    """Run all validation tests"""
    print("🚀 Starting conversation state management validation...")
    
    tests = [
        test_conversation_state_creation,
        test_state_machine_transitions,
        test_error_handler,
        test_conversation_manager,
        test_step_handlers,
        test_conversation_factory
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Validation Summary:")
    print(f"   Passed: {passed}/{total}")
    print(f"   Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All conversation state management components are working correctly!")
        return 0
    else:
        print("⚠️  Some components need attention")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)