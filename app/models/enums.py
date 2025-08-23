"""
Enums for conversation state management and application constants
"""
from enum import Enum


class ConversationStep(str, Enum):
    """Conversation flow states for bill splitting process"""
    INITIAL = "initial"
    EXTRACTING_BILL = "extracting_bill"
    CONFIRMING_BILL = "confirming_bill"
    COLLECTING_CONTACTS = "collecting_contacts"
    CALCULATING_SPLITS = "calculating_splits"
    CONFIRMING_SPLITS = "confirming_splits"
    SENDING_REQUESTS = "sending_requests"
    TRACKING_PAYMENTS = "tracking_payments"
    COMPLETED = "completed"


class PaymentStatus(str, Enum):
    """Payment status for bill participants"""
    PENDING = "pending"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class MessageType(str, Enum):
    """Types of input messages from users"""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class DeliveryMethod(str, Enum):
    """Message delivery methods through Siren"""
    WHATSAPP = "whatsapp"
    SMS = "sms"


class BillStatus(str, Enum):
    """Overall bill status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ErrorType(str, Enum):
    """Error categories for handling"""
    INPUT_PROCESSING = "input_processing"
    EXTERNAL_SERVICE = "external_service"
    BUSINESS_LOGIC = "business_logic"
    DATABASE = "database"
    VALIDATION = "validation"