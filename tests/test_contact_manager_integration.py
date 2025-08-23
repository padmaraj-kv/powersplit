"""
Integration tests for ContactManager with database
"""
import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.contact_manager import ContactManager
from app.database.repositories import SQLContactRepository, SQLUserRepository
from app.models.schemas import Participant
from app.models.database import User, Contact
from app.models.enums import PaymentStatus
from app.core.database import get_db_session


class TestContactManagerIntegration:
    """Integration tests for ContactManager with real database operations"""
    
    @pytest.fixture
    def db_session(self):
        """Get database session for testing"""
        session = next(get_db_session())
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def contact_manager(self, db_session):
        """ContactManager with real repository implementations"""
        contact_repo = SQLContactRepository(db_session)
        user_repo = SQLUserRepository(db_session)
        return ContactManager(contact_repo, user_repo)
    
    @pytest.fixture
    async def test_user(self, db_session):
        """Create test user"""
        user = User(phone_number="+919876543210", name="Test User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        yield user
        # Cleanup
        db_session.delete(user)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_find_or_create_contact_integration(self, contact_manager, test_user):
        """Test find or create contact with real database"""
        user_id = str(test_user.id)
        
        # Create new contact
        contact_id = await contact_manager.find_or_create_contact(
            user_id, "John Doe", "+919876543211"
        )
        
        assert contact_id is not None
        
        # Find existing contact
        same_contact_id = await contact_manager.find_or_create_contact(
            user_id, "John Doe", "+919876543211"
        )
        
        assert contact_id == same_contact_id
    
    @pytest.mark.asyncio
    async def test_get_user_contacts_integration(self, contact_manager, test_user):
        """Test getting user contacts with real database"""
        user_id = str(test_user.id)
        
        # Create some contacts
        await contact_manager.find_or_create_contact(user_id, "Alice Smith", "+919876543212")
        await contact_manager.find_or_create_contact(user_id, "Bob Johnson", "+919876543213")
        
        # Get contacts
        contacts = await contact_manager.get_user_contacts(user_id)
        
        assert len(contacts) >= 2
        contact_names = [c["name"] for c in contacts]
        assert "Alice Smith" in contact_names
        assert "Bob Johnson" in contact_names
    
    @pytest.mark.asyncio
    async def test_collect_participants_workflow_integration(self, contact_manager, test_user):
        """Test complete participant collection workflow"""
        user_id = str(test_user.id)
        
        # Create existing contact
        await contact_manager.find_or_create_contact(user_id, "Existing Contact", "+919876543214")
        
        participants = [
            Participant(
                name="Existing Contact",
                phone_number="9876543214",  # Different format, should match
                amount_owed=Decimal("100.00"),
                payment_status=PaymentStatus.PENDING
            ),
            Participant(
                name="New Contact",
                phone_number="+919876543215",
                amount_owed=Decimal("150.00"),
                payment_status=PaymentStatus.PENDING
            )
        ]
        
        updated_participants, missing_questions = await contact_manager.collect_participants_workflow(
            user_id, participants
        )
        
        assert len(updated_participants) == 2
        assert len(missing_questions) == 0
        assert all(p.contact_id is not None for p in updated_participants)
    
    @pytest.mark.asyncio
    async def test_deduplicate_contacts_integration(self, contact_manager, test_user):
        """Test contact deduplication with real database"""
        user_id = str(test_user.id)
        
        # Create existing contact
        await contact_manager.find_or_create_contact(user_id, "John Doe", "+919876543216")
        
        # Create participants with duplicate phone numbers
        participants = [
            Participant(
                name="John Doe",
                phone_number="+919876543216",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="John Doe",
                phone_number="919876543216",  # Same number, different format
                amount_owed=Decimal("150.00")
            ),
            Participant(
                name="Jane Smith",
                phone_number="+919876543217",
                amount_owed=Decimal("200.00")
            )
        ]
        
        deduplicated = await contact_manager.deduplicate_contacts(user_id, participants)
        
        assert len(deduplicated) == 2  # One duplicate removed
        phone_numbers = [p.phone_number for p in deduplicated]
        assert "+919876543216" in phone_numbers
        assert "+919876543217" in phone_numbers
    
    @pytest.mark.asyncio
    async def test_auto_populate_from_history_integration(self, contact_manager, test_user):
        """Test auto-population from contact history with real database"""
        user_id = str(test_user.id)
        
        # Create some contacts
        await contact_manager.find_or_create_contact(user_id, "Alice Smith", "+919876543218")
        await contact_manager.find_or_create_contact(user_id, "Bob Johnson", "+919876543219")
        
        # Auto-populate participants
        participant_names = ["Alice Smith", "Bob Johnson", "Unknown Person"]
        participants = await contact_manager.auto_populate_from_history(user_id, participant_names)
        
        assert len(participants) == 3
        
        # Check Alice Smith
        alice = next(p for p in participants if p.name == "Alice Smith")
        assert alice.phone_number == "+919876543218"
        assert alice.contact_id is not None
        
        # Check Bob Johnson
        bob = next(p for p in participants if p.name == "Bob Johnson")
        assert bob.phone_number == "+919876543219"
        assert bob.contact_id is not None
        
        # Check Unknown Person
        unknown = next(p for p in participants if p.name == "Unknown Person")
        assert unknown.phone_number == ""
        assert unknown.contact_id is None
    
    @pytest.mark.asyncio
    async def test_handle_missing_contacts_integration(self, contact_manager, test_user):
        """Test handling missing contacts with real database"""
        user_id = str(test_user.id)
        
        participants = [
            Participant(
                name="Missing Contact",
                phone_number="",
                amount_owed=Decimal("100.00")
            )
        ]
        
        user_responses = {
            "Missing Contact_phone": "+919876543220"
        }
        
        updated_participants, remaining_questions = await contact_manager.handle_missing_contacts(
            user_id, participants, user_responses
        )
        
        assert len(updated_participants) == 1
        assert len(remaining_questions) == 0
        assert updated_participants[0].phone_number == "+919876543220"
        assert updated_participants[0].contact_id is not None
    
    @pytest.mark.asyncio
    async def test_phone_number_formatting_consistency(self, contact_manager, test_user):
        """Test that phone number formatting is consistent across operations"""
        user_id = str(test_user.id)
        
        # Create contact with one format
        contact_id1 = await contact_manager.find_or_create_contact(
            user_id, "Test Contact", "9876543221"
        )
        
        # Try to find with different format
        contact_id2 = await contact_manager.find_or_create_contact(
            user_id, "Test Contact", "+919876543221"
        )
        
        # Should be the same contact
        assert contact_id1 == contact_id2
    
    @pytest.mark.asyncio
    async def test_participant_validation_integration(self, contact_manager):
        """Test participant validation with various scenarios"""
        # Valid participants
        valid_participants = [
            Participant(
                name="Alice Smith",
                phone_number="+919876543222",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Bob Johnson",
                phone_number="8765432109",
                amount_owed=Decimal("150.00")
            )
        ]
        
        result = await contact_manager.validate_participants(valid_participants)
        assert result.is_valid is True
        
        # Invalid participants
        invalid_participants = [
            Participant(
                name="",  # Missing name
                phone_number="+919876543223",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Invalid Phone",
                phone_number="invalid",  # Invalid phone
                amount_owed=Decimal("150.00")
            ),
            Participant(
                name="Negative Amount",
                phone_number="+919876543224",
                amount_owed=Decimal("-50.00")  # Negative amount
            )
        ]
        
        result = await contact_manager.validate_participants(invalid_participants)
        assert result.is_valid is False
        assert len(result.errors) >= 3