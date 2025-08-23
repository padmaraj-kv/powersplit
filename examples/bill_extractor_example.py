#!/usr/bin/env python3
"""
Example usage of BillExtractor service
Demonstrates multi-modal bill extraction and processing
"""
import asyncio
import sys
from decimal import Decimal
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, '.')

from app.services.bill_extractor import BillExtractor, BillExtractionError
from app.models.schemas import BillData, BillItem, Message, ValidationResult
from app.models.enums import MessageType


async def example_text_extraction():
    """Example of extracting bill data from text message"""
    print("📝 TEXT EXTRACTION EXAMPLE")
    print("-" * 40)
    
    extractor = BillExtractor()
    
    # Create a text message with bill information
    text_message = Message(
        id="msg_001",
        user_id="user_123",
        content="Bill from Pizza Palace for ₹150. Had Margherita Pizza ₹120 and Coke ₹30",
        message_type=MessageType.TEXT,
        timestamp=datetime.now(),
        metadata={}
    )
    
    try:
        print(f"Input: {text_message.content}")
        
        # Extract bill data
        bill_data = await extractor.extract_bill_data(text_message)
        print(f"✅ Extracted amount: ₹{bill_data.total_amount}")
        print(f"✅ Description: {bill_data.description}")
        print(f"✅ Merchant: {bill_data.merchant}")
        print(f"✅ Items: {len(bill_data.items)} items")
        
        # Validate the data
        validation = await extractor.validate_bill_data(bill_data)
        print(f"✅ Validation: {'Valid' if validation.is_valid else 'Invalid'}")
        
        # Create summary
        summary = await extractor.create_bill_summary(bill_data)
        print("\n📋 Generated Summary:")
        print(summary)
        
    except BillExtractionError as e:
        print(f"❌ Extraction failed: {e}")


async def example_voice_extraction():
    """Example of extracting bill data from voice message"""
    print("\n🎤 VOICE EXTRACTION EXAMPLE")
    print("-" * 40)
    
    extractor = BillExtractor()
    
    # Create a voice message (with mock audio data)
    voice_message = Message(
        id="msg_002",
        user_id="user_123",
        content="",
        message_type=MessageType.VOICE,
        timestamp=datetime.now(),
        metadata={"audio_data": b"mock_audio_data_representing_speech"}
    )
    
    try:
        print("Input: Voice message with audio data")
        
        # This would normally process real audio data
        # For demo purposes, we'll show what would happen
        print("🔄 Processing voice message...")
        print("   1. Converting speech to text using Sarvam AI")
        print("   2. Extracting bill information from transcript")
        print("   3. Validating extracted data")
        
        # In a real scenario:
        # bill_data = await extractor.extract_bill_data(voice_message)
        
        print("✅ Voice extraction would process audio and return bill data")
        
    except BillExtractionError as e:
        print(f"❌ Voice extraction failed: {e}")


async def example_image_extraction():
    """Example of extracting bill data from image message"""
    print("\n📸 IMAGE EXTRACTION EXAMPLE")
    print("-" * 40)
    
    extractor = BillExtractor()
    
    # Create an image message (with mock image data)
    image_message = Message(
        id="msg_003",
        user_id="user_123",
        content="",
        message_type=MessageType.IMAGE,
        timestamp=datetime.now(),
        metadata={"image_data": b"mock_image_data_representing_bill_photo"}
    )
    
    try:
        print("Input: Image message with bill photo")
        
        # This would normally process real image data
        print("🔄 Processing image message...")
        print("   1. Validating image quality")
        print("   2. Extracting text and amounts using Gemini Vision")
        print("   3. Structuring data into bill format")
        print("   4. Validating extracted information")
        
        # In a real scenario:
        # bill_data = await extractor.extract_bill_data(image_message)
        
        print("✅ Image extraction would process photo and return bill data")
        
    except BillExtractionError as e:
        print(f"❌ Image extraction failed: {e}")


