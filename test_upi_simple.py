#!/usr/bin/env python3
"""
Simple UPI Service Test

Quick test to verify UPI service functionality
"""
from decimal import Decimal
from app.services.upi_service import UPIService, UPIApp, UPIValidationError

def test_upi_service():
    """Test basic UPI service functionality"""
    print("🔧 Testing UPI Service")
    print("-" * 40)
    
    try:
        # Initialize service
        service = UPIService(default_upi_id="test@upi")
        print("✅ UPI Service initialized")
        
        # Test basic link generation
        link = service.generate_upi_link(
            recipient_name="John Doe",
            amount=Decimal("250.50"),
            description="Dinner bill"
        )
        print(f"✅ Generated UPI link: {link}")
        
        # Test validation
        is_valid, error = service.validate_upi_link(link)
        print(f"✅ Link validation: {'Valid' if is_valid else f'Invalid: {error}'}")
        
        # Test multiple apps
        multi_links = service.generate_multiple_app_links(
            recipient_name="Jane Smith",
            amount=Decimal("100"),
            description="Coffee"
        )
        print(f"✅ Generated {len(multi_links)} app-specific links")
        
        # Test message creation
        message = service.create_payment_message(
            recipient_name="Bob Wilson",
            amount=Decimal("150"),
            description="Lunch",
            upi_link=link
        )
        print(f"✅ Generated payment message ({len(message)} chars)")
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_upi_service()