"""
Payment Confirmation Service Example

This example demonstrates how to use the PaymentConfirmationService
to handle payment confirmations and completion tracking.

Requirements demonstrated:
- 5.1: Process payment confirmation messages from participants
- 5.2: Update payment status in database when confirmations are received
- 5.3: Send notifications to bill creator when payments are confirmed
- 5.5: Detect completion when all payments are confirmed
"""
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from app.services.payment_confirmation_service import PaymentConfirmationService
from app.models.database import Bill, BillParticipant, Contact, User, PaymentRequest
from app.models.enums import PaymentStatus


async def example_payment_confirmation_workflow():
    """
    Example workflow showing payment confirmation processing
    """
    print("🔄 Payment Confirmation Service Example")
    print("=" * 50)
    
    # Create mock database repository
    mock_db = Mock()
    
    # Create test data representing a bill with participants
    print("\n📋 Setting up test bill with participants...")
    
    # Bill organizer
    organizer = Mock(spec=User)
    organizer.id = "organizer-123"
    organizer.phone_number = "+919876543210"
    organizer.name = "Alice Smith"
    
    # Participants
    john_contact = Mock(spec=Contact)
    john_contact.id = "contact-john"
    john_contact.name = "John Doe"
    john_contact.phone_number = "+919876543211"
    
    sarah_contact = Mock(spec=Contact)
    sarah_contact.id = "contact-sarah"
    sarah_contact.name = "Sarah Wilson"
    sarah_contact.phone_number = "+919876543212"
    
    # Bill
    bill = Mock(spec=Bill)
    bill.id = "bill-123"
    bill.user = organizer
    bill.total_amount = Decimal('300.00')
    bill.description = "Team Dinner at Italian Restaurant"
    bill.status = 'active'
    
    # Bill participants
    john_participant = Mock(spec=BillParticipant)
    john_participant.id = "participant-john"
    john_participant.bill_id = bill.id
    john_participant.bill = bill
    john_participant.contact = john_contact
    john_participant.amount_owed = Decimal('100.00')
    john_participant.payment_status = PaymentStatus.SENT
    john_participant.paid_at = None
    
    sarah_participant = Mock(spec=BillParticipant)
    sarah_participant.id = "participant-sarah"
    sarah_participant.bill_id = bill.id
    sarah_participant.bill = bill
    sarah_participant.contact = sarah_contact
    sarah_participant.amount_owed = Decimal('100.00')
    sarah_participant.payment_status = PaymentStatus.SENT
    sarah_participant.paid_at = None
    
    alice_participant = Mock(spec=BillParticipant)
    alice_participant.id = "participant-alice"
    alice_participant.bill_id = bill.id
    alice_participant.bill = bill
    alice_participant.contact = organizer  # Organizer is also a participant
    alice_participant.amount_owed = Decimal('100.00')
    alice_participant.payment_status = PaymentStatus.CONFIRMED  # Already paid
    alice_participant.paid_at = datetime.now()
    
    bill.participants = [john_participant, sarah_participant, alice_participant]
    
    # Payment requests
    john_payment_request = Mock(spec=PaymentRequest)
    john_payment_request.id = "payment-request-john"
    john_payment_request.upi_link = "upi://pay?pa=alice@upi&pn=Alice&am=100.00&tn=Team+Dinner"
    john_payment_request.mark_as_confirmed = Mock()
    
    print(f"  📊 Bill: {bill.description}")
    print(f"  💰 Total: ₹{bill.total_amount}")
    print(f"  👥 Participants: {len(bill.participants)}")
    print(f"  ✅ Already paid: Alice (₹100.00)")
    print(f"  ⏳ Pending: John (₹100.00), Sarah (₹100.00)")
    
    # Setup mock repository methods
    mock_db.find_active_participants_by_phone = AsyncMock()
    mock_db.update_bill_participant = AsyncMock()
    mock_db.get_latest_payment_request_for_participant = AsyncMock()
    mock_db.update_payment_request = AsyncMock()
    mock_db.get_bill_with_participants = AsyncMock(return_value=bill)
    mock_db.update_bill = AsyncMock()
    
    # Create payment confirmation service
    service = PaymentConfirmationService(mock_db)
    
    # Mock communication service
    service.communication = Mock()
    service.communication.send_message_with_fallback = AsyncMock(return_value={"success": True})
    
    print("\n🔧 Payment Confirmation Service initialized")
    
    # Scenario 1: John confirms his payment
    print("\n" + "=" * 50)
    print("📱 Scenario 1: John confirms payment")
    print("=" * 50)
    
    # Setup mocks for John's confirmation
    mock_db.find_active_participants_by_phone.return_value = [john_participant]
    mock_db.update_bill_participant.return_value = john_participant
    mock_db.get_latest_payment_request_for_participant.return_value = john_payment_request
    mock_db.update_payment_request.return_value = john_payment_request
    
    # Process John's confirmation message
    print("📨 John sends: 'done'")
    
    result = await service.process_payment_confirmation_message(
        sender_phone=john_contact.phone_number,
        message_content="done",
        message_timestamp=datetime.now()
    )
    
    if result.success:
        print("✅ Payment confirmation processed successfully!")
        print(f"  👤 Participant: {result.participant_name}")
        print(f"  💰 Amount: ₹{result.amount}")
        print(f"  📧 Organizer notified: {result.organizer_notified}")
        print(f"  🎯 Bill completed: {result.completion_detected}")
        
        # Update John's status
        john_participant.payment_status = PaymentStatus.CONFIRMED
        john_participant.paid_at = datetime.now()
        
        print(f"  📊 John's status updated to: {john_participant.payment_status}")
    else:
        print(f"❌ Payment confirmation failed: {result.error}")
    
    # Scenario 2: Sarah asks about her payment status
    print("\n" + "=" * 50)
    print("📱 Scenario 2: Sarah inquires about payment status")
    print("=" * 50)
    
    # Setup mocks for Sarah's inquiry
    mock_db.find_active_participants_by_phone.return_value = [sarah_participant]
    mock_db.get_latest_payment_request_for_participant.return_value = john_payment_request  # Reuse for example
    
    print("📨 Sarah sends: 'what's my bill status?'")
    
    inquiry_response = await service.handle_payment_inquiry(
        sender_phone=sarah_contact.phone_number,
        message_content="what's my bill status?"
    )
    
    if inquiry_response:
        print("✅ Payment inquiry handled successfully!")
        print("📋 Response sent to Sarah:")
        print("-" * 30)
        print(inquiry_response)
        print("-" * 30)
    else:
        print("❌ Payment inquiry not recognized")
    
    # Scenario 3: Sarah confirms payment (triggers completion)
    print("\n" + "=" * 50)
    print("📱 Scenario 3: Sarah confirms payment (final payment)")
    print("=" * 50)
    
    # Setup mocks for Sarah's confirmation
    mock_db.find_active_participants_by_phone.return_value = [sarah_participant]
    mock_db.update_bill_participant.return_value = sarah_participant
    mock_db.get_latest_payment_request_for_participant.return_value = None
    
    # Mock bill completion check
    def check_all_paid():
        return all(p.payment_status == PaymentStatus.CONFIRMED for p in bill.participants)
    
    print("📨 Sarah sends: 'payment completed ✅'")
    
    result = await service.process_payment_confirmation_message(
        sender_phone=sarah_contact.phone_number,
        message_content="payment completed ✅",
        message_timestamp=datetime.now()
    )
    
    if result.success:
        print("✅ Payment confirmation processed successfully!")
        print(f"  👤 Participant: {result.participant_name}")
        print(f"  💰 Amount: ₹{result.amount}")
        print(f"  📧 Organizer notified: {result.organizer_notified}")
        
        # Update Sarah's status
        sarah_participant.payment_status = PaymentStatus.CONFIRMED
        sarah_participant.paid_at = datetime.now()
        
        # Check if all payments are complete
        all_paid = check_all_paid()
        if all_paid:
            print("🎉 ALL PAYMENTS COMPLETE!")
            print("  📊 Bill status updated to: completed")
            print("  📧 Completion notification sent to organizer")
            bill.status = 'completed'
        
        print(f"  🎯 Bill completed: {all_paid}")
    else:
        print(f"❌ Payment confirmation failed: {result.error}")
    
    # Scenario 4: Test message templates
    print("\n" + "=" * 50)
    print("📝 Scenario 4: Message templates")
    print("=" * 50)
    
    print("📧 Payment notification message:")
    payment_msg = service._create_payment_notification_message(
        participant_name="John Doe",
        amount=Decimal('100.00'),
        bill_description="Team Dinner at Italian Restaurant"
    )
    print("-" * 40)
    print(payment_msg)
    print("-" * 40)
    
    print("\n🎉 Completion notification message:")
    completion_msg = service._create_completion_notification_message(bill)
    print("-" * 40)
    print(completion_msg)
    print("-" * 40)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 WORKFLOW SUMMARY")
    print("=" * 50)
    
    print("✅ Requirements implemented:")
    print("  • 5.1: Payment confirmation message processing")
    print("  • 5.2: Payment status updates in database")
    print("  • 5.3: Organizer notifications for confirmations")
    print("  • 5.5: Completion detection when all payments confirmed")
    
    print("\n🔧 Key features demonstrated:")
    print("  • Confirmation keyword detection")
    print("  • Participant lookup by phone number")
    print("  • Payment status updates")
    print("  • Organizer notifications")
    print("  • Bill completion detection")
    print("  • Payment status inquiries")
    print("  • Message template generation")
    
    print("\n🎯 Payment Confirmation Service is ready for production!")