async def example_validation_and_questions():
    """Example of validation and clarifying questions"""
    print("\n🔍 VALIDATION & CLARIFYING QUESTIONS EXAMPLE")
    print("-" * 50)
    
    extractor = BillExtractor()
    
    # Create incomplete bill data
    incomplete_bill = BillData(
        total_amount=Decimal('0.00'),  # Missing amount
        description="",  # Missing description
        items=[],
        currency="INR",
        merchant=None  # Missing merchant
    )
    
    print("Testing with incomplete bill data:")
    print(f"  Amount: ₹{incomplete_bill.total_amount}")
    print(f"  Description: '{incomplete_bill.description}'")
    print(f"  Merchant: {incomplete_bill.merchant}")
    
    # Validate the incomplete data
    validation = await extractor.validate_bill_data(incomplete_bill)
    print(f"\n✅ Validation result: {'Valid' if validation.is_valid else 'Invalid'}")
    
    if validation.errors:
        print("❌ Errors found:")
        for error in validation.errors:
            print(f"   • {error}")
    
    if validation.warnings:
        print("⚠️ Warnings:")
        for warning in validation.warnings:
            print(f"   • {warning}")
    
    # Generate clarifying questions
    questions = await extractor.generate_clarifying_questions(incomplete_bill)
    print(f"\n❓ Generated {len(questions)} clarifying questions:")
    for i, question in enumerate(questions, 1):
        print(f"   {i}. {question}")


async def example_confirmation_processing():
    """Example of processing user confirmations"""
    print("\n✅ CONFIRMATION PROCESSING EXAMPLE")
    print("-" * 40)
    
    extractor = BillExtractor()
    
    # Sample bill data for confirmation
    bill_data = BillData(
        total_amount=Decimal('250.00'),
        description="Dinner at Italian Restaurant",
        items=[
            BillItem(name="Pasta Carbonara", amount=Decimal('180.00'), quantity=1),
            BillItem(name="Garlic Bread", amount=Decimal('70.00'), quantity=1)
        ],
        currency="INR",
        merchant="Italian Restaurant"
    )
    
    print("Bill to confirm:")
    summary = await extractor.create_bill_summary(bill_data)
    print(summary)
    
    # Test different confirmation responses
    test_responses = [
        ("yes, that's correct", "Positive confirmation"),
        ("no, the amount is wrong", "Negative confirmation"),
        ("maybe, I'm not sure", "Ambiguous response"),
        ("looks good to me", "Positive with different wording")
    ]
    
    print("\n🧪 Testing different confirmation responses:")
    
    for response_text, description in test_responses:
        message = Message(
            id=f"msg_confirm_{hash(response_text)}",
            user_id="user_123",
            content=response_text,
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        is_confirmed, error_msg = await extractor.process_bill_confirmation(message, bill_data)
        
        print(f"\n  📝 {description}: '{response_text}'")
        print(f"     Result: {'✅ Confirmed' if is_confirmed else '❌ Not confirmed'}")
        if error_msg:
            print(f"     Message: {error_msg}")


async def example_error_handling():
    """Example of error handling and fallback mechanisms"""
    print("\n🚨 ERROR HANDLING EXAMPLE")
    print("-" * 30)
    
    extractor = BillExtractor()
    
    # Test with invalid message type
    try:
        invalid_message = Message(
            id="msg_invalid",
            user_id="user_123",
            content="test",
            message_type="INVALID_TYPE",  # Invalid type
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Manually set invalid type to test error handling
        invalid_message.message_type = "INVALID_TYPE"
        
        await extractor.extract_bill_data(invalid_message)
        
    except BillExtractionError as e:
        print(f"✅ Correctly caught invalid message type: {e}")
    
    # Test with missing metadata
    try:
        voice_without_audio = Message(
            id="msg_no_audio",
            user_id="user_123",
            content="",
            message_type=MessageType.VOICE,
            timestamp=datetime.now(),
            metadata={}  # Missing audio_data
        )
        
        await extractor.extract_bill_data(voice_without_audio)
        
    except BillExtractionError as e:
        print(f"✅ Correctly caught missing audio data: {e}")
    
    print("✅ Error handling working correctly")


async def main():
    """Run all examples"""
    print("🚀 BillExtractor Examples")
    print("=" * 50)
    
    # Run all examples
    await example_text_extraction()
    await example_voice_extraction()
    await example_image_extraction()
    await example_validation_and_questions()
    await example_confirmation_processing()
    await example_error_handling()
    
    print("\n" + "=" * 50)
    print("🎉 All examples completed!")
    print("\nThe BillExtractor service provides:")
    print("  • Multi-modal input processing (text, voice, image)")
    print("  • Comprehensive data validation")
    print("  • Intelligent clarifying questions")
    print("  • User-friendly bill summaries")
    print("  • Robust confirmation processing")
    print("  • Graceful error handling")


if __name__ == "__main__":
    asyncio.run(main())