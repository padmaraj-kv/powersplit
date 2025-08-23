"""
Example usage of BillQueryService
Demonstrates requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.bill_query_service import BillQueryService
from app.services.payment_request_service import PaymentRequestService
from app.services.communication_service import CommunicationService
from app.models.schemas import BillFilters
from app.models.enums import BillStatus


async def demonstrate_bill_query_service():
    """Demonstrate BillQueryService functionality"""
    
    # Mock dependencies (in real usage, these would be properly injected)
    db_session = None  # Would be actual database session
    payment_service = None  # Would be actual PaymentRequestService
    communication_service = None  # Would be actual CommunicationService
    
    # Create service instance
    bill_query_service = BillQueryService(db_session, payment_service, communication_service)
    
    # Example user ID
    user_id = str(uuid4())
    bill_id = str(uuid4())
    
    print("=== Bill Query Service Examples ===\n")
    
    # Example 1: Get user bills with basic query (Requirement 6.1)
    print("1. Getting user bills (basic query):")
    try:
        bills = await bill_query_service.get_user_bills(user_id)
        print(f"   Found {len(bills)} bills")
        for bill in bills:
            print(f"   - Bill {bill.id}: {bill.description} - ₹{bill.total_amount}")
            print(f"     Status: {bill.status}, Participants: {bill.participant_count}, Paid: {bill.paid_count}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 2: Get user bills with filters (Requirement 6.1)
    print("2. Getting user bills with filters:")
    try:
        filters = BillFilters(
            status=BillStatus.ACTIVE,
            date_from=datetime.now() - timedelta(days=30),
            min_amount=Decimal("50.00"),
            merchant="Restaurant",
            limit=10
        )
        filtered_bills = await bill_query_service.get_user_bills(user_id, filters)
        print(f"   Found {len(filtered_bills)} bills matching filters")
        for bill in filtered_bills:
            print(f"   - {bill.description}: ₹{bill.total_amount} from {bill.merchant}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 3: Get bill status (Requirement 6.2)
    print("3. Getting bill status:")
    try:
        status = await bill_query_service.get_bill_status(user_id, bill_id)
        if status:
            print(f"   Bill: {status.description}")
            print(f"   Total: ₹{status.total_amount}")
            print(f"   Paid: ₹{status.total_paid}")
            print(f"   Remaining: ₹{status.remaining_amount}")
            print(f"   Completion: {status.completion_percentage:.1f}%")
            print(f"   Participants: {len(status.participants)}")
            
            for participant in status.participants:
                status_emoji = "✅" if participant.payment_status.value == "confirmed" else "⏳"
                print(f"     {status_emoji} {participant.name}: ₹{participant.amount_owed} ({participant.payment_status.value})")
        else:
            print("   Bill not found")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 4: Get detailed bill information (Requirement 6.3)
    print("4. Getting detailed bill information:")
    try:
        details = await bill_query_service.get_bill_details(user_id, bill_id)
        if details:
            print(f"   Bill: {details.description}")
            print(f"   Merchant: {details.merchant}")
            print(f"   Date: {details.bill_date}")
            print(f"   Total: ₹{details.total_amount} {details.currency}")
            print(f"   Status: {details.status}")
            
            print(f"   Items ({len(details.items)}):")
            for item in details.items:
                print(f"     - {item.name}: ₹{item.amount} x {item.quantity}")
            
            print(f"   Participants ({len(details.participants)}):")
            for participant in details.participants:
                print(f"     - {participant.name} ({participant.phone_number})")
                print(f"       Amount: ₹{participant.amount_owed}")
                print(f"       Status: {participant.payment_status.value}")
                if participant.paid_at:
                    print(f"       Paid at: {participant.paid_at}")
                if participant.reminder_count > 0:
                    print(f"       Reminders sent: {participant.reminder_count}")
        else:
            print("   Bill not found")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 5: Get unpaid participants
    print("5. Getting unpaid participants:")
    try:
        unpaid = await bill_query_service.get_unpaid_participants(user_id, bill_id)
        print(f"   Found {len(unpaid)} unpaid participants")
        for participant in unpaid:
            print(f"   - {participant.name}: ₹{participant.amount_owed}")
            print(f"     Status: {participant.payment_status.value}")
            if participant.reminder_count > 0:
                print(f"     Reminders sent: {participant.reminder_count}")
                print(f"     Last reminder: {participant.last_reminder_sent}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 6: Send payment reminders (Requirement 6.4)
    print("6. Sending payment reminders:")
    try:
        # Send reminders to all unpaid participants
        result = await bill_query_service.send_payment_reminders(user_id, bill_id)
        
        if result["success"]:
            print(f"   Successfully sent {result['reminded_count']} reminders")
            if result["failed_count"] > 0:
                print(f"   Failed to send {result['failed_count']} reminders")
            
            print("   Details:")
            for detail in result["details"]:
                status_emoji = "✅" if detail["status"] == "sent" else "❌"
                print(f"     {status_emoji} {detail['name']}: {detail['status']}")
                if detail["status"] == "sent":
                    print(f"        Method: {detail.get('method', 'unknown')}")
                elif detail["status"] == "failed":
                    print(f"        Error: {detail.get('error', 'unknown')}")
        else:
            print(f"   Failed to send reminders: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 7: Send reminders to specific participants (Requirement 6.4)
    print("7. Sending reminders to specific participants:")
    try:
        # Get unpaid participants first
        unpaid = await bill_query_service.get_unpaid_participants(user_id, bill_id)
        if unpaid:
            # Send reminder to first unpaid participant only
            specific_participant_ids = [unpaid[0].id]
            result = await bill_query_service.send_payment_reminders(
                user_id, bill_id, specific_participant_ids
            )
            
            if result["success"]:
                print(f"   Sent reminder to {result['reminded_count']} specific participant(s)")
            else:
                print(f"   Failed: {result.get('error', 'Unknown error')}")
        else:
            print("   No unpaid participants found")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Example 8: Query bills with different filters
    print("8. Advanced filtering examples:")
    
    # Recent bills only
    try:
        recent_filters = BillFilters(
            date_from=datetime.now() - timedelta(days=7),
            limit=5
        )
        recent_bills = await bill_query_service.get_user_bills(user_id, recent_filters)
        print(f"   Recent bills (last 7 days): {len(recent_bills)}")
    except Exception as e:
        print(f"   Error getting recent bills: {e}")
    
    # High-value bills
    try:
        high_value_filters = BillFilters(
            min_amount=Decimal("500.00"),
            status=BillStatus.ACTIVE
        )
        high_value_bills = await bill_query_service.get_user_bills(user_id, high_value_filters)
        print(f"   High-value active bills (>₹500): {len(high_value_bills)}")
    except Exception as e:
        print(f"   Error getting high-value bills: {e}")
    
    # Bills from specific merchant
    try:
        merchant_filters = BillFilters(
            merchant="Swiggy",
            limit=20
        )
        merchant_bills = await bill_query_service.get_user_bills(user_id, merchant_filters)
        print(f"   Bills from Swiggy: {len(merchant_bills)}")
    except Exception as e:
        print(f"   Error getting merchant bills: {e}")
    
    print("\n=== Examples completed ===")


def demonstrate_error_scenarios():
    """Demonstrate error handling scenarios"""
    print("\n=== Error Handling Examples ===\n")
    
    # These examples show how the service handles various error conditions
    # that satisfy requirement 6.5 (user isolation and security)
    
    examples = [
        {
            "scenario": "Invalid user ID format",
            "user_id": "invalid-uuid",
            "bill_id": str(uuid4()),
            "expected": "Should return empty list or None"
        },
        {
            "scenario": "Non-existent bill ID",
            "user_id": str(uuid4()),
            "bill_id": str(uuid4()),
            "expected": "Should return None for bill queries"
        },
        {
            "scenario": "User trying to access another user's bill",
            "user_id": str(uuid4()),
            "bill_id": str(uuid4()),
            "expected": "Should return None (requirement 6.5 - user isolation)"
        }
    ]
    
    for example in examples:
        print(f"Scenario: {example['scenario']}")
        print(f"Expected: {example['expected']}")
        print()


if __name__ == "__main__":
    print("Bill Query Service Example")
    print("This example demonstrates the bill query and history functionality.")
    print("Note: This example uses mock data and won't actually query a database.")
    print()
    
    # Run the async demonstration
    asyncio.run(demonstrate_bill_query_service())
    
    # Show error scenarios
    demonstrate_error_scenarios()
    
    print("\nFor actual usage:")
    print("1. Initialize with proper database session and services")
    print("2. Handle exceptions appropriately in your application")
    print("3. Use proper authentication to ensure user isolation")
    print("4. Consider rate limiting for reminder functionality")