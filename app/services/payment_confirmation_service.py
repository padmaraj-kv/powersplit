"""
Payment Confirmation Tracking Service

This service handles payment confirmation message processing, status updates,
and notifications for bill creators when participants confirm payments.

Requirements implemented:
- 5.1: Process payment confirmation messages from participants
- 5.2: Update payment status in database when confirmations are received
- 5.3: Send notifications to bill creator when payments are confirmed
- 5.5: Detect completion when all payments are confirmed
"""
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from app.models.database import Bill, BillParticipant, PaymentRequest, Contact, User
from app.models.enums import PaymentStatus, DeliveryMethod
from app.database.repositories import DatabaseRepository
from app.services.communication_service import communication_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConfirmationKeyword(str, Enum):
    """Keywords that indicate payment confirmation"""
    DONE = "done"
    PAID = "paid"
    COMPLETE = "complete"
    COMPLETED = "completed"
    FINISHED = "finished"
    YES = "yes"
    CONFIRMED = "confirmed"
    SENT = "sent"


@dataclass
class PaymentConfirmationResult:
    """Result of payment confirmation processing"""
    success: bool
    participant_id: Optional[str]
    participant_name: Optional[str]
    amount: Optional[Decimal]
    bill_id: Optional[str]
    bill_description: Optional[str]
    organizer_notified: bool
    completion_detected: bool
    error: Optional[str] = None


