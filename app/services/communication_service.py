"""
Communication service implementation using Siren AI Toolkit
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.interfaces.services import CommunicationServiceInterface
from app.services.siren_client import siren_client, SirenError, SirenWhatsAppError, SirenSMSError
from app.models.enums import DeliveryMethod, ErrorType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CommunicationService(CommunicationServiceInterface):
    """
    Communication service implementation using Siren AI Toolkit
    Implements requirements 4.1, 4.2, 4.3 for message delivery
    """
    
    def __init__(self):
        self.client = siren_client
        self.delivery_log = []  # In-memory log, will be moved to database in later tasks
    
    async def send_whatsapp_message(self, phone_number: str, message: str) -> bool:
        """
        Send WhatsApp message via Siren
        Implements requirement 4.1
        """
        try:
            result = await self.client.send_whatsapp_message(phone_number, message)
            
            # Log delivery attempt
            self._log_delivery_attempt(
                phone_number=phone_number,
                method=DeliveryMethod.WHATSAPP,
                success=result["success"],
                message_id=result.get("message_id"),
                error=None
            )
            
            return result["success"]
            
        except SirenWhatsAppError as e:
            logger.error(f"WhatsApp message failed for {phone_number}: {e}")
            
            # Log failed delivery attempt
            self._log_delivery_attempt(
                phone_number=phone_number,
                method=DeliveryMethod.WHATSAPP,
                success=False,
                message_id=None,
                error=str(e)
            )
            
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp to {phone_number}: {e}")
            return False
    
    async def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS via Siren
        Implements requirement 4.2
        """
        try:
            result = await self.client.send_sms(phone_number, message)
            
            # Log delivery attempt
            self._log_delivery_attempt(
                phone_number=phone_number,
                method=DeliveryMethod.SMS,
                success=result["success"],
                message_id=result.get("message_id"),
                error=None
            )
            
            return result["success"]
            
        except SirenSMSError as e:
            logger.error(f"SMS message failed for {phone_number}: {e}")
            
            # Log failed delivery attempt
            self._log_delivery_attempt(
                phone_number=phone_number,
                method=DeliveryMethod.SMS,
                success=False,
                message_id=None,
                error=str(e)
            )
            
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {phone_number}: {e}")
            return False
    
    async def send_message_with_fallback(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Send message with WhatsApp/SMS fallback
        Implements requirement 4.3
        """
        try:
            result = await self.client.send_message_with_fallback(phone_number, message)
            
            # Log the complete delivery attempt with all methods tried
            for attempt in result.get("delivery_attempts", []):
                self._log_delivery_attempt(
                    phone_number=phone_number,
                    method=attempt.get("delivery_method"),
                    success=attempt.get("success", False),
                    message_id=attempt.get("message_id"),
                    error=attempt.get("error")
                )
            
            return {
                "success": result["success"],
                "primary_method": result.get("primary_method"),
                "fallback_used": result.get("fallback_used", False),
                "delivery_attempts": len(result.get("delivery_attempts", [])),
                "final_method": result.get("primary_method") if result["success"] else None,
                "error": result.get("error") if not result["success"] else None
            }
            
        except Exception as e:
            logger.error(f"Message delivery with fallback failed for {phone_number}: {e}")
            
            # Log the failed attempt
            self._log_delivery_attempt(
                phone_number=phone_number,
                method=None,
                success=False,
                message_id=None,
                error=str(e)
            )
            
            return {
                "success": False,
                "primary_method": None,
                "fallback_used": False,
                "delivery_attempts": 0,
                "final_method": None,
                "error": str(e)
            }
    
    async def send_bulk_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Send multiple messages with fallback for each
        Useful for sending payment requests to multiple participants
        """
        try:
            # Prepare messages for bulk sending
            bulk_messages = [
                {
                    "phone_number": msg["phone_number"],
                    "message": msg["message"],
                    "metadata": msg.get("metadata", {})
                }
                for msg in messages
            ]
            
            results = await self.client.send_bulk_messages(bulk_messages)
            
            # Process and log results
            processed_results = []
            for result in results:
                phone_number = result["phone_number"]
                
                # Log delivery attempts for this message
                for attempt in result.get("delivery_attempts", []):
                    self._log_delivery_attempt(
                        phone_number=phone_number,
                        method=attempt.get("delivery_method"),
                        success=attempt.get("success", False),
                        message_id=attempt.get("message_id"),
                        error=attempt.get("error")
                    )
                
                processed_results.append({
                    "phone_number": phone_number,
                    "success": result["success"],
                    "delivery_method": result.get("primary_method"),
                    "fallback_used": result.get("fallback_used", False),
                    "error": result.get("error")
                })
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Bulk message sending failed: {e}")
            return [
                {
                    "phone_number": msg["phone_number"],
                    "success": False,
                    "delivery_method": None,
                    "fallback_used": False,
                    "error": str(e)
                }
                for msg in messages
            ]
    
    async def get_delivery_statistics(self, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """Get delivery statistics from logs"""
        if phone_number:
            logs = [log for log in self.delivery_log if log["phone_number"] == phone_number]
        else:
            logs = self.delivery_log
        
        total_attempts = len(logs)
        successful_attempts = len([log for log in logs if log["success"]])
        whatsapp_attempts = len([log for log in logs if log["method"] == DeliveryMethod.WHATSAPP])
        sms_attempts = len([log for log in logs if log["method"] == DeliveryMethod.SMS])
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0,
            "whatsapp_attempts": whatsapp_attempts,
            "sms_attempts": sms_attempts,
            "phone_number": phone_number
        }
    
    def _log_delivery_attempt(
        self,
        phone_number: str,
        method: Optional[DeliveryMethod],
        success: bool,
        message_id: Optional[str],
        error: Optional[str]
    ):
        """Log delivery attempt for tracking and analytics"""
        log_entry = {
            "phone_number": phone_number,
            "method": method,
            "success": success,
            "message_id": message_id,
            "error": error,
            "timestamp": datetime.now()
        }
        
        self.delivery_log.append(log_entry)
        
        # Keep only last 1000 entries to prevent memory issues
        if len(self.delivery_log) > 1000:
            self.delivery_log = self.delivery_log[-1000:]
        
        # Log to application logger
        if success:
            logger.info(f"Message delivered via {method} to {phone_number} (ID: {message_id})")
        else:
            logger.warning(f"Message delivery failed via {method} to {phone_number}: {error}")
    
    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format for Siren compatibility"""
        try:
            formatted = self.client._format_phone_number(phone_number)
            
            # Basic validation - should start with + and have reasonable length
            if not formatted.startswith('+'):
                return False
            
            # Remove + and check if remaining characters are digits
            digits_only = formatted[1:]
            if not digits_only.isdigit():
                return False
            
            # Check reasonable length (7-15 digits as per E.164)
            if len(digits_only) < 7 or len(digits_only) > 15:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Phone number validation failed for {phone_number}: {e}")
            return False
    
    async def close(self):
        """Close the communication service and underlying client"""
        await self.client.close()


# Singleton instance for dependency injection
communication_service = CommunicationService()