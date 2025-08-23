"""
Example usage of the BillSplitter service
Demonstrates bill splitting calculation engine functionality
"""
import asyncio
from decimal import Decimal
from app.services.bill_splitter import BillSplitter
from app.models.schemas import BillData, Participant, BillItem
from app.models.enums import PaymentStatus


async def main():
    """Demonstrate bill splitter functionality"""
    print("🧾 Bill Splitter Example")
    print("=" * 50)
    
    # Create bill splitter instance
    splitter = BillSplitter()
    
    # Create sample bill
    bill = BillData(
        total_amount=Decimal('275.50'),
        description="Dinner at Italian Restaurant",
        items=[
            BillItem(name="Pasta", amount=Decimal('120.00')),
            BillItem(name="Pizza", amount=Decimal('95.00')),
            BillItem(name="Drinks", amount=Decimal('45.50')),
            BillItem(name="Dessert", amount=Decimal('15.00'))
        ],
        currency="INR"
    )
    
    # Create participants
    participants = [
        Participant(
            name="Alice",
            phone_number="+91 9876543210",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_1"
        ),
        Participant(
            name="Bob",
            phone_number="+91 9876543211",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_2"
        ),
        Participant(
            name="Charlie",
            phone_number="+91 9876543212",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_3"
        ),
        Participant(
            name="Diana",
            phone_number="+91 9876543213",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_4"
        )
    ]
    
    print(f"📄 Bill: {bill.description}")
    print(f"💰 Total Amount: ₹{bill.total_amount}")
    print(f"👥 Participants: {len(participants)}")
    print()
    
    # Example 1: Equal splits
    print("1️⃣ EQUAL SPLITS")
    print("-" * 30)
    
    equal_participants = await splitter.calculate_equal_splits(bill, participants)
    
    # Validate equal splits
    validation = await splitter.validate_splits(bill, equal_participants)
    print(f"✅ Validation: {'Valid' if validation.is_valid else 'Invalid'}")
    if validation.warnings:
        print(f"⚠️ Warnings: {', '.join(validation.warnings)}")
    print()
    
    # Display equal splits
    display = await splitter.format_split_display(bill, equal_participants)
    print(display)
    print()
    
    # Example 2: Custom splits
    print("2️⃣ CUSTOM SPLITS")
    print("-" * 30)
    
    # Alice and Bob had more expensive items
    custom_amounts = {
        "Alice": Decimal('85.00'),
        "Bob": Decimal('75.00'),
        "Charlie": Decimal('60.00'),
        "Diana": Decimal('55.50')
    }
    
    custom_participants = await splitter.apply_custom_splits(bill, equal_participants, custom_amounts)
    
    # Validate custom splits
    custom_validation = await splitter.validate_splits(bill, custom_participants)
    print(f"✅ Validation: {'Valid' if custom_validation.is_valid else 'Invalid'}")
    if custom_validation.errors:
        print(f"❌ Errors: {', '.join(custom_validation.errors)}")
    if custom_validation.warnings:
        print(f"⚠️ Warnings: {', '.join(custom_validation.warnings)}")
    print()
    
    # Display custom splits
    custom_display = await splitter.format_split_display(bill, custom_participants)
    print(custom_display)
    print()
    
    # Example 3: Split confirmation format
    print("3️⃣ SPLIT CONFIRMATION")
    print("-" * 30)
    
    confirmation = await splitter.format_split_confirmation(bill, custom_participants)
    print(confirmation)
    print()
    
    # Example 4: Parse custom amounts from text
    print("4️⃣ PARSING CUSTOM AMOUNTS")
    print("-" * 30)
    
    user_message = "Alice ₹90, Bob ₹80, Charlie: 55.50, Diana - 50"
    parsed_amounts = await splitter.parse_custom_amounts(user_message, participants)
    
    print(f"📝 User message: '{user_message}'")
    print("🔍 Parsed amounts:")
    for name, amount in parsed_amounts.items():
        print(f"   {name}: ₹{amount}")
    print()
    
    # Apply parsed amounts
    if parsed_amounts:
        parsed_participants = await splitter.apply_custom_splits(bill, equal_participants, parsed_amounts)
        parsed_validation = await splitter.validate_splits(bill, parsed_participants)
        
        print(f"✅ Validation: {'Valid' if parsed_validation.is_valid else 'Invalid'}")
        if parsed_validation.errors:
            print(f"❌ Errors: {', '.join(parsed_validation.errors)}")
        print()
    
    # Example 5: Split statistics
    print("5️⃣ SPLIT STATISTICS")
    print("-" * 30)
    
    # Update some payment statuses for demo
    custom_participants[0].payment_status = PaymentStatus.CONFIRMED
    custom_participants[1].payment_status = PaymentStatus.SENT
    
    stats = await splitter.get_split_summary_stats(custom_participants)
    
    print("📊 Split Statistics:")
    print(f"   Total Participants: {stats['total_participants']}")
    print(f"   Total Amount: ₹{stats['total_amount']}")
    print(f"   Average Amount: ₹{stats['average_amount']:.2f}")
    print(f"   Min Amount: ₹{stats['min_amount']}")
    print(f"   Max Amount: ₹{stats['max_amount']}")
    print(f"   Pending Payments: {stats['pending_count']}")
    print(f"   Confirmed Payments: {stats['confirmed_count']}")
    print()
    
    # Example 6: Error handling
    print("6️⃣ ERROR HANDLING")
    print("-" * 30)
    
    # Test with invalid splits
    invalid_custom_amounts = {
        "Alice": Decimal('100.00'),
        "Bob": Decimal('100.00'),
        "Charlie": Decimal('100.00'),
        "Diana": Decimal('100.00')  # Total: 400, Bill: 275.50
    }
    
    try:
        invalid_participants = await splitter.apply_custom_splits(bill, equal_participants, invalid_custom_amounts)
        invalid_validation = await splitter.validate_splits(bill, invalid_participants)
        
        print("❌ Invalid split validation:")
        for error in invalid_validation.errors:
            print(f"   • {error}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
    
    # Example 7: Rounding edge cases
    print("7️⃣ ROUNDING EDGE CASES")
    print("-" * 30)
    
    # Bill that doesn't divide evenly
    odd_bill = BillData(
        total_amount=Decimal('100.00'),
        description="Bill with rounding",
        currency="INR"
    )
    
    three_participants = participants[:3]  # Only first 3 participants
    
    rounded_participants = await splitter.calculate_equal_splits(odd_bill, three_participants)
    
    print(f"📄 Bill: ₹{odd_bill.total_amount} ÷ {len(three_participants)} participants")
    print("💰 Split amounts:")
    for p in rounded_participants:
        print(f"   {p.name}: ₹{p.amount_owed}")
    
    total_check = sum(p.amount_owed for p in rounded_participants)
    print(f"✅ Total verification: ₹{total_check} (matches bill: {total_check == odd_bill.total_amount})")
    
    print("\n🎉 Bill Splitter Example Complete!")


if __name__ == "__main__":
    asyncio.run(main())