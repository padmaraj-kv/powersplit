"""
Example usage of ContactManager service
"""
import asyncio
from decimal import Decimal
from uuid import uuid4
from app.services.contact_manager import ContactManager
from app.database.repositories import SQLContactRepository, SQLUserRepository
from app.models.schemas import Participant
from app.models.database import User
from app.models.enums import PaymentStatus
from app.core.database import get_db_session


async def demonstrate_contact_manager():
    """Demonstrate ContactManager functionality"""
    print("=== ContactManager Example ===\n")
    
    # Get database session
    db_session = next(get_db_session())
    
    try:
        # Initialize repositories and service
        contact_repo = SQLContactRepository(db_session)
        user_repo = SQLUserRepository(db_session)
        contact_manager = ContactManager(contact_repo, user_repo)
        
        # Create test user
        test_user = User(phone_number="+919876543210", name="Test User")
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)
        user_id = str(test_user.id)
        
        print(f"Created test user: {test_user.name} ({test_user.phone_number})")
        print(f"User ID: {user_id}\n")
        
        # 1. Phone Number Validation
        print("1. Phone Number Validation:")
        test_numbers = [
            "9876543210",
            "+919876543210", 
            "invalid",
            "+1234567890",
            "123"
        ]
        
        for number in test_numbers:
            is_valid = contact_manager.validate_phone_number(number)
            formatted = contact_manager.format_phone_number(number)
            print(f"  {number:15} -> Valid: {is_valid:5} | Formatted: {formatted}")
        print()
        
        # 2. Create some contacts
        print("2. Creating Contacts:")
        contacts_to_create = [
            ("Alice Smith", "+919876543211"),
            ("Bob Johnson", "8765432109"),
            ("Charlie Brown", "+919876543213")
        ]
        
        contact_ids = []
        for name, phone in contacts_to_create:
            contact_id = await contact_manager.find_or_create_contact(user_id, name, phone)
            contact_ids.append(contact_id)
            print(f"  Created contact: {name} ({phone}) -> ID: {contact_id}")
        print()
        
        # 3. Get user contacts
        print("3. Retrieving User Contacts:")
        user_contacts = await contact_manager.get_user_contacts(user_id)
        for contact in user_contacts:
            print(f"  {contact['name']:15} | {contact['phone_number']:15} | ID: {contact['id']}")
        print()
        
        # 4. Test deduplication
        print("4. Contact Deduplication:")
        participants_with_duplicates = [
            Participant(
                name="Alice Smith",
                phone_number="+919876543211",
                amount_owed=Decimal("100.00"),
                payment_status=PaymentStatus.PENDING
            ),
            Participant(
                name="Alice Smith",
                phone_number="919876543211",  # Same number, different format
                amount_owed=Decimal("150.00"),
                payment_status=PaymentStatus.PENDING
            ),
            Participant(
                name="Bob Johnson",
                phone_number="+918765432109",
                amount_owed=Decimal("200.00"),
                payment_status=PaymentStatus.PENDING
            )
        ]
        
        print(f"  Original participants: {len(participants_with_duplicates)}")
        deduplicated = await contact_manager.deduplicate_contacts(user_id, participants_with_duplicates)
        print(f"  After deduplication: {len(deduplicated)}")
        for p in deduplicated:
            print(f"    {p.name:15} | {p.phone_number:15} | Amount: {p.amount_owed}")
        print()
        
        # 5. Auto-populate from history
        print("5. Auto-populate from History:")
        participant_names = ["Alice Smith", "Bob Johnson", "Unknown Person"]
        auto_populated = await contact_manager.auto_populate_from_history(user_id, participant_names)
        
        for participant in auto_populated:
            status = "Found" if participant.contact_id else "Not found"
            print(f"  {participant.name:15} | {participant.phone_number:15} | {status}")
        print()
        
        # 6. Participant validation
        print("6. Participant Validation:")
        
        # Valid participants
        valid_participants = [
            Participant(
                name="Alice Smith",
                phone_number="+919876543211",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Bob Johnson",
                phone_number="+918765432109",
                amount_owed=Decimal("150.00")
            )
        ]
        
        validation_result = await contact_manager.validate_participants(valid_participants)
        print(f"  Valid participants: {validation_result.is_valid}")
        if validation_result.errors:
            for error in validation_result.errors:
                print(f"    Error: {error}")
        
        # Invalid participants
        invalid_participants = [
            Participant(
                name="",  # Missing name
                phone_number="+919876543214",
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="Invalid Phone",
                phone_number="invalid",
                amount_owed=Decimal("150.00")
            )
        ]
        
        validation_result = await contact_manager.validate_participants(invalid_participants)
        print(f"  Invalid participants: {validation_result.is_valid}")
        for error in validation_result.errors:
            print(f"    Error: {error}")
        print()
        
        # 7. Complete workflow
        print("7. Complete Participant Collection Workflow:")
        workflow_participants = [
            Participant(
                name="Alice Smith",
                phone_number="9876543211",  # Existing contact, different format
                amount_owed=Decimal("100.00")
            ),
            Participant(
                name="New Person",
                phone_number="+919876543215",
                amount_owed=Decimal("150.00")
            ),
            Participant(
                name="Missing Phone",
                phone_number="",  # Missing phone number
                amount_owed=Decimal("75.00")
            )
        ]
        
        updated_participants, missing_questions = await contact_manager.collect_participants_workflow(
            user_id, workflow_participants
        )
        
        print(f"  Successfully processed: {len(updated_participants)} participants")
        for p in updated_participants:
            print(f"    {p.name:15} | {p.phone_number:15} | Contact ID: {p.contact_id}")
        
        print(f"  Missing contact questions: {len(missing_questions)}")
        for question in missing_questions:
            print(f"    {question}")
        print()
        
        # 8. Handle missing contacts
        if missing_questions:
            print("8. Handling Missing Contacts:")
            user_responses = {
                "Missing Phone_phone": "+919876543216"
            }
            
            final_participants, remaining_questions = await contact_manager.handle_missing_contacts(
                user_id, workflow_participants, user_responses
            )
            
            print(f"  Final participants: {len(final_participants)}")
            print(f"  Remaining questions: {len(remaining_questions)}")
        
        print("\n=== ContactManager Example Complete ===")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        raise
    finally:
        # Cleanup
        try:
            db_session.delete(test_user)
            db_session.commit()
            print("\nCleaned up test data")
        except:
            pass
        db_session.close()


if __name__ == "__main__":
    asyncio.run(demonstrate_contact_manager())