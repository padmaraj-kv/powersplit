"""
Database repository implementations for data access layer
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, func
from app.models.database import User, Contact, Bill, BillParticipant, PaymentRequest, ConversationState
from app.models.enums import PaymentStatus
from app.interfaces.repositories import (
    UserRepository, ContactRepository, BillRepository, 
    PaymentRepository, ConversationRepository
)
import logging

logger = logging.getLogger(__name__)


class SQLUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_user(self, phone_number: str, name: Optional[str] = None) -> User:
        """Create a new user"""
        try:
            user = User(phone_number=phone_number, name=name)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"Created user with ID: {user.id}")
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise
    
    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        try:
            # Note: We need to search by encrypted phone number
            users = self.db.query(User).all()
            for user in users:
                if user.phone_number == phone_number:
                    return user
            return None
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user by phone: {e}")
            raise
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        try:
            return self.db.query(User).filter(User.id == user_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user by ID: {e}")
            raise
    
    async def update_user(self, user_id: UUID, **kwargs) -> Optional[User]:
        """Update user information"""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return None
            
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"Updated user {user_id}")
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update user: {e}")
            raise


class SQLContactRepository(ContactRepository):
    """SQLAlchemy implementation of ContactRepository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_contact(self, user_id: UUID, name: str, phone_number: str) -> Contact:
        """Create a new contact"""
        try:
            contact = Contact(user_id=user_id, name=name, phone_number=phone_number)
            self.db.add(contact)
            self.db.commit()
            self.db.refresh(contact)
            logger.info(f"Created contact with ID: {contact.id}")
            return contact
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create contact: {e}")
            raise
    
    async def get_user_contacts(self, user_id: UUID) -> List[Contact]:
        """Get all contacts for a user"""
        try:
            return self.db.query(Contact).filter(Contact.user_id == user_id).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user contacts: {e}")
            raise
    
    async def find_contact_by_phone(self, user_id: UUID, phone_number: str) -> Optional[Contact]:
        """Find contact by phone number for a specific user"""
        try:
            contacts = await self.get_user_contacts(user_id)
            for contact in contacts:
                if contact.phone_number == phone_number:
                    return contact
            return None
        except SQLAlchemyError as e:
            logger.error(f"Failed to find contact by phone: {e}")
            raise
    
    async def update_contact(self, contact_id: UUID, **kwargs) -> Optional[Contact]:
        """Update contact information"""
        try:
            contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact:
                return None
            
            for key, value in kwargs.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            
            self.db.commit()
            self.db.refresh(contact)
            logger.info(f"Updated contact {contact_id}")
            return contact
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update contact: {e}")
            raise


