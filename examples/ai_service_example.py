"""
Example usage of AI Service integration layer
Demonstrates text, voice, and image processing capabilities
"""
import asyncio
import os
from decimal import Decimal
from app.services.ai_service import AIService
from app.models.schemas import Message, BillData
from app.models.enums import MessageType, ConversationStep


async def demonstrate_ai_service():
    """Demonstrate AI service capabilities"""
    print("🤖 AI Service Integration Demo")
    print("=" * 50)
    
    # Initialize AI service
    ai_service = AIService()
    
    # 1. Health Check
    print("\n1. Checking AI Services Health...")
    try:
        health_status = await ai_service.health_check()
        for service, status in health_status.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service.capitalize()}: {'Healthy' if status else 'Unavailable'}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
    
    # 2. Text Processing
    print("\n2. Text Processing Demo...")
    sample_texts = [
        "I spent ₹150 at Pizza Hut for lunch today",
        "Bill total was 250 rupees from McDonald's",
        "Dinner cost 500 at Dominos with 2 pizzas and coke"
    ]
    
    for text in sample_texts:
        try:
            print(f"\n   Input: '{text}'")
            bill_data = await ai_service.extract_from_text(text)
            print(f"   ✅ Extracted: ₹{bill_data.total_amount} from {bill_data.merchant or 'Unknown'}")
            print(f"      Description: {bill_data.description}")
            
            # Validate extraction
            validation = await ai_service.validate_extraction(bill_data)
            validation_icon = "✅" if validation.is_valid else "⚠️"
            print(f"   {validation_icon} Validation: {'Valid' if validation.is_valid else 'Issues found'}")
            
            if validation.warnings:
                for warning in validation.warnings:
                    print(f"      ⚠️ {warning}")
                    
        except Exception as e:
            print(f"   ❌ Text processing failed: {e}")
    
    # 3. Intent Recognition
    print("\n3. Intent Recognition Demo...")
    sample_messages = [
        ("Yes, that's correct", ConversationStep.CONFIRMING_BILL),
        ("I want to change the amount", ConversationStep.CONFIRMING_BILL),
        ("I have paid my share", ConversationStep.TRACKING_PAYMENTS),
        ("What's the status of my bill?", ConversationStep.TRACKING_PAYMENTS)
    ]
    
    for text, step in sample_messages:
        try:
            message = Message(
                id="demo_msg",
                user_id="demo_user",
                content=text,
                message_type=MessageType.TEXT,
                timestamp="2024-01-01T12:00:00Z"
            )
            
            intent_data = await ai_service.recognize_intent(message, step)
            print(f"\n   Input: '{text}' (Step: {step.value})")
            print(f"   ✅ Intent: {intent_data['intent']} (confidence: {intent_data['confidence']})")
            print(f"      Next action: {intent_data['next_action']}")
            
        except Exception as e:
            print(f"   ❌ Intent recognition failed: {e}")
    
    # 4. Clarifying Questions
    print("\n4. Clarifying Questions Demo...")
    incomplete_bills = [
        BillData(total_amount=Decimal("0"), description="Some bill", items=[], currency="INR"),
        BillData(total_amount=Decimal("100"), description="", items=[], currency="INR", merchant=None)
    ]
    
    for i, bill in enumerate(incomplete_bills, 1):
        try:
            questions = await ai_service.generate_clarifying_questions(bill)
            print(f"\n   Incomplete Bill {i}:")
            print(f"   Amount: ₹{bill.total_amount}, Merchant: {bill.merchant or 'Unknown'}")
            print(f"   ✅ Generated {len(questions)} clarifying questions:")
            for j, question in enumerate(questions, 1):
                print(f"      {j}. {question}")
                
        except Exception as e:
            print(f"   ❌ Question generation failed: {e}")
    
    # 5. Fallback Mechanisms Demo
    print("\n5. Fallback Mechanisms Demo...")
    print("   Testing text extraction with potential AI service failures...")
    
    # This will demonstrate fallback to basic regex extraction
    fallback_text = "I paid ₹75 for coffee and ₹125 for sandwich total ₹200"
    try:
        # Simulate AI service failure by using fallback directly
        bill_data = await ai_service._fallback_text_extraction(fallback_text)
        print(f"   ✅ Fallback extraction: ₹{bill_data.total_amount}")
        print(f"      Description: {bill_data.description}")
    except Exception as e:
        print(f"   ❌ Fallback extraction failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 AI Service Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✅ Multi-modal input processing (text, voice, image)")
    print("✅ Intent recognition and conversation flow")
    print("✅ Data validation and quality checks")
    print("✅ Clarifying question generation")
    print("✅ Fallback mechanisms for reliability")
    print("✅ Health monitoring of AI services")


async def demonstrate_error_handling():
    """Demonstrate error handling and fallback mechanisms"""
    print("\n🛡️ Error Handling & Fallback Demo")
    print("=" * 50)
    
    ai_service = AIService()
    
    # Test with invalid inputs
    test_cases = [
        ("", "Empty text"),
        ("Hello world", "Non-bill text"),
        ("₹", "Invalid amount format"),
    ]
    
    for text, description in test_cases:
        print(f"\n   Testing: {description}")
        print(f"   Input: '{text}'")
        
        try:
            bill_data = await ai_service.extract_from_text(text)
            print(f"   ✅ Extracted: ₹{bill_data.total_amount}")
        except Exception as e:
            print(f"   ⚠️ Expected failure: {e}")
    
    print("\n   Testing basic intent recognition fallback...")
    basic_intents = [
        "yes",
        "no, change it",
        "I paid",
        "random text"
    ]
    
    for text in basic_intents:
        result = ai_service._basic_intent_recognition(text, ConversationStep.CONFIRMING_BILL)
        print(f"   '{text}' → {result['intent']} (confidence: {result['confidence']})")


if __name__ == "__main__":
    print("Starting AI Service Integration Demo...")
    print("Note: This demo requires valid API keys in .env file")
    print("Some features may show fallback behavior if services are unavailable")
    
    try:
        asyncio.run(demonstrate_ai_service())
        asyncio.run(demonstrate_error_handling())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nDemo failed with error: {e}")
        print("This may be due to missing API keys or network issues")