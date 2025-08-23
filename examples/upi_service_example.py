"""
UPI Service Usage Examples

This example demonstrates how to use the UPI service for generating
payment links and handling various UPI-related operations.
"""
import asyncio
from decimal import Decimal
from app.services.upi_service import UPIService, UPIApp, UPIValidationError


async def main():
    """Main example function"""
    print("🔗 UPI Service Examples\n")
    
    # Initialize UPI service with custom UPI ID
    upi_service = UPIService(default_upi_id="billsplitter@paytm")
    
    # Example 1: Generate a basic UPI link
    print("1. Basic UPI Link Generation")
    print("-" * 40)
    
    try:
        link = upi_service.generate_upi_link(
            recipient_name="John Doe",
            amount=Decimal("250.50"),
            description="Dinner at Pizza Palace"
        )
        print(f"Generated UPI Link: {link}")
        print()
    except UPIValidationError as e:
        print(f"Error: {e}")
    
    # Example 2: Generate links for specific UPI apps
    print("2. App-Specific UPI Links")
    print("-" * 40)
    
    apps_to_test = [UPIApp.GPAY, UPIApp.PHONEPE, UPIApp.PAYTM, UPIApp.BHIM]
    
    for app in apps_to_test:
        try:
            link = upi_service.generate_upi_link(
                recipient_name="Jane Smith",
                amount=Decimal("150"),
                description="Coffee meetup",
                upi_app=app
            )
            app_name = upi_service.get_app_display_name(app)
            print(f"{app_name}: {link}")
        except UPIValidationError as e:
            print(f"{app.value} Error: {e}")
    print()
    
    # Example 3: Generate multiple app links at once
    print("3. Multiple App Links")
    print("-" * 40)
    
    multi_links = upi_service.generate_multiple_app_links(
        recipient_name="Bob Wilson",
        amount=Decimal("300"),
        description="Movie tickets",
        apps=[UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE]
    )
    
    for app, link in multi_links.items():
        app_name = upi_service.get_app_display_name(app)
        print(f"{app_name}: {link}")
    print()
    
    # Example 4: Validate UPI links
    print("4. UPI Link Validation")
    print("-" * 40)
    
    test_links = [
        "upi://pay?pa=test@upi&am=100&cu=INR&tn=Test",
        "gpay://upi/pay?pa=user@paytm&am=250.50&pn=Test",
        "invalid://link",
        "upi://pay?am=100",  # Missing payee address
    ]
    
    for link in test_links:
        is_valid, error = upi_service.validate_upi_link(link)
        status = "✅ Valid" if is_valid else f"❌ Invalid: {error}"
        print(f"{link[:50]}... -> {status}")
    print()
    
    # Example 5: Extract payment information
    print("5. Extract Payment Information")
    print("-" * 40)
    
    sample_link = "upi://pay?pa=merchant@upi&am=500&cu=INR&pn=Restaurant&tn=Lunch%20bill"
    payment_info = upi_service.extract_payment_info(sample_link)
    
    if payment_info:
        print("Extracted Information:")
        for key, value in payment_info.items():
            print(f"  {key}: {value}")
    else:
        print("Failed to extract payment information")
    print()
    
    # Example 6: Create payment messages
    print("6. Payment Message Creation")
    print("-" * 40)
    
    message = upi_service.create_payment_message(
        recipient_name="Alice Brown",
        amount=Decimal("175.75"),
        description="Grocery shopping",
        upi_link="upi://pay?pa=store@upi&am=175.75"
    )
    
    print("Generated Payment Message:")
    print(message)
    print()
    
    # Example 7: Error handling
    print("7. Error Handling Examples")
    print("-" * 40)
    
    error_cases = [
        {
            "name": "Invalid Amount",
            "params": {
                "recipient_name": "Test User",
                "amount": Decimal("0"),
                "description": "Invalid payment"
            }
        },
        {
            "name": "Invalid UPI ID",
            "params": {
                "recipient_name": "Test User",
                "amount": Decimal("100"),
                "description": "Test payment",
                "payee_upi_id": "invalid_upi"
            }
        },
        {
            "name": "Amount Too Large",
            "params": {
                "recipient_name": "Test User",
                "amount": Decimal("200000"),
                "description": "Large payment"
            }
        }
    ]
    
    for case in error_cases:
        try:
            link = upi_service.generate_upi_link(**case["params"])
            print(f"{case['name']}: Unexpected success - {link}")
        except UPIValidationError as e:
            print(f"{case['name']}: ❌ {e}")
    print()
    
    # Example 8: Validation methods
    print("8. Individual Validation Methods")
    print("-" * 40)
    
    # Test UPI ID validation
    test_upi_ids = ["user@paytm", "9876543210@ybl", "invalid", "@bank", "user@"]
    print("UPI ID Validation:")
    for upi_id in test_upi_ids:
        is_valid = upi_service.validate_upi_id(upi_id)
        status = "✅" if is_valid else "❌"
        print(f"  {upi_id}: {status}")
    
    # Test amount validation
    test_amounts = [Decimal("1"), Decimal("0"), Decimal("100000"), Decimal("100001")]
    print("\nAmount Validation:")
    for amount in test_amounts:
        is_valid = upi_service.validate_amount(amount)
        status = "✅" if is_valid else "❌"
        print(f"  ₹{amount}: {status}")
    
    # Test text sanitization
    test_texts = [
        "Normal text",
        "Text with @#$% symbols",
        "Very long text that exceeds the character limit for UPI parameters",
        "Text\nwith\nnewlines"
    ]
    print("\nText Sanitization:")
    for text in test_texts:
        sanitized = upi_service.sanitize_text(text)
        print(f"  '{text}' -> '{sanitized}'")
    print()
    
    # Example 9: Supported apps information
    print("9. Supported Apps Information")
    print("-" * 40)
    
    supported_apps = upi_service.get_supported_apps()
    print("Supported UPI Apps:")
    for app_code in supported_apps:
        app_enum = UPIApp(app_code)
        display_name = upi_service.get_app_display_name(app_enum)
        print(f"  {app_code} -> {display_name}")
    print()
    
    # Example 10: Real-world scenario
    print("10. Real-world Bill Splitting Scenario")
    print("-" * 40)
    
    # Simulate a bill splitting scenario
    bill_description = "Dinner at Italian Restaurant"
    participants = [
        {"name": "Alice", "amount": Decimal("450")},
        {"name": "Bob", "amount": Decimal("380")},
        {"name": "Charlie", "amount": Decimal("420")},
        {"name": "Diana", "amount": Decimal("350")}
    ]
    
    print(f"Bill: {bill_description}")
    print("Payment links for participants:")
    
    for participant in participants:
        # Generate generic UPI link
        link = upi_service.generate_upi_link(
            recipient_name=participant["name"],
            amount=participant["amount"],
            description=bill_description
        )
        
        # Create payment message
        message = upi_service.create_payment_message(
            recipient_name=participant["name"],
            amount=participant["amount"],
            description=bill_description,
            upi_link=link
        )
        
        print(f"\n{participant['name']} (₹{participant['amount']}):")
        print(f"UPI Link: {link}")
        print("Message preview:")
        print(message[:100] + "..." if len(message) > 100 else message)
    
    print("\n✅ UPI Service examples completed!")


if __name__ == "__main__":
    asyncio.run(main())