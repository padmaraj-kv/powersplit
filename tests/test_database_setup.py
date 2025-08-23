"""
Tests for database setup and models
"""
import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal, init_database
from app.models.database import User, Contact, Bill, BillParticipant, PaymentRequest, ConversationState
from app.database.migrations import migration_manager
from app.database.repositories import (
    SQLUserRepository, SQLContactRepository, SQLBillRepository,
    SQLPaymentRepository, SQLConversationRepository
)
from app.database.encryption import encryption


class TestDatabaseSetup:
    """Test database setup and initialization"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Test database health check functionality"""
        health_status = await migration_manager.check_database_health()
        
        assert 'status' in health_status
        assert 'connection' in health_status
        assert health_status['status'] in ['healthy', 'missing_tables', 'unhealthy']
    
    @pytest.mark.asyncio
    async def test_schema_validation(self):
        """Test database schema validation"""
        validation_result = await migration_manager._validate_schema()
        
        assert 'valid' in validation_result
        assert isinstance(validation_result['valid'], bool)
        
        if not validation_result['valid']:
            assert 'errors' in validation_result
            print(f"Schema validation errors: {validation_result['errors']}")


class TestDatabaseModels:
    """Test database models and relationships"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
    
    def test_user_model_encryption(self, db_session):
        """Test user model with encryption"""
        # Create user
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        # Verify encryption
        assert user.phone_number == "+1234567890"  # Decrypted access
        assert user._phone_number != "+1234567890"  # Encrypted storage
        assert user.name == "Test User"
        assert user._name != "Test User"
        
        # Test retrieval
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        assert retrieved_user.phone_number == "+1234567890"
        assert retrieved_user.name == "Test User"
    
    def test_contact_model_encryption(self, db_session):
        """Test contact model with encryption"""
        # Create user first
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        # Create contact
        contact = Contact(
            user_id=user.id,
            name="Test Contact",
            phone_number="+0987654321"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Verify encryption
        assert contact.name == "Test Contact"
        assert contact._name != "Test Contact"
        assert contact.phone_number == "+0987654321"
        assert contact._phone_number != "+0987654321"
    
    def test_bill_model_constraints(self, db_session):
        """Test bill model constraints and validation"""
        # Create user
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        # Create bill
        bill = Bill(
            user_id=user.id,
            total_amount=Decimal('100.50'),
            description="Test Bill",
            merchant="Test Merchant",
            currency="INR"
        )
        db_session.add(bill)
        db_session.commit()
        
        # Verify properties
        assert bill.total_amount == Decimal('100.50')
        assert bill.currency == "INR"
        assert bill.status == "active"
        assert bill.total_paid == 0  # No participants yet
        assert not bill.is_fully_paid
    
    def test_bill_participant_model(self, db_session):
        """Test bill participant model and payment tracking"""
        # Create user and contact
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        contact = Contact(
            user_id=user.id,
            name="Test Contact",
            phone_number="+0987654321"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Create bill
        bill = Bill(
            user_id=user.id,
            total_amount=Decimal('100.00'),
            description="Test Bill"
        )
        db_session.add(bill)
        db_session.commit()
        
        # Create participant
        participant = BillParticipant(
            bill_id=bill.id,
            contact_id=contact.id,
            amount_owed=Decimal('50.00')
        )
        db_session.add(participant)
        db_session.commit()
        
        # Test payment status
        assert participant.payment_status == "pending"
        
        # Mark as paid
        participant.mark_as_paid()
        db_session.commit()
        
        assert participant.payment_status == "confirmed"
        assert participant.paid_at is not None
    
    def test_conversation_state_model(self, db_session):
        """Test conversation state model"""
        # Create user
        user = User(phone_number="+1234567890", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        # Create conversation state
        context = {"current_bill": {"amount": 100}, "step_data": {"participants": []}}
        conversation = ConversationState(
            user_id=user.id,
            session_id="test_session_123",
            current_step="extracting_bill",
            context=context
        )
        db_session.add(conversation)
        db_session.commit()
        
        # Verify
        assert conversation.current_step == "extracting_bill"
        assert conversation.context == context
        assert conversation.retry_count == 0
        
        # Test retry increment
        conversation.increment_retry("Test error")
        assert conversation.retry_count == 1
        assert conversation.last_error == "Test error"


class TestDatabaseRepositories:
    """Test database repository implementations"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
    
    @pytest.mark.asyncio
    async def test_user_repository(self, db_session):
        """Test user repository operations"""
        repo = SQLUserRepository(db_session)
        
        # Create user
        user = await repo.create_user("+1234567890", "Test User")
        assert user.phone_number == "+1234567890"
        assert user.name == "Test User"
        
        # Get user by phone
        found_user = await repo.get_user_by_phone("+1234567890")
        assert found_user is not None
        assert found_user.id == user.id
        
        # Get user by ID
        found_by_id = await repo.get_user_by_id(user.id)
        assert found_by_id is not None
        assert found_by_id.phone_number == "+1234567890"
        
        # Update user
        updated_user = await repo.update_user(user.id, name="Updated Name")
        assert updated_user.name == "Updated Name"
    
    @pytest.mark.asyncio
    async def test_bill_repository(self, db_session):
        """Test bill repository operations"""
        # Create user first
        user_repo = SQLUserRepository(db_session)
        user = await user_repo.create_user("+1234567890", "Test User")
        
        # Create contact
        contact_repo = SQLContactRepository(db_session)
        contact = await contact_repo.create_contact(user.id, "Test Contact", "+0987654321")
        
        # Test bill operations
        bill_repo = SQLBillRepository(db_session)
        
        # Create bill
        bill = await bill_repo.create_bill(
            user.id, 
            100.50, 
            description="Test Bill",
            merchant="Test Merchant"
        )
        assert bill.total_amount == Decimal('100.50')
        
        # Add participant
        participant = await bill_repo.add_participant(bill.id, contact.id, 50.25)
        assert participant.amount_owed == Decimal('50.25')
        
        # Get participants
        participants = await bill_repo.get_bill_participants(bill.id)
        assert len(participants) == 1
        assert participants[0].id == participant.id
        
        # Update bill status
        updated_bill = await bill_repo.update_bill_status(bill.id, "completed")
        assert updated_bill.status == "completed"


