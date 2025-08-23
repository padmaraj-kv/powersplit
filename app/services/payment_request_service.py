"""
Payment Request Distribution Service

This service handles the distribution of payment requests to bill participants
using WhatsApp and SMS via Siren integration, with delivery tracking and
personalized message templates.

Requirements implemented:
- 4.1: Generate UPI deeplinks for each participant with their specific amount
- 4.2: Send WhatsApp messages to each participant with their payment link
- 4.3: Send SMS as fallback when WhatsApp delivery fails
- 4.4: Send confirmation message to original user when all messages are sent
- 4.5: Store tracking information in the database
"""
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from app.services.siren_client import siren_client, SirenError
from app.services.communication_service import communication_service
from app.services.upi_service import UPIService, UPIApp
from app.models.database import Bill, BillParticipant, PaymentRequest, Contact, User
from app.models.enums import DeliveryMethod
from app.database.repositories import DatabaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PaymentRequestStatus(Enum):
    """Payment request status enumeration"""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class PaymentRequestResult:
    """Result of payment request distribution"""
    participant_id: str
    participant_name: str
    phone_number: str
    amount: Decimal
    success: bool
    delivery_method: Optional[DeliveryMethod]
    fallback_used: bool
    upi_link: str
    message_sent: str
    error: Optional[str] = None
    payment_request_id: Optional[str] = None


@dataclass
class DistributionSummary:
    """Summary of payment request distribution"""
    bill_id: str
    total_participants: int
    successful_sends: int
    failed_sends: int
    whatsapp_sends: int
    sms_sends: int
    results: List[PaymentRequestResult]
    started_at: datetime
    completed_at: datetime


