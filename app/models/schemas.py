"""
Pydantic schemas for data validation and serialization
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from app.models.enums import (
    ConversationStep,
    PaymentStatus,
    MessageType,
    DeliveryMethod,
    BillStatus,
    ErrorType,
)


class BillItem(BaseModel):
    """Individual item in a bill"""

    name: str
    amount: Decimal = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)


class BillData(BaseModel):
    """Core bill information extracted from user input"""

    total_amount: Decimal = Field(..., gt=0)
    description: str
    items: List[BillItem] = Field(default_factory=list)
    currency: str = Field(default="INR")
    date: Optional[datetime] = None
    merchant: Optional[str] = None

    @validator("total_amount")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Total amount must be positive")
        return v


class Participant(BaseModel):
    """Bill participant information"""

    name: str
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
    amount_owed: Decimal = Field(..., gt=0)
    payment_status: PaymentStatus = PaymentStatus.PENDING
    contact_id: Optional[str] = None


class ConversationState(BaseModel):
    """Conversation state for maintaining context"""

    user_id: str
    session_id: str
    current_step: ConversationStep
    bill_data: Optional[BillData] = None
    participants: List[Participant] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Message(BaseModel):
    """Incoming message from Siren webhook"""

    id: str
    user_id: str
    content: str
    message_type: MessageType
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Response(BaseModel):
    """Response to send back to user"""

    content: str
    message_type: MessageType = MessageType.TEXT
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaymentRequest(BaseModel):
    """Payment request information"""

    id: str
    bill_id: str
    participant_id: str
    amount: Decimal
    upi_link: str
    status: PaymentStatus
    sent_via: List[DeliveryMethod] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None


class BillSummary(BaseModel):
    """Summary information for bill queries"""

    id: str
    description: str
    total_amount: Decimal
    participant_count: int
    paid_count: int
    status: BillStatus
    created_at: datetime
    bill_date: Optional[datetime] = None
    merchant: Optional[str] = None


class BillDetails(BaseModel):
    """Detailed bill information for queries"""

    id: str
    description: str
    total_amount: Decimal
    currency: str = "INR"
    merchant: Optional[str] = None
    bill_date: Optional[datetime] = None
    created_at: datetime
    status: BillStatus
    items: List[BillItem] = Field(default_factory=list)
    participants: List["ParticipantDetails"] = Field(default_factory=list)


class ParticipantDetails(BaseModel):
    """Detailed participant information for bill queries"""

    id: str
    name: str
    phone_number: str
    amount_owed: Decimal
    payment_status: PaymentStatus
    paid_at: Optional[datetime] = None
    reminder_count: int = 0
    last_reminder_sent: Optional[datetime] = None


class BillFilters(BaseModel):
    """Filters for bill queries"""

    status: Optional[BillStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    merchant: Optional[str] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


class BillStatusInfo(BaseModel):
    """Bill status information"""

    id: str
    description: str
    total_amount: Decimal
    status: BillStatus
    created_at: datetime
    participants: List[ParticipantDetails] = Field(default_factory=list)
    total_paid: Decimal = Field(default=0)
    remaining_amount: Decimal = Field(default=0)
    completion_percentage: float = Field(default=0.0)


class ValidationResult(BaseModel):
    """Result of data validation"""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standardized error response"""

    error_type: ErrorType
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# Forward reference resolution
BillDetails.model_rebuild()
