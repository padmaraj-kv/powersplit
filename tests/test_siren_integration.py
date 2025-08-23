"""
Tests for Siren AI Toolkit integration
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient

from app.services.siren_client import SirenClient, SirenWebhookPayload, SirenError
from app.services.communication_service import CommunicationService
from app.models.enums import DeliveryMethod, MessageType


class TestSirenClient:
    """Test Siren client functionality"""
    
    @pytest.fixture
    def siren_client(self):
        """Create Siren client for testing"""
        with patch('app.services.siren_client.settings') as mock_settings:
            mock_settings.siren_api_key = "test-api-key"
            mock_settings.siren_base_url = "https://api.test-siren.ai"
            mock_settings.siren_webhook_secret = "test-webhook-secret"
            
            client = SirenClient()
            return client
    
    def test_phone_number_formatting(self, siren_client):
        """Test phone number formatting"""
        # Test Indian number without country code
        assert siren_client._format_phone_number("9876543210") == "+919876543210"
        
        # Test Indian number with country code
        assert siren_client._format_phone_number("919876543210") == "+919876543210"
        
        # Test number with + prefix
        assert siren_client._format_phone_number("+919876543210") == "+919876543210"
        
        # Test number with spaces and dashes
        assert siren_client._format_phone_number("98-765-43210") == "+919876543210"
    
    def test_webhook_signature_validation(self, siren_client):
        """Test webhook signature validation"""
        payload = b'{"test": "data"}'
        
        # Test with correct signature
        import hmac
        import hashlib
        expected_signature = hmac.new(
            b"test-webhook-secret",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        assert siren_client.validate_webhook_signature(payload, expected_signature)
        assert siren_client.validate_webhook_signature(payload, f"sha256={expected_signature}")
        
        # Test with incorrect signature
        assert not siren_client.validate_webhook_signature(payload, "invalid-signature")
    
    @pytest.mark.asyncio
    async def test_send_whatsapp_message_success(self, siren_client):
        """Test successful WhatsApp message sending"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message_id": "test-msg-123"}
        
        with patch.object(siren_client.client, 'post', return_value=mock_response):
            result = await siren_client.send_whatsapp_message("+919876543210", "Test message")
            
            assert result["success"] is True
            assert result["message_id"] == "test-msg-123"
            assert result["delivery_method"] == DeliveryMethod.WHATSAPP
    
    @pytest.mark.asyncio
    async def test_send_whatsapp_message_failure(self, siren_client):
        """Test WhatsApp message sending failure"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        
        with patch.object(siren_client.client, 'post', return_value=mock_response):
            with pytest.raises(Exception):  # Should raise SirenWhatsAppError
                await siren_client.send_whatsapp_message("+919876543210", "Test message")
    
    @pytest.mark.asyncio
    async def test_send_message_with_fallback_success_whatsapp(self, siren_client):
        """Test message with fallback - WhatsApp succeeds"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message_id": "test-msg-123"}
        
        with patch.object(siren_client.client, 'post', return_value=mock_response):
            result = await siren_client.send_message_with_fallback("+919876543210", "Test message")
            
            assert result["success"] is True
            assert result["primary_method"] == DeliveryMethod.WHATSAPP
            assert result["fallback_used"] is False
    
    @pytest.mark.asyncio
    async def test_send_message_with_fallback_uses_sms(self, siren_client):
        """Test message with fallback - WhatsApp fails, SMS succeeds"""
        def mock_post(url, **kwargs):
            mock_response = MagicMock()
            if "whatsapp" in url:
                mock_response.status_code = 400
                mock_response.text = "WhatsApp failed"
            else:  # SMS
                mock_response.status_code = 200
                mock_response.json.return_value = {"message_id": "sms-msg-123"}
            return mock_response
        
        with patch.object(siren_client.client, 'post', side_effect=mock_post):
            result = await siren_client.send_message_with_fallback("+919876543210", "Test message")
            
            assert result["success"] is True
            assert result["primary_method"] == DeliveryMethod.SMS
            assert result["fallback_used"] is True


class TestCommunicationService:
    """Test communication service functionality"""
    
    @pytest.fixture
    def communication_service(self):
        """Create communication service for testing"""
        return CommunicationService()
    
    @pytest.mark.asyncio
    async def test_send_whatsapp_message(self, communication_service):
        """Test WhatsApp message sending through service"""
        with patch.object(communication_service.client, 'send_whatsapp_message') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "test-123",
                "delivery_method": DeliveryMethod.WHATSAPP
            }
            
            result = await communication_service.send_whatsapp_message("+919876543210", "Test")
            
            assert result is True
            mock_send.assert_called_once_with("+919876543210", "Test")
    
    @pytest.mark.asyncio
    async def test_send_message_with_fallback(self, communication_service):
        """Test message with fallback through service"""
        with patch.object(communication_service.client, 'send_message_with_fallback') as mock_send:
            mock_send.return_value = {
                "success": True,
                "primary_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False,
                "delivery_attempts": [
                    {
                        "success": True,
                        "delivery_method": DeliveryMethod.WHATSAPP,
                        "message_id": "test-123"
                    }
                ]
            }
            
            result = await communication_service.send_message_with_fallback("+919876543210", "Test")
            
            assert result["success"] is True
            assert result["primary_method"] == DeliveryMethod.WHATSAPP
            assert result["fallback_used"] is False
    
    @pytest.mark.asyncio
    async def test_phone_number_validation(self, communication_service):
        """Test phone number validation"""
        # Valid numbers
        assert await communication_service.validate_phone_number("+919876543210")
        assert await communication_service.validate_phone_number("9876543210")
        assert await communication_service.validate_phone_number("+1234567890")
        
        # Invalid numbers
        assert not await communication_service.validate_phone_number("123")  # Too short
        assert not await communication_service.validate_phone_number("12345678901234567890")  # Too long
        assert not await communication_service.validate_phone_number("abc123")  # Contains letters


class TestWebhookPayload:
    """Test webhook payload parsing"""
    
    def test_webhook_payload_creation(self):
        """Test creating webhook payload from data"""
        data = {
            "message_id": "msg-123",
            "from_number": "+919876543210",
            "to_number": "+918765432109",
            "content": "Hello world",
            "message_type": "text",
            "timestamp": "2024-01-01T12:00:00Z",
            "metadata": {"source": "whatsapp"}
        }
        
        payload = SirenWebhookPayload(**data)
        
        assert payload.message_id == "msg-123"
        assert payload.from_number == "+919876543210"
        assert payload.content == "Hello world"
        assert payload.message_type == "text"
        assert payload.metadata["source"] == "whatsapp"
    
    def test_webhook_payload_with_minimal_data(self):
        """Test webhook payload with minimal required data"""
        data = {
            "message_id": "msg-123",
            "from_number": "+919876543210",
            "to_number": "+918765432109",
            "content": "Hello",
            "message_type": "text",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        payload = SirenWebhookPayload(**data)
        
        assert payload.message_id == "msg-123"
        assert payload.metadata == {}


if __name__ == "__main__":
    pytest.main([__file__])