#!/usr/bin/env python3
"""
Validation script for bill splitter functionality
Tests the bill splitting calculation engine
"""
import asyncio
import sys
from decimal import Decimal
from app.services.bill_splitter import BillSplitter
from app.models.schemas import BillData, Participant, BillItem
from app.models.enums import PaymentStatus


async def test_equal_splits():
    """Test equal split calculations"""
    print("🧪 Testing Equal Splits...")
    
    splitter = BillSplitter()
    
    # Test case 1: Simple equal split
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Test bill",
        currency="INR"
    )
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    result = await splitter.calculate_equal_splits(bill, participants)
    
    # Verify each person pays 50.00
    expected_amount = Decimal('50.00')
    for p in result:
        if p.amount_owed != expected_amount:
            print(f"❌ Equal split failed: {p.name} has ₹{p.amount_owed}, expected ₹{expected_amount}")
            return False
    
    # Verify total matches
    total = sum(p.amount_owed for p in result)
    if total != bill.total_amount:
        print(f"❌ Total mismatch: got ₹{total}, expected ₹{bill.total_amount}")
        return False
    
    print("✅ Equal splits test passed")
    return True


async def test_rounding():
    """Test rounding in equal splits"""
    print("🧪 Testing Rounding...")
    
    splitter = BillSplitter()
    
    # Test case: 100.00 ÷ 3 = 33.33, 33.33, 33.34
    bill = BillData(
        total_amount=Decimal('100.00'),
        description="Rounding test",
        currency="INR"
    )
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    result = await splitter.calculate_equal_splits(bill, participants)
    
    # First participant should get the extra cent
    if result[0].amount_owed != Decimal('33.34'):
        print(f"❌ Rounding failed: first participant has ₹{result[0].amount_owed}, expected ₹33.34")
        return False
    
    if result[1].amount_owed != Decimal('33.33') or result[2].amount_owed != Decimal('33.33'):
        print(f"❌ Rounding failed: other participants should have ₹33.33")
        return False
    
    # Verify total still matches exactly
    total = sum(p.amount_owed for p in result)
    if total != bill.total_amount:
        print(f"❌ Rounding total mismatch: got ₹{total}, expected ₹{bill.total_amount}")
        return False
    
    print("✅ Rounding test passed")
    return True


async def test_custom_splits():
    """Test custom split functionality"""
    print("🧪 Testing Custom Splits...")
    
    splitter = BillSplitter()
    
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Custom split test",
        currency="INR"
    )
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    # Apply custom amounts
    custom_amounts = {
        "Alice": Decimal('70.00'),
        "Bob": Decimal('30.00')
        # Charlie keeps original 50.00
    }
    
    result = await splitter.apply_custom_splits(bill, participants, custom_amounts)
    
    # Verify custom amounts applied
    if result[0].amount_owed != Decimal('70.00'):
        print(f"❌ Custom split failed: Alice has ₹{result[0].amount_owed}, expected ₹70.00")
        return False
    
    if result[1].amount_owed != Decimal('30.00'):
        print(f"❌ Custom split failed: Bob has ₹{result[1].amount_owed}, expected ₹30.00")
        return False
    
    if result[2].amount_owed != Decimal('50.00'):
        print(f"❌ Custom split failed: Charlie has ₹{result[2].amount_owed}, expected ₹50.00")
        return False
    
    print("✅ Custom splits test passed")
    return True


