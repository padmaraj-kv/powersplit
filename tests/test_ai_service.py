"""
Tests for AI service integration layer
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from app.services.ai_service import AIService, AIServiceError
from app.models.schemas import BillData, BillItem, Message, ValidationResult
from app.models.enums import MessageType, ConversationStep


class TestAIService:
    """Test cases for AI service integration"""
    
    @pytest.fixture
    def ai_service(self):
        """Create AI service instance for testing"""
        return AIService()
    
    @pytest.fixture
    def sample_bill_data(self):
        """Sample bill data for testing"""
        return BillData(
            total_amount=Decimal("150.00"),
            description="Lunch at Pizza Hut",
            merchant="Pizza Hut",
            items=[
                BillItem(name="Pizza", amount=Decimal("120.00"), quantity=1),
                BillItem(name="Coke", amount=Decimal("30.00"), quantity=1)
            ],
            currency="INR"
        )
    
    @pytest.fixture
    def sample_message(self):
        """Sample message for testing"""
        return Message(
            id="msg_123",
            user_id="user_123",
            content="I spent 150 rupees at Pizza Hut for lunch",
            message_type=MessageType.TEXT,
            timestamp="2024-01-01T12:00:00Z",
            metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_extract_from_text_success(self, ai_service, sample_bill_data):
        """Test successful text extraction"""
        with patch.object(ai_service.litellm_client, 'extract_bill_from_text', 
                         return_value=sample_bill_data) as mock_extract:
            
            result = await ai_service.extract_from_text("I spent 150 at Pizza Hut")
            
            assert result.total_amount == Decimal("150.00")
            assert result.merchant == "Pizza Hut"
            mock_extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_from_text_with_fallback(self, ai_service):
        """Test text extraction with fallback when LiteLLM fails"""
        with patch.object(ai_service.litellm_client, 'extract_bill_from_text', 
                         side_effect=Exception("LiteLLM failed")):
            
            result = await ai_service.extract_from_text("I spent ₹150 for lunch")
            
            assert result.total_amount == Decimal("150.00")
            assert result.description == "Bill from text message"
    
    @pytest.mark.asyncio
    async def test_extract_from_voice_success(self, ai_service, sample_bill_data):
        """Test successful voice extraction"""
        audio_data = b"fake_audio_data"
        transcript = "I spent 150 rupees at Pizza Hut"
        
        with patch.object(ai_service.sarvam_client, 'transcribe_audio', 
                         return_value=transcript) as mock_transcribe:
            with patch.object(ai_service, 'extract_from_text', 
                             return_value=sample_bill_data) as mock_extract_text:
                
                result = await ai_service.extract_from_voice(audio_data)
                
                assert result.total_amount == Decimal("150.00")
                mock_transcribe.assert_called_once_with(audio_data)
                mock_extract_text.assert_called_once_with(transcript)
    
    @pytest.mark.asyncio
    async def test_extract_from_image_success(self, ai_service, sample_bill_data):
        """Test successful image extraction"""
        image_data = b"fake_image_data"
        validation_result = {"is_valid": True, "issues": [], "suggestions": []}
        
        with patch.object(ai_service.gemini_client, 'validate_image_quality', 
                         return_value=validation_result):
            with patch.object(ai_service.gemini_client, 'extract_bill_from_image', 
                             return_value=sample_bill_data) as mock_extract:
                with patch.object(ai_service.gemini_client, 'enhance_bill_description', 
                                 return_value="Enhanced description"):
                    
                    result = await ai_service.extract_from_image(image_data)
                    
                    assert result.total_amount == Decimal("150.00")
                    assert result.description == "Enhanced description"
                    mock_extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_from_image_invalid_quality(self, ai_service):
        """Test image extraction with invalid image quality"""
        image_data = b"fake_image_data"
        validation_result = {
            "is_valid": False, 
            "issues": ["Image too small"], 
            "suggestions": ["Use higher resolution"]
        }
        
        with patch.object(ai_service.gemini_client, 'validate_image_quality', 
                         return_value=validation_result):
            
            with pytest.raises(AIServiceError) as exc_info:
                await ai_service.extract_from_image(image_data)
            
            assert "Image quality issues" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_extraction_success(self, ai_service, sample_bill_data):
        """Test successful validation"""
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        with patch.object(ai_service.litellm_client, 'validate_bill_data', 
                         return_value=validation_result) as mock_validate:
            
            result = await ai_service.validate_extraction(sample_bill_data)
            
            assert result.is_valid is True
            assert len(result.errors) == 0
            mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_extraction_with_fallback(self, ai_service, sample_bill_data):
        """Test validation with fallback when AI validation fails"""
        with patch.object(ai_service.litellm_client, 'validate_bill_data', 
                         side_effect=Exception("Validation failed")):
            
            result = await ai_service.validate_extraction(sample_bill_data)
            
            assert result.is_valid is True  # Should pass basic validation
    
    @pytest.mark.asyncio
    async def test_recognize_intent_success(self, ai_service, sample_message):
        """Test successful intent recognition"""
        intent_data = {
            "intent": "provide_bill_info",
            "confidence": 0.9,
            "entities": {"amounts": [150]},
            "next_action": "extract_bill"
        }
        
        with patch.object(ai_service.litellm_client, 'recognize_intent', 
                         return_value=intent_data) as mock_recognize:
            
            result = await ai_service.recognize_intent(sample_message, ConversationStep.INITIAL)
            
            assert result["intent"] == "provide_bill_info"
            assert result["confidence"] == 0.9
            mock_recognize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recognize_intent_with_fallback(self, ai_service, sample_message):
        """Test intent recognition with fallback"""
        with patch.object(ai_service.litellm_client, 'recognize_intent', 
                         side_effect=Exception("Intent recognition failed")):
            
            result = await ai_service.recognize_intent(sample_message, ConversationStep.INITIAL)
            
            assert result["intent"] == "general_question"
            assert result["confidence"] == 0.5
    
    @pytest.mark.asyncio
    async def test_generate_clarifying_questions(self, ai_service):
        """Test clarifying questions generation"""
        incomplete_bill = BillData(
            total_amount=Decimal("0.00"),  # Missing amount
            description="Some bill",
            items=[],
            currency="INR"
        )
        
        questions = ["What was the total amount?", "Which store was this from?"]
        
        with patch.object(ai_service.litellm_client, 'generate_clarifying_questions', 
                         return_value=questions) as mock_generate:
            
            result = await ai_service.generate_clarifying_questions(incomplete_bill)
            
            assert len(result) == 2
            assert "total amount" in result[0].lower()
            mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_all_services_healthy(self, ai_service):
        """Test health check when all services are healthy"""
        with patch.object(ai_service.sarvam_client, 'health_check', return_value=True):
            with patch.object(ai_service.gemini_client, 'health_check', return_value=True):
                with patch.object(ai_service.litellm_client, 'health_check', return_value=True):
                    
                    result = await ai_service.health_check()
                    
                    assert result["sarvam"] is True
                    assert result["gemini"] is True
                    assert result["litellm"] is True
    
    @pytest.mark.asyncio
    async def test_health_check_some_services_unhealthy(self, ai_service):
        """Test health check when some services are unhealthy"""
        with patch.object(ai_service.sarvam_client, 'health_check', return_value=False):
            with patch.object(ai_service.gemini_client, 'health_check', return_value=True):
                with patch.object(ai_service.litellm_client, 'health_check', 
                                 side_effect=Exception("Service down")):
                    
                    result = await ai_service.health_check()
                    
                    assert result["sarvam"] is False
                    assert result["gemini"] is True
                    assert result["litellm"] is False
    
    @pytest.mark.asyncio
    async def test_retry_operation_success_after_retry(self, ai_service):
        """Test retry operation succeeds after initial failure"""
        mock_operation = AsyncMock()
        mock_operation.side_effect = [Exception("First failure"), "Success"]
        
        result = await ai_service._retry_operation(mock_operation, "test_arg")
        
        assert result == "Success"
        assert mock_operation.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_operation_fails_after_max_retries(self, ai_service):
        """Test retry operation fails after max retries"""
        mock_operation = AsyncMock()
        mock_operation.side_effect = Exception("Persistent failure")
        
        with pytest.raises(Exception) as exc_info:
            await ai_service._retry_operation(mock_operation, "test_arg")
        
        assert "Persistent failure" in str(exc_info.value)
        assert mock_operation.call_count == ai_service.max_retries
    
    def test_basic_validation_invalid_amount(self, ai_service):
        """Test basic validation with invalid amount"""
        invalid_bill = BillData(
            total_amount=Decimal("0.00"),
            description="",
            items=[],
            currency="INR"
        )
        
        result = ai_service._basic_validation(invalid_bill)
        
        assert result.is_valid is False
        assert "Total amount must be greater than zero" in result.errors
        assert "Bill description is missing" in result.warnings
    
    def test_basic_intent_recognition_confirm(self, ai_service):
        """Test basic intent recognition for confirmation"""
        result = ai_service._basic_intent_recognition("yes, that's correct", ConversationStep.CONFIRMING_BILL)
        
        assert result["intent"] == "confirm"
        assert result["confidence"] == 0.7
    
    def test_basic_intent_recognition_payment(self, ai_service):
        """Test basic intent recognition for payment confirmation"""
        result = ai_service._basic_intent_recognition("I have paid", ConversationStep.TRACKING_PAYMENTS)
        
        assert result["intent"] == "confirm_payment"
        assert result["confidence"] == 0.8
    
    def test_basic_clarifying_questions(self, ai_service):
        """Test basic clarifying questions generation"""
        incomplete_bill = BillData(
            total_amount=Decimal("0.00"),
            description="Some bill",
            items=[],
            currency="INR"
        )
        
        questions = ai_service._basic_clarifying_questions(incomplete_bill)
        
        assert len(questions) >= 1
        assert any("total amount" in q.lower() for q in questions)


if __name__ == "__main__":
    pytest.main([__file__])