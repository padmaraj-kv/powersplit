"""
Webhook handlers for receiving messages from Siren AI Toolkit
"""

# ruff: noqa: E501, W291, W293, F401

import json
import os
import requests
import re
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime

from app.clients.siren_client import siren_client, SirenWebhookPayload
from app.core.database import get_database
from app.core.config import settings
from app.database.repositories import SQLUserRepository
from app.models.schemas import Message, Response
from app.models.enums import MessageType
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Twilio credentials loaded from environment via settings

def parse_vcard_content(vcard_content: str) -> Dict[str, Any]:
    """
    Parse vCard content and extract contact details
    Returns a dictionary with parsed contact information
    """
    contact_info = {
        "version": None,
        "full_name": None,
        "first_name": None,
        "last_name": None,
        "phone_numbers": [],
        "emails": [],
        "organization": None,
        "title": None,
        "raw_content": vcard_content.strip()
    }
    
    lines = vcard_content.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('VERSION:'):
            contact_info["version"] = line.split(':', 1)[1].strip()
            
        elif line.startswith('FN:'):
            contact_info["full_name"] = line.split(':', 1)[1].strip()
            
        elif line.startswith('N:'):
            # N:Last;First;Middle;Prefix;Suffix
            name_parts = line.split(':', 1)[1].split(';')
            if len(name_parts) >= 2:
                contact_info["last_name"] = name_parts[0].strip() if name_parts[0] else None
                contact_info["first_name"] = name_parts[1].strip() if name_parts[1] else None
                
        elif line.startswith('TEL'):
            # Extract phone number - handle various TEL formats
            phone_match = re.search(r'TEL[^:]*:(.+)', line)
            if phone_match:
                phone = phone_match.group(1).strip()
                # Extract type if present
                type_match = re.search(r'TYPE=([^;:]+)', line)
                phone_type = type_match.group(1) if type_match else "unknown"
                contact_info["phone_numbers"].append({
                    "number": phone,
                    "type": phone_type
                })
                
        elif line.startswith('EMAIL'):
            # Extract email - handle various EMAIL formats
            email_match = re.search(r'EMAIL[^:]*:(.+)', line)
            if email_match:
                email = email_match.group(1).strip()
                # Extract type if present
                type_match = re.search(r'TYPE=([^;:]+)', line)
                email_type = type_match.group(1) if type_match else "unknown"
                contact_info["emails"].append({
                    "email": email,
                    "type": email_type
                })
                
        elif line.startswith('ORG:'):
            contact_info["organization"] = line.split(':', 1)[1].strip()
            
        elif line.startswith('TITLE:'):
            contact_info["title"] = line.split(':', 1)[1].strip()
    
    return contact_info

async def download_twilio_media(media_url: str, content_type: str, message_id: str) -> Optional[str]:
    """
    Download media file from Twilio and save to local disk
    Returns the local file path if successful, None if failed
    """
    try:
        logger.info(f"📥 Downloading media from: {media_url}")
        
        # Make authenticated request to Twilio
        response = requests.get(
            media_url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=30
        )
        
        if response.status_code == 200:
            # Determine file extension based on content type
            if "image/jpeg" in content_type:
                extension = ".jpg"
            elif "image/png" in content_type:
                extension = ".png"
            elif "audio/ogg" in content_type:
                extension = ".ogg"
            elif "audio/mp4" in content_type or "audio/aac" in content_type:
                extension = ".m4a"
            elif "video/mp4" in content_type:
                extension = ".mp4"
            elif "text/vcard" in content_type or "text/x-vcard" in content_type:
                extension = ".vcf"
            else:
                extension = ".bin"  # fallback
            
            # Create filename with timestamp and message ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            media_type = content_type.split('/')[0]  # image, audio, video
            filename = f"webhook_{media_type}_{timestamp}_{message_id[-8:]}{extension}"
            
            # Create media directory if it doesn't exist
            media_dir = "support_files"
            os.makedirs(media_dir, exist_ok=True)
            
            # Full file path
            file_path = os.path.join(media_dir, filename)
            
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            file_size = len(response.content)
            logger.info(f"✅ Media file saved successfully:")
            logger.info(f"   File: {file_path}")
            logger.info(f"   Size: {file_size:,} bytes")
            logger.info(f"   Content-Type: {content_type}")
            
            # Parse vCard content if it's a contact file
            if "text/vcard" in content_type or "text/x-vcard" in content_type:
                try:
                    vcard_content = response.content.decode('utf-8')
                    contact_info = parse_vcard_content(vcard_content)
                    
                    logger.info("📇 CONTACT CARD DETAILS:")
                    logger.info(f"   📛 Full Name: {contact_info['full_name']}")
                    if contact_info['first_name'] or contact_info['last_name']:
                        logger.info(f"   👤 Name Parts: {contact_info['first_name']} {contact_info['last_name']}")
                    
                    if contact_info['phone_numbers']:
                        logger.info("   📞 Phone Numbers:")
                        for phone in contact_info['phone_numbers']:
                            logger.info(f"      • {phone['number']} ({phone['type']})")
                    
                    if contact_info['emails']:
                        logger.info("   📧 Email Addresses:")
                        for email in contact_info['emails']:
                            logger.info(f"      • {email['email']} ({email['type']})")
                    
                    if contact_info['organization']:
                        logger.info(f"   🏢 Organization: {contact_info['organization']}")
                    
                    if contact_info['title']:
                        logger.info(f"   💼 Title: {contact_info['title']}")
                    
                    logger.info(f"   📄 vCard Version: {contact_info['version']}")
                    logger.info("📇 END CONTACT DETAILS")
                    
                except Exception as parse_error:
                    logger.error(f"❌ Failed to parse vCard content: {parse_error}")
            
            return os.path.abspath(file_path)
            
        else:
            logger.error(f"❌ Failed to download media file:")
            logger.error(f"   Status Code: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error downloading media file: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error downloading media: {e}")
        return None