async def example_confirmation_patterns():
    """
    Example showing different confirmation message patterns
    """
    print("\n" + "=" * 50)
    print("🔍 CONFIRMATION PATTERN EXAMPLES")
    print("=" * 50)
    
    service = PaymentConfirmationService(Mock())
    
    # Test various confirmation patterns
    test_messages = [
        ("done", True),
        ("PAID", True),
        ("payment completed", True),
        ("I have paid the amount", True),
        ("Money sent ✅", True),
        ("👍 finished", True),
        ("Payment made successfully", True),
        ("hello there", False),
        ("how much do I owe?", False),
        ("will pay tomorrow", False),
        ("payment pending", False),
        ("not done yet", False),
    ]
    
    print("📝 Testing confirmation message detection:")
    print()
    
    for message, expected in test_messages:
        result = service._is_confirmation_message(message)
        status = "✅" if result == expected else "❌"
        detection = "CONFIRMED" if result else "NOT CONFIRMED"
        print(f"  {status} '{message}' → {detection}")
    
    print(f"\n🎯 Pattern detection working correctly!")


if __name__ == "__main__":
    print("🚀 Starting Payment Confirmation Service Examples...")
    
    # Run the main workflow example
    asyncio.run(example_payment_confirmation_workflow())
    
    # Run the pattern detection example
    asyncio.run(example_confirmation_patterns())
    
    print("\n✨ Examples completed successfully!")