class PaymentRequestService:
    """
    Service for distributing payment requests to bill participants
    Implements requirements 4.1, 4.2, 4.3, 4.4, 4.5
    """
    
    def __init__(self, db_repository: DatabaseRepository, upi_service: UPIService):
        self.db = db_repository
        self.upi_service = upi_service
        self.communication = communication_service
        
        # Message templates
        self.templates = {
            "payment_request": self._get_payment_request_template(),
            "confirmation_to_organizer": self._get_organizer_confirmation_template(),
            "reminder": self._get_reminder_template(),
            "completion_notification": self._get_completion_notification_template()
        }
    
    async def distribute_payment_requests(
        self,
        bill_id: str,
        organizer_phone: str,
        custom_message: Optional[str] = None
    ) -> DistributionSummary:
        """
        Distribute payment requests to all participants of a bill
        Implements requirements 4.1, 4.2, 4.3, 4.4, 4.5
        
        Args:
            bill_id: ID of the bill to distribute payment requests for
            organizer_phone: Phone number of the bill organizer
            custom_message: Optional custom message to include
            
        Returns:
            DistributionSummary: Summary of the distribution process
        """
        started_at = datetime.now()
        logger.info(f"Starting payment request distribution for bill {bill_id}")
        
        try:
            # Get bill and participants from database
            bill = await self.db.get_bill_with_participants(bill_id)
            if not bill:
                raise ValueError(f"Bill {bill_id} not found")
            
            if not bill.participants:
                raise ValueError(f"No participants found for bill {bill_id}")
            
            # Generate payment requests for each participant
            results = []
            for participant in bill.participants:
                if participant.payment_status == 'confirmed':
                    logger.info(f"Skipping participant {participant.id} - already paid")
                    continue
                
                result = await self._send_payment_request_to_participant(
                    bill=bill,
                    participant=participant,
                    custom_message=custom_message
                )
                results.append(result)
            
            # Create distribution summary
            completed_at = datetime.now()
            summary = DistributionSummary(
                bill_id=bill_id,
                total_participants=len(results),
                successful_sends=len([r for r in results if r.success]),
                failed_sends=len([r for r in results if not r.success]),
                whatsapp_sends=len([r for r in results if r.delivery_method == DeliveryMethod.WHATSAPP]),
                sms_sends=len([r for r in results if r.delivery_method == DeliveryMethod.SMS]),
                results=results,
                started_at=started_at,
                completed_at=completed_at
            )
            
            # Send confirmation to organizer
            await self._send_organizer_confirmation(
                organizer_phone=organizer_phone,
                bill=bill,
                summary=summary
            )
            
            logger.info(f"Payment request distribution completed for bill {bill_id}: "
                       f"{summary.successful_sends}/{summary.total_participants} successful")
            
            return summary
            
        except Exception as e:
            logger.error(f"Payment request distribution failed for bill {bill_id}: {e}")
            raise
    
    async def _send_payment_request_to_participant(
        self,
        bill: Bill,
        participant: BillParticipant,
        custom_message: Optional[str] = None
    ) -> PaymentRequestResult:
        """
        Send payment request to a single participant
        Implements requirements 4.1, 4.2, 4.3, 4.5
        """
        try:
            # Get contact information
            contact = participant.contact
            if not contact:
                raise ValueError(f"Contact not found for participant {participant.id}")
            
            participant_name = contact.name or "Friend"
            phone_number = contact.phone_number
            
            if not phone_number:
                raise ValueError(f"Phone number not found for participant {participant.id}")
            
            # Generate UPI link (Requirement 4.1)
            upi_link = self.upi_service.generate_upi_link(
                recipient_name=participant_name,
                amount=participant.amount_owed,
                description=f"Bill Split: {bill.description or 'Shared Expense'}",
                upi_app=UPIApp.GENERIC
            )
            
            # Create personalized message
            message = self._create_payment_message(
                participant_name=participant_name,
                amount=participant.amount_owed,
                bill_description=bill.description or "Shared Expense",
                upi_link=upi_link,
                custom_message=custom_message
            )
            
            # Create payment request record in database (Requirement 4.5)
            payment_request = await self._create_payment_request_record(
                participant=participant,
                upi_link=upi_link
            )
            
            # Send message with fallback (Requirements 4.2, 4.3)
            delivery_result = await self.communication.send_message_with_fallback(
                phone_number=phone_number,
                message=message
            )
            
            # Update payment request record with delivery status
            await self._update_payment_request_status(
                payment_request_id=payment_request.id,
                delivery_result=delivery_result
            )
            
            # Update participant status
            if delivery_result["success"]:
                participant.payment_status = 'sent'
                await self.db.update_bill_participant(participant)
            
            return PaymentRequestResult(
                participant_id=str(participant.id),
                participant_name=participant_name,
                phone_number=phone_number,
                amount=participant.amount_owed,
                success=delivery_result["success"],
                delivery_method=delivery_result.get("final_method"),
                fallback_used=delivery_result.get("fallback_used", False),
                upi_link=upi_link,
                message_sent=message,
                error=delivery_result.get("error"),
                payment_request_id=str(payment_request.id)
            )
            
        except Exception as e:
            logger.error(f"Failed to send payment request to participant {participant.id}: {e}")
            return PaymentRequestResult(
                participant_id=str(participant.id),
                participant_name=getattr(participant.contact, 'name', 'Unknown') if participant.contact else 'Unknown',
                phone_number=getattr(participant.contact, 'phone_number', 'Unknown') if participant.contact else 'Unknown',
                amount=participant.amount_owed,
                success=False,
                delivery_method=None,
                fallback_used=False,
                upi_link="",
                message_sent="",
                error=str(e)
            )
    
    async def _create_payment_request_record(
        self,
        participant: BillParticipant,
        upi_link: str
    ) -> PaymentRequest:
        """
        Create payment request record in database
        Implements requirement 4.5
        """
        payment_request = PaymentRequest(
            bill_participant_id=participant.id,
            upi_link=upi_link,
            status='pending',
            delivery_attempts=0
        )
        
        return await self.db.create_payment_request(payment_request)
    
    async def _update_payment_request_status(
        self,
        payment_request_id: str,
        delivery_result: Dict[str, Any]
    ):
        """Update payment request status based on delivery result"""
        try:
            payment_request = await self.db.get_payment_request(payment_request_id)
            if not payment_request:
                logger.error(f"Payment request {payment_request_id} not found")
                return
            
            # Update delivery status
            if delivery_result["success"]:
                final_method = delivery_result.get("final_method")
                if final_method == DeliveryMethod.WHATSAPP:
                    payment_request.whatsapp_sent = True
                elif final_method == DeliveryMethod.SMS:
                    payment_request.sms_sent = True
                
                payment_request.status = 'sent'
            else:
                payment_request.status = 'failed'
                payment_request.delivery_error = delivery_result.get("error")
            
            payment_request.delivery_attempts += 1
            payment_request.last_delivery_attempt = datetime.now()
            
            await self.db.update_payment_request(payment_request)
            
        except Exception as e:
            logger.error(f"Failed to update payment request status: {e}")
    
    def _create_payment_message(
        self,
        participant_name: str,
        amount: Decimal,
        bill_description: str,
        upi_link: str,
        custom_message: Optional[str] = None
    ) -> str:
        """
        Create personalized payment message for participant
        Implements requirement 4.4 for personalized message templates
        """
        # Base message template
        message_parts = [
            f"Hi {participant_name}! 👋",
            "",
            "You have a bill split payment request:",
            "",
            f"💰 Amount: ₹{amount}",
            f"📝 Description: {bill_description}",
            ""
        ]
        
        # Add custom message if provided
        if custom_message:
            message_parts.extend([
                f"📋 Note: {custom_message}",
                ""
            ])
        
        # Add payment instructions
        message_parts.extend([
            "Click the link below to pay instantly:",
            upi_link,
            "",
            "Or reply 'DONE' once you've completed the payment.",
            "",
            "Thanks! 🙏"
        ])
        
        return "\n".join(message_parts)
    
    async def _send_organizer_confirmation(
        self,
        organizer_phone: str,
        bill: Bill,
        summary: DistributionSummary
    ):
        """
        Send confirmation message to bill organizer
        Implements requirement 4.4
        """
        try:
            # Create confirmation message
            message = self._create_organizer_confirmation_message(bill, summary)
            
            # Send confirmation
            await self.communication.send_message_with_fallback(
                phone_number=organizer_phone,
                message=message
            )
            
            logger.info(f"Organizer confirmation sent to {organizer_phone}")
            
        except Exception as e:
            logger.error(f"Failed to send organizer confirmation: {e}")
    
    def _create_organizer_confirmation_message(
        self,
        bill: Bill,
        summary: DistributionSummary
    ) -> str:
        """Create confirmation message for bill organizer"""
        message_parts = [
            "✅ Payment requests sent successfully!",
            "",
            f"📋 Bill: {bill.description or 'Shared Expense'}",
            f"💰 Total Amount: ₹{bill.total_amount}",
            f"👥 Participants: {summary.total_participants}",
            "",
            "📊 Delivery Summary:",
            f"✅ Successful: {summary.successful_sends}",
            f"❌ Failed: {summary.failed_sends}",
            f"📱 WhatsApp: {summary.whatsapp_sends}",
            f"💬 SMS: {summary.sms_sends}",
            ""
        ]
        
        if summary.failed_sends > 0:
            message_parts.extend([
                "⚠️ Some messages failed to deliver. You may need to contact those participants directly.",
                ""
            ])
        
        message_parts.extend([
            "I'll notify you when participants confirm their payments.",
            "",
            "You can check payment status anytime by asking 'show bill status'."
        ])
        
        return "\n".join(message_parts)
    
    async def send_payment_reminder(
        self,
        bill_id: str,
        participant_ids: Optional[List[str]] = None,
        custom_message: Optional[str] = None
    ) -> DistributionSummary:
        """
        Send payment reminders to unpaid participants
        Implements requirement 6.4 for resending payment requests
        """
        started_at = datetime.now()
        logger.info(f"Sending payment reminders for bill {bill_id}")
        
        try:
            # Get bill and participants
            bill = await self.db.get_bill_with_participants(bill_id)
            if not bill:
                raise ValueError(f"Bill {bill_id} not found")
            
            # Filter participants to remind
            participants_to_remind = []
            for participant in bill.participants:
                # Skip if already paid
                if participant.payment_status == 'confirmed':
                    continue
                
                # If specific participant IDs provided, only include those
                if participant_ids and str(participant.id) not in participant_ids:
                    continue
                
                participants_to_remind.append(participant)
            
            if not participants_to_remind:
                logger.info(f"No participants to remind for bill {bill_id}")
                return DistributionSummary(
                    bill_id=bill_id,
                    total_participants=0,
                    successful_sends=0,
                    failed_sends=0,
                    whatsapp_sends=0,
                    sms_sends=0,
                    results=[],
                    started_at=started_at,
                    completed_at=datetime.now()
                )
            
            # Send reminders
            results = []
            for participant in participants_to_remind:
                result = await self._send_payment_reminder_to_participant(
                    bill=bill,
                    participant=participant,
                    custom_message=custom_message
                )
                results.append(result)
                
                # Update reminder tracking
                participant.reminder_count += 1
                participant.last_reminder_sent = datetime.now()
                await self.db.update_bill_participant(participant)
            
            # Create summary
            completed_at = datetime.now()
            summary = DistributionSummary(
                bill_id=bill_id,
                total_participants=len(results),
                successful_sends=len([r for r in results if r.success]),
                failed_sends=len([r for r in results if not r.success]),
                whatsapp_sends=len([r for r in results if r.delivery_method == DeliveryMethod.WHATSAPP]),
                sms_sends=len([r for r in results if r.delivery_method == DeliveryMethod.SMS]),
                results=results,
                started_at=started_at,
                completed_at=completed_at
            )
            
            logger.info(f"Payment reminders sent for bill {bill_id}: "
                       f"{summary.successful_sends}/{summary.total_participants} successful")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to send payment reminders for bill {bill_id}: {e}")
            raise
    
    async def _send_payment_reminder_to_participant(
        self,
        bill: Bill,
        participant: BillParticipant,
        custom_message: Optional[str] = None
    ) -> PaymentRequestResult:
        """Send payment reminder to a single participant"""
        try:
            contact = participant.contact
            if not contact:
                raise ValueError(f"Contact not found for participant {participant.id}")
            
            participant_name = contact.name or "Friend"
            phone_number = contact.phone_number
            
            if not phone_number:
                raise ValueError(f"Phone number not found for participant {participant.id}")
            
            # Get existing payment request or create new UPI link
            existing_request = await self.db.get_latest_payment_request_for_participant(participant.id)
            if existing_request and existing_request.upi_link:
                upi_link = existing_request.upi_link
            else:
                upi_link = self.upi_service.generate_upi_link(
                    recipient_name=participant_name,
                    amount=participant.amount_owed,
                    description=f"Bill Split: {bill.description or 'Shared Expense'}",
                    upi_app=UPIApp.GENERIC
                )
            
            # Create reminder message
            message = self._create_reminder_message(
                participant_name=participant_name,
                amount=participant.amount_owed,
                bill_description=bill.description or "Shared Expense",
                upi_link=upi_link,
                reminder_count=participant.reminder_count + 1,
                custom_message=custom_message
            )
            
            # Send reminder
            delivery_result = await self.communication.send_message_with_fallback(
                phone_number=phone_number,
                message=message
            )
            
            return PaymentRequestResult(
                participant_id=str(participant.id),
                participant_name=participant_name,
                phone_number=phone_number,
                amount=participant.amount_owed,
                success=delivery_result["success"],
                delivery_method=delivery_result.get("final_method"),
                fallback_used=delivery_result.get("fallback_used", False),
                upi_link=upi_link,
                message_sent=message,
                error=delivery_result.get("error")
            )
            
        except Exception as e:
            logger.error(f"Failed to send reminder to participant {participant.id}: {e}")
            return PaymentRequestResult(
                participant_id=str(participant.id),
                participant_name=getattr(participant.contact, 'name', 'Unknown') if participant.contact else 'Unknown',
                phone_number=getattr(participant.contact, 'phone_number', 'Unknown') if participant.contact else 'Unknown',
                amount=participant.amount_owed,
                success=False,
                delivery_method=None,
                fallback_used=False,
                upi_link="",
                message_sent="",
                error=str(e)
            )
    
    def _create_reminder_message(
        self,
        participant_name: str,
        amount: Decimal,
        bill_description: str,
        upi_link: str,
        reminder_count: int,
        custom_message: Optional[str] = None
    ) -> str:
        """Create payment reminder message"""
        # Friendly reminder prefixes based on count
        reminder_prefixes = {
            1: "Friendly reminder! 😊",
            2: "Just checking in! 👋",
            3: "Hope you're doing well! 🙂"
        }
        
        prefix = reminder_prefixes.get(reminder_count, "Following up on your payment 📝")
        
        message_parts = [
            f"Hi {participant_name}! {prefix}",
            "",
            "You still have a pending payment for:",
            "",
            f"💰 Amount: ₹{amount}",
            f"📝 Description: {bill_description}",
            ""
        ]
        
        if custom_message:
            message_parts.extend([
                f"📋 Note: {custom_message}",
                ""
            ])
        
        message_parts.extend([
            "You can pay using this link:",
            upi_link,
            "",
            "Or reply 'DONE' if you've already paid.",
            "",
            "Thanks for your patience! 🙏"
        ])
        
        return "\n".join(message_parts)
    
    async def process_payment_confirmation(
        self,
        participant_phone: str,
        bill_id: str,
        confirmation_message: str
    ) -> bool:
        """
        Process payment confirmation from participant
        Implements requirement 5.1, 5.2, 5.3
        """
        try:
            # Find participant by phone number and bill
            participant = await self.db.get_participant_by_phone_and_bill(
                phone_number=participant_phone,
                bill_id=bill_id
            )
            
            if not participant:
                logger.warning(f"Participant not found for phone {participant_phone} and bill {bill_id}")
                return False
            
            # Mark as confirmed
            participant.payment_status = 'confirmed'
            participant.paid_at = datetime.now()
            await self.db.update_bill_participant(participant)
            
            # Update payment request status
            payment_request = await self.db.get_latest_payment_request_for_participant(participant.id)
            if payment_request:
                payment_request.mark_as_confirmed()
                await self.db.update_payment_request(payment_request)
            
            # Notify organizer
            bill = await self.db.get_bill_with_participants(bill_id)
            if bill and bill.user:
                await self._send_payment_confirmation_to_organizer(
                    organizer_phone=bill.user.phone_number,
                    participant_name=participant.contact.name if participant.contact else "Participant",
                    amount=participant.amount_owed,
                    bill_description=bill.description or "Shared Expense"
                )
                
                # Check if all payments are complete
                if bill.is_fully_paid:
                    await self._send_completion_notification(
                        organizer_phone=bill.user.phone_number,
                        bill=bill
                    )
            
            logger.info(f"Payment confirmed for participant {participant.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process payment confirmation: {e}")
            return False
    
    async def _send_payment_confirmation_to_organizer(
        self,
        organizer_phone: str,
        participant_name: str,
        amount: Decimal,
        bill_description: str
    ):
        """Send payment confirmation notification to organizer"""
        try:
            message = f"""✅ Payment Confirmed!

{participant_name} has paid ₹{amount} for "{bill_description}".

Great! One less person to follow up with. 😊"""
            
            await self.communication.send_message_with_fallback(
                phone_number=organizer_phone,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Failed to send payment confirmation to organizer: {e}")
    
    async def _send_completion_notification(
        self,
        organizer_phone: str,
        bill: Bill
    ):
        """Send completion notification when all payments are confirmed"""
        try:
            message = f"""🎉 All Payments Complete!

Great news! Everyone has paid for "{bill.description or 'Shared Expense'}".

💰 Total Amount: ₹{bill.total_amount}
✅ All participants have confirmed payment

The bill is now complete. Thanks for using Bill Splitter! 🙏"""
            
            await self.communication.send_message_with_fallback(
                phone_number=organizer_phone,
                message=message
            )
            
            # Update bill status to completed
            bill.status = 'completed'
            await self.db.update_bill(bill)
            
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")
    
    def _get_payment_request_template(self) -> str:
        """Get payment request message template"""
        return """Hi {participant_name}! 👋

You have a bill split payment request:

💰 Amount: ₹{amount}
📝 Description: {bill_description}

{custom_message}

Click the link below to pay instantly:
{upi_link}

Or reply "DONE" once you've completed the payment.

Thanks! 🙏"""
    
    def _get_organizer_confirmation_template(self) -> str:
        """Get organizer confirmation message template"""
        return """✅ Payment requests sent successfully!

📋 Bill: {bill_description}
💰 Total Amount: ₹{total_amount}
👥 Participants: {participant_count}

📊 Delivery Summary:
✅ Successful: {successful_sends}
❌ Failed: {failed_sends}
📱 WhatsApp: {whatsapp_sends}
💬 SMS: {sms_sends}

I'll notify you when participants confirm their payments."""
    
    def _get_reminder_template(self) -> str:
        """Get payment reminder message template"""
        return """Hi {participant_name}! {reminder_prefix}

You still have a pending payment for:

💰 Amount: ₹{amount}
📝 Description: {bill_description}

{custom_message}

You can pay using this link:
{upi_link}

Or reply "DONE" if you've already paid.

Thanks for your patience! 🙏"""
    
    def _get_completion_notification_template(self) -> str:
        """Get completion notification message template"""
        return """🎉 All Payments Complete!

Great news! Everyone has paid for "{bill_description}".

💰 Total Amount: ₹{total_amount}
✅ All participants have confirmed payment

The bill is now complete. Thanks for using Bill Splitter! 🙏"""
    
    async def get_payment_request_statistics(
        self,
        bill_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get payment request statistics"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get statistics from database
            stats = await self.db.get_payment_request_statistics(
                bill_id=bill_id,
                since_date=cutoff_date
            )
            
            return {
                "total_requests": stats.get("total_requests", 0),
                "successful_deliveries": stats.get("successful_deliveries", 0),
                "failed_deliveries": stats.get("failed_deliveries", 0),
                "whatsapp_deliveries": stats.get("whatsapp_deliveries", 0),
                "sms_deliveries": stats.get("sms_deliveries", 0),
                "confirmed_payments": stats.get("confirmed_payments", 0),
                "success_rate": stats.get("success_rate", 0.0),
                "confirmation_rate": stats.get("confirmation_rate", 0.0),
                "period_days": days,
                "bill_id": bill_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get payment request statistics: {e}")
            return {}