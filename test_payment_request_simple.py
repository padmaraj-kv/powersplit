#!/usr/bin/env python3
"""
Simple Payment Request Service Integration Test

This script performs a basic integration test of the payment request service
to verify it works with the existing codebase.
"""
import sys
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, patch

# Add the app directory to the path
sys.path.append('.')

try:
    from app.services.payment_request_service import PaymentRequestService
    from app.services.upi_service import UPIService
    from app.models.database import Bill, BillParticipant, Contact, User, PaymentRequest
    from app.models.enums import DeliveryMethod
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_service_initialization():
    """Test that the payment request service can be initialized"""
    try:
        # Create mock dependencies
        mock_db = Mock()
        upi_service = UPIService(default_upi_id="test@upi")
        
        # Initialize service
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Check that service has required attributes
        assert hasattr(payment_service, 'db')
        assert hasattr(payment_service, 'upi_service')
        assert hasattr(payment_service, 'communication')
        assert hasattr(payment_service, 'templates')
        
        print("✅ Service initialization test passed")
        return True
        
    except Exception as e:
        print(f"❌ Service initialization test failed: {e}")
        return False


def test_message_template_creation():
    """Test message template creation"""
    try:
        mock_db = Mock()
        upi_service = UPIService(default_upi_id="test@upi")
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Test payment message creation
        message = payment_service._create_payment_message(
            participant_name="Alice",
            amount=Decimal("500.00"),
            bill_description="Test Bill",
            upi_link="upi://pay?pa=test@upi&am=500.00",
            custom_message="Please pay soon"
        )
        
        # Verify message content
        assert "Alice" in message
        assert "₹500.00" in message
        assert "Test Bill" in message
        assert "upi://pay?pa=test@upi&am=500.00" in message
        assert "Please pay soon" in message
        assert "DONE" in message
        
        print("✅ Message template creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Message template creation test failed: {e}")
        return False


def test_upi_link_integration():
    """Test UPI service integration"""
    try:
        mock_db = Mock()
        upi_service = UPIService(default_upi_id="billsplitter@upi")
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Test UPI link generation through the service
        upi_link = upi_service.generate_upi_link(
            recipient_name="Test User",
            amount=Decimal("250.00"),
            description="Test Payment"
        )
        
        # Verify UPI link format
        assert upi_link.startswith("upi://pay")
        assert "billsplitter@upi" in upi_link
        assert "250.00" in upi_link
        
        print("✅ UPI link integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ UPI link integration test failed: {e}")
        return False


def test_data_model_creation():
    """Test that data models can be created correctly"""
    try:
        # Create test user
        user = User(
            id=uuid4(),
            phone_number="+919876543210",
            name="Test User"
        )
        
        # Create test bill
        bill = Bill(
            id=uuid4(),
            user_id=user.id,
            user=user,
            total_amount=Decimal("600.00"),
            description="Test Bill",
            status="active"
        )
        
        # Create test contact
        contact = Contact(
            id=uuid4(),
            user_id=user.id,
            name="Test Participant",
            phone_number="+919876543211"
        )
        
        # Create test participant
        participant = BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contact.id,
            contact=contact,
            amount_owed=Decimal("300.00"),
            payment_status="pending"
        )
        
        # Create test payment request
        payment_request = PaymentRequest(
            id=uuid4(),
            bill_participant_id=participant.id,
            upi_link="upi://pay?pa=test@upi&am=300.00",
            status="pending"
        )
        
        # Verify all models were created successfully
        assert user.id is not None
        assert bill.total_amount == Decimal("600.00")
        assert contact.name == "Test Participant"
        assert participant.amount_owed == Decimal("300.00")
        assert payment_request.upi_link.startswith("upi://pay")
        
        print("✅ Data model creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Data model creation test failed: {e}")
        return False


def test_enum_usage():
    """Test that enums are working correctly"""
    try:
        # Test DeliveryMethod enum
        whatsapp_method = DeliveryMethod.WHATSAPP
        sms_method = DeliveryMethod.SMS
        
        assert whatsapp_method.value == "whatsapp"
        assert sms_method.value == "sms"
        
        # Test that enums can be compared
        assert whatsapp_method != sms_method
        assert whatsapp_method == DeliveryMethod.WHATSAPP
        
        print("✅ Enum usage test passed")
        return True
        
    except Exception as e:
        print(f"❌ Enum usage test failed: {e}")
        return False


def test_service_methods_exist():
    """Test that all required service methods exist"""
    try:
        mock_db = Mock()
        upi_service = UPIService(default_upi_id="test@upi")
        payment_service = PaymentRequestService(mock_db, upi_service)
        
        # Check that all required methods exist
        required_methods = [
            'distribute_payment_requests',
            'send_payment_reminder',
            'process_payment_confirmation',
            'get_payment_request_statistics',
            '_create_payment_message',
            '_create_reminder_message',
            '_create_organizer_confirmation_message'
        ]
        
        for method_name in required_methods:
            assert hasattr(payment_service, method_name), f"Missing method: {method_name}"
            method = getattr(payment_service, method_name)
            assert callable(method), f"Method {method_name} is not callable"
        
        print("✅ Service methods existence test passed")
        return True
        
    except Exception as e:
        print(f"❌ Service methods existence test failed: {e}")
        return False


def run_simple_tests():
    """Run all simple integration tests"""
    print("🚀 Running Payment Request Service Simple Tests\n")
    
    tests = [
        test_service_initialization,
        test_message_template_creation,
        test_upi_link_integration,
        test_data_model_creation,
        test_enum_usage,
        test_service_methods_exist
    ]
    
    results = []
    for test in tests:
        try:
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
    print(f"📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All simple tests passed! Payment Request Service basic functionality is working.")
        return True
    else:
        print(f"⚠️  {total - passed} tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = run_simple_tests()
    
    if success:
        print("\n✅ Payment Request Service is ready for use!")
        print("\nNext steps:")
        print("1. Set up database connection")
        print("2. Configure Siren API credentials")
        print("3. Test with real WhatsApp/SMS delivery")
        print("4. Run full integration tests")
    else:
        print("\n❌ Please fix the issues before proceeding.")
    
    sys.exit(0 if success else 1)