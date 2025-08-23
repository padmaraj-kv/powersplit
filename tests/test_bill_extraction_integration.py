"""
Integration tests for bill extraction and processing logic
Tests the complete flow from message input to bill confirmation
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from decimal import Decimal
from datetime import datetime

from app.services.bill_extractor import BillExtractor, BillExtractionError
from app.services.step_handlers import BillExtractionHandler, BillConfirmationHandler
from app.services.ai_service import AIService, AIServiceError
from app.models.schemas import (
    BillData, BillItem, ValidationResult, Message, Response, ConversationState
)
from app.models.enums import MessageType, ConversationStep


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing"""
    ai_service = Mock(spec=AIService)
    ai_service.extract_from_text = AsyncMock()
    ai_service.extract_from_voice = AsyncMock()
    ai_service.extract_from_image = AsyncMock()
    ai_service.validate_extraction = AsyncMock()
    ai_service.generate_clarifying_questions = AsyncMock()
    ai_service.recognize_intent = AsyncMock()
    return ai_service


@pytest.fixture
def bill_extractor(mock_ai_service):
    """BillExtractor with mocked AI service"""
    return BillExtractor(ai_service=mock_ai_service)


@pytest.fixture
def extraction_handler(bill_extractor):
    """BillExtractionHandler with mocked dependencies"""
    return BillExtractionHandler(bill_extractor=bill_extractor)


@pytest.fixture
def confirmation_handler(bill_extractor):
    """BillConfirmationHandler with mocked dependencies"""
    return BillConfirmationHandler(bill_extractor=bill_extractor)


@pytest.fixture
def sample_conversation_state():
    """Sample conversation state for testing"""
    return ConversationState(
        user_id="user_123",
        session_id="session_456",
        current_step=ConversationStep.EXTRACTING_BILL,
        context={}
    )


@pytest.fixture
def confirmed_conversation_state():
    """Conversation state with confirmed bill data"""
    bill_data = BillData(
        total_amount=Decimal('150.00'),
        description="Lunch at Pizza Palace",
        items=[
            BillItem(name="Margherita Pizza", amount=Decimal('120.00'), quantity=1),
            BillItem(name="Coke", amount=Decimal('30.00'), quantity=1)
        ],
        currency="INR",
        merchant="Pizza Palace"
    )
    
    return ConversationState(
        user_id="user_123",
        session_id="session_456",
        current_step=ConversationStep.CONFIRMING_BILL,
        context={
            "bill_data": bill_data.dict(),
            "extraction_successful": True
        }
    )


