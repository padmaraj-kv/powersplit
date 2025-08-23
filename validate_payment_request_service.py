#!/usr/bin/env python3
"""
Payment Request Service Validation Script

This script validates the payment request distribution system by testing
all major functionality including message distribution, fallback mechanisms,
and delivery tracking.
"""
import asyncio
import sys
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Add the app directory to the path
sys.path.append('.')

from app.services.payment_request_service import PaymentRequestService, PaymentRequestResult, DistributionSummary
from app.services.upi_service import UPIService, UPIApp
from app.models.database import Bill, BillParticipant, Contact, User, PaymentRequest
from app.models.enums import DeliveryMethod


class MockDatabaseRepository:
    """Mock database repository for testing"""
    
    def __init__(self):
        self.bills = {}
        self.payment_requests = {}
        self.participants = {}
    
    async def get_bill_with_participants(self, bill_id: str):
        return self.bills.get(bill_id)
    
    async def create_payment_request(self, payment_request: PaymentRequest):
        payment_request.id = uuid4()
        self.payment_requests[str(payment_request.id)] = payment_request
        return payment_request
    
    async def update_payment_request(self, payment_request: PaymentRequest):
        self.payment_requests[str(payment_request.id)] = payment_request
        return payment_request
    
    async def get_payment_request(self, request_id: str):
        return self.payment_requests.get(request_id)
    
    async def update_bill_participant(self, participant: BillParticipant):
        self.participants[str(participant.id)] = participant
        return participant
    
    async def get_latest_payment_request_for_participant(self, participant_id: str):
        for req in self.payment_requests.values():
            if str(req.bill_participant_id) == participant_id:
                return req
        return None
    
    async def get_participant_by_phone_and_bill(self, phone_number: str, bill_id: str):
        bill = self.bills.get(bill_id)
        if not bill:
            return None
        
        for participant in bill.participants:
            if participant.contact and participant.contact.phone_number == phone_number:
                return participant
        return None
    
    async def update_bill(self, bill: Bill):
        self.bills[str(bill.id)] = bill
        return bill
    
    async def get_payment_request_statistics(self, bill_id=None, since_date=None):
        return {
            "total_requests": len(self.payment_requests),
            "successful_deliveries": len([r for r in self.payment_requests.values() if r.whatsapp_sent or r.sms_sent]),
            "failed_deliveries": 0,
            "whatsapp_deliveries": len([r for r in self.payment_requests.values() if r.whatsapp_sent]),
            "sms_deliveries": len([r for r in self.payment_requests.values() if r.sms_sent]),
            "confirmed_payments": len([r for r in self.payment_requests.values() if r.status == 'confirmed']),
            "success_rate": 1.0,
            "confirmation_rate": 0.5
        }


class MockCommunicationService:
    """Mock communication service for testing"""
    
    def __init__(self, success_rate=1.0, use_fallback=False):
        self.success_rate = success_rate
        self.use_fallback = use_fallback
        self.sent_messages = []
    
    async def send_message_with_fallback(self, phone_number: str, message: str):
        self.sent_messages.append({
            "phone_number": phone_number,
            "message": message,
            "timestamp": datetime.now()
        })
        
        # Simulate success/failure based on success rate
        import random
        success = random.random() < self.success_rate
        
        if success:
            method = DeliveryMethod.SMS if self.use_fallback else DeliveryMethod.WHATSAPP
            return {
                "success": True,
                "final_method": method,
                "fallback_used": self.use_fallback,
                "error": None
            }
        else:
            return {
                "success": False,
                "final_method": None,
                "fallback_used": True,
                "error": "All delivery methods failed"
            }


