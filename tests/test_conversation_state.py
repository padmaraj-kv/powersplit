"""
Tests for conversation state management
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, AsyncMock
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import Message, ConversationState
from app.services.conversation_manager import ConversationManager
from app.services.state_machine import ConversationStateMachine
from app.services.error_handler import ConversationErrorHandler
from app.services.step_handlers import InitialStepHandler
from app.interfaces.repositories import ConversationRepository


class TestConversationStateManagement:
    """Test conversation state management functionality"""
    
    @pytest.fixture
    def mock_conversation_repo(self):
        """Mock conversation repository"""
        repo = Mock(spec=ConversationRepository)
        repo.get_conversation_state = AsyncMock(return_value=None)
        repo.create_conversation_state = AsyncMock()
        repo.update_conversation_state = AsyncMock()
        repo.delete_conversation_state = AsyncMock(return_value=True)
        repo.cleanup_expired_states = AsyncMock(return_value=0)
        return repo
    
    @pytest.fixture
    def mock_state_machine(self):
        """Mock state machine"""
        machine = Mock(spec=ConversationStateMachine)
        machine.process_message = AsyncMock()
        return machine
    
    @pytest.fixture
    def error_handler(self):
        """Real error handler for testing"""
        return ConversationErrorHandler()
    
    @pytest.fixture
    def conversation_manager(self, mock_conversation_repo, mock_state_machine, error_handler):
        """Conversation manager with mocked dependencies"""
        return ConversationManager(
            conversation_repo=mock_conversation_repo,
            state_machine=mock_state_machine,
            error_handler=error_handler
        )
    
    @pytest.mark.asyncio
    async def test_create_new_conversation_state(self, conversation_manager):
        """Test creating new conversation state"""
        user_id = str(uuid4())
        session_id = "test_session"
        
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        
        assert state.user_id == user_id
        assert state.session_id == session_id
        assert state.current_step == ConversationStep.INITIAL
        assert state.retry_count == 0
        assert "session_started" in state.context
    
    @pytest.mark.asyncio
    async def test_state_validation(self, conversation_manager):
        """Test conversation state validation"""
        # Valid state
        valid_state = ConversationState(
            user_id=str(uuid4()),
            session_id="test_session",
            current_step=ConversationStep.INITIAL,
            context={"test": "data"}
        )
        
        is_valid = await conversation_manager._validate_state(valid_state)
        assert is_valid is True
        
        # Invalid state - missing user_id
        invalid_state = ConversationState(
            user_id="",
            session_id="test_session",
            current_step=ConversationStep.INITIAL
        )
        
        is_valid = await conversation_manager._validate_state(invalid_state)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_state_expiry_check(self, conversation_manager):
        """Test conversation state expiry checking"""
        # Non-expired state
        recent_state = ConversationState(
            user_id=str(uuid4()),
            session_id="test_session",
            current_step=ConversationStep.INITIAL,
            updated_at=datetime.now()
        )
        
        is_expired = await conversation_manager._is_state_expired(recent_state)
        assert is_expired is False
        
        # Expired state
        old_state = ConversationState(
            user_id=str(uuid4()),
            session_id="test_session",
            current_step=ConversationStep.INITIAL,
            updated_at=datetime.now() - timedelta(hours=25)
        )
        
        is_expired = await conversation_manager._is_state_expired(old_state)
        assert is_expired is True
    
    @pytest.mark.asyncio
    async def test_context_validation_for_steps(self, conversation_manager):
        """Test context validation for different conversation steps"""
        # Initial step - no specific requirements
        is_valid = await conversation_manager._validate_context_for_step(
            ConversationStep.INITIAL, {}
        )
        assert is_valid is True
        
        # Extracting bill step - should have input type
        is_valid = await conversation_manager._validate_context_for_step(
            ConversationStep.EXTRACTING_BILL, {"input_type": "text"}
        )
        assert is_valid is True
        
        is_valid = await conversation_manager._validate_context_for_step(
            ConversationStep.EXTRACTING_BILL, {}
        )
        assert is_valid is False
        
        # Confirming bill step - should have bill data
        is_valid = await conversation_manager._validate_context_for_step(
            ConversationStep.CONFIRMING_BILL, {"bill_data": {"amount": 100}}
        )
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_error_recovery_with_retry(self, conversation_manager, mock_state_machine):
        """Test error recovery with retry mechanism"""
        user_id = str(uuid4())
        message = Message(
            id="test_msg",
            user_id=user_id,
            content="test message",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        # Mock state machine to raise error first time, succeed second time
        mock_state_machine.process_message.side_effect = [
            Exception("Test error"),
            Mock(response=Mock(content="Success"))
        ]
        
        # First call should handle error gracefully
        response = await conversation_manager.process_message(user_id, message)
        assert "error" in response.content.lower() or "try again" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_conversation_reset(self, conversation_manager):
        """Test conversation reset functionality"""
        user_id = str(uuid4())
        session_id = "test_session"
        
        # Reset conversation
        state = await conversation_manager.reset_conversation(user_id, session_id)
        
        assert state.current_step == ConversationStep.INITIAL
        assert state.retry_count == 0
        assert state.last_error is None
        assert "session_started" in state.context


class TestStateMachine:
    """Test state machine functionality"""
    
    @pytest.fixture
    def step_handlers(self):
        """Mock step handlers"""
        return {
            ConversationStep.INITIAL: Mock(spec=InitialStepHandler)
        }
    
    @pytest.fixture
    def state_machine(self, step_handlers):
        """State machine with mock handlers"""
        return ConversationStateMachine(step_handlers)
    
    def test_valid_transitions(self, state_machine):
        """Test valid state transitions"""
        # Initial to extracting bill should be valid
        is_valid = asyncio.run(
            state_machine._is_valid_transition(
                ConversationStep.INITIAL, 
                ConversationStep.EXTRACTING_BILL
            )
        )
        assert is_valid is True
        
        # Initial to completed should be invalid
        is_valid = asyncio.run(
            state_machine._is_valid_transition(
                ConversationStep.INITIAL, 
                ConversationStep.COMPLETED
            )
        )
        assert is_valid is False
    
    def test_step_descriptions(self, state_machine):
        """Test step descriptions"""
        description = state_machine.get_step_description(ConversationStep.INITIAL)
        assert "Ready to receive" in description
        
        description = state_machine.get_step_description(ConversationStep.EXTRACTING_BILL)
        assert "Processing bill" in description


class TestErrorHandler:
    """Test error handler functionality"""
    
    @pytest.fixture
    def error_handler(self):
        """Error handler instance"""
        return ConversationErrorHandler()
    
    @pytest.mark.asyncio
    async def test_retry_operation_success(self, error_handler):
        """Test successful retry operation"""
        call_count = 0
        
        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"
        
        result = await error_handler.retry_operation(operation, max_retries=3)
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_operation_failure(self, error_handler):
        """Test retry operation that ultimately fails"""
        async def operation():
            raise Exception("Persistent error")
        
        with pytest.raises(Exception, match="Persistent error"):
            await error_handler.retry_operation(operation, max_retries=2)
    
    @pytest.mark.asyncio
    async def test_error_classification(self, error_handler):
        """Test error classification"""
        from app.models.enums import ErrorType
        
        # Database error
        db_error = Exception("database connection failed")
        error_type = error_handler._classify_error(db_error)
        assert error_type == ErrorType.DATABASE
        
        # Validation error
        validation_error = Exception("invalid format provided")
        error_type = error_handler._classify_error(validation_error)
        assert error_type == ErrorType.VALIDATION
        
        # External service error
        service_error = Exception("API timeout occurred")
        error_type = error_handler._classify_error(service_error)
        assert error_type == ErrorType.EXTERNAL_SERVICE
    
    @pytest.mark.asyncio
    async def test_conversation_error_handling(self, error_handler):
        """Test conversation-specific error handling"""
        user_id = str(uuid4())
        message = Message(
            id="test_msg",
            user_id=user_id,
            content="test message",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        # Test input processing error
        input_error = Exception("failed to parse input")
        response = await error_handler.handle_conversation_error(input_error, user_id, message)
        
        assert response.content
        assert response.message_type == MessageType.TEXT
        assert "error_type" in response.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])