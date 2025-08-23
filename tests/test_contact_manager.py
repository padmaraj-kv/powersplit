"""
Tests for ContactManager service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from decimal import Decimal
from app.services.contact_manager import ContactManager
from app.models.schemas import Participant, ValidationResult
from app.models.database import Contact, User
from app.models.enums import PaymentStatus


class TestContactManager:
    """Test cases for ContactManager service"""
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock contact repository"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository"""
        return AsyncMock()
    
    @pytest.fixture
    def contact_manager(self, mock_contact_repo, mock_user_repo):
        """ContactManager instance with mocked dependencies"""
        return ContactManager(mock_contact_repo, mock_user_repo)
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID"""
        return str(uuid4())
    
    @pytest.fixture
    def sample_contact(self):
        """Sample contact for testing"""
        contact = MagicMock(spec=Contact)
        contact.id = uuid4()
        contact.name = "John Doe"
        contact.phone_number = "+919876543210"
        contact.created_at = "2024-01-01T00:00:00"
        return contact
    
    @pytest.fixture
    def sample_participants(self):
        """Sample participants for testing"""
        return [
            Participant(
                name="Alice Smith",
                phone_number="9876543210",
                amount_owed=Decimal("100.00"),
                payment_status=PaymentStatus.PENDING
            ),
            Participant(
                name="Bob Johnson",
                phone_number="+919876543211",
                amount_owed=Decimal("150.00"),
                payment_status=PaymentStatus.PENDING
            )
        ]
    
    class TestPhoneNumberValidation:
        """Test phone number validation functionality"""
        
        def test_validate_phone_number_valid_indian(self, contact_manager):
            """Test validation of valid Indian phone numbers"""
            valid_numbers = [
                "9876543210",
                "+919876543210",
                "8765432109",
                "+918765432109"
            ]
            
            for number in valid_numbers:
                assert contact_manager.validate_phone_number(number) is True
        
        def test_validate_phone_number_valid_international(self, contact_manager):
            """Test validation of valid international phone numbers"""
            valid_numbers = [
                "+1234567890",
                "+447123456789",
                "+861234567890"
            ]
            
            for number in valid_numbers:
                assert contact_manager.validate_phone_number(number) is True
        
        def test_validate_phone_number_invalid(self, contact_manager):
            """Test validation of invalid phone numbers"""
            invalid_numbers = [
                "",
                "123",
                "abcdefghij",
                "123456789",  # Too short
                "+1234567890123456",  # Too long
                "5876543210",  # Invalid Indian prefix
                "+91123456789"  # Invalid Indian number
            ]
            
            for number in invalid_numbers:
                assert contact_manager.validate_phone_number(number) is False
        
        def test_format_phone_number_indian(self, contact_manager):
            """Test formatting of Indian phone numbers"""
            test_cases = [
                ("9876543210", "+919876543210"),
                ("+919876543210", "+919876543210"),
                ("919876543210", "+919876543210"),
                ("98765 43210", "+919876543210"),
                ("98-765-43210", "+919876543210")
            ]
            
            for input_number, expected in test_cases:
                result = contact_manager.format_phone_number(input_number)
                assert result == expected
        
        def test_format_phone_number_international(self, contact_manager):
            """Test formatting of international phone numbers"""
            test_cases = [
                ("+1234567890", "+1234567890"),
                ("+44 7123 456789", "+447123456789"),
                ("+86-123-4567-890", "+861234567890")
            ]
            
            for input_number, expected in test_cases:
                result = contact_manager.format_phone_number(input_number)
                assert result == expected
    
    class TestContactOperations:
        """Test contact CRUD operations"""
        
        @pytest.mark.asyncio
        async def test_find_or_create_contact_existing(self, contact_manager, mock_contact_repo, 
                                                     sample_user_id, sample_contact):
            """Test finding existing contact"""
            mock_contact_repo.find_contact_by_phone.return_value = sample_contact
            
            result = await contact_manager.find_or_create_contact(
                sample_user_id, "John Doe", "+919876543210"
            )
            
            assert result == str(sample_contact.id)
            mock_contact_repo.find_contact_by_phone.assert_called_once()
            mock_contact_repo.create_contact.assert_not_called()
        
        @pytest.mark.asyncio
        async def test_find_or_create_contact_new(self, contact_manager, mock_contact_repo, 
                                                sample_user_id, sample_contact):
            """Test creating new contact"""
            mock_contact_repo.find_contact_by_phone.return_value = None
            mock_contact_repo.create_contact.return_value = sample_contact
            
            result = await contact_manager.find_or_create_contact(
                sample_user_id, "Jane Doe", "+919876543211"
            )
            
            assert result == str(sample_contact.id)
            mock_contact_repo.find_contact_by_phone.assert_called_once()
            mock_contact_repo.create_contact.assert_called_once()
        
        @pytest.mark.asyncio
        async def test_get_user_contacts(self, contact_manager, mock_contact_repo, 
                                       sample_user_id, sample_contact):
            """Test retrieving user contacts"""
            mock_contact_repo.get_user_contacts.return_value = [sample_contact]
            
            result = await contact_manager.get_user_contacts(sample_user_id)
            
            assert len(result) == 1
            assert result[0]["id"] == str(sample_contact.id)
            assert result[0]["name"] == sample_contact.name
            assert result[0]["phone_number"] == sample_contact.phone_number
            mock_contact_repo.get_user_contacts.assert_called_once()
    
    class TestParticipantValidation:
        """Test participant validation functionality"""
        
        @pytest.mark.asyncio
        async def test_validate_participants_valid(self, contact_manager, sample_participants):
            """Test validation of valid participants"""
            result = await contact_manager.validate_participants(sample_participants)
            
            assert result.is_valid is True
            assert len(result.errors) == 0
        
        @pytest.mark.asyncio
        async def test_validate_participants_empty(self, contact_manager):
            """Test validation of empty participant list"""
            result = await contact_manager.validate_participants([])
            
            assert result.is_valid is False
            assert "At least one participant is required" in result.errors
        
        @pytest.mark.asyncio
        async def test_validate_participants_missing_name(self, contact_manager):
            """Test validation with missing participant name"""
            participants = [
                Participant(
                    name="",
                    phone_number="+919876543210",
                    amount_owed=Decimal("100.00")
                )
            ]
            
            result = await contact_manager.validate_participants(participants)
            
            assert result.is_valid is False
            assert any("Name is required" in error for error in result.errors)
        
        @pytest.mark.asyncio
        async def test_validate_participants_invalid_phone(self, contact_manager):
            """Test validation with invalid phone number"""
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="invalid",
                    amount_owed=Decimal("100.00")
                )
            ]
            
            result = await contact_manager.validate_participants(participants)
            
            assert result.is_valid is False
            assert any("Invalid phone number format" in error for error in result.errors)
        
        @pytest.mark.asyncio
        async def test_validate_participants_duplicate_phone(self, contact_manager):
            """Test validation with duplicate phone numbers"""
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="+919876543210",
                    amount_owed=Decimal("100.00")
                ),
                Participant(
                    name="Jane Doe",
                    phone_number="9876543210",  # Same number, different format
                    amount_owed=Decimal("150.00")
                )
            ]
            
            result = await contact_manager.validate_participants(participants)
            
            assert result.is_valid is False
            assert any("Duplicate phone number" in error for error in result.errors)
        
        @pytest.mark.asyncio
        async def test_validate_participants_negative_amount(self, contact_manager):
            """Test validation with negative amount"""
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="+919876543210",
                    amount_owed=Decimal("-100.00")
                )
            ]
            
            result = await contact_manager.validate_participants(participants)
            
            assert result.is_valid is False
            assert any("Amount must be positive" in error for error in result.errors)
    
    class TestParticipantWorkflow:
        """Test participant collection workflow"""
        
        @pytest.mark.asyncio
        async def test_collect_participants_workflow_success(self, contact_manager, mock_contact_repo,
                                                           sample_user_id, sample_participants, sample_contact):
            """Test successful participant collection workflow"""
            mock_contact_repo.find_contact_by_phone.return_value = sample_contact
            
            updated_participants, missing_questions = await contact_manager.collect_participants_workflow(
                sample_user_id, sample_participants
            )
            
            assert len(updated_participants) == 2
            assert len(missing_questions) == 0
            assert all(p.contact_id == str(sample_contact.id) for p in updated_participants)
        
        @pytest.mark.asyncio
        async def test_collect_participants_workflow_missing_phone(self, contact_manager, sample_user_id):
            """Test workflow with missing phone numbers"""
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="",
                    amount_owed=Decimal("100.00")
                )
            ]
            
            updated_participants, missing_questions = await contact_manager.collect_participants_workflow(
                sample_user_id, participants
            )
            
            assert len(updated_participants) == 0
            assert len(missing_questions) > 0
            assert "phone number" in missing_questions[0].lower()
        
        @pytest.mark.asyncio
        async def test_deduplicate_contacts(self, contact_manager, mock_contact_repo, 
                                          sample_user_id, sample_contact):
            """Test contact deduplication"""
            mock_contact_repo.get_user_contacts.return_value = [sample_contact]
            
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="+919876543210",
                    amount_owed=Decimal("100.00")
                ),
                Participant(
                    name="John Doe",
                    phone_number="919876543210",  # Same number, different format
                    amount_owed=Decimal("150.00")
                )
            ]
            
            result = await contact_manager.deduplicate_contacts(sample_user_id, participants)
            
            assert len(result) == 1
            assert result[0].contact_id == str(sample_contact.id)
        
        @pytest.mark.asyncio
        async def test_auto_populate_from_history(self, contact_manager, mock_contact_repo,
                                                sample_user_id, sample_contact):
            """Test auto-population from contact history"""
            mock_contact_repo.get_user_contacts.return_value = [sample_contact]
            
            participant_names = ["John Doe", "Unknown Person"]
            
            result = await contact_manager.auto_populate_from_history(sample_user_id, participant_names)
            
            assert len(result) == 2
            assert result[0].name == "John Doe"
            assert result[0].phone_number == sample_contact.phone_number
            assert result[0].contact_id == str(sample_contact.id)
            assert result[1].name == "Unknown Person"
            assert result[1].phone_number == ""
            assert result[1].contact_id is None
        
        @pytest.mark.asyncio
        async def test_handle_missing_contacts(self, contact_manager, mock_contact_repo,
                                             sample_user_id, sample_contact):
            """Test handling missing contact responses"""
            mock_contact_repo.find_contact_by_phone.return_value = None
            mock_contact_repo.create_contact.return_value = sample_contact
            
            participants = [
                Participant(
                    name="John Doe",
                    phone_number="",
                    amount_owed=Decimal("100.00")
                )
            ]
            
            user_responses = {
                "John Doe_phone": "+919876543210"
            }
            
            updated_participants, remaining_questions = await contact_manager.handle_missing_contacts(
                sample_user_id, participants, user_responses
            )
            
            assert len(updated_participants) == 1
            assert len(remaining_questions) == 0
            assert updated_participants[0].phone_number == "+919876543210"
            assert updated_participants[0].contact_id == str(sample_contact.id)
    
    class TestErrorHandling:
        """Test error handling scenarios"""
        
        @pytest.mark.asyncio
        async def test_find_or_create_contact_repository_error(self, contact_manager, mock_contact_repo, sample_user_id):
            """Test handling repository errors"""
            mock_contact_repo.find_contact_by_phone.side_effect = Exception("Database error")
            
            with pytest.raises(Exception, match="Database error"):
                await contact_manager.find_or_create_contact(sample_user_id, "John Doe", "+919876543210")
        
        @pytest.mark.asyncio
        async def test_get_user_contacts_repository_error(self, contact_manager, mock_contact_repo, sample_user_id):
            """Test handling repository errors in get_user_contacts"""
            mock_contact_repo.get_user_contacts.side_effect = Exception("Database error")
            
            with pytest.raises(Exception, match="Database error"):
                await contact_manager.get_user_contacts(sample_user_id)
        
        def test_validate_phone_number_none_input(self, contact_manager):
            """Test phone number validation with None input"""
            assert contact_manager.validate_phone_number(None) is False
        
        def test_format_phone_number_none_input(self, contact_manager):
            """Test phone number formatting with None input"""
            assert contact_manager.format_phone_number(None) is None