"""
Service interfaces for business logic layer
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from app.models.schemas import (
    Message, Response, BillData, Participant, ConversationState,
    PaymentRequest, BillSummary, ValidationResult, BillDetails,
    BillStatusInfo, BillFilters, ParticipantDetails
)
from app.models.enums import ConversationStep


class BillExtractorInterface(ABC):
    """Interface for bill extraction and processing logic"""
    
    @abstractmethod
    async def extract_bill_data(self, message: Message) -> BillData:
        """Extract bill data from multi-modal input"""
        pass
    
    @abstractmethod
    async def validate_bill_data(self, bill_data: BillData) -> ValidationResult:
        """Validate extracted bill data with comprehensive checks"""
        pass
    
    @abstractmethod
    async def generate_clarifying_questions(self, bill_data: BillData) -> List[str]:
        """Generate clarifying questions for incomplete bill data"""
        pass
    
    @abstractmethod
    async def create_bill_summary(self, bill_data: BillData) -> str:
        """Create a formatted summary of the bill for user confirmation"""
        pass
    
    @abstractmethod
    async def process_bill_confirmation(self, message: Message, bill_data: BillData) -> Tuple[bool, Optional[str]]:
        """Process user's confirmation response for bill data"""
        pass


class AIServiceInterface(ABC):
    """Interface for AI service integrations"""
    
    @abstractmethod
    async def extract_from_text(self, text: str) -> BillData:
        """Extract bill data from text input"""
        pass
    
    @abstractmethod
    async def extract_from_voice(self, audio_data: bytes) -> BillData:
        """Extract bill data from voice input"""
        pass
    
    @abstractmethod
    async def extract_from_image(self, image_data: bytes) -> BillData:
        """Extract bill data from image input"""
        pass
    
    @abstractmethod
    async def validate_extraction(self, bill_data: BillData) -> ValidationResult:
        """Validate extracted bill data"""
        pass
    
    @abstractmethod
    async def recognize_intent(self, message: Message, current_step: ConversationStep) -> Dict[str, Any]:
        """Recognize user intent from message"""
        pass
    
    @abstractmethod
    async def generate_clarifying_questions(self, bill_data: BillData) -> List[str]:
        """Generate clarifying questions for incomplete bill data"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all AI services"""
        pass


