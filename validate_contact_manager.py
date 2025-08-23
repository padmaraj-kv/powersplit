"""
Validation script for ContactManager implementation
"""
import asyncio
import sys
from decimal import Decimal
from uuid import uuid4
from app.services.contact_manager import ContactManager
from app.database.repositories import SQLContactRepository, SQLUserRepository
from app.models.schemas import Participant
from app.models.database import User
from app.models.enums import PaymentStatus
from app.core.database import get_db_session


class ContactManagerValidator:
    """Validator for ContactManager functionality"""
    
    def __init__(self):
        self.db_session = next(get_db_session())
        self.contact_repo = SQLContactRepository(self.db_session)
        self.user_repo = SQLUserRepository(self.db_session)
        self.contact_manager = ContactManager(self.contact_repo, self.user_repo)
        self.test_user = None
        self.passed_tests = 0
        self.total_tests = 0
    
    def assert_test(self, condition, test_name):
        """Assert test condition and track results"""
        self.total_tests += 1
        if condition:
            print(f"✅ {test_name}")
            self.passed_tests += 1
        else:
            print(f"❌ {test_name}")
    
    async def setup_test_user(self):
        """Create test user for validation"""
        self.test_user = User(phone_number="+919876543210", name="Test User")
        self.db_session.add(self.test_user)
        self.db_session.commit()
        self.db_session.refresh(self.test_user)
        print(f"Created test user: {self.test_user.id}")
    
    def cleanup_test_user(self):
        """Clean up test user"""
        if self.test_user:
            try:
                self.db_session.delete(self.test_user)
                self.db_session.commit()
                print(f"Cleaned up test user: {self.test_user.id}")
            except:
                pass
        self.db_session.close()
    
    def test_phone_validation(self):
        """Test phone number validation"""
        print("\n=== Testing Phone Number Validation ===")
        
        # Valid numbers
        valid_numbers = [
            "9876543210",
            "+919876543210",
            "8765432109",
            "+918765432109",
            "+1234567890",
            "+447123456789"
        ]
        
        for number in valid_numbers:
            result = self.contact_manager.validate_phone_number(number)
            self.assert_test(result, f"Valid phone number: {number}")
        
        # Invalid numbers
        invalid_numbers = [
            "",
            "123",
            "abcdefghij",
            "123456789",
            "+1234567890123456",
            "5876543210",
            None
        ]
        
        for number in invalid_numbers:
            result = self.contact_manager.validate_phone_number(number)
            self.assert_test(not result, f"Invalid phone number: {number}")
    
    def test_phone_formatting(self):
        """Test phone number formatting"""
        print("\n=== Testing Phone Number Formatting ===")
        
        test_cases = [
            ("9876543210", "+919876543210"),
            ("+919876543210", "+919876543210"),
            ("919876543210", "+919876543210"),
            ("98765 43210", "+919876543210"),
            ("98-765-43210", "+919876543210"),
            ("+1234567890", "+1234567890"),
            ("+44 7123 456789", "+447123456789")
        ]
        
        for input_number, expected in test_cases:
            result = self.contact_manager.format_phone_number(input_number)
            self.assert_test(result == expected, f"Format {input_number} -> {expected} (got {result})")
    
    async def test_contact_operations(self):
        """Test contact CRUD operations"""
        print("\n=== Testing Contact Operations ===")
        
        user_id = str(self.test_user.id)
        
        # Test create contact
        contact_id = await self.contact_manager.find_or_create_contact(
            user_id, "John Doe", "+919876543211"
        )
        self.assert_test(contact_id is not None, "Create new contact")
        
        # Test find existing contact
        same_contact_id = await self.contact_manager.find_or_create_contact(
            user_id, "John Doe", "+919876543211"
        )
        self.assert_test(contact_id == same_contact_id, "Find existing contact")
        
        # Test get user contacts
        contacts = await self.contact_manager.get_user_contacts(user_id)
        self.assert_test(len(contacts) >= 1, "Get user contacts")
        self.assert_test(any(c["name"] == "John Doe" for c in contacts), "Contact in user list")
    
    async def test_participant_validation(self):
        """Test participant validation"""
        print("\n=== Testing Participant Validation ===")
        
        # Valid participants
        valid_participants = [
            Participant(
                name="Alice Smith",
                phone_number="+919876543212",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Bob Johnson",
                phone_number="+919876543213",
                amount_owed=Decimal("150.00")
            )
        ]
        
        result = await self.contact_manager.validate_participants(valid_participants)
        self.assert_test(result.is_valid, "Valid participants validation")
        
        # Empty participants
        result = await self.contact_manager.validate_participants([])
        self.assert_test(not result.is_valid, "Empty participants validation")
        
        # Invalid participants
        invalid_participants = [
            Participant(
                name="",
                phone_number="+919876543214",
                amount_owed=Decimal("100.00")
            )
        ]
        
        result = await self.contact_manager.validate_participants(invalid_participants)
        self.assert_test(not result.is_valid, "Invalid participants validation")
        self.assert_test(len(result.errors) > 0, "Validation errors present")
    
    async def test_deduplication(self):
        """Test contact deduplication"""
        print("\n=== Testing Contact Deduplication ===")
        
        user_id = str(self.test_user.id)
        
        # Create existing contact
        await self.contact_manager.find_or_create_contact(user_id, "Test Contact", "+919876543215")
        
        # Create participants with duplicates
        participants = [
            Participant(
                name="Test Contact",
                phone_number="+919876543215",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Test Contact",
                phone_number="919876543215",  # Same number, different format
                amount_owed=Decimal("150.00")
            ),
            Participant(
                name="Different Contact",
                phone_number="+919876543216",
                amount_owed=Decimal("200.00")
            )
        ]
        
        deduplicated = await self.contact_manager.deduplicate_contacts(user_id, participants)
        self.assert_test(len(deduplicated) == 2, "Deduplication removes duplicates")
        
        phone_numbers = [p.phone_number for p in deduplicated]
        self.assert_test("+919876543215" in phone_numbers, "Original contact preserved")
        self.assert_test("+919876543216" in phone_numbers, "Different contact preserved")
    
    async def test_auto_population(self):
        """Test auto-population from history"""
        print("\n=== Testing Auto-population ===")
        
        user_id = str(self.test_user.id)
        
        # Create some contacts
        await self.contact_manager.find_or_create_contact(user_id, "Alice Smith", "+919876543217")
        await self.contact_manager.find_or_create_contact(user_id, "Bob Johnson", "+919876543218")
        
        # Auto-populate
        participant_names = ["Alice Smith", "Bob Johnson", "Unknown Person"]
        participants = await self.contact_manager.auto_populate_from_history(user_id, participant_names)
        
        self.assert_test(len(participants) == 3, "Auto-population creates all participants")
        
        alice = next((p for p in participants if p.name == "Alice Smith"), None)
        self.assert_test(alice is not None, "Alice found in auto-population")
        self.assert_test(alice.phone_number == "+919876543217", "Alice phone auto-populated")
        self.assert_test(alice.contact_id is not None, "Alice contact ID set")
        
        unknown = next((p for p in participants if p.name == "Unknown Person"), None)
        self.assert_test(unknown is not None, "Unknown person created")
        self.assert_test(unknown.phone_number == "", "Unknown person has no phone")
        self.assert_test(unknown.contact_id is None, "Unknown person has no contact ID")
    
    async def test_workflow(self):
        """Test complete participant collection workflow"""
        print("\n=== Testing Complete Workflow ===")
        
        user_id = str(self.test_user.id)
        
        # Create existing contact
        await self.contact_manager.find_or_create_contact(user_id, "Existing Contact", "+919876543219")
        
        participants = [
            Participant(
                name="Existing Contact",
                phone_number="9876543219",  # Different format
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="New Contact",
                phone_number="+919876543220",
                amount_owed=Decimal("150.00")
            ),
            Participant(
                name="Missing Phone",
                phone_number="",
                amount_owed=Decimal("75.00")
            )
        ]
        
        updated_participants, missing_questions = await self.contact_manager.collect_participants_workflow(
            user_id, participants
        )
        
        self.assert_test(len(updated_participants) == 2, "Workflow processes valid participants")
        self.assert_test(len(missing_questions) > 0, "Workflow identifies missing contacts")
        self.assert_test(all(p.contact_id is not None for p in updated_participants), "All processed participants have contact IDs")
    
    async def test_missing_contact_handling(self):
        """Test handling missing contact responses"""
        print("\n=== Testing Missing Contact Handling ===")
        
        user_id = str(self.test_user.id)
        
        participants = [
            Participant(
                name="Missing Contact",
                phone_number="",
                amount_owed=Decimal("100.00")
            )
        ]
        
        user_responses = {
            "Missing Contact_phone": "+919876543221"
        }
        
        updated_participants, remaining_questions = await self.contact_manager.handle_missing_contacts(
            user_id, participants, user_responses
        )
        
        self.assert_test(len(updated_participants) == 1, "Missing contact handled")
        self.assert_test(len(remaining_questions) == 0, "No remaining questions")
        self.assert_test(updated_participants[0].phone_number == "+919876543221", "Phone number updated")
        self.assert_test(updated_participants[0].contact_id is not None, "Contact ID assigned")
    
    async def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting ContactManager Validation")
        
        try:
            await self.setup_test_user()
            
            # Run all tests
            self.test_phone_validation()
            self.test_phone_formatting()
            await self.test_contact_operations()
            await self.test_participant_validation()
            await self.test_deduplication()
            await self.test_auto_population()
            await self.test_workflow()
            await self.test_missing_contact_handling()
            
            # Print results
            print(f"\n📊 Test Results: {self.passed_tests}/{self.total_tests} passed")
            
            if self.passed_tests == self.total_tests:
                print("🎉 All tests passed! ContactManager implementation is working correctly.")
                return True
            else:
                print("❌ Some tests failed. Please check the implementation.")
                return False
                
        except Exception as e:
            print(f"💥 Validation failed with error: {e}")
            return False
        finally:
            self.cleanup_test_user()


async def main():
    """Main validation function"""
    validator = ContactManagerValidator()
    success = await validator.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())