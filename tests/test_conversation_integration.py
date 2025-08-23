"""
Integration tests for conversation state management with database
"""
import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.database import User, ConversationState as DBConversationState
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import Message, ConversationState
from app.database.repositories import SQLConversationRepository
from app.services.conversation_manager import ConversationManager
from app.services.state_machine import ConversationStateMachine
from app.services.error_handler import ConversationErrorHandler
from app.services.step_handlers import InitialStepHandler
from app.services.conversation_factory import ConversationFactory


class TestConversationIntegration:
    """Integration tests for conversation state management"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
    
    @pytest.fixture
    def test_user(self, db_session):
        """Create a test user"""
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def conversation_repo(self, db_session):
        """Create conversation repository"""
        return SQLConversationRepository(db_session)
    
    @pytest.fixture
    def conversation_factory(self, conversation_repo):
        """Create conversation factory"""
        return ConversationFactory(conversation_repo)
    
    @pytest.mark.asyncio
    async def test_conversation_state_persistence(self, conversation_repo, test_user):
        """Test conversation state persistence to database"""
        user_id = test_user.id
        session_id = "test_session"
        
        # Create conversation state
        context = {"test": "data", "step_info": {"current": "initial"}}
        db_state = await conversation_repo.create_conversation_state(
            user_id=user_id,
            session_id=session_id,
            current_step="initial",
            context=context
        )
        
        assert db_state.user_id == user_id
        assert db_state.session_id == session_id
        assert db_state.current_step == "initial"
        assert db_state.context == context
        
        # Retrieve conversation state
        retrieved_state = await conversation_repo.get_conversation_state(user_id, session_id)
        assert retrieved_state is not None
        assert retrieved_state.id == db_state.id
        assert retrieved_state.context == context
        
        # Update conversation state
        new_context = {"test": "updated", "step_info": {"current": "extracting_bill"}}
        updated_state = await conversation_repo.update_conversation_state(
            user_id=user_id,
            session_id=session_id,
            current_step="extracting_bill",
            context=new_context
        )
        
        assert updated_state.current_step == "extracting_bill"
        assert updated_state.context == new_context
    
    @pytest.mark.asyncio
    async def test_conversation_manager_with_database(self, conversation_factory, test_user):
        """Test conversation manager with real database operations"""
        conversation_manager = conversation_factory.create_conversation_manager()
        
        user_id = str(test_user.id)
        session_id = "test_session"
        
        # Get initial conversation state
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        
        assert state.user_id == user_id
        assert state.session_id == session_id
        assert state.current_step == ConversationStep.INITIAL
        assert isinstance(state.context, dict)
        
        # Update state
        state.current_step = ConversationStep.EXTRACTING_BILL
        state.context["bill_info"] = {"amount": 100}
        
        updated_state = await conversation_manager.update_conversation_state(state)
        assert updated_state.current_step == ConversationStep.EXTRACTING_BILL
        assert updated_state.context["bill_info"]["amount"] == 100
        
        # Retrieve updated state
        retrieved_state = await conversation_manager.get_conversation_state(user_id, session_id)
        assert retrieved_state.current_step == ConversationStep.EXTRACTING_BILL
        assert retrieved_state.context["bill_info"]["amount"] == 100
    
    @pytest.mark.asyncio
    async def test_conversation_reset_with_database(self, conversation_factory, test_user):
        """Test conversation reset functionality with database"""
        conversation_manager = conversation_factory.create_conversation_manager()
        
        user_id = str(test_user.id)
        session_id = "test_session"
        
        # Create initial state with some data
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        state.current_step = ConversationStep.CONFIRMING_BILL
        state.context["bill_data"] = {"amount": 100}
        state.retry_count = 2
        await conversation_manager.update_conversation_state(state)
        
        # Reset conversation
        reset_state = await conversation_manager.reset_conversation(user_id, session_id)
        
        assert reset_state.current_step == ConversationStep.INITIAL
        assert reset_state.retry_count == 0
        assert reset_state.last_error is None
        assert "session_started" in reset_state.context
        assert "bill_data" not in reset_state.context
    
    @pytest.mark.asyncio
    async def test_state_validation_with_database(self, conversation_factory, test_user):
        """Test state validation with database operations"""
        conversation_manager = conversation_factory.create_conversation_manager()
        
        user_id = str(test_user.id)
        session_id = "test_session"
        
        # Create state with valid context for extracting bill step
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        state.current_step = ConversationStep.EXTRACTING_BILL
        state.context["input_type"] = "text"
        
        # Validate state
        is_valid = await conversation_manager._validate_state(state)
        assert is_valid is True
        
        # Create state with invalid context
        invalid_state = await conversation_manager.get_conversation_state(user_id, "invalid_session")
        invalid_state.current_step = ConversationStep.CONFIRMING_BILL
        # Missing required bill_data in context
        
        is_valid = await conversation_manager._validate_state(invalid_state)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_error_recovery_with_database(self, conversation_factory, test_user):
        """Test error recovery mechanisms with database"""
        conversation_manager = conversation_factory.create_conversation_manager()
        
        user_id = str(test_user.id)
        session_id = "test_session"
        
        # Create state and simulate error
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        state.retry_count = 2
        state.last_error = "Test error"
        
        # Update state with error
        updated_state = await conversation_manager.update_conversation_state(state)
        assert updated_state.retry_count == 2
        assert updated_state.last_error == "Test error"
        
        # Simulate successful operation (should reset retry count)
        state.retry_count = 0
        state.last_error = None
        final_state = await conversation_manager.update_conversation_state(state)
        assert final_state.retry_count == 0
        assert final_state.last_error is None
    
    def test_conversation_factory_initialization(self, conversation_repo):
        """Test conversation factory initialization"""
        factory = ConversationFactory(conversation_repo)
        
        # Test component creation
        state_machine = factory.get_state_machine()
        assert isinstance(state_machine, ConversationStateMachine)
        
        error_handler = factory.get_error_handler()
        assert isinstance(error_handler, ConversationErrorHandler)
        
        step_handlers = factory.get_step_handlers()
        assert ConversationStep.INITIAL in step_handlers
        assert isinstance(step_handlers[ConversationStep.INITIAL], InitialStepHandler)
        
        conversation_manager = factory.create_conversation_manager()
        assert isinstance(conversation_manager, ConversationManager)
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow_simulation(self, conversation_factory, test_user):
        """Test a complete conversation flow simulation"""
        conversation_manager = conversation_factory.create_conversation_manager()
        
        user_id = str(test_user.id)
        session_id = "test_session"
        
        # Step 1: Initial message
        initial_message = Message(
            id="msg_1",
            user_id=user_id,
            content="I have a bill for ₹500 for dinner",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        # Process initial message
        response = await conversation_manager.process_message(user_id, initial_message)
        assert response.content
        assert response.message_type == MessageType.TEXT
        
        # Check state after processing
        state = await conversation_manager.get_conversation_state(user_id, session_id)
        assert state.context.get("message_count", 0) >= 1
        
        # Step 2: Follow-up message
        followup_message = Message(
            id="msg_2",
            user_id=user_id,
            content="yes",
            message_type=MessageType.TEXT,
            timestamp=datetime.now()
        )
        
        response2 = await conversation_manager.process_message(user_id, followup_message)
        assert response2.content
        
        # Check final state
        final_state = await conversation_manager.get_conversation_state(user_id, session_id)
        assert final_state.context.get("message_count", 0) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])