class TestBillExtractionIntegration:
    """Integration tests for bill extraction flow"""
    
    @pytest.mark.asyncio
    async def test_successful_text_extraction_flow(self, extraction_handler, mock_ai_service, sample_conversation_state):
        """Test complete successful text extraction flow"""
        # Setup mock responses
        bill_data = BillData(
            total_amount=Decimal('150.00'),
            description="Lunch at Pizza Palace",
            items=[],
            currency="INR",
            merchant="Pizza Palace"
        )
        
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        mock_ai_service.extract_from_text.return_value = bill_data
        mock_ai_service.validate_extraction.return_value = validation_result
        
        # Create test message
        message = Message(
            id="msg_123",
            user_id="user_123",
            content="Bill from Pizza Palace for ₹150",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process message
        result = await extraction_handler.handle_message(sample_conversation_state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.CONFIRMING_BILL
        assert "Bill Summary" in result.response.content
        assert "₹150.00" in result.response.content
        assert "Pizza Palace" in result.response.content
        assert result.context_updates["extraction_successful"] is True
        assert "bill_data" in result.context_updates
    
    @pytest.mark.asyncio
    async def test_extraction_with_validation_errors(self, extraction_handler, mock_ai_service, sample_conversation_state):
        """Test extraction with validation errors requiring clarification"""
        # Setup mock responses
        invalid_bill = BillData(
            total_amount=Decimal('0.00'),  # Invalid amount
            description="",
            items=[],
            currency="INR"
        )
        
        validation_result = ValidationResult(
            is_valid=False,
            errors=["Amount must be greater than zero", "Description is required"],
            warnings=[]
        )
        
        mock_ai_service.extract_from_text.return_value = invalid_bill
        mock_ai_service.validate_extraction.return_value = validation_result
        
        # Create test message
        message = Message(
            id="msg_123",
            user_id="user_123",
            content="Had lunch today",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process message
        result = await extraction_handler.handle_message(sample_conversation_state, message)
        
        # Verify results
        assert result.next_step is None  # Stay in same step
        assert "clarify" in result.response.content.lower() or "need" in result.response.content.lower()
        assert result.context_updates["validation_errors"] == validation_result.errors
        assert "partial_bill_data" in result.context_updates
    
    @pytest.mark.asyncio
    async def test_extraction_failure_with_clarifying_questions(self, extraction_handler, mock_ai_service, sample_conversation_state):
        """Test extraction failure leading to clarifying questions"""
        # Setup mock to fail extraction
        mock_ai_service.extract_from_text.side_effect = AIServiceError("Could not extract bill information")
        
        # Setup clarifying questions
        mock_ai_service.generate_clarifying_questions.return_value = [
            "What was the total amount of the bill?",
            "Which restaurant or store was this from?"
        ]
        
        # Create test message
        message = Message(
            id="msg_123",
            user_id="user_123",
            content="had food",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process message
        result = await extraction_handler.handle_message(sample_conversation_state, message)
        
        # Verify results
        assert result.next_step is None  # Stay in same step
        assert "total amount" in result.response.content
        assert "restaurant" in result.response.content
        assert result.context_updates["awaiting_clarification"] is True
        assert result.context_updates["attempt_count"] == 1
    
    @pytest.mark.asyncio
    async def test_clarification_response_handling(self, extraction_handler, mock_ai_service):
        """Test handling of clarification responses"""
        # Setup conversation state awaiting clarification
        state = ConversationState(
            user_id="user_123",
            session_id="session_456",
            current_step=ConversationStep.EXTRACTING_BILL,
            context={
                "awaiting_clarification": True,
                "attempt_count": 1,
                "partial_bill_data": {
                    "total_amount": 0.0,
                    "description": "",
                    "items": [],
                    "currency": "INR"
                }
            }
        )
        
        # Setup mock responses for clarification
        complete_bill = BillData(
            total_amount=Decimal('150.00'),
            description="Pizza Palace lunch",
            items=[],
            currency="INR",
            merchant="Pizza Palace"
        )
        
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        mock_ai_service.extract_from_text.return_value = complete_bill
        mock_ai_service.validate_extraction.return_value = validation_result
        
        # Create clarification message
        message = Message(
            id="msg_clarify",
            user_id="user_123",
            content="Total was ₹150 from Pizza Palace",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process clarification
        result = await extraction_handler.handle_message(state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.CONFIRMING_BILL
        assert "Bill Summary" in result.response.content
        assert result.context_updates["extraction_successful"] is True
        assert result.context_updates["awaiting_clarification"] is False
    
    @pytest.mark.asyncio
    async def test_voice_message_extraction(self, extraction_handler, mock_ai_service, sample_conversation_state):
        """Test voice message extraction"""
        # Setup mock responses
        bill_data = BillData(
            total_amount=Decimal('200.00'),
            description="Dinner at restaurant",
            items=[],
            currency="INR"
        )
        
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        mock_ai_service.extract_from_voice.return_value = bill_data
        mock_ai_service.validate_extraction.return_value = validation_result
        
        # Create voice message
        message = Message(
            id="msg_voice",
            user_id="user_123",
            content="",
            message_type=MessageType.VOICE,
            timestamp=datetime.now(),
            metadata={"audio_data": b"fake_audio_data"}
        )
        
        # Process message
        result = await extraction_handler.handle_message(sample_conversation_state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.CONFIRMING_BILL
        assert "₹200.00" in result.response.content
        mock_ai_service.extract_from_voice.assert_called_once_with(b"fake_audio_data")
    
    @pytest.mark.asyncio
    async def test_image_message_extraction(self, extraction_handler, mock_ai_service, sample_conversation_state):
        """Test image message extraction"""
        # Setup mock responses
        bill_data = BillData(
            total_amount=Decimal('300.00'),
            description="Restaurant bill",
            items=[
                BillItem(name="Pasta", amount=Decimal('250.00'), quantity=1),
                BillItem(name="Drink", amount=Decimal('50.00'), quantity=1)
            ],
            currency="INR",
            merchant="Italian Restaurant"
        )
        
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        mock_ai_service.extract_from_image.return_value = bill_data
        mock_ai_service.validate_extraction.return_value = validation_result
        
        # Create image message
        message = Message(
            id="msg_image",
            user_id="user_123",
            content="",
            message_type=MessageType.IMAGE,
            timestamp=datetime.now(),
            metadata={"image_data": b"fake_image_data"}
        )
        
        # Process message
        result = await extraction_handler.handle_message(sample_conversation_state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.CONFIRMING_BILL
        assert "₹300.00" in result.response.content
        assert "Italian Restaurant" in result.response.content
        assert "Pasta" in result.response.content
        mock_ai_service.extract_from_image.assert_called_once_with(b"fake_image_data")


class TestBillConfirmationIntegration:
    """Integration tests for bill confirmation flow"""
    
    @pytest.mark.asyncio
    async def test_positive_confirmation(self, confirmation_handler, mock_ai_service, confirmed_conversation_state):
        """Test positive bill confirmation"""
        # Setup mock intent recognition
        mock_ai_service.recognize_intent.return_value = {
            "intent": "confirm",
            "confidence": 0.9,
            "entities": {},
            "next_action": "proceed"
        }
        
        # Create confirmation message
        message = Message(
            id="msg_confirm",
            user_id="user_123",
            content="yes, that's correct",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process confirmation
        result = await confirmation_handler.handle_message(confirmed_conversation_state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.COLLECTING_CONTACTS
        assert "confirmed" in result.response.content.lower()
        assert "contact details" in result.response.content.lower()
        assert result.context_updates["bill_confirmed"] is True
    
    @pytest.mark.asyncio
    async def test_negative_confirmation(self, confirmation_handler, mock_ai_service, confirmed_conversation_state):
        """Test negative bill confirmation (user wants changes)"""
        # Setup mock intent recognition
        mock_ai_service.recognize_intent.return_value = {
            "intent": "modify",
            "confidence": 0.8,
            "entities": {},
            "next_action": "ask_changes"
        }
        
        # Create rejection message
        message = Message(
            id="msg_reject",
            user_id="user_123",
            content="no, the amount is wrong",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process confirmation
        result = await confirmation_handler.handle_message(confirmed_conversation_state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.EXTRACTING_BILL
        assert "change" in result.response.content.lower()
        assert result.context_updates["bill_rejected"] is True
    
    @pytest.mark.asyncio
    async def test_ambiguous_confirmation(self, confirmation_handler, mock_ai_service, confirmed_conversation_state):
        """Test ambiguous confirmation response"""
        # Setup mock intent recognition for ambiguous response
        mock_ai_service.recognize_intent.return_value = {
            "intent": "general_question",
            "confidence": 0.3,
            "entities": {},
            "next_action": "ask_clarification"
        }
        
        # Create ambiguous message
        message = Message(
            id="msg_ambiguous",
            user_id="user_123",
            content="maybe, I'm not sure",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process confirmation
        result = await confirmation_handler.handle_message(confirmed_conversation_state, message)
        
        # Verify results
        assert result.next_step is None  # Stay in same step
        assert "didn't understand" in result.response.content.lower()
        assert result.context_updates["clarification_requested"] is True
    
    @pytest.mark.asyncio
    async def test_confirmation_with_missing_bill_data(self, confirmation_handler, mock_ai_service):
        """Test confirmation handler with missing bill data"""
        # Create state without bill data
        state = ConversationState(
            user_id="user_123",
            session_id="session_456",
            current_step=ConversationStep.CONFIRMING_BILL,
            context={}  # No bill_data
        )
        
        message = Message(
            id="msg_confirm",
            user_id="user_123",
            content="yes",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process confirmation
        result = await confirmation_handler.handle_message(state, message)
        
        # Verify results
        assert result.next_step == ConversationStep.EXTRACTING_BILL
        assert "don't have any bill information" in result.response.content
        assert result.context_updates["error"] == "missing_bill_data"
    
    @pytest.mark.asyncio
    async def test_confirmation_with_ai_service_failure(self, confirmation_handler, mock_ai_service, confirmed_conversation_state):
        """Test confirmation handling when AI service fails"""
        # Setup AI service to fail
        mock_ai_service.recognize_intent.side_effect = Exception("AI service unavailable")
        
        # Create confirmation message with clear positive keywords
        message = Message(
            id="msg_confirm",
            user_id="user_123",
            content="yes, looks good to me",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Process confirmation
        result = await confirmation_handler.handle_message(confirmed_conversation_state, message)
        
        # Verify results - should fallback to keyword matching
        assert result.next_step == ConversationStep.COLLECTING_CONTACTS
        assert "confirmed" in result.response.content.lower()
        assert result.context_updates["bill_confirmed"] is True