async def test_validation():
    """Test split validation"""
    print("🧪 Testing Validation...")
    
    splitter = BillSplitter()
    
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Validation test",
        currency="INR"
    )
    
    # Test valid splits
    valid_participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('50.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    validation = await splitter.validate_splits(bill, valid_participants)
    if not validation.is_valid:
        print(f"❌ Valid splits marked as invalid: {validation.errors}")
        return False
    
    # Test invalid splits (total mismatch)
    invalid_participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('40.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('40.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('40.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    invalid_validation = await splitter.validate_splits(bill, invalid_participants)
    if invalid_validation.is_valid:
        print("❌ Invalid splits marked as valid")
        return False
    
    if not any("don't match bill total" in error for error in invalid_validation.errors):
        print(f"❌ Expected total mismatch error not found: {invalid_validation.errors}")
        return False
    
    print("✅ Validation test passed")
    return True


async def test_display_formatting():
    """Test display formatting"""
    print("🧪 Testing Display Formatting...")
    
    splitter = BillSplitter()
    
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Pizza Night",
        currency="INR"
    )
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('60.00'), payment_status=PaymentStatus.CONFIRMED),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('45.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('45.00'), payment_status=PaymentStatus.SENT)
    ]
    
    display = await splitter.format_split_display(bill, participants)
    
    # Check required elements
    required_elements = [
        "Bill Split Summary",
        "Pizza Night",
        "₹150.00",
        "3 participants",
        "Alice: ₹60.00",
        "Bob: ₹45.00",
        "Charlie: ₹45.00",
        "Total splits: ₹150.00"
    ]
    
    for element in required_elements:
        if element not in display:
            print(f"❌ Display missing required element: '{element}'")
            return False
    
    # Check status emojis
    if "✅" not in display:  # Confirmed status
        print("❌ Display missing confirmed status emoji")
        return False
    
    print("✅ Display formatting test passed")
    return True


async def test_amount_parsing():
    """Test custom amount parsing"""
    print("🧪 Testing Amount Parsing...")
    
    splitter = BillSplitter()
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Bob", phone_number="+91 9876543211", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING),
        Participant(name="Charlie", phone_number="+91 9876543212", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    # Test various formats
    test_cases = [
        ("Alice ₹60, Bob ₹40, Charlie ₹50", {"Alice": Decimal('60'), "Bob": Decimal('40'), "Charlie": Decimal('50')}),
        ("Alice: ₹60.50, Bob - 40", {"Alice": Decimal('60.50'), "Bob": Decimal('40')}),
        ("alice ₹60, BOB ₹40", {"Alice": Decimal('60'), "Bob": Decimal('40')}),  # Case insensitive
    ]
    
    for message, expected in test_cases:
        result = await splitter.parse_custom_amounts(message, participants)
        
        for name, amount in expected.items():
            if name not in result or result[name] != amount:
                print(f"❌ Parsing failed for '{message}': expected {name}=₹{amount}, got {result.get(name, 'missing')}")
                return False
    
    print("✅ Amount parsing test passed")
    return True


async def test_error_handling():
    """Test error handling"""
    print("🧪 Testing Error Handling...")
    
    splitter = BillSplitter()
    
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Error test",
        currency="INR"
    )
    
    # Test empty participants
    try:
        await splitter.calculate_equal_splits(bill, [])
        print("❌ Expected error for empty participants")
        return False
    except ValueError as e:
        if "No participants provided" not in str(e):
            print(f"❌ Wrong error message: {e}")
            return False
    
    # Test zero amount bill
    zero_bill = BillData(
        total_amount=Decimal('0.00'),
        description="Zero bill",
        currency="INR"
    )
    
    participants = [
        Participant(name="Alice", phone_number="+91 9876543210", amount_owed=Decimal('0.00'), payment_status=PaymentStatus.PENDING)
    ]
    
    try:
        await splitter.calculate_equal_splits(zero_bill, participants)
        print("❌ Expected error for zero amount bill")
        return False
    except ValueError as e:
        if "Bill total amount must be positive" not in str(e):
            print(f"❌ Wrong error message: {e}")
            return False
    
    # Test negative custom amount
    try:
        await splitter.apply_custom_splits(bill, participants, {"Alice": Decimal('-10.00')})
        print("❌ Expected error for negative custom amount")
        return False
    except ValueError as e:
        if "must be positive" not in str(e):
            print(f"❌ Wrong error message: {e}")
            return False
    
    print("✅ Error handling test passed")
    return True


async def main():
    """Run all validation tests"""
    print("🚀 Bill Splitter Validation")
    print("=" * 50)
    
    tests = [
        test_equal_splits,
        test_rounding,
        test_custom_splits,
        test_validation,
        test_display_formatting,
        test_amount_parsing,
        test_error_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Bill splitter is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)