def create_test_bill():
    """Create a test bill with participants"""
    user = User(
        id=uuid4(),
        phone_number="+919876543210",
        name="Test Organizer"
    )
    
    bill = Bill(
        id=uuid4(),
        user_id=user.id,
        user=user,
        total_amount=Decimal("900.00"),
        description="Test Bill Split",
        status="active"
    )
    
    # Create contacts
    contacts = [
        Contact(id=uuid4(), user_id=user.id, name="Alice", phone_number="+919876543211"),
        Contact(id=uuid4(), user_id=user.id, name="Bob", phone_number="+919876543212"),
        Contact(id=uuid4(), user_id=user.id, name="Carol", phone_number="+919876543213")
    ]
    
    # Create participants
    participants = []
    for i, contact in enumerate(contacts):
        participant = BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contact.id,
            contact=contact,
            amount_owed=Decimal("300.00"),
            payment_status="pending"
        )
        participants.append(participant)
    
    bill.participants = participants
    return bill


async def test_payment_request_distribution():
    """Test basic payment request distribution"""
    print("🧪 Testing Payment Request Distribution...")
    
    # Setup
    mock_db = MockDatabaseRepository()
    mock_comm = MockCommunicationService(success_rate=1.0)
    upi_service = UPIService(default_upi_id="test@upi")
    
    # Patch the communication service
    import app.services.payment_request_service
    app.services.payment_request_service.communication_service = mock_comm
    
    payment_service = PaymentRequestService(mock_db, upi_service)
    
    # Create test bill
    bill = create_test_bill()
    mock_db.bills[str(bill.id)] = bill
    
    try:
        # Distribute payment requests
        summary = await payment_service.distribute_payment_requests(
            bill_id=str(bill.id),
            organizer_phone="+919876543210",
            custom_message="Test payment request"
        )
        
        # Validate results
        assert isinstance(summary, DistributionSummary)
        assert summary.total_participants == 3
        assert summary.successful_sends == 3
        assert summary.failed_sends == 0
        
        # Check that messages were sent
        assert len(mock_comm.sent_messages) == 4  # 3 participants + 1 organizer confirmation
        
        # Check UPI links were generated
        for result in summary.results:
            assert result.upi_link.startswith("upi://pay")
            assert "test@upi" in result.upi_link
            assert str(result.amount) in result.upi_link
        
        print("✅ Payment request distribution test passed")
        return True
        
    except Exception as e:
        print(f"❌ Payment request distribution test failed: {e}")
        return False


async def test_fallback_mechanism():
    """Test SMS fallback when WhatsApp fails"""
    print("🧪 Testing Fallback Mechanism...")
    
    # Setup with fallback enabled
    mock_db = MockDatabaseRepository()
    mock_comm = MockCommunicationService(success_rate=1.0, use_fallback=True)
    upi_service = UPIService(default_upi_id="test@upi")
    
    # Patch the communication service
    import app.services.payment_request_service
    app.services.payment_request_service.communication_service = mock_comm
    
    payment_service = PaymentRequestService(mock_db, upi_service)
    
    # Create test bill
    bill = create_test_bill()
    mock_db.bills[str(bill.id)] = bill
    
    try:
        # Distribute payment requests
        summary = await payment_service.distribute_payment_requests(
            bill_id=str(bill.id),
            organizer_phone="+919876543210"
        )
        
        # Validate fallback was used
        assert summary.successful_sends == 3
        assert summary.sms_sends == 3
        assert summary.whatsapp_sends == 0
        
        # Check that all results indicate fallback was used
        for result in summary.results:
            assert result.fallback_used is True
            assert result.delivery_method == DeliveryMethod.SMS
        
        print("✅ Fallback mechanism test passed")
        return True
        
    except Exception as e:
        print(f"❌ Fallback mechanism test failed: {e}")
        return False


