"""
Webhook handlers for receiving messages from Siren AI Toolkit
"""
import json
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime

from app.services.siren_client import siren_client, SirenWebhookPayload
from app.models.schemas import Message, Response
from app.models.enums import MessageType, ErrorType
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookHandler:
    """
    Webhook handler for processing incoming Siren messages
    Implements requirements 1.1, 1.2, 1.3 for message reception
    """
    
    def __init__(self):
        self.conversation_manager = None  # Will be injected during startup
    
    async def process_incoming_message(self, webhook_payload: SirenWebhookPayload) -> Dict[str, Any]:
        """
        Process incoming message from Siren webhook
        Routes to conversation manager for processing
        """
        try:
            # Convert webhook payload to internal message format
            message = Message(
                id=webhook_payload.message_id,
                user_id=webhook_payload.from_number,
                content=webhook_payload.content,
                message_type=self._determine_message_type(webhook_payload),
                timestamp=webhook_payload.timestamp,
                metadata=webhook_payload.metadata or {}
            )
            
            logger.info(f"Processing message from {message.user_id}: {message.message_type}")
            
            # Process message through conversation manager if available
            if self.conversation_manager:
                try:
                    response = await self.conversation_manager.process_message(message)
                    
                    # Send response back to user
                    await self._send_response(webhook_payload.from_number, response)
                    
                    return {
                        "status": "processed",
                        "message_id": webhook_payload.message_id,
                        "response_sent": True,
                        "conversation_step": response.metadata.get("conversation_step")
                    }
                    
                except Exception as conv_error:
                    logger.error(f"Conversation manager error: {conv_error}")
                    # Fall back to error response
                    error_response = Response(
                        content="I'm having trouble processing your request right now. Please try again in a moment.",
                        message_type=MessageType.TEXT,
                        metadata={"error": "conversation_processing_failed"}
                    )
                    await self._send_response(webhook_payload.from_number, error_response)
                    
                    return {
                        "status": "error",
                        "message_id": webhook_payload.message_id,
                        "error": str(conv_error),
                        "fallback_response_sent": True
                    }
            else:
                # Conversation manager not initialized - send fallback response
                logger.warning("Conversation manager not initialized")
                fallback_response = Response(
                    content="Hello! I'm the Bill Splitting Agent. I can help you split bills among friends. The service is starting up - please try again in a moment.",
                    message_type=MessageType.TEXT,
                    metadata={"status": "service_initializing"}
                )
                await self._send_response(webhook_payload.from_number, fallback_response)
                
                return {
                    "status": "fallback",
                    "message_id": webhook_payload.message_id,
                    "response_sent": True,
                    "reason": "conversation_manager_not_initialized"
                }
            
        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            # Send error response to user
            error_response = Response(
                content="Sorry, I encountered an error processing your message. Please try again.",
                message_type=MessageType.TEXT,
                metadata={"error": "webhook_processing_failed"}
            )
            await self._send_response(webhook_payload.from_number, error_response)
            
            return {
                "status": "error",
                "message_id": webhook_payload.message_id,
                "error": str(e),
                "error_response_sent": True
            }
    
    def _determine_message_type(self, webhook_payload: SirenWebhookPayload) -> MessageType:
        """Determine message type from webhook payload"""
        message_type = webhook_payload.message_type.lower()
        
        if message_type in ["image", "photo"]:
            return MessageType.IMAGE
        elif message_type in ["voice", "audio"]:
            return MessageType.VOICE
        else:
            return MessageType.TEXT
    
    async def _send_response(self, phone_number: str, response: Response):
        """Send response back to user via Siren"""
        try:
            await siren_client.send_message_with_fallback(
                phone_number=phone_number,
                message=response.content,
                metadata=response.metadata
            )
        except Exception as e:
            logger.error(f"Failed to send response to {phone_number}: {e}")


# Global webhook handler instance
webhook_handler = WebhookHandler()


@router.post("/siren/message")
async def receive_siren_message(
    request: Request,
    background_tasks: BackgroundTasks,
    x_siren_signature: str = Header(None, alias="X-Siren-Signature")
):
    """
    Receive incoming messages from Siren AI Toolkit
    Implements webhook signature validation for security
    """
    try:
        # Get raw request body for signature validation
        body = await request.body()
        
        # Validate webhook signature
        if not x_siren_signature:
            logger.warning("Missing webhook signature")
            raise HTTPException(status_code=401, detail="Missing signature")
        
        if not siren_client.validate_webhook_signature(body, x_siren_signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook payload
        try:
            payload_data = json.loads(body.decode())
            webhook_payload = SirenWebhookPayload(**payload_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload format")
        
        # Process message in background to avoid timeout
        background_tasks.add_task(
            webhook_handler.process_incoming_message,
            webhook_payload
        )
        
        # Return immediate acknowledgment
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "message_id": webhook_payload.message_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/siren/delivery-status")
async def receive_delivery_status(
    request: Request,
    x_siren_signature: str = Header(None, alias="X-Siren-Signature")
):
    """
    Receive delivery status updates from Siren
    """
    try:
        # Get raw request body for signature validation
        body = await request.body()
        
        # Validate webhook signature
        if not x_siren_signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        
        if not siren_client.validate_webhook_signature(body, x_siren_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse delivery status payload
        try:
            status_data = json.loads(body.decode())
            logger.info(f"Delivery status update: {status_data}")
            
            # TODO: Update delivery status in database
            # This will be implemented in later tasks
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid delivery status payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload format")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "processed",
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delivery status processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/siren/health")
async def siren_health_check():
    """Health check endpoint for Siren integration"""
    try:
        # Test Siren client connectivity
        # This is a simple connectivity test
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "siren-integration",
                "timestamp": datetime.now().isoformat(),
                "base_url": siren_client.base_url
            }
        )
    except Exception as e:
        logger.error(f"Siren health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "siren-integration",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )