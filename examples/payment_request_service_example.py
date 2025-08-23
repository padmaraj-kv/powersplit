"""
Payment Request Distribution Service Example

This example demonstrates how to use the PaymentRequestService to distribute
payment requests to bill participants via WhatsApp and SMS.
"""
import asyncio
from decimal import Decimal
from uuid import uuid4
from datetime import datetime

from app.services.payment_request_service import PaymentRequestService
from app.services.upi_service import UPIService
from app.database.repositories import DatabaseRepository
from app.models.database import Bill, BillParticipant, Contact, User
from app.core.database import get_db


async def create_sample_bill_with_participants():
    """Create a sample bill with participants for demonstration"""
    # Create user (bill organizer)
    user = User(
        id=uuid4(),
        phone_number="+919876543210",
        name="John Organizer"
    )
    
    # Create bill
    bill = Bill(
        id=uuid4(),
        user_id=user.id,
        user=user,
        total_amount=Decimal("1200.00"),
        description="Team Dinner at Italian Restaurant",
        merchant="Bella Vista Restaurant",
        bill_date=datetime.now(),
        status="active"
    )
    
    # Create contacts for participants
    contacts = [
        Contact(
            id=uuid4(),
            user_id=user.id,
            name="Alice Smith",
            phone_number="+919876543211"
        ),
        Contact(
            id=uuid4(),
            user_id=user.id,
            name="Bob Johnson",
            phone_number="+919876543212"
        ),
        Contact(
            id=uuid4(),
            user_id=user.id,
            name="Carol Davis",
            phone_number="+919876543213"
        )
    ]
    
    # Create bill participants
    participants = [
        BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contacts[0].id,
            contact=contacts[0],
            amount_owed=Decimal("400.00"),
            payment_status="pending"
        ),
        BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contacts[1].id,
            contact=contacts[1],
            amount_owed=Decimal("400.00"),
            payment_status="pending"
        ),
        BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contacts[2].id,
            contact=contacts[2],
            amount_owed=Decimal("400.00"),
            payment_status="pending"
        )
    ]
    
    bill.participants = participants
    return bill


async def example_distribute_payment_requests():
    """Example: Distribute payment requests to all participants"""
    print("=== Payment Request Distribution Example ===\n")
    
    # Initialize services
    db_session = next(get_db())
    db_repository = DatabaseRepository(db_session)
    upi_service = UPIService(default_upi_id="restaurant@paytm")
    payment_service = PaymentRequestService(db_repository, upi_service)
    
    # Create sample bill (in real scenario, this would come from database)
    bill = await create_sample_bill_with_participants()
    
    print(f"Bill Details:")
    print(f"  Description: {bill.description}")
    print(f"  Total Amount: ₹{bill.total_amount}")
    print(f"  Participants: {len(bill.participants)}")
    print()
    
    try:
        # Distribute payment requests
        print("Distributing payment requests...")
        summary = await payment_service.distribute_payment_requests(
            bill_id=str(bill.id),
            organizer_phone="+919876543210",
            custom_message="Please pay by tomorrow evening. Thanks!"
        )
        
        # Display results
        print(f"\n=== Distribution Summary ===")
        print(f"Total Participants: {summary.total_participants}")
        print(f"Successful Sends: {summary.successful_sends}")
        print(f"Failed Sends: {summary.failed_sends}")
        print(f"WhatsApp Deliveries: {summary.whatsapp_sends}")
        print(f"SMS Deliveries: {summary.sms_sends}")
        print(f"Duration: {(summary.completed_at - summary.started_at).total_seconds():.2f} seconds")
        print()
        
        # Display individual results
        print("=== Individual Results ===")
        for i, result in enumerate(summary.results, 1):
            print(f"{i}. {result.participant_name} ({result.phone_number})")
            print(f"   Amount: ₹{result.amount}")
            print(f"   Status: {'✅ Success' if result.success else '❌ Failed'}")
            if result.success:
                print(f"   Method: {result.delivery_method.value}")
                print(f"   Fallback Used: {'Yes' if result.fallback_used else 'No'}")
                print(f"   UPI Link: {result.upi_link[:50]}...")
            else:
                print(f"   Error: {result.error}")
            print()
        
    except Exception as e:
        print(f"Error distributing payment requests: {e}")


async def example_send_payment_reminders():
    """Example: Send payment reminders to unpaid participants"""
    print("=== Payment Reminder Example ===\n")
    
    # Initialize services
    db_session = next(get_db())
    db_repository = DatabaseRepository(db_session)
    upi_service = UPIService(default_upi_id="restaurant@paytm")
    payment_service = PaymentRequestService(db_repository, upi_service)
    
    # Create sample bill
    bill = await create_sample_bill_with_participants()
    
    # Simulate that one participant has already paid
    bill.participants[0].payment_status = 'confirmed'
    bill.participants[0].paid_at = datetime.now()
    
    print(f"Sending reminders for unpaid participants...")
    print(f"Bill: {bill.description}")
    print(f"Unpaid participants: {len([p for p in bill.participants if p.payment_status != 'confirmed'])}")
    print()
    
    try:
        # Send reminders to unpaid participants only
        summary = await payment_service.send_payment_reminder(
            bill_id=str(bill.id),
            custom_message="Friendly reminder: Please complete your payment when convenient."
        )
        
        print(f"=== Reminder Summary ===")
        print(f"Reminders Sent: {summary.successful_sends}")
        print(f"Failed: {summary.failed_sends}")
        print()
        
        for result in summary.results:
            print(f"Reminder sent to {result.participant_name}: {'✅' if result.success else '❌'}")
        
    except Exception as e:
        print(f"Error sending reminders: {e}")


