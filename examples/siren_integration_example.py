"""
Example demonstrating Siren AI Toolkit integration
"""
import asyncio
import json
from datetime import datetime
from app.services.siren_client import SirenClient, SirenWebhookPayload
from app.services.communication_service import CommunicationService
from app.models.enums import MessageType


async def example_send_messages():
    """Example of sending messages through Siren"""
    print("=== Siren Integration Example ===\n")
    
    # Initialize communication service
    comm_service = CommunicationService()
    
    # Example 1: Send WhatsApp message
    print("1. Sending WhatsApp message...")
    try:
        result = await comm_service.send_whatsapp_message(
            phone_number="+919876543210",
            message="Hello! This is a test message from the Bill Splitting Agent."
        )
        print(f"   WhatsApp result: {'Success' if result else 'Failed'}")
    except Exception as e:
        print(f"   WhatsApp error: {e}")
    
    # Example 2: Send SMS message
    print("\n2. Sending SMS message...")
    try:
        result = await comm_service.send_sms(
            phone_number="+919876543210",
            message="Hello! This is a test SMS from the Bill Splitting Agent."
        )
        print(f"   SMS result: {'Success' if result else 'Failed'}")
    except Exception as e:
        print(f"   SMS error: {e}")
    
    # Example 3: Send message with fallback
    print("\n3. Sending message with WhatsApp/SMS fallback...")
    try:
        result = await comm_service.send_message_with_fallback(
            phone_number="+919876543210",
            message="This message will try WhatsApp first, then SMS if needed."
        )
        print(f"   Fallback result: {json.dumps(result, indent=2, default=str)}")
    except Exception as e:
        print(f"   Fallback error: {e}")
    
    # Example 4: Send bulk messages
    print("\n4. Sending bulk messages...")
    messages = [
        {
            "phone_number": "+919876543210",
            "message": "Your share for dinner: ₹250. Pay here: upi://pay?pa=test@upi"
        },
        {
            "phone_number": "+918765432109",
            "message": "Your share for dinner: ₹300. Pay here: upi://pay?pa=test@upi"
        }
    ]
    
    try:
        results = await comm_service.send_bulk_messages(messages)
        print("   Bulk message results:")
        for result in results:
            print(f"     {result['phone_number']}: {'Success' if result['success'] else 'Failed'}")
    except Exception as e:
        print(f"   Bulk message error: {e}")
    
    # Example 5: Get delivery statistics
    print("\n5. Delivery statistics:")
    try:
        stats = await comm_service.get_delivery_statistics()
        print(f"   Total attempts: {stats['total_attempts']}")
        print(f"   Success rate: {stats['success_rate']:.2%}")
        print(f"   WhatsApp attempts: {stats['whatsapp_attempts']}")
        print(f"   SMS attempts: {stats['sms_attempts']}")
    except Exception as e:
        print(f"   Statistics error: {e}")
    
    # Close the service
    await comm_service.close()


def example_webhook_processing():
    """Example of processing webhook payloads"""
    print("\n=== Webhook Processing Example ===\n")
    
    # Example webhook payload from Siren
    webhook_data = {
        "message_id": "msg_12345",
        "from_number": "+919876543210",
        "to_number": "+918765432109",
        "content": "Split bill for dinner ₹1200 among 4 people",
        "message_type": "text",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "source": "whatsapp",
            "conversation_id": "conv_67890"
        }
    }
    
    print("1. Processing incoming webhook payload:")
    print(f"   Raw payload: {json.dumps(webhook_data, indent=2, default=str)}")
    
    # Create webhook payload object
    try:
        payload = SirenWebhookPayload(**webhook_data)
        print(f"   Parsed successfully!")
        print(f"   Message ID: {payload.message_id}")
        print(f"   From: {payload.from_number}")
        print(f"   Content: {payload.content}")
        print(f"   Type: {payload.message_type}")
    except Exception as e:
        print(f"   Parsing error: {e}")
    
    # Example signature validation
    print("\n2. Webhook signature validation:")
    client = SirenClient()
    
    # Simulate webhook payload and signature
    payload_bytes = json.dumps(webhook_data).encode()
    
    # This would normally come from the webhook header
    import hmac
    import hashlib
    test_secret = "test-webhook-secret"
    expected_signature = hmac.new(
        test_secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Test validation (this will fail with real settings, but shows the process)
    try:
        is_valid = client.validate_webhook_signature(payload_bytes, expected_signature)
        print(f"   Signature validation: {'Valid' if is_valid else 'Invalid'}")
    except Exception as e:
        print(f"   Validation error: {e}")


def example_phone_number_formatting():
    """Example of phone number formatting"""
    print("\n=== Phone Number Formatting Example ===\n")
    
    client = SirenClient()
    
    test_numbers = [
        "9876543210",           # Indian number without country code
        "919876543210",         # Indian number with country code
        "+919876543210",        # Indian number with + prefix
        "98-765-43210",         # Number with dashes
        "+1 234 567 8900",      # US number with spaces
        "1234567890"            # Generic number
    ]
    
    print("Phone number formatting examples:")
    for number in test_numbers:
        try:
            formatted = client._format_phone_number(number)
            print(f"   {number:15} -> {formatted}")
        except Exception as e:
            print(f"   {number:15} -> Error: {e}")


async def main():
    """Run all examples"""
    print("Bill Splitting Agent - Siren Integration Examples")
    print("=" * 50)
    
    # Note: These examples will fail without proper Siren API credentials
    # They demonstrate the integration structure and error handling
    
    try:
        await example_send_messages()
    except Exception as e:
        print(f"Message sending examples failed: {e}")
    
    example_webhook_processing()
    example_phone_number_formatting()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nNote: To run these examples with real Siren integration:")
    print("1. Set up proper API credentials in .env file")
    print("2. Configure webhook endpoints")
    print("3. Test with actual phone numbers")


if __name__ == "__main__":
    asyncio.run(main())