#!/usr/bin/env python3
"""
UPI Service Validation Script

This script validates the UPI service implementation by running
comprehensive tests and examples.
"""
import sys
import traceback
from decimal import Decimal
from app.services.upi_service import UPIService, UPIApp, UPIValidationError


def test_basic_functionality():
    """Test basic UPI service functionality"""
    print("🔧 Testing Basic Functionality")
    print("-" * 50)
    
    try:
        # Initialize service
        service = UPIService(default_upi_id="test@upi")
        print("✅ UPI Service initialized successfully")
        
        # Test basic link generation
        link = service.generate_upi_link(
            recipient_name="Test User",
            amount=Decimal("100"),
            description="Test payment"
        )
        print(f"✅ Basic UPI link generated: {link[:50]}...")
        
        # Test validation
        is_valid, error = service.validate_upi_link(link)
        if is_valid:
            print("✅ Generated link passes validation")
        else:
            print(f"❌ Generated link failed validation: {error}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        traceback.print_exc()
        return False


def test_all_upi_apps():
    """Test UPI link generation for all supported apps"""
    print("\n📱 Testing All UPI Apps")
    print("-" * 50)
    
    try:
        service = UPIService()
        success_count = 0
        
        for app in UPIApp:
            try:
                link = service.generate_upi_link(
                    recipient_name="Test User",
                    amount=Decimal("150"),
                    description="App test",
                    upi_app=app
                )
                app_name = service.get_app_display_name(app)
                print(f"✅ {app_name}: {link[:60]}...")
                success_count += 1
                
            except Exception as e:
                print(f"❌ {app.value} failed: {e}")
        
        print(f"\n📊 Successfully generated links for {success_count}/{len(UPIApp)} apps")
        return success_count == len(UPIApp)
        
    except Exception as e:
        print(f"❌ UPI apps test failed: {e}")
        return False


def test_validation_functions():
    """Test validation functions"""
    print("\n🔍 Testing Validation Functions")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        # Test UPI ID validation
        valid_upi_ids = ["user@paytm", "9876543210@ybl", "test.user@okaxis"]
        invalid_upi_ids = ["user", "@paytm", "user@", "invalid_format"]
        
        print("UPI ID Validation:")
        for upi_id in valid_upi_ids:
            if service.validate_upi_id(upi_id):
                print(f"  ✅ {upi_id} (valid)")
            else:
                print(f"  ❌ {upi_id} (should be valid)")
                return False
        
        for upi_id in invalid_upi_ids:
            if not service.validate_upi_id(upi_id):
                print(f"  ✅ {upi_id} (correctly identified as invalid)")
            else:
                print(f"  ❌ {upi_id} (should be invalid)")
                return False
        
        # Test amount validation
        valid_amounts = [Decimal("1"), Decimal("100.50"), Decimal("100000")]
        invalid_amounts = [Decimal("0"), Decimal("-1"), Decimal("100001")]
        
        print("\nAmount Validation:")
        for amount in valid_amounts:
            if service.validate_amount(amount):
                print(f"  ✅ ₹{amount} (valid)")
            else:
                print(f"  ❌ ₹{amount} (should be valid)")
                return False
        
        for amount in invalid_amounts:
            if not service.validate_amount(amount):
                print(f"  ✅ ₹{amount} (correctly identified as invalid)")
            else:
                print(f"  ❌ ₹{amount} (should be invalid)")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False


def test_error_handling():
    """Test error handling"""
    print("\n⚠️  Testing Error Handling")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        # Test invalid amount error
        try:
            service.generate_upi_link(
                recipient_name="Test",
                amount=Decimal("0"),
                description="Invalid"
            )
            print("❌ Should have raised error for invalid amount")
            return False
        except UPIValidationError:
            print("✅ Correctly raised error for invalid amount")
        
        # Test invalid UPI ID error
        try:
            service.generate_upi_link(
                recipient_name="Test",
                amount=Decimal("100"),
                description="Test",
                payee_upi_id="invalid"
            )
            print("❌ Should have raised error for invalid UPI ID")
            return False
        except UPIValidationError:
            print("✅ Correctly raised error for invalid UPI ID")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def test_link_validation():
    """Test UPI link validation"""
    print("\n🔗 Testing UPI Link Validation")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        # Valid links
        valid_links = [
            "upi://pay?pa=test@upi&am=100&cu=INR&tn=Test",
            "gpay://upi/pay?pa=user@paytm&am=250.50&pn=Test",
            "phonepe://pay?pa=9876543210@ybl&am=75"
        ]
        
        # Invalid links
        invalid_links = [
            "http://example.com",
            "upi://pay?am=100",  # Missing payee
            "upi://pay?pa=test@upi",  # Missing amount
            "upi://pay?pa=invalid&am=100"  # Invalid UPI ID
        ]
        
        print("Valid Links:")
        for link in valid_links:
            is_valid, error = service.validate_upi_link(link)
            if is_valid:
                print(f"  ✅ {link[:50]}...")
            else:
                print(f"  ❌ {link[:50]}... (should be valid): {error}")
                return False
        
        print("\nInvalid Links:")
        for link in invalid_links:
            is_valid, error = service.validate_upi_link(link)
            if not is_valid:
                print(f"  ✅ {link[:50]}... (correctly invalid)")
            else:
                print(f"  ❌ {link[:50]}... (should be invalid)")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Link validation test failed: {e}")
        return False


def test_payment_info_extraction():
    """Test payment information extraction"""
    print("\n📊 Testing Payment Info Extraction")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        test_link = "upi://pay?pa=test@upi&am=250.50&cu=INR&pn=Bill%20Splitter&tn=Dinner"
        info = service.extract_payment_info(test_link)
        
        if info:
            expected_fields = ['payee_address', 'amount', 'currency', 'payee_name', 'transaction_note']
            for field in expected_fields:
                if field in info:
                    print(f"  ✅ {field}: {info[field]}")
                else:
                    print(f"  ❌ Missing field: {field}")
                    return False
            
            # Verify specific values
            if info['payee_address'] == 'test@upi' and info['amount'] == '250.50':
                print("✅ Extracted values are correct")
                return True
            else:
                print("❌ Extracted values are incorrect")
                return False
        else:
            print("❌ Failed to extract payment info")
            return False
        
    except Exception as e:
        print(f"❌ Payment info extraction test failed: {e}")
        return False


def test_message_creation():
    """Test payment message creation"""
    print("\n💬 Testing Message Creation")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        message = service.create_payment_message(
            recipient_name="John Doe",
            amount=Decimal("150.75"),
            description="Lunch bill",
            upi_link="upi://pay?pa=test@upi&am=150.75"
        )
        
        # Check if message contains required elements
        required_elements = ["John Doe", "₹150.75", "Lunch bill", "upi://pay", "DONE"]
        
        for element in required_elements:
            if element in message:
                print(f"  ✅ Contains: {element}")
            else:
                print(f"  ❌ Missing: {element}")
                return False
        
        print(f"\n📝 Generated message preview:")
        print(message[:200] + "..." if len(message) > 200 else message)
        
        return True
        
    except Exception as e:
        print(f"❌ Message creation test failed: {e}")
        return False


def test_multiple_app_links():
    """Test multiple app link generation"""
    print("\n🔄 Testing Multiple App Links")
    print("-" * 50)
    
    try:
        service = UPIService()
        
        links = service.generate_multiple_app_links(
            recipient_name="Multi User",
            amount=Decimal("200"),
            description="Multi test",
            apps=[UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE]
        )
        
        if len(links) == 3:
            print(f"✅ Generated {len(links)} links as expected")
            
            for app, link in links.items():
                app_name = service.get_app_display_name(app)
                print(f"  ✅ {app_name}: {link[:50]}...")
            
            return True
        else:
            print(f"❌ Expected 3 links, got {len(links)}")
            return False
        
    except Exception as e:
        print(f"❌ Multiple app links test failed: {e}")
        return False


def run_comprehensive_validation():
    """Run all validation tests"""
    print("🚀 UPI Service Comprehensive Validation")
    print("=" * 60)
    
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("All UPI Apps", test_all_upi_apps),
        ("Validation Functions", test_validation_functions),
        ("Error Handling", test_error_handling),
        ("Link Validation", test_link_validation),
        ("Payment Info Extraction", test_payment_info_extraction),
        ("Message Creation", test_message_creation),
        ("Multiple App Links", test_multiple_app_links)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 VALIDATION SUMMARY")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! UPI Service is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    try:
        success = run_comprehensive_validation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Validation script failed: {e}")
        traceback.print_exc()
        sys.exit(1)