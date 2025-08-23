#!/usr/bin/env python3
"""
Simple test for bill splitter functionality
"""
import asyncio
from decimal import Decimal
from app.services.bill_splitter import BillSplitter
from app.models.schemas import BillData, Participant
from app.models.enums import PaymentStatus


async def test_basic_functionality():
    """Test basic bill splitter functionality"""
    print("Testing BillSplitter...")
    
    # Create bill splitter
    splitter = BillSplitter()
    
    # Create test bill
    bill = BillData(
        total_amount=Decimal('150.00'),
        description="Test Lunch",
        currency="INR"
    )
    
    # Create test participants
    participants = [
        Participant(
            name="Alice",
            phone_number="+91 9876543210",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING
        ),
        Participant(
            name="Bob",
            phone_number="+91 9876543211",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING
        ),
        Participant(
            name="Charlie",
            phone_number="+91 9876543212",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING
        )
    ]
    
    print(f"Bill: {bill.description} - ₹{bill.total_amount}")
    print(f"Participants: {len(participants)}")
    
    # Test equal splits
    print("\n1. Testing equal splits...")
    equal_participants = await splitter.calculate_equal_splits(bill, participants)
    
    for p in equal_participants:
        print(f"   {p.name}: ₹{p.amount_owed}")
    
    total = sum(p.amount_owed for p in equal_participants)
    print(f"   Total: ₹{total} (matches bill: {total == bill.total_amount})")
    
    # Test validation
    print("\n2. Testing validation...")
    validation = await splitter.validate_splits(bill, equal_participants)
    print(f"   Valid: {validation.is_valid}")
    if validation.errors:
        print(f"   Errors: {validation.errors}")
    if validation.warnings:
        print(f"   Warnings: {validation.warnings}")
    
    # Test display formatting
    print("\n3. Testing display formatting...")
    display = await splitter.format_split_display(bill, equal_participants)
    print("   Display output:")
    for line in display.split('\n'):
        print(f"   {line}")
    
    # Test custom splits
    print("\n4. Testing custom splits...")
    custom_amounts = {
        "Alice": Decimal('70.00'),
        "Bob": Decimal('40.00'),
        "Charlie": Decimal('40.00')
    }
    
    custom_participants = await splitter.apply_custom_splits(bill, equal_participants, custom_amounts)
    
    for p in custom_participants:
        print(f"   {p.name}: ₹{p.amount_owed}")
    
    custom_total = sum(p.amount_owed for p in custom_participants)
    print(f"   Total: ₹{custom_total} (matches bill: {custom_total == bill.total_amount})")
    
    # Test custom validation
    custom_validation = await splitter.validate_splits(bill, custom_participants)
    print(f"   Valid: {custom_validation.is_valid}")
    
    # Test amount parsing
    print("\n5. Testing amount parsing...")
    test_message = "Alice ₹80, Bob ₹35, Charlie ₹35"
    parsed_amounts = await splitter.parse_custom_amounts(test_message, participants)
    
    print(f"   Message: '{test_message}'")
    print(f"   Parsed: {parsed_amounts}")
    
    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())