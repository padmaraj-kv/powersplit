"""
Repository interfaces for data access layer
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID
from app.models.schemas import (
    ConversationState, BillData, Participant, BillSummary, 
    PaymentRequest, ValidationResult
)
from app.models.database import User, Contact, Bill, BillParticipant


class BaseRepository(ABC):
    """Base repository interface with common CRUD operations"""
    
    @abstractmethod
    async def create(self, entity: Any) -> Any:
        """Create a new entity"""
        pass
    
    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Optional[Any]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def update(self, entity_id: UUID, updates: Dict[str, Any]) -> Optional[Any]:
        """Update entity by ID"""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete entity by ID"""
        pass


class UserRepository(BaseRepository):
    """Repository interface for user operations"""
    
    @abstractmethod
    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        pass
    
    @abstractmethod
    async def create_user(self, phone_number: str, name: Optional[str] = None) -> User:
        """Create new user"""
        pass


class ContactRepository(BaseRepository):
    """Repository interface for contact operations"""
    
    @abstractmethod
    async def get_user_contacts(self, user_id: UUID) -> List[Contact]:
        """Get all contacts for a user"""
        pass
    
    @abstractmethod
    async def find_contact_by_phone(self, user_id: UUID, phone_number: str) -> Optional[Contact]:
        """Find contact by phone number for a user"""
        pass
    
    @abstractmethod
    async def create_contact(self, user_id: UUID, name: str, phone_number: str) -> Contact:
        """Create new contact"""
        pass


class BillRepository(BaseRepository):
    """Repository interface for bill operations"""
    
    @abstractmethod
    async def get_user_bills(self, user_id: UUID, limit: int = 10) -> List[Bill]:
        """Get bills for a user"""
        pass
    
    @abstractmethod
    async def create_bill(self, user_id: UUID, bill_data: BillData) -> Bill:
        """Create new bill"""
        pass
    
    @abstractmethod
    async def add_participants(self, bill_id: UUID, participants: List[Participant]) -> List[BillParticipant]:
        """Add participants to a bill"""
        pass
    
    @abstractmethod
    async def update_payment_status(self, participant_id: UUID, status: str) -> bool:
        """Update payment status for a participant"""
        pass


class ConversationRepository(BaseRepository):
    """Repository interface for conversation state operations"""
    
    @abstractmethod
    async def get_conversation_state(self, user_id: UUID, session_id: str) -> Optional[ConversationState]:
        """Get conversation state for user session"""
        pass
    
    @abstractmethod
    async def save_conversation_state(self, state: ConversationState) -> ConversationState:
        """Save or update conversation state"""
        pass
    
    @abstractmethod
    async def clear_conversation_state(self, user_id: UUID, session_id: str) -> bool:
        """Clear conversation state"""
        pass


class PaymentRepository(BaseRepository):
    """Repository interface for payment operations"""
    
    @abstractmethod
    async def create_payment_request(self, participant_id: UUID, upi_link: str) -> PaymentRequest:
        """Create payment request"""
        pass
    
    @abstractmethod
    async def get_payment_request(self, request_id: UUID) -> Optional[PaymentRequest]:
        """Get payment request by ID"""
        pass
    
    @abstractmethod
    async def update_delivery_status(self, request_id: UUID, method: str, success: bool) -> bool:
        """Update delivery status for payment request"""
        pass
    
    @abstractmethod
    async def update_payment_status(self, request_id: UUID, status: str) -> bool:
        """Update payment request status"""
        pass
    
    @abstractmethod
    async def confirm_payment(self, request_id: UUID) -> bool:
        """Confirm payment received"""
        pass
    
    @abstractmethod
    async def reset_delivery_status(self, request_id: UUID) -> bool:
        """Reset delivery status for resending"""
        pass
    
    @abstractmethod
    async def get_payment_requests_by_bill(self, bill_id: UUID) -> List[PaymentRequest]:
        """Get all payment requests for a bill"""
        pass