async def example_process_payment_confirmation():
    """Example: Process payment confirmation from participant"""
    print("=== Payment Confirmation Example ===\n")
    
    # Initialize services
    db_session = next(get_db())
    db_repository = DatabaseRepository(db_session)
    upi_service = UPIService()
    payment_service = PaymentRequestService(db_repository, upi_service)
    
    # Create sample bill
    bill = await create_sample_bill_with_participants()
    
    print(f"Processing payment confirmation...")
    print(f"Bill: {bill.description}")
    print(f"Participant: {bill.participants[0].contact.name}")
    print(f"Amount: ₹{bill.participants[0].amount_owed}")
    print()
    
    try:
        # Process payment confirmation
        success = await payment_service.process_payment_confirmation(
            participant_phone="+919876543211",  # Alice's phone
            bill_id=str(bill.id),
            confirmation_message="DONE - paid via GPay"
        )
        
        if success:
            print("✅ Payment confirmation processed successfully!")
            print("- Participant marked as paid")
            print("- Organizer notified")
            print("- Payment request updated")
        else:
            print("❌ Failed to process payment confirmation")
        
    except Exception as e:
        print(f"Error processing payment confirmation: {e}")


async def example_payment_message_templates():
    """Example: Demonstrate different message templates"""
    print("=== Message Templates Example ===\n")
    
    # Initialize services
    db_session = next(get_db())
    db_repository = DatabaseRepository(db_session)
    upi_service = UPIService()
    payment_service = PaymentRequestService(db_repository, upi_service)
    
    # Example payment request message
    payment_message = payment_service._create_payment_message(
        participant_name="Alice",
        amount=Decimal("450.00"),
        bill_description="Birthday Party Expenses",
        upi_link="upi://pay?pa=party@upi&am=450.00&tn=Birthday%20Party",
        custom_message="Thanks for joining the celebration!"
    )
    
    print("=== Payment Request Message ===")
    print(payment_message)
    print("\n" + "="*50 + "\n")
    
    # Example reminder message
    reminder_message = payment_service._create_reminder_message(
        participant_name="Bob",
        amount=Decimal("300.00"),
        bill_description="Movie Night",
        upi_link="upi://pay?pa=movies@upi&am=300.00",
        reminder_count=2,
        custom_message="Hope you enjoyed the movie!"
    )
    
    print("=== Payment Reminder Message ===")
    print(reminder_message)
    print("\n" + "="*50 + "\n")


async def example_get_statistics():
    """Example: Get payment request statistics"""
    print("=== Payment Statistics Example ===\n")
    
    # Initialize services
    db_session = next(get_db())
    db_repository = DatabaseRepository(db_session)
    upi_service = UPIService()
    payment_service = PaymentRequestService(db_repository, upi_service)
    
    try:
        # Get overall statistics for last 30 days
        stats = await payment_service.get_payment_request_statistics(days=30)
        
        print("=== Payment Request Statistics (Last 30 Days) ===")
        print(f"Total Requests: {stats.get('total_requests', 0)}")
        print(f"Successful Deliveries: {stats.get('successful_deliveries', 0)}")
        print(f"Failed Deliveries: {stats.get('failed_deliveries', 0)}")
        print(f"WhatsApp Deliveries: {stats.get('whatsapp_deliveries', 0)}")
        print(f"SMS Deliveries: {stats.get('sms_deliveries', 0)}")
        print(f"Confirmed Payments: {stats.get('confirmed_payments', 0)}")
        print(f"Success Rate: {stats.get('success_rate', 0.0):.1%}")
        print(f"Confirmation Rate: {stats.get('confirmation_rate', 0.0):.1%}")
        
    except Exception as e:
        print(f"Error getting statistics: {e}")


async def main():
    """Run all examples"""
    print("🚀 Payment Request Service Examples\n")
    
    # Run examples
    await example_distribute_payment_requests()
    print("\n" + "="*60 + "\n")
    
    await example_send_payment_reminders()
    print("\n" + "="*60 + "\n")
    
    await example_process_payment_confirmation()
    print("\n" + "="*60 + "\n")
    
    await example_payment_message_templates()
    print("\n" + "="*60 + "\n")
    
    await example_get_statistics()
    
    print("\n✅ All examples completed!")


if __name__ == "__main__":
    # Note: In a real application, you would have proper database setup
    # and configuration. This example assumes a working database connection.
    
    print("Note: This example requires a working database connection.")
    print("Make sure to set up your database and configuration before running.\n")
    
    # Uncomment the line below to run the examples
    # asyncio.run(main())
    
    print("Example code is ready to run with proper database setup!")