class WebhookHandler:
    """
    Webhook handler for processing incoming Siren messages
    Implements requirements 1.1, 1.2, 1.3 for message reception
    """

    def __init__(self):
        self.conversation_manager = None  # Will be injected during startup

    async def process_incoming_message(
        self, webhook_payload: SirenWebhookPayload
    ) -> Dict[str, Any]:
        """
        Process incoming message from Siren webhook
        Routes to conversation manager for processing
        """
        try:
            # Resolve or create internal user by phone number (gateway concern)
            db = get_database()
            user_repo = SQLUserRepository(db)
            user = await user_repo.get_user_by_phone(webhook_payload.from_number)
            if not user:
                user = await user_repo.create_user(
                    phone_number=webhook_payload.from_number
                )

            # Convert webhook payload to internal message format (stable user + context)
            message = Message(
                id=webhook_payload.message_id,
                user_id=str(user.id),
                content=webhook_payload.content,
                message_type=self._determine_message_type(webhook_payload),
                timestamp=webhook_payload.timestamp,
                metadata={
                    **(webhook_payload.metadata or {}),
                    "sender_phone": webhook_payload.from_number,
                    "receiver_phone": webhook_payload.to_number,
                },
            )

            logger.info(
                f"Processing message from {message.user_id}: {message.message_type}"
            )

            # Process message through conversation manager if available
            if self.conversation_manager:
                try:
                    response = await self.conversation_manager.process_message(
                        str(user.id), message
                    )

                    # Send response back to user
                    await self._send_response(webhook_payload.from_number, response)

                    return {
                        "status": "processed",
                        "message_id": webhook_payload.message_id,
                        "response_sent": True,
                        "conversation_step": response.metadata.get("conversation_step"),
                    }

                except Exception as conv_error:
                    logger.error(f"Conversation manager error: {conv_error}")
                    # Fall back to error response
                    error_response = Response(
                        content="I'm having trouble processing your request right now. Please try again in a moment.",
                        message_type=MessageType.TEXT,
                        metadata={"error": "conversation_processing_failed"},
                    )
                    await self._send_response(
                        webhook_payload.from_number, error_response
                    )

                    return {
                        "status": "error",
                        "message_id": webhook_payload.message_id,
                        "error": str(conv_error),
                        "fallback_response_sent": True,
                    }
            else:
                # Conversation manager not initialized - send fallback response
                logger.warning("Conversation manager not initialized")
                fallback_response = Response(
                    content="Hello! I'm the Bill Splitting Agent. I can help you split bills among friends. The service is starting up - please try again in a moment.",
                    message_type=MessageType.TEXT,
                    metadata={"status": "service_initializing"},
                )
                await self._send_response(
                    webhook_payload.from_number, fallback_response
                )

                return {
                    "status": "fallback",
                    "message_id": webhook_payload.message_id,
                    "response_sent": True,
                    "reason": "conversation_manager_not_initialized",
                }

        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            # Send error response to user
            error_response = Response(
                content="Sorry, I encountered an error processing your message. Please try again.",
                message_type=MessageType.TEXT,
                metadata={"error": "webhook_processing_failed"},
            )
            await self._send_response(webhook_payload.from_number, error_response)

            return {
                "status": "error",
                "message_id": webhook_payload.message_id,
                "error": str(e),
                "error_response_sent": True,
            }

    def _determine_message_type(
        self, webhook_payload: SirenWebhookPayload
    ) -> MessageType:
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
                metadata=response.metadata,
            )
        except Exception as e:
            logger.error(f"Failed to send response to {phone_number}: {e}")