class PaymentConfirmationService:
    """
    Service for processing payment confirmations and managing completion tracking
    Implements requirements 5.1, 5.2, 5.3, 5.5
    """
    
    def __init__(self, db_repository: DatabaseRepository):
        self.db = db_repository
        self.communication = communication_service
        
        # Confirmation patterns for message parsing
        self.confirmation_patterns = [
            r'\b(done|paid|complete|completed|finished|confirmed|sent)\b',
            r'\b(payment\s+(done|made|sent|completed))\b',
            r'\b(money\s+(sent|transferred|paid))\b',
            r'\b(amount\s+(paid|sent|transferred))\b',
            r'✅',  # Checkmark emoji
            r'👍',  # Thumbs up emoji
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.confirmation_patterns]
    
    async def process_payment_confirmation_message(
        self,
        sender_phone: str,
        message_content: str,
        message_timestamp: datetime
    ) -> PaymentConfirmationResult:
        """
        Process incoming message to detect and handle payment confirmations
        Implements requirement 5.1
        
        Args:
            sender_phone: Phone number of the message sender
            message_content: Content of the message
            message_timestamp: When the message was received
            
        Returns:
            PaymentConfirmationResult: Result of the confirmation processing
        """
        logger.info(f"Processing potential payment confirmation from {sender_phone}")
        
        try:
            # Check if message indicates payment confirmation
            if not self._is_confirmation_message(message_content):
                logger.debug(f"Message from {sender_phone} does not indicate payment confirmation")
                return PaymentConfirmationResult(
                    success=False,
                    participant_id=None,
                    participant_name=None,
                    amount=None,
                    bill_id=None,
                    bill_description=None,
                    organizer_notified=False,
                    completion_detected=False,
                    error="Message does not indicate payment confirmation"
                )
            
            # Find active bills where this phone number is a participant
            active_participants = await self._find_active_participants_by_phone(sender_phone)
            
            if not active_participants:
                logger.info(f"No active bill participants found for phone {sender_phone}")
                return PaymentConfirmationResult(
                    success=False,
                    participant_id=None,
                    participant_name=None,
                    amount=None,
                    bill_id=None,
                    bill_description=None,
                    organizer_notified=False,
                    completion_detected=False,
                    error="No active bill participants found for this phone number"
                )
            
            # Process confirmations for all active participants
            results = []
            for participant in active_participants:
                result = await self._process_participant_confirmation(
                    participant=participant,
                    message_content=message_content,
                    message_timestamp=message_timestamp
                )
                results.append(result)
            
            # Return the first successful result or the last result if none succeeded
            successful_results = [r for r in results if r.success]
            if successful_results:
                return successful_results[0]
            else:
                return results[-1] if results else PaymentConfirmationResult(
                    success=False,
                    participant_id=None,
                    participant_name=None,
                    amount=None,
                    bill_id=None,
                    bill_description=None,
                    organizer_notified=False,
                    completion_detected=False,
                    error="Failed to process confirmation for any active participants"
                )
                
        except Exception as e:
            logger.error(f"Error processing payment confirmation message: {e}")
            return PaymentConfirmationResult(
                success=False,
                participant_id=None,
                participant_name=None,
                amount=None,
                bill_id=None,
                bill_description=None,
                organizer_notified=False,
                completion_detected=False,
                error=str(e)
            )
    
    async def _process_participant_confirmation(
        self,
        participant: BillParticipant,
        message_content: str,
        message_timestamp: datetime
    ) -> PaymentConfirmationResult:
        """
        Process payment confirmation for a specific participant
        Implements requirements 5.2, 5.3, 5.5
        """
        try:
            # Check if participant is already confirmed
            if participant.payment_status == PaymentStatus.CONFIRMED:
                logger.info(f"Participant {participant.id} already confirmed payment")
                return PaymentConfirmationResult(
                    success=True,
                    participant_id=str(participant.id),
                    participant_name=participant.contact.name if participant.contact else "Participant",
                    amount=participant.amount_owed,
                    bill_id=str(participant.bill_id),
                    bill_description=participant.bill.description if participant.bill else None,
                    organizer_notified=False,
                    completion_detected=False,
                    error="Payment already confirmed"
                )
            
            # Update participant payment status (Requirement 5.2)
            participant.payment_status = PaymentStatus.CONFIRMED
            participant.paid_at = message_timestamp
            await self.db.update_bill_participant(participant)
            
            # Update payment request status if exists
            payment_request = await self.db.get_latest_payment_request_for_participant(str(participant.id))
            if payment_request:
                payment_request.mark_as_confirmed()
                await self.db.update_payment_request(payment_request)
            
            # Get bill information for notifications
            bill = await self.db.get_bill_with_participants(str(participant.bill_id))
            if not bill:
                raise ValueError(f"Bill {participant.bill_id} not found")
            
            participant_name = participant.contact.name if participant.contact else "Participant"
            
            # Send notification to bill organizer (Requirement 5.3)
            organizer_notified = await self._notify_organizer_of_payment(
                bill=bill,
                participant_name=participant_name,
                amount=participant.amount_owed
            )
            
            # Check if all payments are complete (Requirement 5.5)
            completion_detected = await self._check_and_handle_completion(bill)
            
            logger.info(f"Payment confirmed for participant {participant.id} on bill {bill.id}")
            
            return PaymentConfirmationResult(
                success=True,
                participant_id=str(participant.id),
                participant_name=participant_name,
                amount=participant.amount_owed,
                bill_id=str(bill.id),
                bill_description=bill.description,
                organizer_notified=organizer_notified,
                completion_detected=completion_detected
            )
            
        except Exception as e:
            logger.error(f"Error processing participant confirmation: {e}")
            return PaymentConfirmationResult(
                success=False,
                participant_id=str(participant.id) if participant else None,
                participant_name=None,
                amount=None,
                bill_id=None,
                bill_description=None,
                organizer_notified=False,
                completion_detected=False,
                error=str(e)
            )
    
    async def _notify_organizer_of_payment(
        self,
        bill: Bill,
        participant_name: str,
        amount: Decimal
    ) -> bool:
        """
        Send payment confirmation notification to bill organizer
        Implements requirement 5.3
        """
        try:
            if not bill.user or not bill.user.phone_number:
                logger.warning(f"No organizer contact found for bill {bill.id}")
                return False
            
            # Create notification message
            message = self._create_payment_notification_message(
                participant_name=participant_name,
                amount=amount,
                bill_description=bill.description or "Shared Expense"
            )
            
            # Send notification
            delivery_result = await self.communication.send_message_with_fallback(
                phone_number=bill.user.phone_number,
                message=message
            )
            
            if delivery_result["success"]:
                logger.info(f"Payment notification sent to organizer for bill {bill.id}")
                return True
            else:
                logger.error(f"Failed to send payment notification: {delivery_result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending organizer notification: {e}")
            return False
    
    async def _check_and_handle_completion(self, bill: Bill) -> bool:
        """
        Check if all payments are complete and handle completion
        Implements requirement 5.5
        """
        try:
            # Check if all participants have confirmed payment
            all_confirmed = all(
                p.payment_status == PaymentStatus.CONFIRMED 
                for p in bill.participants
            )
            
            if not all_confirmed:
                logger.debug(f"Bill {bill.id} not yet complete - some payments pending")
                return False
            
            # All payments confirmed - send completion notification
            completion_sent = await self._send_completion_notification(bill)
            
            if completion_sent:
                # Update bill status to completed
                bill.status = 'completed'
                await self.db.update_bill(bill)
                
                logger.info(f"Bill {bill.id} marked as completed - all payments confirmed")
                return True
            else:
                logger.warning(f"Bill {bill.id} complete but failed to send notification")
                return False
                
        except Exception as e:
            logger.error(f"Error checking bill completion: {e}")
            return False
    
    async def _send_completion_notification(self, bill: Bill) -> bool:
        """Send completion notification to bill organizer"""
        try:
            if not bill.user or not bill.user.phone_number:
                logger.warning(f"No organizer contact found for completion notification")
                return False
            
            # Create completion message
            message = self._create_completion_notification_message(bill)
            
            # Send notification
            delivery_result = await self.communication.send_message_with_fallback(
                phone_number=bill.user.phone_number,
                message=message
            )
            
            if delivery_result["success"]:
                logger.info(f"Completion notification sent for bill {bill.id}")
                return True
            else:
                logger.error(f"Failed to send completion notification: {delivery_result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")
            return False
    
    def _is_confirmation_message(self, message_content: str) -> bool:
        """
        Check if message content indicates payment confirmation
        Uses pattern matching to detect confirmation keywords
        """
        if not message_content:
            return False
        
        # Check against compiled patterns
        for pattern in self.compiled_patterns:
            if pattern.search(message_content):
                return True
        
        return False
    
    async def _find_active_participants_by_phone(self, phone_number: str) -> List[BillParticipant]:
        """
        Find all active bill participants for a given phone number
        Returns participants from bills that are not yet completed
        """
        try:
            # Use repository method to find active participants
            participants = await self.db.find_active_participants_by_phone(
                phone_number=phone_number,
                days_back=30  # Look back 30 days for active bills
            )
            
            logger.info(f"Found {len(participants)} active participants for phone {phone_number}")
            return participants
            
        except Exception as e:
            logger.error(f"Error finding active participants: {e}")
            return []
    
    def _create_payment_notification_message(
        self,
        participant_name: str,
        amount: Decimal,
        bill_description: str
    ) -> str:
        """Create payment confirmation notification message for organizer"""
        return f"""✅ Payment Confirmed!

{participant_name} has confirmed payment of ₹{amount} for "{bill_description}".

Great! One less person to follow up with. 😊

You can check the status of all payments by asking "show bill status"."""
    
    def _create_completion_notification_message(self, bill: Bill) -> str:
        """Create completion notification message for organizer"""
        participant_count = len(bill.participants)
        
        return f"""🎉 All Payments Complete!

Fantastic news! All {participant_count} participants have confirmed their payments for "{bill.description or 'Shared Expense'}".

💰 Total Amount: ₹{bill.total_amount}
✅ All payments confirmed

The bill is now complete. Thanks for using Bill Splitter! 🙏"""
    
    async def get_payment_confirmation_statistics(
        self,
        bill_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get statistics about payment confirmations"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get payment confirmation statistics
            # This would need to be implemented in the repository
            stats = {
                "total_confirmations": 0,
                "confirmations_today": 0,
                "average_confirmation_time": 0.0,
                "completion_rate": 0.0,
                "period_days": days,
                "bill_id": bill_id
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get payment confirmation statistics: {e}")
            return {}
    
    async def handle_payment_inquiry(
        self,
        sender_phone: str,
        message_content: str
    ) -> Optional[str]:
        """
        Handle inquiries about payment status from participants
        Returns response message if inquiry detected, None otherwise
        """
        try:
            # Check if message is asking about payment status
            inquiry_patterns = [
                r'\b(status|check|how much|amount|bill|payment)\b',
                r'\b(what.*owe|how.*much.*pay)\b',
                r'\b(bill.*details|payment.*info)\b'
            ]
            
            is_inquiry = any(
                re.search(pattern, message_content, re.IGNORECASE) 
                for pattern in inquiry_patterns
            )
            
            if not is_inquiry:
                return None
            
            # Find participant's active bills
            active_participants = await self._find_active_participants_by_phone(sender_phone)
            
            if not active_participants:
                return "I don't have any active bill information for your number. Please check with the person who created the bill."
            
            # Create status response for the most recent bill
            participant = active_participants[0]  # Most recent
            bill = await self.db.get_bill_with_participants(str(participant.bill_id))
            
            if not bill:
                return "Sorry, I couldn't find the bill details. Please contact the bill organizer."
            
            # Create status message
            status_message = f"""📋 Your Bill Status

Bill: {bill.description or 'Shared Expense'}
Your Amount: ₹{participant.amount_owed}
Status: {participant.payment_status.title()}

"""
            
            if participant.payment_status == PaymentStatus.CONFIRMED:
                status_message += "✅ Your payment has been confirmed. Thank you!"
            else:
                # Get payment request if available
                payment_request = await self.db.get_latest_payment_request_for_participant(str(participant.id))
                if payment_request and payment_request.upi_link:
                    status_message += f"You can pay using this link:\n{payment_request.upi_link}\n\n"
                
                status_message += "Reply 'DONE' once you've completed the payment."
            
            return status_message
            
        except Exception as e:
            logger.error(f"Error handling payment inquiry: {e}")
            return "Sorry, I encountered an error while checking your payment status. Please try again later."