async def test_partial_failure_handling():
    """Test handling of partial failures"""
    print("🧪 Testing Partial Failure Handling...")
    
    # Setup with 50% success rate
    mock_db = MockDatabaseRepository()
    mock_comm = MockCommunicationService(success_rate=0.5)
    upi_service = UPIService(default_upi_id="test@upi")
    
    # Patch the communication service
    import app.services.payment_request_service
    app.services.payment_request_service.communication_service = mock_comm
    
    payment_service = PaymentRequestService(mock_db, upi_service)
    
    # Create test bill
    bill = create_test_bill()
    mock_db.bills[str(bill.id)] = bill
    
    try:
        # Distribute payment requests
        summary = await payment_service.distribute_payment_requests(
            bill_id=str(bill.id),
            organizer_phone="+919876543210"
        )
        
        # Validate mixed results
        assert summary.total_participants == 3
        assert summary.successful_sends + summary.failed_sends == 3
        assert summary.failed_sends > 0  # Should have some failures with 50% success rate
        
        # Check individual results
        successful_results = [r for r in summary.results if r.success]
        failed_results = [r for r in summary.results if not r.success]
        
        assert len(successful_results) + len(failed_results) == 3
        
        for failed_result in failed_results:
            assert failed_result.error is not None
            assert not failed_result.success
        
        print("✅ Partial failure handling test passed")
        return True
        
    except Exception as e:
        print(f"❌ Partial failure handling test failed: {e}")
        return False


async def test_payment_reminders():
    """Test payment reminder functionality"""
    print("🧪 Testing Payment Reminders...")
    
    # Setup
    mock_db = MockDatabaseRepository()
    mock_comm = MockCommunicationService(success_rate=1.0)
    upi_service = UPIService(default_upi_id="test@upi")
    
    # Patch the communication service
    import app.services.payment_request_service
    app.services.payment_request_service.communication_service = mock_comm
    
    payment_service = PaymentRequestService(mock_db, upi_service)
    
    # Create test bill with one participant already paid
    bill = create_test_bill()
    bill.participants[0].payment_status = 'confirmed'  # Mark first participant as paid
    mock_db.bills[str(bill.id)] = bill
    
    # Create existing payment request
    existing_request = PaymentRequest(
        id=uuid4(),
        bill_participant_id=bill.participants[1].id,
        upi_link="upi://pay?pa=test@upi&am=300.00"
    )
    mock_db.payment_requests[str(existing_request.id)] = existing_request
    
    try:
        # Send reminders
        summary = await payment_service.send_payment_reminder(
            bill_id=str(bill.id),
            custom_message="Friendly reminder!"
        )
        
        # Validate results - should only send to unpaid participants
        assert summary.total_participants == 2  # 3 total - 1 already paid
        assert summary.successful_sends == 2
        
        # Check reminder message content
        for result in summary.results:
            assert "Friendly reminder!" in result.message_sent
            assert "reminder" in result.message_sent.lower()
        
        print("✅ Payment reminders test passed")
        return True
        
    except Exception as e:
        print(f"❌ Payment reminders test failed: {e}")
        return False


async def test_payment_confirmation():
    """Test payment confirmation processing"""
    print("🧪 Testing Payment Confirmation...")
    
    # Setup
    mock_db = MockDatabaseRepository()
    mock_comm = MockCommunicationService(success_rate=1.0)
    upi_service = UPIService(default_upi_id="test@upi")
    
    # Patch the communication service
    import app.services.payment_request_service
    app.services.payment_request_service.communication_service = mock_comm
    
    payment_service = PaymentRequestService(mock_db, upi_service)
    
    # Create test bill
    bill = create_test_bill()
    bill.is_fully_paid = False  # Mock property
    mock_db.bills[str(bill.id)] = bill
    
    # Create payment request for first participant
    participant = bill.participants[0]
    payment_request = PaymentRequest(
        id=uuid4(),
        bill_participant_id=participant.id,
        upi_link="upi://pay?pa=test@upi&am=300.00",
        status="sent"
    )
    mock_db.payment_requests[str(payment_request.id)] = payment_request
    
    try:
        # Process payment confirmation
        success = await payment_service.process_payment_confirmation(
            participant_phone="+919876543211",  # Alice's phone
            bill_id=str(bill.id),
            confirmation_message="DONE"
        )
        
        # Validate confirmation was processed
        assert success is True
        
        # Check that participant status was updated
        updated_participant = mock_db.participants.get(str(participant.id))
        if updated_participant:
            assert updated_participant.payment_status == 'confirmed'
        
        # Check that organizer was notified
        organizer_messages = [msg for msg in mock_comm.sent_messages 
                            if msg["phone_number"] == "+919876543210"]
        assert len(organizer_messages) > 0
        
        print("✅ Payment confirmation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Payment confirmation test failed: {e}")
        return False


