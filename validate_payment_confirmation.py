#!/usr/bin/env python3
"""
Validation script for Payment Confirmation Service
Tests the core functionality of payment confirmation tracking
"""
import asyncio
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

# Add the app directory to the path
sys.path.append('.')

from app.services.payment_confirmation_service import PaymentConfirmationService
from app.models.database import Bill, BillParticipant, Contact, User
from app.models.enums import PaymentStatus


async def test_payment_confirmation_service():
    """Test payment confirmation service functionality"""
    print("🧪 Testing Payment Confirmation Service...")
    
    # Create mock database repository
    mock_db = Mock()
    
    # Create test data
    user = Mock(spec=User)
    user.id = "user-123"
    user.phone_number = "+919876543210"
    user.name = "Bill Organizer"
    
    contact = Mock(spec=Contact)
    contact.id = "contact-123"
    contact.name = "John Doe"
    contact.phone_number = "+919876543211"
    
    bill = Mock(spec=Bill)
    bill.id = "bill-123"
    bill.user = user
    bill.total_amount = Decimal('150.00')
    bill.description = "Lunch at Pizza Palace"
    bill.status = 'active'
    
    participant = Mock(spec=BillParticipant)
    participant.id = "participant-123"
    participant.bill_id = bill.id
    participant.bill = bill
    participant.contact = contact
    participant.amount_owed = Decimal('50.00')
    participant.payment_status = PaymentStatus.SENT
    participant.paid_at = None
    
    bill.participants = [participant]
    
    # Setup mock repository methods
    mock_db.find_active_participants_by_phone = AsyncMock(return_value=[participant])
    mock_db.update_bill_participant = AsyncMock(return_value=participant)
    mock_db.get_latest_payment_request_for_participant = AsyncMock(return_value=None)
    mock_db.get_bill_with_participants = AsyncMock(return_value=bill)
    
    # Create service
    service = PaymentConfirmationService(mock_db)
    
    # Mock communication service
    service.communication = Mock()
    service.communication.send_message_with_fallback = AsyncMock(return_value={"success": True})
    
    print("✅ Service created successfully")
    
    # Test 1: Confirmation message detection
    print("\n📝 Test 1: Confirmation message detection")
    
    confirmation_messages = ["done", "PAID", "payment completed", "✅", "finished"]
    non_confirmation_messages = ["hello", "how much?", "pending", "will pay later"]
    
    for msg in confirmation_messages:
        assert service._is_confirmation_message(msg), f"Should detect '{msg}' as confirmation"
        print(f"  ✅ '{msg}' detected as confirmation")
    
    for msg in non_confirmation_messages:
        assert not service._is_confirmation_message(msg), f"Should not detect '{msg}' as confirmation"
        print(f"  ✅ '{msg}' correctly not detected as confirmation")
    
    # Test 2: Process payment confirmation
    print("\n📝 Test 2: Process payment confirmation")
    
    result = await service.process_payment_confirmation_message(
        sender_phone="+919876543211",
        message_content="done",
        message_timestamp=datetime.now()
    )
    
    assert result.success, f"Payment confirmation should succeed: {result.error}"
    assert result.participant_name == "John Doe"
    assert result.amount == Decimal('50.00')
    assert result.organizer_notified
    print("  ✅ Payment confirmation processed successfully")
    print(f"  ✅ Participant: {result.participant_name}")
    print(f"  ✅ Amount: ₹{result.amount}")
    print(f"  ✅ Organizer notified: {result.organizer_notified}")
    
    # Verify participant status was updated
    assert participant.payment_status == PaymentStatus.CONFIRMED
    print("  ✅ Participant status updated to CONFIRMED")
    
    # Test 3: Handle payment inquiry
    print("\n📝 Test 3: Handle payment inquiry")
    
    # Reset participant status for inquiry test
    participant.payment_status = PaymentStatus.SENT
    
    inquiry_response = await service.handle_payment_inquiry(
        sender_phone="+919876543211",
        message_content="what's my bill status?"
    )
    
    assert inquiry_response is not None, "Should return response for inquiry"
    assert "Your Bill Status" in inquiry_response
    assert "Lunch at Pizza Palace" in inquiry_response
    assert "₹50.00" in inquiry_response
    print("  ✅ Payment inquiry handled successfully")
    print(f"  ✅ Response includes bill details")
    
    # Test 4: Non-confirmation message
    print("\n📝 Test 4: Non-confirmation message handling")
    
    result = await service.process_payment_confirmation_message(
        sender_phone="+919876543211",
        message_content="hello there",
        message_timestamp=datetime.now()
    )
    
    assert not result.success, "Non-confirmation message should not succeed"
    assert "does not indicate payment confirmation" in result.error
    print("  ✅ Non-confirmation message correctly rejected")
    
    # Test 5: No active participants
    print("\n📝 Test 5: No active participants")
    
    mock_db.find_active_participants_by_phone = AsyncMock(return_value=[])
    
    result = await service.process_payment_confirmation_message(
        sender_phone="+919999999999",
        message_content="done",
        message_timestamp=datetime.now()
    )
    
    assert not result.success, "Should fail when no active participants"
    assert "No active bill participants found" in result.error
    print("  ✅ Correctly handled case with no active participants")
    
    # Test 6: Message creation
    print("\n📝 Test 6: Message creation")
    
    payment_msg = service._create_payment_notification_message(
        participant_name="John Doe",
        amount=Decimal('50.00'),
        bill_description="Lunch at Pizza Palace"
    )
    
    assert "✅ Payment Confirmed!" in payment_msg
    assert "John Doe" in payment_msg
    assert "₹50.00" in payment_msg
    print("  ✅ Payment notification message created correctly")
    
    completion_msg = service._create_completion_notification_message(bill)
    
    assert "🎉 All Payments Complete!" in completion_msg
    assert "₹150.00" in completion_msg
    assert "Lunch at Pizza Palace" in completion_msg
    print("  ✅ Completion notification message created correctly")
    
    print("\n🎉 All tests passed! Payment Confirmation Service is working correctly.")
    return True


async def main():
    """Main validation function"""
    try:
        success = await test_payment_confirmation_service()
        if success:
            print("\n✅ Payment Confirmation Service validation completed successfully!")
            return 0
        else:
            print("\n❌ Payment Confirmation Service validation failed!")
            return 1
    except Exception as e:
        print(f"\n💥 Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)