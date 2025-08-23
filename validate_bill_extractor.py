#!/usr/bin/env python3
"""
Validation script for BillExtractor implementation
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


async def test_bill_extractor():
    """Test basic BillExtractor functionality"""
    print("🧪 Testing BillExtractor implementation...")
    
    try:
        # Test 1: Create BillExtractor instance
        print("\n1. Creating BillExtractor instance...")
        extractor = BillExtractor()
        print("✅ BillExtractor created successfully")
        
        # Test 2: Test bill summary creation
        print("\n2. Testing bill summary creation...")
        sample_bill = BillData(
            total_amount=Decimal('150.00'),
            description="Lunch at Pizza Palace",
            items=[
                BillItem(name="Margherita Pizza", amount=Decimal('120.00'), quantity=1),
                BillItem(name="Coke", amount=Decimal('30.00'), quantity=1)
            ],
            currency="INR",
            merchant="Pizza Palace",
            date=datetime(2024, 1, 15, 12, 30)
        )
        
        summary = await extractor.create_bill_summary(sample_bill)
        print("✅ Bill summary created successfully")
        print(f"Summary preview: {summary[:100]}...")
        
        # Test 3: Test validation
        print("\n3. Testing bill validation...")
        validation_result = await extractor.validate_bill_data(sample_bill)
        print(f"✅ Validation completed: {'Valid' if validation_result.is_valid else 'Invalid'}")
        
        # Test 4: Test clarifying questions generation
        print("\n4. Testing clarifying questions generation...")
        incomplete_bill = BillData(
            total_amount=Decimal('0.00'),
            description="",
            items=[],
            currency="INR"
        )
        
        questions = await extractor.generate_clarifying_questions(incomplete_bill)
        print(f"✅ Generated {len(questions)} clarifying questions")
        for i, question in enumerate(questions, 1):
            print(f"   {i}. {question}")
        
        # Test 5: Test confirmation processing
        print("\n5. Testing confirmation processing...")
        confirm_message = Message(
            id="test_msg",
            user_id="test_user",
            content="yes, that's correct",
            message_type=MessageType.TEXT,
            timestamp=datetime.now(),
            metadata={}
        )
        
        is_confirmed, error_msg = await extractor.process_bill_confirmation(confirm_message, sample_bill)
        print(f"✅ Confirmation processed: {'Confirmed' if is_confirmed else 'Not confirmed'}")
        if error_msg:
            print(f"   Error message: {error_msg}")
        
        print("\n🎉 All BillExtractor tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_step_handlers():
    """Test step handler integration"""
    print("\n🧪 Testing step handler integration...")
    
    try:
        from app.services.step_handlers import BillExtractionHandler, BillConfirmationHandler
        from app.models.schemas import ConversationState
        from app.models.enums import ConversationStep
        
        # Test 1: Create handlers
        print("\n1. Creating step handlers...")
        extraction_handler = BillExtractionHandler()
        confirmation_handler = BillConfirmationHandler()
        print("✅ Step handlers created successfully")
        
        # Test 2: Test handler methods exist
        print("\n2. Checking handler methods...")
        assert hasattr(extraction_handler, 'handle_message')
        assert hasattr(confirmation_handler, 'handle_message')
        print("✅ Handler methods exist")
        
        print("\n🎉 Step handler integration tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Step handler test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all validation tests"""
    print("🚀 Starting BillExtractor validation...")
    
    # Test BillExtractor
    extractor_success = await test_bill_extractor()
    
    # Test step handlers
    handler_success = await test_step_handlers()
    
    # Summary
    print("\n" + "="*50)
    print("📊 VALIDATION SUMMARY")
    print("="*50)
    print(f"BillExtractor: {'✅ PASS' if extractor_success else '❌ FAIL'}")
    print(f"Step Handlers: {'✅ PASS' if handler_success else '❌ FAIL'}")
    
    if extractor_success and handler_success:
        print("\n🎉 All validations passed! BillExtractor implementation is ready.")
        return 0
    else:
        print("\n❌ Some validations failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)