class TestEncryption:
    """Test encryption functionality"""
    
    def test_basic_encryption(self):
        """Test basic encryption and decryption"""
        test_data = "sensitive_information"
        
        # Encrypt
        encrypted = encryption.encrypt(test_data)
        assert encrypted != test_data
        assert len(encrypted) > len(test_data)
        
        # Decrypt
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == test_data
    
    def test_phone_number_encryption(self):
        """Test phone number specific encryption"""
        phone = "+1234567890"
        
        encrypted = encryption.encrypt_phone_number(phone)
        assert encrypted != phone
        
        decrypted = encryption.decrypt_phone_number(encrypted)
        assert decrypted == phone
    
    def test_contact_info_encryption(self):
        """Test contact information encryption"""
        contact_data = {
            "name": "John Doe",
            "phone_number": "+1234567890",
            "other_field": "not_encrypted"
        }
        
        encrypted_data = encryption.encrypt_contact_info(contact_data)
        assert encrypted_data["name"] != contact_data["name"]
        assert encrypted_data["phone_number"] != contact_data["phone_number"]
        assert encrypted_data["other_field"] == contact_data["other_field"]
        
        decrypted_data = encryption.decrypt_contact_info(encrypted_data)
        assert decrypted_data == contact_data
    
    def test_empty_data_handling(self):
        """Test encryption with empty or None data"""
        assert encryption.encrypt("") == ""
        assert encryption.encrypt(None) == None
        assert encryption.decrypt("") == ""
        assert encryption.decrypt(None) == None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])