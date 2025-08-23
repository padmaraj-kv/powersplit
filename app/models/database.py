"""
SQLAlchemy database models with encryption support
"""
from sqlalchemy import Column, String, Decimal, DateTime, Boolean, Text, Integer, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.core.database import Base
from app.database.encryption import encryption
import uuid
import logging

logger = logging.getLogger(__name__)


class User(Base):
    """User model for storing basic user information with encryption"""
    __tablename__ = "users"
    __table_args__ = (
        Index('idx_users_phone', 'phone_number'),
        Index('idx_users_created_at', 'created_at'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    _phone_number = Column('phone_number', String(255), unique=True, nullable=False)  # Encrypted
    _name = Column('name', String(255))  # Encrypted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    bills = relationship("Bill", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    conversation_states = relationship("ConversationState", back_populates="user", cascade="all, delete-orphan")
    
    @hybrid_property
    def phone_number(self):
        """Decrypt phone number for access"""
        try:
            return encryption.decrypt_phone_number(self._phone_number) if self._phone_number else None
        except Exception as e:
            logger.error(f"Failed to decrypt phone number: {e}")
            return None
    
    @phone_number.setter
    def phone_number(self, value):
        """Encrypt phone number for storage"""
        try:
            self._phone_number = encryption.encrypt_phone_number(value) if value else None
        except Exception as e:
            logger.error(f"Failed to encrypt phone number: {e}")
            self._phone_number = value
    
    @hybrid_property
    def name(self):
        """Decrypt name for access"""
        try:
            return encryption.decrypt(self._name) if self._name else None
        except Exception as e:
            logger.error(f"Failed to decrypt name: {e}")
            return None
    
    @name.setter
    def name(self, value):
        """Encrypt name for storage"""
        try:
            self._name = encryption.encrypt(value) if value else None
        except Exception as e:
            logger.error(f"Failed to encrypt name: {e}")
            self._name = value
    
    @validates('_phone_number')
    def validate_phone_number(self, key, phone_number):
        """Validate phone number format before encryption"""
        if phone_number and len(phone_number) > 255:
            raise ValueError("Encrypted phone number too long")
        return phone_number
    
    def __repr__(self):
        return f"<User(id={self.id}, phone=*****, created_at={self.created_at})>"


class Contact(Base):
    """Contact model for storing participant information with encryption"""
    __tablename__ = "contacts"
    __table_args__ = (
        Index('idx_contacts_user_id', 'user_id'),
        Index('idx_contacts_phone', 'phone_number'),
        Index('idx_contacts_created_at', 'created_at'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    _name = Column('name', String(255), nullable=False)  # Encrypted
    _phone_number = Column('phone_number', String(255), nullable=False)  # Encrypted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="contacts")
    bill_participants = relationship("BillParticipant", back_populates="contact", cascade="all, delete-orphan")
    
    @hybrid_property
    def name(self):
        """Decrypt name for access"""
        try:
            return encryption.decrypt(self._name) if self._name else None
        except Exception as e:
            logger.error(f"Failed to decrypt contact name: {e}")
            return None
    
    @name.setter
    def name(self, value):
        """Encrypt name for storage"""
        try:
            self._name = encryption.encrypt(value) if value else None
        except Exception as e:
            logger.error(f"Failed to encrypt contact name: {e}")
            self._name = value
    
    @hybrid_property
    def phone_number(self):
        """Decrypt phone number for access"""
        try:
            return encryption.decrypt_phone_number(self._phone_number) if self._phone_number else None
        except Exception as e:
            logger.error(f"Failed to decrypt contact phone: {e}")
            return None
    
    @phone_number.setter
    def phone_number(self, value):
        """Encrypt phone number for storage"""
        try:
            self._phone_number = encryption.encrypt_phone_number(value) if value else None
        except Exception as e:
            logger.error(f"Failed to encrypt contact phone: {e}")
            self._phone_number = value
    
    @validates('_name', '_phone_number')
    def validate_encrypted_fields(self, key, value):
        """Validate encrypted field lengths"""
        if value and len(value) > 255:
            raise ValueError(f"Encrypted {key} too long")
        return value
    
    def __repr__(self):
        return f"<Contact(id={self.id}, name=*****, phone=*****, user_id={self.user_id})>"


class Bill(Base):
    """Bill model for storing bill information with enhanced constraints"""
    __tablename__ = "bills"
    __table_args__ = (
        Index('idx_bills_user_id', 'user_id'),
        Index('idx_bills_status', 'status'),
        Index('idx_bills_created_at', 'created_at'),
        Index('idx_bills_bill_date', 'bill_date'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Decimal(12, 2), nullable=False)  # Increased precision for larger amounts
    description = Column(Text)
    merchant = Column(String(200))  # Increased length for merchant names
    bill_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default='active', nullable=False)
    
    # Additional metadata
    currency = Column(String(3), default='INR', nullable=False)
    items_data = Column(JSON)  # Store bill items as JSON
    
    # Relationships
    user = relationship("User", back_populates="bills")
    participants = relationship("BillParticipant", back_populates="bill", cascade="all, delete-orphan")
    
    @validates('total_amount')
    def validate_total_amount(self, key, total_amount):
        """Validate that total amount is positive"""
        if total_amount is not None and total_amount <= 0:
            raise ValueError("Total amount must be positive")
        return total_amount
    
    @validates('status')
    def validate_status(self, key, status):
        """Validate bill status"""
        valid_statuses = ['active', 'completed', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return status
    
    @validates('currency')
    def validate_currency(self, key, currency):
        """Validate currency code"""
        if currency and len(currency) != 3:
            raise ValueError("Currency must be a 3-letter code")
        return currency.upper() if currency else currency
    
    @property
    def total_paid(self):
        """Calculate total amount paid by participants"""
        return sum(p.amount_owed for p in self.participants if p.payment_status == 'confirmed')
    
    @property
    def is_fully_paid(self):
        """Check if bill is fully paid"""
        return self.total_paid >= self.total_amount
    
    def __repr__(self):
        return f"<Bill(id={self.id}, amount={self.total_amount}, status={self.status})>"


class BillParticipant(Base):
    """Bill participant model for tracking individual amounts and payments"""
    __tablename__ = "bill_participants"
    __table_args__ = (
        Index('idx_bill_participants_bill_id', 'bill_id'),
        Index('idx_bill_participants_contact_id', 'contact_id'),
        Index('idx_bill_participants_status', 'payment_status'),
        Index('idx_bill_participants_created_at', 'created_at'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    amount_owed = Column(Decimal(12, 2), nullable=False)
    payment_status = Column(String(20), default='pending', nullable=False)
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Additional tracking fields
    reminder_count = Column(Integer, default=0)
    last_reminder_sent = Column(DateTime(timezone=True))
    
    # Relationships
    bill = relationship("Bill", back_populates="participants")
    contact = relationship("Contact", back_populates="bill_participants")
    payment_requests = relationship("PaymentRequest", back_populates="bill_participant", cascade="all, delete-orphan")
    
    @validates('amount_owed')
    def validate_amount_owed(self, key, amount_owed):
        """Validate that amount owed is positive"""
        if amount_owed is not None and amount_owed <= 0:
            raise ValueError("Amount owed must be positive")
        return amount_owed
    
    @validates('payment_status')
    def validate_payment_status(self, key, payment_status):
        """Validate payment status"""
        valid_statuses = ['pending', 'sent', 'confirmed', 'failed']
        if payment_status not in valid_statuses:
            raise ValueError(f"Payment status must be one of: {valid_statuses}")
        return payment_status
    
    @validates('reminder_count')
    def validate_reminder_count(self, key, reminder_count):
        """Validate reminder count is non-negative"""
        if reminder_count is not None and reminder_count < 0:
            raise ValueError("Reminder count cannot be negative")
        return reminder_count
    
    def mark_as_paid(self):
        """Mark participant as paid"""
        self.payment_status = 'confirmed'
        self.paid_at = func.now()
    
    def __repr__(self):
        return f"<BillParticipant(id={self.id}, amount={self.amount_owed}, status={self.payment_status})>"


class PaymentRequest(Base):
    """Payment request model for tracking payment links and delivery"""
    __tablename__ = "payment_requests"
    __table_args__ = (
        Index('idx_payment_requests_participant_id', 'bill_participant_id'),
        Index('idx_payment_requests_created_at', 'created_at'),
        Index('idx_payment_requests_status', 'status'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_participant_id = Column(UUID(as_uuid=True), ForeignKey("bill_participants.id", ondelete="CASCADE"), nullable=False)
    upi_link = Column(Text, nullable=False)
    whatsapp_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    
    # Enhanced tracking fields
    status = Column(String(20), default='pending', nullable=False)
    delivery_attempts = Column(Integer, default=0)
    last_delivery_attempt = Column(DateTime(timezone=True))
    delivery_error = Column(Text)
    
    # Relationships
    bill_participant = relationship("BillParticipant", back_populates="payment_requests")
    
    @validates('status')
    def validate_status(self, key, status):
        """Validate payment request status"""
        valid_statuses = ['pending', 'sent', 'delivered', 'confirmed', 'failed']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return status
    
    @validates('delivery_attempts')
    def validate_delivery_attempts(self, key, delivery_attempts):
        """Validate delivery attempts is non-negative"""
        if delivery_attempts is not None and delivery_attempts < 0:
            raise ValueError("Delivery attempts cannot be negative")
        return delivery_attempts
    
    def mark_as_sent(self, method: str):
        """Mark payment request as sent via specific method"""
        if method == 'whatsapp':
            self.whatsapp_sent = True
        elif method == 'sms':
            self.sms_sent = True
        
        self.status = 'sent'
        self.delivery_attempts += 1
        self.last_delivery_attempt = func.now()
    
    def mark_as_confirmed(self):
        """Mark payment request as confirmed"""
        self.status = 'confirmed'
        self.confirmed_at = func.now()
    
    def __repr__(self):
        return f"<PaymentRequest(id={self.id}, status={self.status}, whatsapp={self.whatsapp_sent}, sms={self.sms_sent})>"


class ConversationState(Base):
    """Conversation state model for maintaining user context"""
    __tablename__ = "conversation_states"
    __table_args__ = (
        Index('idx_conv_states_user_id', 'user_id'),
        Index('idx_conv_states_session_id', 'session_id'),
        Index('idx_conv_states_step', 'current_step'),
        Index('idx_conv_states_updated_at', 'updated_at'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(100), nullable=False)
    current_step = Column(String(50), nullable=False)
    context = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Additional tracking fields
    retry_count = Column(Integer, default=0)
    last_error = Column(Text)
    expires_at = Column(DateTime(timezone=True))  # For automatic cleanup
    
    # Relationships
    user = relationship("User", back_populates="conversation_states")
    
    @validates('current_step')
    def validate_current_step(self, key, current_step):
        """Validate conversation step"""
        valid_steps = [
            'initial', 'extracting_bill', 'confirming_bill', 'collecting_contacts',
            'calculating_splits', 'confirming_splits', 'sending_requests',
            'tracking_payments', 'completed'
        ]
        if current_step not in valid_steps:
            raise ValueError(f"Current step must be one of: {valid_steps}")
        return current_step
    
    @validates('retry_count')
    def validate_retry_count(self, key, retry_count):
        """Validate retry count is non-negative"""
        if retry_count is not None and retry_count < 0:
            raise ValueError("Retry count cannot be negative")
        return retry_count
    
    def increment_retry(self, error_message: str = None):
        """Increment retry count and set error message"""
        self.retry_count += 1
        if error_message:
            self.last_error = error_message
        self.updated_at = func.now()
    
    def reset_retry(self):
        """Reset retry count and clear error"""
        self.retry_count = 0
        self.last_error = None
        self.updated_at = func.now()
    
    @property
    def is_expired(self):
        """Check if conversation state has expired"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<ConversationState(id={self.id}, step={self.current_step}, user_id={self.user_id})>"