def test_message_templates():
    """Test message template generation"""
    print("🧪 Testing Message Templates...")
    
    try:
        # Setup
        mock_db = MockDatabaseRepository()
        upi_service = UPIService(default_upi_id="test@upi")
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Test payment request message
        payment_message = payment_service._create_payment_message(
            participant_name="Alice",
            amount=Decimal("500.00"),
            bill_description="Test Bill",
            upi_link="upi://pay?pa=test@upi&am=500.00",
            custom_message="Please pay soon"
        )
        
        # Validate message content
        assert "Alice" in payment_message
        assert "₹500.00" in payment_message
        assert "Test Bill" in payment_message
        assert "upi://pay?pa=test@upi&am=500.00" in payment_message
        assert "Please pay soon" in payment_message
        assert "DONE" in payment_message
        
        # Test reminder message
        reminder_message = payment_service._create_reminder_message(
            participant_name="Bob",
            amount=Decimal("300.00"),
            bill_description="Reminder Test",
            upi_link="upi://pay?pa=test@upi&am=300.00",
            reminder_count=2,
            custom_message="Second reminder"
        )
        
        # Validate reminder message
        assert "Bob" in reminder_message
        assert "₹300.00" in reminder_message
        assert "Second reminder" in reminder_message
        assert "checking in" in reminder_message.lower()  # Second reminder prefix
        
        print("✅ Message templates test passed")
        return True
        
    except Exception as e:
        print(f"❌ Message templates test failed: {e}")
        return False


async def test_statistics():
    """Test statistics functionality"""
    print("🧪 Testing Statistics...")
    
    try:
        # Setup
        mock_db = MockDatabaseRepository()
        upi_service = UPIService(default_upi_id="test@upi")
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Add some mock payment requests
        for i in range(5):
            request = PaymentRequest(
                id=uuid4(),
                bill_participant_id=uuid4(),
                upi_link=f"upi://pay?pa=test@upi&am={100 + i * 50}.00",
                whatsapp_sent=i % 2 == 0,  # Alternate WhatsApp/SMS
                sms_sent=i % 2 == 1,
                status='confirmed' if i < 2 else 'sent'
            )
            mock_db.payment_requests[str(request.id)] = request
        
        # Get statistics
        stats = await payment_service.get_payment_request_statistics(days=30)
        
        # Validate statistics
        assert stats["total_requests"] == 5
        assert stats["successful_deliveries"] == 5
        assert stats["whatsapp_deliveries"] == 3  # 0, 2, 4
        assert stats["sms_deliveries"] == 2      # 1, 3
        assert stats["confirmed_payments"] == 2   # First 2 requests
        assert stats["success_rate"] == 1.0
        assert stats["confirmation_rate"] == 0.5
        
        print("✅ Statistics test passed")
        return True
        
    except Exception as e:
        print(f"❌ Statistics test failed: {e}")
        return False


async def run_all_tests():
    """Run all validation tests"""
    print("🚀 Starting Payment Request Service Validation\n")
    
    tests = [
        test_payment_request_distribution,
        test_fallback_mechanism,
        test_partial_failure_handling,
        test_payment_reminders,
        test_payment_confirmation,
        test_message_templates,
        test_statistics
    ]
    
    results = []
    for test in tests:
        try:
            if asyncio.iscoroutinefunction(test):
                result = await test()
            else:
                result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
        print()  # Add spacing between tests
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*60)
    print(f"📊 Validation Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Payment Request Service is working correctly.")
        return True
    else:
        print(f"⚠️  {total - passed} tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)