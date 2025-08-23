"""
Siren AI Toolkit client wrapper for WhatsApp and SMS messaging
"""

import asyncio
import hmac
import hashlib
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.models.enums import DeliveryMethod, ErrorType
from app.models.schemas import ErrorResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SirenMessage(BaseModel):
    """Siren message payload"""

    to: str
    content: str
    type: str = "text"
    metadata: Dict[str, Any] = {}


class SirenDeliveryStatus(BaseModel):
    """Siren delivery status response"""

    message_id: str
    status: str
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


class SirenWebhookPayload(BaseModel):
    """Siren webhook payload structure"""

    message_id: str
    from_number: str
    to_number: str
    content: str
    message_type: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class SirenError(Exception):
    """Base exception for Siren-related errors"""

    pass


class SirenWhatsAppError(SirenError):
    """WhatsApp-specific Siren errors"""

    pass


class SirenSMSError(SirenError):
    """SMS-specific Siren errors"""

    pass


class SirenClient:
    """
    Siren AI Toolkit client for WhatsApp and SMS messaging
    Implements requirements 1.1, 1.2, 1.3, 4.1, 4.2, 4.3
    """

    def __init__(self):
        self.api_key = settings.siren_api_key
        self.base_url = settings.siren_base_url
        self.webhook_secret = settings.siren_webhook_secret
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def validate_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate webhook signature for security
        Implements security requirement for webhook validation
        """
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode(), payload, hashlib.sha256
            ).hexdigest()

            # Remove 'sha256=' prefix if present
            if signature.startswith("sha256="):
                signature = signature[7:]

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Webhook signature validation failed: {e}")
            return False

    async def send_whatsapp_message(
        self, phone_number: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message via Siren
        Implements requirement 4.1 for WhatsApp messaging
        """
        try:
            payload = SirenMessage(
                to=self._format_phone_number(phone_number),
                content=message,
                type="text",
                metadata=metadata or {},
            )

            response = await self.client.post(
                f"{self.base_url}/v1/messages/whatsapp", json=payload.dict()
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"WhatsApp message sent successfully to {phone_number}")
                return {
                    "success": True,
                    "message_id": result.get("message_id"),
                    "delivery_method": DeliveryMethod.WHATSAPP,
                    "sent_at": datetime.now(),
                }
            else:
                error_msg = (
                    f"WhatsApp send failed: {response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                raise SirenWhatsAppError(error_msg)

        except httpx.RequestError as e:
            error_msg = f"WhatsApp request failed: {str(e)}"
            logger.error(error_msg)
            raise SirenWhatsAppError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected WhatsApp error: {str(e)}"
            logger.error(error_msg)
            raise SirenWhatsAppError(error_msg)

    async def send_sms(
        self, phone_number: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send SMS via Siren
        Implements requirement 4.2 for SMS messaging
        """
        try:
            payload = SirenMessage(
                to=self._format_phone_number(phone_number),
                content=message,
                type="text",
                metadata=metadata or {},
            )

            response = await self.client.post(
                f"{self.base_url}/v1/messages/sms", json=payload.dict()
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"SMS sent successfully to {phone_number}")
                return {
                    "success": True,
                    "message_id": result.get("message_id"),
                    "delivery_method": DeliveryMethod.SMS,
                    "sent_at": datetime.now(),
                }
            else:
                error_msg = f"SMS send failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise SirenSMSError(error_msg)

        except httpx.RequestError as e:
            error_msg = f"SMS request failed: {str(e)}"
            logger.error(error_msg)
            raise SirenSMSError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected SMS error: {str(e)}"
            logger.error(error_msg)
            raise SirenSMSError(error_msg)

    async def send_message_with_fallback(
        self, phone_number: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send message with WhatsApp/SMS fallback
        Implements requirement 4.3 for fallback messaging
        """
        delivery_attempts = []

        # Try WhatsApp first
        try:
            result = await self.send_whatsapp_message(phone_number, message, metadata)
            delivery_attempts.append(result)
            return {
                "success": True,
                "primary_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False,
                "delivery_attempts": delivery_attempts,
            }
        except SirenWhatsAppError as whatsapp_error:
            logger.warning(
                f"WhatsApp delivery failed for {phone_number}: {whatsapp_error}"
            )
            delivery_attempts.append(
                {
                    "success": False,
                    "delivery_method": DeliveryMethod.WHATSAPP,
                    "error": str(whatsapp_error),
                    "attempted_at": datetime.now(),
                }
            )

        # Fallback to SMS
        try:
            result = await self.send_sms(phone_number, message, metadata)
            delivery_attempts.append(result)
            return {
                "success": True,
                "primary_method": DeliveryMethod.SMS,
                "fallback_used": True,
                "delivery_attempts": delivery_attempts,
            }
        except SirenSMSError as sms_error:
            logger.error(f"SMS fallback also failed for {phone_number}: {sms_error}")
            delivery_attempts.append(
                {
                    "success": False,
                    "delivery_method": DeliveryMethod.SMS,
                    "error": str(sms_error),
                    "attempted_at": datetime.now(),
                }
            )

            # Both methods failed
            return {
                "success": False,
                "primary_method": None,
                "fallback_used": True,
                "delivery_attempts": delivery_attempts,
                "error": "All delivery methods failed",
            }

    async def get_delivery_status(self, message_id: str) -> SirenDeliveryStatus:
        """Get delivery status for a sent message"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/messages/{message_id}/status"
            )

            if response.status_code == 200:
                data = response.json()
                return SirenDeliveryStatus(**data)
            else:
                raise SirenError(f"Status check failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to get delivery status for {message_id}: {e}")
            raise SirenError(f"Status check error: {str(e)}")

    async def send_bulk_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Send multiple messages with fallback for each"""
        results = []

        # Process messages concurrently but with rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

        async def send_single_message(msg_data):
            async with semaphore:
                return await self.send_message_with_fallback(
                    phone_number=msg_data["phone_number"],
                    message=msg_data["message"],
                    metadata=msg_data.get("metadata"),
                )

        tasks = [send_single_message(msg) for msg in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "success": False,
                        "phone_number": messages[i]["phone_number"],
                        "error": str(result),
                        "delivery_attempts": [],
                    }
                )
            else:
                result["phone_number"] = messages[i]["phone_number"]
                processed_results.append(result)

        return processed_results

    def _format_phone_number(self, phone_number: str) -> str:
        """Format phone number for Siren API"""
        # Remove any non-digit characters except +
        cleaned = "".join(c for c in phone_number if c.isdigit() or c == "+")

        # Add + prefix if not present and number doesn't start with country code
        if not cleaned.startswith("+"):
            if cleaned.startswith("91") and len(cleaned) == 12:
                # Indian number with country code
                cleaned = "+" + cleaned
            elif len(cleaned) == 10:
                # Indian number without country code
                cleaned = "+91" + cleaned
            else:
                # Assume it needs + prefix
                cleaned = "+" + cleaned

        return cleaned

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Singleton instance for dependency injection
siren_client = SirenClient()
