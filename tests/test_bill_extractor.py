"""
Tests for BillExtractor service
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from decimal import Decimal
from datetime import datetime

from app.services.bill_extractor import BillExtractor, BillExtractionError
from app.services.ai_service import AIService, AIServiceError
from app.models.schemas import (
    BillData, BillItem, ValidationResult, Message, Response
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
    """BillExtractor instance with mocked AI service"""
    return BillExtractor(ai_service=mock_ai_service)


@pytest.fixture
def sample_bill_data():
    """Sample bill data for testing"""
    return BillData(
        total_amount=Decimal('150.00'),
        description="Lunch at Pizza Palace",
        items=[
            BillItem(name="Margherita Pizza", amount=Decimal('120.00'), quantity=1),
            BillItem(name="Coke", amount=Decimal('30.00'), quantity=1)
        ],
        currency="INR",
        merchant="Pizza Palace",
        date=datetime(2024, 1, 15, 12, 30)
    )


@pytest.fixture
def text_message():
    """Sample text message"""
    return Message(
        id="msg_123",
        user_id="user_456",
        content="Bill from Pizza Palace for ₹150. Had Margherita Pizza ₹120 and Coke ₹30",
        message_type=MessageType.TEXT,
        timestamp=datetime.now(),
        metadata={}
    )


@pytest.fixture
def voice_message():
    """Sample voice message"""
    return Message(
        id="msg_124",
        user_id="user_456",
        content="",
        message_type=MessageType.VOICE,
        timestamp=datetime.now(),
        metadata={"audio_data": b"fake_audio_data"}
    )


@pytest.fixture
def image_message():
    """Sample image message"""
    return Message(
        id="msg_125",
        user_id="user_456",
        content="",
        message_type=MessageType.IMAGE,
        timestamp=datetime.now(),
        metadata={"image_data": b"fake_image_data"}
    )


class TestBillExtractor:
    """Test cases for BillExtractor"""
    
    @pytest.mark.asyncio
    async def test_extract_from_text_success(self, bill_extractor, mock_ai_service, text_message, sample_bill_data):
        """Test successful text extraction"""
        mock_ai_service.extract_from_text.return_value = sample_bill_data
        
        result = await bill_extractor.extract_bill_data(text_message)
        
        assert result.total_amount == Decimal('150.00')
        assert result.merchant == "Pizza Palace"
        assert len(result.items) == 2
        mock_ai_service.extract_from_text.assert_called_once_with(text_message.content)
    
    @pytest.mark.asyncio
    async def test_extract_from_voice_success(self, bill_extractor, mock_ai_service, voice_message, sample_bill_data):
        """Test successful voice extraction"""
        mock_ai_service.extract_from_voice.return_value = sample_bill_data
        
        result = await bill_extractor.extract_bill_data(voice_message)
        
        assert result.total_amount == Decimal('150.00')
        mock_ai_service.extract_from_voice.assert_called_once_with(b"fake_audio_data")
    
    @pytest.mark.asyncio
    async def test_extract_from_image_success(self, bill_extractor, mock_ai_service, image_message, sample_bill_data):
        """Test successful image extraction"""
        mock_ai_service.extract_from_image.return_value = sample_bill_data
        
        result = await bill_extractor.extract_bill_data(image_message)
        
        assert result.total_amount == Decimal('150.00')
        mock_ai_service.extract_from_image.assert_called_once_with(b"fake_image_data")
    
    @pytest.mark.asyncio
    async def test_extract_voice_missing_audio_data(self, bill_extractor, voice_message):
        """Test voice extraction with missing audio data"""
        voice_message.metadata = {}  # No audio data
        
        with pytest.raises(BillExtractionError, match="No audio data found"):
            await bill_extractor.extract_bill_data(voice_message)
    
    @pytest.mark.asyncio
    async def test_extract_image_missing_image_data(self, bill_extractor, image_message):
        """Test image extraction with missing image data"""
        image_message.metadata = {}  # No image data
        
        with pytest.raises(BillExtractionError, match="No image data found"):
            await bill_extractor.extract_bill_data(image_message)
    
    @pytest.mark.asyncio
    async def test_extract_ai_service_error(self, bill_extractor, mock_ai_service, text_message):
        """Test handling of AI service errors"""
        mock_ai_service.extract_from_text.side_effect = AIServiceError("Service unavailable")
        
        with pytest.raises(BillExtractionError, match="Failed to process text input"):
            await bill_extractor.extract_bill_data(text_message)
    
    @pytest.mark.asyncio
    async def test_validate_bill_data_success(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test successful bill data validation"""
        ai_validation = ValidationResult(is_valid=True, errors=[], warnings=[])
        mock_ai_service.validate_extraction.return_value = ai_validation
        
        result = await bill_extractor.validate_bill_data(sample_bill_data)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_bill_data_with_errors(self, bill_extractor, mock_ai_service):
        """Test validation with business rule errors"""
        invalid_bill = BillData(
            total_amount=Decimal('0.00'),  # Invalid amount
            description="",
            items=[],
            currency="INR"
        )
        
        ai_validation = ValidationResult(is_valid=True, errors=[], warnings=[])
        mock_ai_service.validate_extraction.return_value = ai_validation
        
        result = await bill_extractor.validate_bill_data(invalid_bill)
        
        assert result.is_valid is False
        assert any("Amount must be at least" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_items_total_mismatch(self, bill_extractor, mock_ai_service):
        """Test validation with items total mismatch"""
        mismatched_bill = BillData(
            total_amount=Decimal('100.00'),
            description="Test bill",
            items=[
                BillItem(name="Item 1", amount=Decimal('50.00'), quantity=1),
                BillItem(name="Item 2", amount=Decimal('30.00'), quantity=1)  # Total: 80, but bill total is 100
            ],
            currency="INR"
        )
        
        ai_validation = ValidationResult(is_valid=True, errors=[], warnings=[])
        mock_ai_service.validate_extraction.return_value = ai_validation
        
        result = await bill_extractor.validate_bill_data(mismatched_bill)
        
        assert result.is_valid is True  # Should be valid but with warnings
        assert any("doesn't match bill total" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_generate_clarifying_questions_ai_success(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test AI-generated clarifying questions"""
        expected_questions = ["What was the total amount?", "Which restaurant was this from?"]
        mock_ai_service.generate_clarifying_questions.return_value = expected_questions
        
        result = await bill_extractor.generate_clarifying_questions(sample_bill_data)
        
        assert result == expected_questions
        mock_ai_service.generate_clarifying_questions.assert_called_once_with(sample_bill_data)
    
    @pytest.mark.asyncio
    async def test_generate_clarifying_questions_fallback(self, bill_extractor, mock_ai_service):
        """Test fallback clarifying questions when AI fails"""
        incomplete_bill = BillData(
            total_amount=Decimal('0.00'),  # Missing amount
            description="",  # Missing description
            items=[],
            currency="INR",
            merchant=None  # Missing merchant
        )
        
        mock_ai_service.generate_clarifying_questions.side_effect = Exception("AI service failed")
        
        result = await bill_extractor.generate_clarifying_questions(incomplete_bill)
        
        assert len(result) > 0
        assert any("total amount" in question.lower() for question in result)
        assert any("restaurant" in question.lower() or "store" in question.lower() for question in result)
    
    @pytest.mark.asyncio
    async def test_create_bill_summary_complete(self, bill_extractor, sample_bill_data):
        """Test bill summary creation with complete data"""
        result = await bill_extractor.create_bill_summary(sample_bill_data)
        
        assert "📋 *Bill Summary*" in result
        assert "Pizza Palace" in result
        assert "₹150.00" in result
        assert "Margherita Pizza" in result
        assert "Coke" in result
        assert "Is this information correct?" in result
    
    @pytest.mark.asyncio
    async def test_create_bill_summary_minimal(self, bill_extractor):
        """Test bill summary with minimal data"""
        minimal_bill = BillData(
            total_amount=Decimal('50.00'),
            description="Simple bill",
            items=[],
            currency="INR"
        )
        
        result = await bill_extractor.create_bill_summary(minimal_bill)
        
        assert "₹50.00" in result
        assert "Simple bill" in result
        assert "📋 *Bill Summary*" in result
    
    @pytest.mark.asyncio
    async def test_process_confirmation_yes(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test processing positive confirmation"""
        confirm_message = Message(
            id="msg_confirm",
            user_id="user_456",
            content="yes",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        mock_ai_service.recognize_intent.return_value = {
            "intent": "confirm",
            "confidence": 0.9,
            "entities": {},
            "next_action": "proceed"
        }
        
        is_confirmed, error_msg = await bill_extractor.process_bill_confirmation(confirm_message, sample_bill_data)
        
        assert is_confirmed is True
        assert error_msg is None
    
    @pytest.mark.asyncio
    async def test_process_confirmation_no(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test processing negative confirmation"""
        reject_message = Message(
            id="msg_reject",
            user_id="user_456",
            content="no, the amount is wrong",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        mock_ai_service.recognize_intent.return_value = {
            "intent": "modify",
            "confidence": 0.8,
            "entities": {},
            "next_action": "ask_changes"
        }
        
        is_confirmed, error_msg = await bill_extractor.process_bill_confirmation(reject_message, sample_bill_data)
        
        assert is_confirmed is False
        assert "What would you like to change" in error_msg
    
    @pytest.mark.asyncio
    async def test_process_confirmation_ambiguous(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test processing ambiguous confirmation"""
        ambiguous_message = Message(
            id="msg_ambiguous",
            user_id="user_456",
            content="maybe",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        mock_ai_service.recognize_intent.return_value = {
            "intent": "general_question",
            "confidence": 0.3,
            "entities": {},
            "next_action": "ask_clarification"
        }
        
        is_confirmed, error_msg = await bill_extractor.process_bill_confirmation(ambiguous_message, sample_bill_data)
        
        assert is_confirmed is False
        assert "didn't understand" in error_msg
    
    @pytest.mark.asyncio
    async def test_process_confirmation_fallback(self, bill_extractor, mock_ai_service, sample_bill_data):
        """Test confirmation processing with AI service failure"""
        confirm_message = Message(
            id="msg_confirm",
            user_id="user_456",
            content="yes, looks good",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        mock_ai_service.recognize_intent.side_effect = Exception("AI service failed")
        
        is_confirmed, error_msg = await bill_extractor.process_bill_confirmation(confirm_message, sample_bill_data)
        
        assert is_confirmed is True  # Should fallback to keyword matching
        assert error_msg is None
    
    @pytest.mark.asyncio
    async def test_normalization_precision(self, bill_extractor, mock_ai_service):
        """Test amount precision normalization"""
        bill_with_precision = BillData(
            total_amount=Decimal('150.999'),  # Should be normalized to 151.00
            description="  Test Bill  ",  # Should be stripped
            items=[
                BillItem(name="  Item 1  ", amount=Decimal('50.555'), quantity=0)  # Should normalize quantity to 1
            ],
            currency="INR"
        )
        
        mock_ai_service.extract_from_text.return_value = bill_with_precision
        
        text_message = Message(
            id="msg_123",
            user_id="user_456",
            content="test bill",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        result = await bill_extractor.extract_bill_data(text_message)
        
        assert result.total_amount == Decimal('151.00')
        assert result.description == "Test Bill"
        assert result.items[0].name == "Item 1"
        assert result.items[0].amount == Decimal('50.56')
        assert result.items[0].quantity == 1
    
    def test_unsupported_message_type(self, bill_extractor):
        """Test handling of unsupported message types"""
        # Create a message with an invalid type by bypassing enum validation
        invalid_message = Message(
            id="msg_invalid",
            user_id="user_456",
            content="test",
            message_type="INVALID_TYPE",  # This would normally be caught by enum validation
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Manually set the message type to bypass validation
        invalid_message.message_type = "INVALID_TYPE"
        
        with pytest.raises(BillExtractionError, match="Unsupported message type"):
            # Use asyncio.run since this is not an async test method
            import asyncio
            asyncio.run(bill_extractor.extract_bill_data(invalid_message))