class SQLBillRepository(BillRepository):
    """SQLAlchemy implementation of BillRepository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_bill(self, user_id: UUID, total_amount: float, **kwargs) -> Bill:
        """Create a new bill"""
        try:
            bill = Bill(user_id=user_id, total_amount=total_amount, **kwargs)
            self.db.add(bill)
            self.db.commit()
            self.db.refresh(bill)
            logger.info(f"Created bill with ID: {bill.id}")
            return bill
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create bill: {e}")
            raise
    
    async def get_user_bills(self, user_id: UUID, limit: int = 50) -> List[Bill]:
        """Get bills for a user"""
        try:
            return (self.db.query(Bill)
                   .filter(Bill.user_id == user_id)
                   .order_by(desc(Bill.created_at))
                   .limit(limit)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get user bills: {e}")
            raise
    
    async def get_bill_by_id(self, bill_id: UUID) -> Optional[Bill]:
        """Get bill by ID"""
        try:
            return self.db.query(Bill).filter(Bill.id == bill_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get bill by ID: {e}")
            raise
    
    async def add_participant(self, bill_id: UUID, contact_id: UUID, amount_owed: float) -> BillParticipant:
        """Add participant to bill"""
        try:
            participant = BillParticipant(
                bill_id=bill_id,
                contact_id=contact_id,
                amount_owed=amount_owed
            )
            self.db.add(participant)
            self.db.commit()
            self.db.refresh(participant)
            logger.info(f"Added participant to bill {bill_id}")
            return participant
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to add participant: {e}")
            raise
    
    async def get_bill_participants(self, bill_id: UUID) -> List[BillParticipant]:
        """Get all participants for a bill"""
        try:
            return (self.db.query(BillParticipant)
                   .filter(BillParticipant.bill_id == bill_id)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get bill participants: {e}")
            raise
    
    async def update_bill_status(self, bill_id: UUID, status: str) -> Optional[Bill]:
        """Update bill status"""
        try:
            bill = await self.get_bill_by_id(bill_id)
            if not bill:
                return None
            
            bill.status = status
            self.db.commit()
            self.db.refresh(bill)
            logger.info(f"Updated bill {bill_id} status to {status}")
            return bill
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update bill status: {e}")
            raise


class SQLPaymentRepository(PaymentRepository):
    """SQLAlchemy implementation of PaymentRepository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_payment_request(self, participant_id: UUID, upi_link: str) -> PaymentRequest:
        """Create a payment request"""
        try:
            payment_request = PaymentRequest(
                bill_participant_id=participant_id,
                upi_link=upi_link
            )
            self.db.add(payment_request)
            self.db.commit()
            self.db.refresh(payment_request)
            logger.info(f"Created payment request with ID: {payment_request.id}")
            return payment_request
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create payment request: {e}")
            raise
    
    async def get_payment_requests_for_bill(self, bill_id: UUID) -> List[PaymentRequest]:
        """Get all payment requests for a bill"""
        try:
            return (self.db.query(PaymentRequest)
                   .join(BillParticipant)
                   .filter(BillParticipant.bill_id == bill_id)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get payment requests for bill: {e}")
            raise
    
    async def update_payment_status(self, participant_id: UUID, status: str) -> Optional[BillParticipant]:
        """Update payment status for participant"""
        try:
            participant = (self.db.query(BillParticipant)
                          .filter(BillParticipant.id == participant_id)
                          .first())
            if not participant:
                return None
            
            participant.payment_status = status
            if status == 'confirmed':
                participant.mark_as_paid()
            
            self.db.commit()
            self.db.refresh(participant)
            logger.info(f"Updated payment status for participant {participant_id}")
            return participant
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update payment status: {e}")
            raise
    
    async def get_payment_request(self, request_id: UUID) -> Optional[PaymentRequest]:
        """Get payment request by ID"""
        try:
            payment_request = (self.db.query(PaymentRequest)
                             .options(joinedload(PaymentRequest.bill_participant))
                             .filter(PaymentRequest.id == request_id)
                             .first())
            if payment_request:
                logger.info(f"Retrieved payment request {request_id}")
            return payment_request
        except SQLAlchemyError as e:
            logger.error(f"Failed to get payment request {request_id}: {e}")
            return None
    
    async def update_delivery_status(self, request_id: UUID, method: str, success: bool) -> bool:
        """Update delivery status for payment request"""
        try:
            payment_request = (self.db.query(PaymentRequest)
                             .filter(PaymentRequest.id == request_id)
                             .first())
            if not payment_request:
                return False
            
            if method == 'whatsapp':
                payment_request.whatsapp_sent = success
            elif method == 'sms':
                payment_request.sms_sent = success
            
            if success:
                payment_request.mark_as_sent(method)
            
            self.db.commit()
            self.db.refresh(payment_request)
            logger.info(f"Updated delivery status for {request_id}: {method}={success}")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update delivery status: {e}")
            return False
    
    async def confirm_payment(self, request_id: UUID) -> bool:
        """Confirm payment received"""
        try:
            payment_request = (self.db.query(PaymentRequest)
                             .filter(PaymentRequest.id == request_id)
                             .first())
            if not payment_request:
                return False
            
            payment_request.mark_as_confirmed()
            
            # Also update the bill participant status
            participant = payment_request.bill_participant
            if participant:
                participant.mark_as_paid()
            
            self.db.commit()
            logger.info(f"Confirmed payment for request {request_id}")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to confirm payment: {e}")
            return False
    
    async def reset_delivery_status(self, request_id: UUID) -> bool:
        """Reset delivery status for resending"""
        try:
            payment_request = (self.db.query(PaymentRequest)
                             .filter(PaymentRequest.id == request_id)
                             .first())
            if not payment_request:
                return False
            
            payment_request.whatsapp_sent = False
            payment_request.sms_sent = False
            payment_request.delivery_attempts = 0
            payment_request.status = 'pending'
            
            self.db.commit()
            logger.info(f"Reset delivery status for payment request {request_id}")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to reset delivery status: {e}")
            return False
    
    async def get_payment_requests_by_bill(self, bill_id: UUID) -> List[PaymentRequest]:
        """Get all payment requests for a bill"""
        try:
            payment_requests = (self.db.query(PaymentRequest)
                              .join(BillParticipant)
                              .options(joinedload(PaymentRequest.bill_participant))
                              .filter(BillParticipant.bill_id == bill_id)
                              .order_by(PaymentRequest.created_at)
                              .all())
            logger.info(f"Retrieved {len(payment_requests)} payment requests for bill {bill_id}")
            return payment_requests
        except SQLAlchemyError as e:
            logger.error(f"Failed to get payment requests for bill {bill_id}: {e}")
            return []
    
    async def mark_payment_request_sent(self, request_id: UUID, method: str) -> Optional[PaymentRequest]:
        """Mark payment request as sent"""
        try:
            payment_request = (self.db.query(PaymentRequest)
                             .filter(PaymentRequest.id == request_id)
                             .first())
            if not payment_request:
                return None
            
            payment_request.mark_as_sent(method)
            self.db.commit()
            self.db.refresh(payment_request)
            logger.info(f"Marked payment request {request_id} as sent via {method}")
            return payment_request
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to mark payment request as sent: {e}")
            raise


class SQLConversationRepository(ConversationRepository):
    """SQLAlchemy implementation of ConversationRepository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_conversation_state(self, user_id: UUID, session_id: str, 
                                      current_step: str, context: Dict[str, Any]) -> ConversationState:
        """Create a new conversation state"""
        try:
            conversation = ConversationState(
                user_id=user_id,
                session_id=session_id,
                current_step=current_step,
                context=context
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            logger.info(f"Created conversation state with ID: {conversation.id}")
            return conversation
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create conversation state: {e}")
            raise
    
    async def get_conversation_state(self, user_id: UUID, session_id: str) -> Optional[ConversationState]:
        """Get conversation state by user and session"""
        try:
            return (self.db.query(ConversationState)
                   .filter(and_(ConversationState.user_id == user_id,
                               ConversationState.session_id == session_id))
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversation state: {e}")
            raise
    
    async def update_conversation_state(self, user_id: UUID, session_id: str, 
                                      current_step: str, context: Dict[str, Any]) -> Optional[ConversationState]:
        """Update conversation state"""
        try:
            conversation = await self.get_conversation_state(user_id, session_id)
            if not conversation:
                return await self.create_conversation_state(user_id, session_id, current_step, context)
            
            conversation.current_step = current_step
            conversation.context = context
            conversation.updated_at = func.now()
            
            self.db.commit()
            self.db.refresh(conversation)
            logger.info(f"Updated conversation state for user {user_id}")
            return conversation
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update conversation state: {e}")
            raise
    
    async def delete_conversation_state(self, user_id: UUID, session_id: str) -> bool:
        """Delete conversation state"""
        try:
            conversation = await self.get_conversation_state(user_id, session_id)
            if not conversation:
                return False
            
            self.db.delete(conversation)
            self.db.commit()
            logger.info(f"Deleted conversation state for user {user_id}")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to delete conversation state: {e}")
            raise
    
    async def cleanup_expired_states(self, hours: int = 24) -> int:
        """Clean up expired conversation states"""
        try:
            result = (self.db.query(ConversationState)
                     .filter(ConversationState.updated_at < func.now() - func.interval(f'{hours} hours'))
                     .delete())
            self.db.commit()
            logger.info(f"Cleaned up {result} expired conversation states")
            return result
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to cleanup expired states: {e}")
            raise
    
    async def get_active_conversations(self, hours: int = 24) -> List[ConversationState]:
        """Get active conversation states within specified hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return (self.db.query(ConversationState)
                   .filter(ConversationState.updated_at >= cutoff_time)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active conversations: {e}")
            raise


class DatabaseRepository:
    """
    Unified database repository for payment request service
    Combines all repository functionality needed for payment request distribution
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = SQLUserRepository(db)
        self.contact_repo = SQLContactRepository(db)
        self.bill_repo = SQLBillRepository(db)
        self.payment_repo = SQLPaymentRepository(db)
        self.conversation_repo = SQLConversationRepository(db)
    
    # Bill-related methods with participants
    async def get_bill_with_participants(self, bill_id: str) -> Optional[Bill]:
        """Get bill with all participants and their contacts"""
        try:
            bill = (self.db.query(Bill)
                   .options(
                       joinedload(Bill.participants).joinedload(BillParticipant.contact),
                       joinedload(Bill.user)
                   )
                   .filter(Bill.id == UUID(bill_id))
                   .first())
            
            if bill:
                logger.info(f"Retrieved bill {bill_id} with {len(bill.participants)} participants")
            return bill
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to get bill with participants: {e}")
            return None
    
    async def update_bill(self, bill: Bill) -> Bill:
        """Update bill in database"""
        try:
            self.db.merge(bill)
            self.db.commit()
            self.db.refresh(bill)
            logger.info(f"Updated bill {bill.id}")
            return bill
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update bill: {e}")
            raise
    
    async def update_bill_participant(self, participant: BillParticipant) -> BillParticipant:
        """Update bill participant in database"""
        try:
            self.db.merge(participant)
            self.db.commit()
            self.db.refresh(participant)
            logger.info(f"Updated bill participant {participant.id}")
            return participant
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update bill participant: {e}")
            raise
    
    # Payment request methods
    async def create_payment_request(self, payment_request: PaymentRequest) -> PaymentRequest:
        """Create payment request in database"""
        try:
            self.db.add(payment_request)
            self.db.commit()
            self.db.refresh(payment_request)
            logger.info(f"Created payment request {payment_request.id}")
            return payment_request
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create payment request: {e}")
            raise
    
    async def get_payment_request(self, request_id: str) -> Optional[PaymentRequest]:
        """Get payment request by ID"""
        try:
            return (self.db.query(PaymentRequest)
                   .options(joinedload(PaymentRequest.bill_participant))
                   .filter(PaymentRequest.id == UUID(request_id))
                   .first())
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to get payment request {request_id}: {e}")
            return None
    
    async def update_payment_request(self, payment_request: PaymentRequest) -> PaymentRequest:
        """Update payment request in database"""
        try:
            self.db.merge(payment_request)
            self.db.commit()
            self.db.refresh(payment_request)
            logger.info(f"Updated payment request {payment_request.id}")
            return payment_request
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update payment request: {e}")
            raise
    
    async def get_latest_payment_request_for_participant(self, participant_id: str) -> Optional[PaymentRequest]:
        """Get the latest payment request for a participant"""
        try:
            return (self.db.query(PaymentRequest)
                   .filter(PaymentRequest.bill_participant_id == UUID(participant_id))
                   .order_by(desc(PaymentRequest.created_at))
                   .first())
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to get latest payment request for participant {participant_id}: {e}")
            return None
    
    async def get_participant_by_phone_and_bill(self, phone_number: str, bill_id: str) -> Optional[BillParticipant]:
        """Get participant by phone number and bill ID"""
        try:
            # Get all participants for the bill and check phone numbers
            participants = (self.db.query(BillParticipant)
                           .options(joinedload(BillParticipant.contact))
                           .filter(BillParticipant.bill_id == UUID(bill_id))
                           .all())
            
            for participant in participants:
                if participant.contact and participant.contact.phone_number == phone_number:
                    return participant
            
            return None
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to get participant by phone and bill: {e}")
            return None
    
    async def get_payment_request_statistics(
        self,
        bill_id: Optional[str] = None,
        since_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get payment request statistics"""
        try:
            query = self.db.query(PaymentRequest)
            
            if bill_id:
                query = query.join(BillParticipant).filter(BillParticipant.bill_id == UUID(bill_id))
            
            if since_date:
                query = query.filter(PaymentRequest.created_at >= since_date)
            
            requests = query.all()
            
            total_requests = len(requests)
            successful_deliveries = len([r for r in requests if r.whatsapp_sent or r.sms_sent])
            failed_deliveries = total_requests - successful_deliveries
            whatsapp_deliveries = len([r for r in requests if r.whatsapp_sent])
            sms_deliveries = len([r for r in requests if r.sms_sent])
            confirmed_payments = len([r for r in requests if r.status == 'confirmed'])
            
            success_rate = successful_deliveries / total_requests if total_requests > 0 else 0.0
            confirmation_rate = confirmed_payments / total_requests if total_requests > 0 else 0.0
            
            return {
                "total_requests": total_requests,
                "successful_deliveries": successful_deliveries,
                "failed_deliveries": failed_deliveries,
                "whatsapp_deliveries": whatsapp_deliveries,
                "sms_deliveries": sms_deliveries,
                "confirmed_payments": confirmed_payments,
                "success_rate": success_rate,
                "confirmation_rate": confirmation_rate
            }
            
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to get payment request statistics: {e}")
            return {}
    
    async def find_active_participants_by_phone(
        self,
        phone_number: str,
        days_back: int = 30
    ) -> List[BillParticipant]:
        """
        Find active bill participants for a phone number
        Returns participants from bills that are not completed and within the specified timeframe
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Get all participants from active bills within the timeframe
            participants = (self.db.query(BillParticipant)
                           .options(
                               joinedload(BillParticipant.contact),
                               joinedload(BillParticipant.bill)
                           )
                           .join(Bill)
                           .filter(
                               and_(
                                   Bill.status != 'completed',
                                   Bill.created_at >= cutoff_date,
                                   BillParticipant.payment_status != PaymentStatus.CONFIRMED
                               )
                           )
                           .order_by(desc(Bill.created_at))
                           .all())
            
            # Filter by phone number (need to decrypt and compare)
            matching_participants = []
            for participant in participants:
                if participant.contact and participant.contact.phone_number == phone_number:
                    matching_participants.append(participant)
            
            logger.info(f"Found {len(matching_participants)} active participants for phone {phone_number}")
            return matching_participants
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to find active participants by phone: {e}")
            return []