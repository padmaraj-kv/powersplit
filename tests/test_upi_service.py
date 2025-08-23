"""
Tests for UPI Service

Tests the UPI payment link generation functionality including:
- Link generation for different UPI apps
- Validation of UPI links and parameters
- Error handling and edge cases
- Message formatting
"""
import pytest
from decimal import Decimal
from app.services.upi_service import UPIService, UPIApp, UPIValidationError


class TestUPIService:
    """Test cases for UPI Service"""
    
    @pytest.fixture
    def upi_service(self):
        """Create UPI service instance for testing"""
        return UPIService(default_upi_id="test@upi")
    
    def test_validate_upi_id_valid(self, upi_service):
        """Test UPI ID validation with valid IDs"""
        valid_ids = [
            "user@paytm",
            "9876543210@ybl",
            "test.user@okaxis",
            "user_name@icici",
            "user-123@hdfc"
        ]
        
        for upi_id in valid_ids:
            assert upi_service.validate_upi_id(upi_id), f"Should be valid: {upi_id}"
    
    def test_validate_upi_id_invalid(self, upi_service):
        """Test UPI ID validation with invalid IDs"""
        invalid_ids = [
            "user",  # Missing @
            "@paytm",  # Missing username
            "user@",  # Missing domain
            "user@paytm@extra",  # Multiple @
            "user with spaces@paytm",  # Spaces not allowed
            "",  # Empty string
            "user@paytm!",  # Invalid characters
        ]
        
        for upi_id in invalid_ids:
            assert not upi_service.validate_upi_id(upi_id), f"Should be invalid: {upi_id}"
    
    def test_validate_amount_valid(self, upi_service):
        """Test amount validation with valid amounts"""
        valid_amounts = [
            Decimal("1"),
            Decimal("100.50"),
            Decimal("1000"),
            Decimal("99999.99"),
            Decimal("100000")  # Max amount
        ]
        
        for amount in valid_amounts:
            assert upi_service.validate_amount(amount), f"Should be valid: {amount}"
    
    def test_validate_amount_invalid(self, upi_service):
        """Test amount validation with invalid amounts"""
        invalid_amounts = [
            Decimal("0"),
            Decimal("-1"),
            Decimal("100000.01"),  # Above max
            Decimal("-100")
        ]
        
        for amount in invalid_amounts:
            assert not upi_service.validate_amount(amount), f"Should be invalid: {amount}"
    
    def test_sanitize_text(self, upi_service):
        """Test text sanitization"""
        test_cases = [
            ("Normal text", "Normal text"),
            ("Text with @#$% symbols", "Text with  symbols"),
            ("Very long text that exceeds the fifty character limit for UPI", "Very long text that exceeds the fifty character"),
            ("Text with\nnewlines\tand\ttabs", "Text withnewlinesandtabs"),
            ("", ""),
            ("   Spaces   ", "Spaces")
        ]
        
        for input_text, expected in test_cases:
            result = upi_service.sanitize_text(input_text)
            assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    def test_generate_upi_link_generic(self, upi_service):
        """Test generic UPI link generation"""
        link = upi_service.generate_upi_link(
            recipient_name="John Doe",
            amount=Decimal("250.50"),
            description="Dinner bill split",
            upi_app=UPIApp.GENERIC
        )
        
        assert link.startswith("upi://pay?")
        assert "pa=test%40upi" in link
        assert "am=250.50" in link
        assert "cu=INR" in link
        assert "pn=Bill%20Splitter" in link
        assert "tn=Dinner%20bill%20split%20-%20John%20Doe" in link
    
    def test_generate_upi_link_gpay(self, upi_service):
        """Test Google Pay specific UPI link generation"""
        link = upi_service.generate_upi_link(
            recipient_name="Jane Smith",
            amount=Decimal("100"),
            description="Coffee",
            upi_app=UPIApp.GPAY
        )
        
        assert link.startswith("gpay://upi/pay?")
        assert "pa=test%40upi" in link
        assert "am=100" in link
        assert "tn=Coffee%20-%20Jane%20Smith" in link
    
    def test_generate_upi_link_phonepe(self, upi_service):
        """Test PhonePe specific UPI link generation"""
        link = upi_service.generate_upi_link(
            recipient_name="Bob Wilson",
            amount=Decimal("75.25"),
            description="Lunch",
            upi_app=UPIApp.PHONEPE
        )
        
        assert link.startswith("phonepe://pay?")
        assert "am=75.25" in link
    
    def test_generate_upi_link_paytm(self, upi_service):
        """Test Paytm specific UPI link generation"""
        link = upi_service.generate_upi_link(
            recipient_name="Alice Brown",
            amount=Decimal("200"),
            description="Movie tickets",
            upi_app=UPIApp.PAYTM
        )
        
        assert link.startswith("paytmmp://pay?")
        assert "am=200" in link
    
    def test_generate_upi_link_bhim(self, upi_service):
        """Test BHIM specific UPI link generation"""
        link = upi_service.generate_upi_link(
            recipient_name="Charlie Davis",
            amount=Decimal("150"),
            description="Groceries",
            upi_app=UPIApp.BHIM
        )
        
        assert link.startswith("bhim://pay?")
        assert "am=150" in link
    
    def test_generate_upi_link_custom_upi_id(self, upi_service):
        """Test UPI link generation with custom UPI ID"""
        link = upi_service.generate_upi_link(
            recipient_name="Test User",
            amount=Decimal("50"),
            description="Test payment",
            payee_upi_id="custom@bank"
        )
        
        assert "pa=custom%40bank" in link
    
    def test_generate_upi_link_invalid_amount(self, upi_service):
        """Test UPI link generation with invalid amount"""
        with pytest.raises(UPIValidationError, match="Invalid amount"):
            upi_service.generate_upi_link(
                recipient_name="Test User",
                amount=Decimal("0"),
                description="Invalid payment"
            )
    
    def test_generate_upi_link_invalid_upi_id(self, upi_service):
        """Test UPI link generation with invalid UPI ID"""
        with pytest.raises(UPIValidationError, match="Invalid UPI ID"):
            upi_service.generate_upi_link(
                recipient_name="Test User",
                amount=Decimal("100"),
                description="Test payment",
                payee_upi_id="invalid_upi_id"
            )
    
    def test_generate_multiple_app_links(self, upi_service):
        """Test generating links for multiple apps"""
        links = upi_service.generate_multiple_app_links(
            recipient_name="Multi User",
            amount=Decimal("300"),
            description="Multi app test",
            apps=[UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE]
        )
        
        assert len(links) == 3
        assert UPIApp.GENERIC in links
        assert UPIApp.GPAY in links
        assert UPIApp.PHONEPE in links
        
        assert links[UPIApp.GENERIC].startswith("upi://pay?")
        assert links[UPIApp.GPAY].startswith("gpay://upi/pay?")
        assert links[UPIApp.PHONEPE].startswith("phonepe://pay?")
    
    def test_generate_multiple_app_links_default(self, upi_service):
        """Test generating links for default apps"""
        links = upi_service.generate_multiple_app_links(
            recipient_name="Default User",
            amount=Decimal("100"),
            description="Default test"
        )
        
        # Should generate links for default apps
        assert len(links) >= 3  # At least generic, gpay, phonepe, paytm
        assert UPIApp.GENERIC in links
    
    def test_validate_upi_link_valid(self, upi_service):
        """Test UPI link validation with valid links"""
        valid_links = [
            "upi://pay?pa=test@upi&am=100&cu=INR&tn=Test",
            "gpay://upi/pay?pa=user@paytm&am=250.50&pn=Test&tn=Payment",
            "phonepe://pay?pa=9876543210@ybl&am=75&cu=INR",
            "paytmmp://pay?pa=test@okaxis&am=1000&tn=Bill%20payment"
        ]
        
        for link in valid_links:
            is_valid, error = upi_service.validate_upi_link(link)
            assert is_valid, f"Should be valid: {link}, Error: {error}"
    
    def test_validate_upi_link_invalid(self, upi_service):
        """Test UPI link validation with invalid links"""
        invalid_links = [
            "http://example.com",  # Wrong scheme
            "upi://pay?am=100",  # Missing payee address
            "upi://pay?pa=test@upi",  # Missing amount
            "upi://pay?pa=invalid&am=100",  # Invalid UPI ID
            "upi://pay?pa=test@upi&am=0",  # Invalid amount
            "upi://pay?pa=test@upi&am=abc",  # Non-numeric amount
            ""  # Empty string
        ]
        
        for link in invalid_links:
            is_valid, error = upi_service.validate_upi_link(link)
            assert not is_valid, f"Should be invalid: {link}"
            assert error is not None, f"Should have error message for: {link}"
    
    def test_extract_payment_info_valid(self, upi_service):
        """Test payment info extraction from valid UPI link"""
        link = "upi://pay?pa=test@upi&am=250.50&cu=INR&pn=Bill%20Splitter&tn=Dinner%20-%20John"
        
        info = upi_service.extract_payment_info(link)
        
        assert info is not None
        assert info['payee_address'] == 'test@upi'
        assert info['amount'] == '250.50'
        assert info['currency'] == 'INR'
        assert info['payee_name'] == 'Bill%20Splitter'
        assert info['transaction_note'] == 'Dinner%20-%20John'
    
    def test_extract_payment_info_invalid(self, upi_service):
        """Test payment info extraction from invalid UPI link"""
        invalid_link = "http://example.com"
        
        info = upi_service.extract_payment_info(invalid_link)
        
        assert info is None
    
    def test_create_payment_message(self, upi_service):
        """Test payment message creation"""
        message = upi_service.create_payment_message(
            recipient_name="John Doe",
            amount=Decimal("250.50"),
            description="Dinner bill split",
            upi_link="upi://pay?pa=test@upi&am=250.50"
        )
        
        assert "John Doe" in message
        assert "₹250.50" in message
        assert "Dinner bill split" in message
        assert "upi://pay?pa=test@upi&am=250.50" in message
        assert "DONE" in message
    
    def test_get_supported_apps(self, upi_service):
        """Test getting supported apps list"""
        apps = upi_service.get_supported_apps()
        
        assert "generic" in apps
        assert "gpay" in apps
        assert "phonepe" in apps
        assert "paytm" in apps
        assert "bhim" in apps
    
    def test_get_app_display_name(self, upi_service):
        """Test getting app display names"""
        display_names = {
            UPIApp.GPAY: "Google Pay",
            UPIApp.PHONEPE: "PhonePe",
            UPIApp.PAYTM: "Paytm",
            UPIApp.BHIM: "BHIM",
            UPIApp.GENERIC: "Any UPI App"
        }
        
        for app, expected_name in display_names.items():
            assert upi_service.get_app_display_name(app) == expected_name
    
    def test_edge_cases(self, upi_service):
        """Test edge cases and boundary conditions"""
        # Test with minimal valid amount
        link = upi_service.generate_upi_link(
            recipient_name="",
            amount=Decimal("0.01"),
            description="",
            upi_app=UPIApp.GENERIC
        )
        assert "am=0.01" in link
        
        # Test with maximum valid amount
        link = upi_service.generate_upi_link(
            recipient_name="Max User",
            amount=Decimal("100000"),
            description="Max payment"
        )
        assert "am=100000" in link
        
        # Test with special characters in description
        link = upi_service.generate_upi_link(
            recipient_name="Special User",
            amount=Decimal("100"),
            description="Payment with @#$% special chars!"
        )
        assert link is not None
        # Special characters should be sanitized
        assert "@#$%" not in link
    
    def test_concurrent_link_generation(self, upi_service):
        """Test that service can handle multiple concurrent requests"""
        import asyncio
        
        async def generate_link(i):
            return upi_service.generate_upi_link(
                recipient_name=f"User {i}",
                amount=Decimal(str(100 + i)),
                description=f"Payment {i}"
            )
        
        # This test doesn't use actual async, but tests that the service
        # doesn't maintain state between calls
        links = []
        for i in range(10):
            link = upi_service.generate_upi_link(
                recipient_name=f"User {i}",
                amount=Decimal(str(100 + i)),
                description=f"Payment {i}"
            )
            links.append(link)
        
        # All links should be different
        assert len(set(links)) == 10
        
        # Each link should contain the correct amount
        for i, link in enumerate(links):
            assert f"am={100 + i}" in link