class CommunicationServiceInterface(ABC):
    """Interface for communication services (Siren integration)"""
    
    @abstractmethod
    async def send_whatsapp_message(self, phone_number: str, message: str) -> bool:
        """Send WhatsApp message via Siren"""
        pass
    
    @abstractmethod
    async def send_sms(self, phone_number: str, message: str) -> bool:
        """Send SMS via Siren"""
        pass
    
    @abstractmethod
    async def send_message_with_fallback(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send message with WhatsApp/SMS fallback"""
        pass


class ConversationServiceInterface(ABC):
    """Interface for conversation management"""
    
    @abstractmethod
    async def process_message(self, user_id: str, message: Message) -> Response:
        """Process incoming message and return response"""
        pass
    
    @abstractmethod
    async def get_conversation_state(self, user_id: str, session_id: str) -> Optional[ConversationState]:
        """Get current conversation state"""
        pass
    
    @abstractmethod
    async def update_conversation_state(self, state: ConversationState) -> ConversationState:
        """Update conversation state"""
        pass


class BillServiceInterface(ABC):
    """Interface for bill management services"""
    
    @abstractmethod
    async def create_bill(self, user_id: str, bill_data: BillData) -> str:
        """Create new bill and return bill ID"""
        pass
    
    @abstractmethod
    async def calculate_splits(self, bill_data: BillData, participants: List[Participant]) -> List[Participant]:
        """Calculate bill splits for participants"""
        pass
    
    @abstractmethod
    async def validate_splits(self, bill_data: BillData, participants: List[Participant]) -> ValidationResult:
        """Validate split calculations"""
        pass
    
    @abstractmethod
    async def get_bill_summary(self, user_id: str, bill_id: str) -> Optional[BillSummary]:
        """Get bill summary"""
        pass


class ContactServiceInterface(ABC):
    """Interface for contact management"""
    
    @abstractmethod
    async def get_user_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all contacts for a user"""
        pass
    
    @abstractmethod
    async def find_or_create_contact(self, user_id: str, name: str, phone_number: str) -> str:
        """Find existing contact or create new one"""
        pass
    
    @abstractmethod
    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format"""
        pass
    
    @abstractmethod
    async def collect_participants_workflow(self, user_id: str, participants: List[Participant]) -> Tuple[List[Participant], List[str]]:
        """Main workflow for collecting participant contacts with missing contact handling"""
        pass
    
    @abstractmethod
    async def validate_participants(self, participants: List[Participant]) -> ValidationResult:
        """Validate participant list for completeness and correctness"""
        pass
    
    @abstractmethod
    async def deduplicate_contacts(self, user_id: str, participants: List[Participant]) -> List[Participant]:
        """Remove duplicate contacts and merge information"""
        pass
    
    @abstractmethod
    async def auto_populate_from_history(self, user_id: str, participant_names: List[str]) -> List[Participant]:
        """Auto-populate participant information from contact history"""
        pass
    
    @abstractmethod
    async def handle_missing_contacts(self, user_id: str, participants: List[Participant], 
                                    user_responses: Dict[str, str]) -> Tuple[List[Participant], List[str]]:
        """Handle user responses for missing contact information"""
        pass


class PaymentServiceInterface(ABC):
    """Interface for payment processing"""
    
    @abstractmethod
    async def generate_upi_link(self, recipient_name: str, amount: Decimal, description: str, 
                              upi_app: Optional[str] = None, payee_upi_id: Optional[str] = None) -> str:
        """Generate UPI deeplink with support for multiple apps"""
        pass
    
    @abstractmethod
    async def generate_multiple_upi_links(self, recipient_name: str, amount: Decimal, 
                                        description: str, apps: Optional[List[str]] = None) -> Dict[str, str]:
        """Generate UPI links for multiple apps"""
        pass
    
    @abstractmethod
    async def validate_upi_link(self, upi_link: str) -> Tuple[bool, Optional[str]]:
        """Validate UPI link format and parameters"""
        pass
    
    @abstractmethod
    async def create_payment_message(self, recipient_name: str, amount: Decimal, 
                                   description: str, upi_link: str) -> str:
        """Create formatted payment message for WhatsApp/SMS"""
        pass
    
    @abstractmethod
    async def create_payment_requests(self, bill_id: str, participants: List[Participant]) -> List[PaymentRequest]:
        """Create payment requests for all participants"""
        pass
    
    @abstractmethod
    async def send_payment_requests(self, requests: List[PaymentRequest]) -> Dict[str, Any]:
        """Send payment requests to participants"""
        pass
    
    @abstractmethod
    async def confirm_payment(self, request_id: str) -> bool:
        """Confirm payment received"""
        pass


class BillQueryServiceInterface(ABC):
    """Interface for bill query and history services"""
    
    @abstractmethod
    async def get_user_bills(self, user_id: str, filters: Optional["BillFilters"] = None) -> List["BillSummary"]:
        """Implements requirement 6.1 for bill history retrieval"""
        pass
    
    @abstractmethod
    async def get_bill_status(self, user_id: str, bill_id: str) -> Optional["BillStatusInfo"]:
        """Implements requirement 6.2 for payment status display"""
        pass
    
    @abstractmethod
    async def get_bill_details(self, user_id: str, bill_id: str) -> Optional["BillDetails"]:
        """Implements requirement 6.3 for complete bill information"""
        pass
    
    @abstractmethod
    async def send_payment_reminders(self, user_id: str, bill_id: str, participant_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Implements requirement 6.4 for resending payment requests"""
        pass
    
    @abstractmethod
    async def get_unpaid_participants(self, user_id: str, bill_id: str) -> List["ParticipantDetails"]:
        """Get list of participants who haven't paid yet"""
        pass


class ErrorHandlingServiceInterface(ABC):
    """Interface for error handling and recovery"""
    
    @abstractmethod
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> Response:
        """Handle errors and provide appropriate response"""
        pass
    
    @abstractmethod
    async def retry_operation(self, operation: callable, max_retries: int = 3) -> Any:
        """Retry operation with exponential backoff"""
        pass
    
    @abstractmethod
    async def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error with context"""
        pass