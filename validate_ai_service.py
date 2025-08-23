#!/usr/bin/env python3
"""
Validation script for AI Service integration
Checks if all components can be imported and basic functionality works
"""
import sys
import asyncio
from decimal import Decimal


def test_imports():
    """Test if all AI service components can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from app.services.ai_service import AIService
        print("✅ AIService imported successfully")
        
        from app.services.sarvam_client import SarvamClient
        print("✅ SarvamClient imported successfully")
        
        from app.services.gemini_client import GeminiVisionClient
        print("✅ GeminiVisionClient imported successfully")
        
        from app.services.litellm_client import LiteLLMClient
        print("✅ LiteLLMClient imported successfully")
        
        from app.models.schemas import BillData, BillItem, Message, ValidationResult
        print("✅ Schema models imported successfully")
        
        from app.models.enums import MessageType, ConversationStep
        print("✅ Enums imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during import: {e}")
        return False


def test_basic_functionality():
    """Test basic functionality without external API calls"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        from app.services.ai_service import AIService
        from app.models.schemas import BillData, Message
        from app.models.enums import MessageType, ConversationStep
        
        # Test AI service initialization
        ai_service = AIService()
        print("✅ AIService initialized successfully")
        
        # Test basic validation
        bill_data = BillData(
            total_amount=Decimal("100.00"),
            description="Test bill",
            items=[],
            currency="INR"
        )
        
        validation_result = ai_service._basic_validation(bill_data)
        assert validation_result.is_valid is True
        print("✅ Basic validation works")
        
        # Test basic intent recognition
        intent_result = ai_service._basic_intent_recognition("yes", ConversationStep.CONFIRMING_BILL)
        assert intent_result["intent"] == "confirm"
        print("✅ Basic intent recognition works")
        
        # Test fallback text extraction
        async def test_fallback():
            try:
                result = await ai_service._fallback_text_extraction("I spent ₹150 for lunch")
                assert result.total_amount == Decimal("150.00")
                print("✅ Fallback text extraction works")
                return True
            except Exception as e:
                print(f"❌ Fallback text extraction failed: {e}")
                return False
        
        return asyncio.run(test_fallback())
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def test_configuration():
    """Test if configuration is properly set up"""
    print("\n⚙️ Testing configuration...")
    
    try:
        from app.core.config import settings
        
        # Check if AI service settings exist
        required_settings = [
            'sarvam_api_key',
            'gemini_api_key',
            'supabase_url',
            'supabase_key'
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not hasattr(settings, setting) or not getattr(settings, setting):
                missing_settings.append(setting)
        
        if missing_settings:
            print(f"⚠️ Missing configuration: {', '.join(missing_settings)}")
            print("   Note: Some AI features may not work without proper API keys")
        else:
            print("✅ All required configuration settings found")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def main():
    """Run all validation tests"""
    print("🚀 AI Service Integration Validation")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Basic Functionality", test_basic_functionality),
        ("Configuration", test_configuration)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Validation Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! AI Service integration is ready.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())