"""
Bill Query Service for retrieving bill history and status information
Implements requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from app.interfaces.services import BillQueryServiceInterface
from app.models.database import User, Bill, BillParticipant, Contact, PaymentRequest
from app.models.schemas import (
    BillSummary, BillDetails, BillStatusInfo, BillFilters, 
    ParticipantDetails, BillItem
)
from app.models.enums import BillStatus, PaymentStatus
from app.services.payment_request_service import PaymentRequestService
from app.services.communication_service import CommunicationService
import logging

logger = logging.getLogger(__name__)


class BillQueryService(BillQueryServiceInterface):
    """
    Service for querying bill history and status information
    Implements requirement 6 for bill query functionality
    """
    
    def __init__(self, db: Session, payment_service: PaymentRequestService, 
                 communication_service: CommunicationService):
        self.db = db
        self.payment_service = payment_service
        self.communication_service = communication_service
    
    async def get_user_bills(self, user_id: str, filters: Optional[BillFilters] = None) -> List[BillSummary]:
        """
        Implements requirement 6.1 for bill history retrieval
        Returns list of bill summaries for the user with optional filtering
        """
        try:
            user_uuid = UUID(user_id)
            query = (self.db.query(Bill)
                    .options(joinedload(Bill.participants))
                    .filter(Bill.user_id == user_uuid))
            
            # Apply filters if provided
            if filters:
                if filters.status:
                    query = query.filter(Bill.status == filters.status.value)
                
                if filters.date_from:
                    query = query.filter(Bill.created_at >= filters.date_from)
                
                if filters.date_to:
                    query = query.filter(Bill.created_at <= filters.date_to)
                
                if filters.min_amount:
                    query = query.filter(Bill.total_amount >= filters.min_amount)
                
                if filters.max_amount:
                    query = query.filter(Bill.total_amount <= filters.max_amount)
                
                if filters.merchant:
                    query = query.filter(Bill.merchant.ilike(f"%{filters.merchant}%"))
                
                # Apply pagination
                query = query.offset(filters.offset).limit(filters.limit)
            else:
                # Default limit if no filters provided
                query = query.limit(50)
            
            # Order by creation date (newest first)
            bills = query.order_by(desc(Bill.created_at)).all()
            
            # Convert to BillSummary objects
            summaries = []
            for bill in bills:
                participant_count = len(bill.participants)
                paid_count = len([p for p in bill.participants if p.payment_status == PaymentStatus.CONFIRMED])
                
                summary = BillSummary(
                    id=str(bill.id),
                    description=bill.description or f"Bill from {bill.merchant or 'Unknown'}",
                    total_amount=bill.total_amount,
                    participant_count=participant_count,
                    paid_count=paid_count,
                    status=BillStatus(bill.status),
                    created_at=bill.created_at,
                    bill_date=bill.bill_date,
                    merchant=bill.merchant
                )
                summaries.append(summary)
            
            logger.info(f"Retrieved {len(summaries)} bills for user {user_id}")
            return summaries
            
        except Exception as e:
            logger.error(f"Failed to get user bills: {e}")
            return []
    
    async def get_bill_status(self, user_id: str, bill_id: str) -> Optional[BillStatusInfo]:
        """
        Implements requirement 6.2 for payment status display
        Returns detailed status information for a specific bill
        """
        try:
            user_uuid = UUID(user_id)
            bill_uuid = UUID(bill_id)
            
            # Get bill with participants and contacts
            bill = (self.db.query(Bill)
                   .options(
                       joinedload(Bill.participants).joinedload(BillParticipant.contact)
                   )
                   .filter(and_(Bill.id == bill_uuid, Bill.user_id == user_uuid))
                   .first())
            
            if not bill:
                logger.warning(f"Bill {bill_id} not found for user {user_id}")
                return None
            
            # Calculate payment statistics
            total_paid = sum(p.amount_owed for p in bill.participants if p.payment_status == PaymentStatus.CONFIRMED)
            remaining_amount = bill.total_amount - total_paid
            completion_percentage = (total_paid / bill.total_amount * 100) if bill.total_amount > 0 else 0
            
            # Build participant details
            participants = []
            for participant in bill.participants:
                contact = participant.contact
                participant_detail = ParticipantDetails(
                    id=str(participant.id),
                    name=contact.name if contact else "Unknown",
                    phone_number=contact.phone_number if contact else "Unknown",
                    amount_owed=participant.amount_owed,
                    payment_status=PaymentStatus(participant.payment_status),
                    paid_at=participant.paid_at,
                    reminder_count=participant.reminder_count,
                    last_reminder_sent=participant.last_reminder_sent
                )
                participants.append(participant_detail)
            
            status_info = BillStatusInfo(
                id=str(bill.id),
                description=bill.description or f"Bill from {bill.merchant or 'Unknown'}",
                total_amount=bill.total_amount,
                status=BillStatus(bill.status),
                created_at=bill.created_at,
                participants=participants,
                total_paid=total_paid,
                remaining_amount=remaining_amount,
                completion_percentage=completion_percentage
            )
            
            logger.info(f"Retrieved status for bill {bill_id}")
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get bill status: {e}")
            return None
    
    async def get_bill_details(self, user_id: str, bill_id: str) -> Optional[BillDetails]:
        """
        Implements requirement 6.3 for complete bill information
        Returns comprehensive bill details including items and participants
        """
        try:
            user_uuid = UUID(user_id)
            bill_uuid = UUID(bill_id)
            
            # Get bill with all related data
            bill = (self.db.query(Bill)
                   .options(
                       joinedload(Bill.participants).joinedload(BillParticipant.contact)
                   )
                   .filter(and_(Bill.id == bill_uuid, Bill.user_id == user_uuid))
                   .first())
            
            if not bill:
                logger.warning(f"Bill {bill_id} not found for user {user_id}")
                return None
            
            # Parse items from JSON data
            items = []
            if bill.items_data:
                for item_data in bill.items_data:
                    item = BillItem(
                        name=item_data.get('name', 'Unknown Item'),
                        amount=Decimal(str(item_data.get('amount', 0))),
                        quantity=item_data.get('quantity', 1)
                    )
                    items.append(item)
            
            # Build participant details
            participants = []
            for participant in bill.participants:
                contact = participant.contact
                participant_detail = ParticipantDetails(
                    id=str(participant.id),
                    name=contact.name if contact else "Unknown",
                    phone_number=contact.phone_number if contact else "Unknown",
                    amount_owed=participant.amount_owed,
                    payment_status=PaymentStatus(participant.payment_status),
                    paid_at=participant.paid_at,
                    reminder_count=participant.reminder_count,
                    last_reminder_sent=participant.last_reminder_sent
                )
                participants.append(participant_detail)
            
            details = BillDetails(
                id=str(bill.id),
                description=bill.description or f"Bill from {bill.merchant or 'Unknown'}",
                total_amount=bill.total_amount,
                currency=bill.currency,
                merchant=bill.merchant,
                bill_date=bill.bill_date,
                created_at=bill.created_at,
                status=BillStatus(bill.status),
                items=items,
                participants=participants
            )
            
            logger.info(f"Retrieved details for bill {bill_id}")
            return details
            
        except Exception as e:
            logger.error(f"Failed to get bill details: {e}")
            return None
    
    async def send_payment_reminders(self, user_id: str, bill_id: str, 
                                   participant_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Implements requirement 6.4 for resending payment requests
        Sends payment reminders to unpaid participants
        """
        try:
            user_uuid = UUID(user_id)
            bill_uuid = UUID(bill_id)
            
            # Get bill with participants
            bill = (self.db.query(Bill)
                   .options(
                       joinedload(Bill.participants).joinedload(BillParticipant.contact)
                   )
                   .filter(and_(Bill.id == bill_uuid, Bill.user_id == user_uuid))
                   .first())
            
            if not bill:
                logger.warning(f"Bill {bill_id} not found for user {user_id}")
                return {"success": False, "error": "Bill not found"}
            
            # Filter participants to remind
            participants_to_remind = []
            for participant in bill.participants:
                # Only remind unpaid participants
                if participant.payment_status != PaymentStatus.CONFIRMED:
                    # If specific participant IDs provided, only include those
                    if participant_ids is None or str(participant.id) in participant_ids:
                        participants_to_remind.append(participant)
            
            if not participants_to_remind:
                return {"success": True, "message": "No participants need reminders", "reminded_count": 0}
            
            # Send reminders using payment request service
            results = {
                "success": True,
                "reminded_count": 0,
                "failed_count": 0,
                "details": []
            }
            
            for participant in participants_to_remind:
                try:
                    # Get or create payment request for this participant
                    payment_request = (self.db.query(PaymentRequest)
                                     .filter(PaymentRequest.bill_participant_id == participant.id)
                                     .order_by(desc(PaymentRequest.created_at))
                                     .first())
                    
                    if not payment_request:
                        # Create new payment request if none exists
                        from app.services.upi_service import UPIService
                        upi_service = UPIService()
                        
                        upi_link = await upi_service.generate_upi_link(
                            recipient_name=participant.contact.name,
                            amount=participant.amount_owed,
                            description=f"Payment for {bill.description or 'bill'}"
                        )
                        
                        payment_request = PaymentRequest(
                            bill_participant_id=participant.id,
                            upi_link=upi_link
                        )
                        self.db.add(payment_request)
                        self.db.commit()
                        self.db.refresh(payment_request)
                    
                    # Send reminder message
                    message = self._create_reminder_message(
                        participant.contact.name,
                        participant.amount_owed,
                        bill.description or "bill",
                        payment_request.upi_link,
                        participant.reminder_count + 1
                    )
                    
                    # Send via communication service with fallback
                    delivery_result = await self.communication_service.send_message_with_fallback(
                        participant.contact.phone_number,
                        message
                    )
                    
                    if delivery_result.get("success"):
                        # Update reminder tracking
                        participant.reminder_count += 1
                        participant.last_reminder_sent = datetime.utcnow()
                        self.db.commit()
                        
                        results["reminded_count"] += 1
                        results["details"].append({
                            "participant_id": str(participant.id),
                            "name": participant.contact.name,
                            "status": "sent",
                            "method": delivery_result.get("method")
                        })
                    else:
                        results["failed_count"] += 1
                        results["details"].append({
                            "participant_id": str(participant.id),
                            "name": participant.contact.name,
                            "status": "failed",
                            "error": delivery_result.get("error")
                        })
                
                except Exception as e:
                    logger.error(f"Failed to send reminder to participant {participant.id}: {e}")
                    results["failed_count"] += 1
                    results["details"].append({
                        "participant_id": str(participant.id),
                        "name": participant.contact.name if participant.contact else "Unknown",
                        "status": "failed",
                        "error": str(e)
                    })
            
            logger.info(f"Sent {results['reminded_count']} reminders for bill {bill_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to send payment reminders: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_unpaid_participants(self, user_id: str, bill_id: str) -> List[ParticipantDetails]:
        """
        Get list of participants who haven't paid yet
        Used for requirement 6.4 to identify who needs reminders
        """
        try:
            user_uuid = UUID(user_id)
            bill_uuid = UUID(bill_id)
            
            # Get unpaid participants
            participants = (self.db.query(BillParticipant)
                          .options(joinedload(BillParticipant.contact))
                          .join(Bill)
                          .filter(and_(
                              Bill.id == bill_uuid,
                              Bill.user_id == user_uuid,
                              BillParticipant.payment_status != PaymentStatus.CONFIRMED
                          ))
                          .all())
            
            unpaid_participants = []
            for participant in participants:
                contact = participant.contact
                participant_detail = ParticipantDetails(
                    id=str(participant.id),
                    name=contact.name if contact else "Unknown",
                    phone_number=contact.phone_number if contact else "Unknown",
                    amount_owed=participant.amount_owed,
                    payment_status=PaymentStatus(participant.payment_status),
                    paid_at=participant.paid_at,
                    reminder_count=participant.reminder_count,
                    last_reminder_sent=participant.last_reminder_sent
                )
                unpaid_participants.append(participant_detail)
            
            logger.info(f"Found {len(unpaid_participants)} unpaid participants for bill {bill_id}")
            return unpaid_participants
            
        except Exception as e:
            logger.error(f"Failed to get unpaid participants: {e}")
            return []
    
    def _create_reminder_message(self, name: str, amount: Decimal, description: str, 
                               upi_link: str, reminder_number: int) -> str:
        """Create a personalized reminder message"""
        reminder_text = "Reminder" if reminder_number == 1 else f"Reminder #{reminder_number}"
        
        message = f"""
🔔 {reminder_text}: Payment Request

Hi {name}! 

This is a friendly reminder about your pending payment:

💰 Amount: ₹{amount}
📝 For: {description}

Please complete your payment using the link below:
{upi_link}

Once paid, simply reply "paid" or "done" to confirm.

Thank you! 🙏
        """.strip()
        
        return message