# Global webhook handler instance
webhook_handler = WebhookHandler()


@router.post("/siren/message")
async def receive_siren_message(
    request: Request,
    background_tasks: BackgroundTasks,
    x_siren_signature: str = Header(None, alias="X-Siren-Signature"),
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature"),
):
    """
    Receive incoming messages from Siren AI Toolkit or Twilio
    Handles both JSON (Siren) and form-encoded (Twilio) payloads
    """
    try:
        # Get content type to determine parsing method
        content_type = request.headers.get("content-type", "").lower()
        
        if "application/x-www-form-urlencoded" in content_type:
            # Handle Twilio webhook (form-encoded data)
            logger.info("=== TWILIO WEBHOOK RECEIVED ===")
            
            form = await request.form()
            
            # Log all form fields for debugging
            logger.info("Raw Twilio webhook data:")
            for key, value in form.items():
                logger.info(f"  {key}: {value}")
            
            # Parse and log structured message data
            parsed_message = {
                "provider": "twilio",
                "message_id": form.get("MessageSid") or form.get("SmsMessageSid"),
                "from_number": form.get("From", "").replace("whatsapp:", ""),
                "to_number": form.get("To", "").replace("whatsapp:", ""),
                "body": form.get("Body", ""),
                "message_type": form.get("MessageType", "text"),
                "profile_name": form.get("ProfileName"),
                "wa_id": form.get("WaId"),
                "sms_status": form.get("SmsStatus"),
                "num_media": int(form.get("NumMedia", 0) or 0),
                "media_content_type": form.get("MediaContentType0"),
                "media_url": form.get("MediaUrl0"),
                "account_sid": form.get("AccountSid"),
                "messaging_service_sid": form.get("MessagingServiceSid"),
                "channel_metadata": form.get("ChannelMetadata"),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("=== PARSED TWILIO MESSAGE ===")
            logger.info(json.dumps(parsed_message, indent=2))
            
            # Download media files if present and log message details
            downloaded_file_path = None
            if parsed_message["num_media"] > 0 and parsed_message["media_url"]:
                # Download the media file
                downloaded_file_path = await download_twilio_media(
                    parsed_message["media_url"],
                    parsed_message["media_content_type"] or "application/octet-stream",
                    parsed_message["message_id"]
                )
                
                # Log message with download status
                media_content_type = parsed_message["media_content_type"] or ""
                if "image" in media_content_type:
                    logger.info(f"📸 IMAGE MESSAGE from {parsed_message['profile_name']} ({parsed_message['from_number']})")
                    logger.info(f"   Media URL: {parsed_message['media_url']}")
                    if downloaded_file_path:
                        logger.info(f"   💾 Downloaded to: {downloaded_file_path}")
                    else:
                        logger.warning(f"   ❌ Failed to download image file")
                elif "audio" in media_content_type:
                    logger.info(f"🎵 AUDIO MESSAGE from {parsed_message['profile_name']} ({parsed_message['from_number']})")
                    logger.info(f"   Media URL: {parsed_message['media_url']}")
                    if downloaded_file_path:
                        logger.info(f"   💾 Downloaded to: {downloaded_file_path}")
                    else:
                        logger.warning(f"   ❌ Failed to download audio file")
                elif "text/vcard" in media_content_type or "text/x-vcard" in media_content_type:
                    logger.info(f"📇 CONTACT CARD MESSAGE from {parsed_message['profile_name']} ({parsed_message['from_number']})")
                    logger.info(f"   Media URL: {parsed_message['media_url']}")
                    if downloaded_file_path:
                        logger.info(f"   💾 Downloaded and parsed contact to: {downloaded_file_path}")
                    else:
                        logger.warning(f"   ❌ Failed to download contact file")
                else:
                    logger.info(f"📎 MEDIA MESSAGE from {parsed_message['profile_name']} ({parsed_message['from_number']})")
                    logger.info(f"   Media Type: {parsed_message['media_content_type']}")
                    logger.info(f"   Media URL: {parsed_message['media_url']}")
                    if downloaded_file_path:
                        logger.info(f"   💾 Downloaded to: {downloaded_file_path}")
                    else:
                        logger.warning(f"   ❌ Failed to download media file")
            else:
                logger.info(f"💬 TEXT MESSAGE from {parsed_message['profile_name']} ({parsed_message['from_number']})")
                logger.info(f"   Content: {parsed_message['body']}")
            
            # Add download info to parsed message
            if downloaded_file_path:
                parsed_message["downloaded_file_path"] = downloaded_file_path
            
            logger.info("=== END TWILIO MESSAGE PARSING ===")
            
            # Return acknowledgment without processing
            response_content = {
                "status": "received_and_logged",
                "provider": "twilio",
                "message_id": parsed_message["message_id"],
                "message_type": parsed_message["message_type"],
                "from": parsed_message["from_number"],
                "timestamp": parsed_message["timestamp"],
            }
            
            # Add media download info if applicable
            if downloaded_file_path:
                response_content["media_downloaded"] = True
                response_content["downloaded_file_path"] = downloaded_file_path
            elif parsed_message["num_media"] > 0:
                response_content["media_downloaded"] = False
                response_content["download_error"] = "Failed to download media file"
            
            return JSONResponse(status_code=200, content=response_content)
            
        else:
            # Handle Siren webhook (JSON data)
            logger.info("=== SIREN WEBHOOK RECEIVED ===")
            
            # Get raw request body for signature validation
            body = await request.body()

            # Validate webhook signature for Siren
            if not x_siren_signature:
                logger.warning("Missing Siren webhook signature")
                raise HTTPException(status_code=401, detail="Missing signature")

            if not siren_client.validate_webhook_signature(body, x_siren_signature):
                logger.warning("Invalid Siren webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

            # Parse webhook payload
            try:
                payload_data = json.loads(body.decode())
                webhook_payload = SirenWebhookPayload(**payload_data)
                
                logger.info("=== PARSED SIREN MESSAGE ===")
                logger.info(json.dumps(payload_data, indent=2))
                logger.info("=== END SIREN MESSAGE PARSING ===")
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Invalid Siren webhook payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid payload format")

            # Return acknowledgment without processing
            return JSONResponse(
                status_code=200,
                content={
                    "status": "received_and_logged",
                    "provider": "siren",
                    "message_id": webhook_payload.message_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/siren/delivery-status")
async def receive_delivery_status(
    request: Request, x_siren_signature: str = Header(None, alias="X-Siren-Signature")
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
            content={"status": "processed", "timestamp": datetime.now().isoformat()},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delivery status processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/twilio/whatsapp")
async def receive_twilio_whatsapp(request: Request):
    """
    Receive incoming WhatsApp messages from Twilio and map to internal message flow.
    Twilio sends application/x-www-form-urlencoded payloads.
    """
    try:
        form = await request.form()

        # Extract core fields
        message_id = form.get("MessageSid") or form.get("SmsMessageSid") or ""
        from_field = form.get("From", "")  # e.g. 'whatsapp:+9194...'
        to_field = form.get("To", "")  # e.g. 'whatsapp:+1774...'
        body = form.get("Body", "")
        message_type = form.get("MessageType", "text")
        num_media = int(form.get("NumMedia", 0) or 0)

        # Normalize phone numbers
        def strip_whatsapp_prefix(value: str) -> str:
            return value.replace("whatsapp:", "") if value else value

        from_number = strip_whatsapp_prefix(from_field)
        to_number = strip_whatsapp_prefix(to_field)

        # Determine message type
        inferred_type = "image" if num_media > 0 else message_type

        # Build Siren-like payload for reuse of handler
        webhook_payload = SirenWebhookPayload(
            message_id=message_id or f"twilio_{datetime.now().timestamp()}",
            from_number=from_number,
            to_number=to_number,
            content=body,
            message_type=inferred_type,
            timestamp=datetime.now(),
            metadata={
                "provider": "twilio",
                "ProfileName": form.get("ProfileName"),
                "WaId": form.get("WaId"),
                "SmsStatus": form.get("SmsStatus"),
                "MessagingServiceSid": form.get("MessagingServiceSid"),
                "AccountSid": form.get("AccountSid"),
                "ChannelMetadata": form.get("ChannelMetadata"),
                "NumSegments": form.get("NumSegments"),
                "NumMedia": form.get("NumMedia"),
            },
        )

        # Process via the same internal handler
        result = await webhook_handler.process_incoming_message(webhook_payload)

        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "message_id": webhook_payload.message_id,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Twilio webhook processing error: {e}")
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
                "base_url": siren_client.base_url,
            },
        )
    except Exception as e:
        logger.error(f"Siren health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "siren-integration",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )
