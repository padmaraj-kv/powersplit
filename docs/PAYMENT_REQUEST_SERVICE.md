# Payment Request Distribution Service

The Payment Request Distribution Service is a comprehensive system for distributing payment requests to bill participants via WhatsApp and SMS, with delivery tracking, fallback mechanisms, and personalized message templates.

## Overview

This service implements **Requirements 4.1, 4.2, 4.3, 4.4, and 4.5** from the bill splitting agent specification:

- **4.1**: Generate UPI deeplinks for each participant with their specific amount
- **4.2**: Send WhatsApp messages to each participant with their payment link
- **4.3**: Send SMS as fallback when WhatsApp delivery fails
- **4.4**: Send confirmation message to original user when all messages are sent
- **4.5**: Store tracking information in the database

## Features

### Core Functionality
- **Multi-channel Delivery**: WhatsApp primary, SMS fallback via Siren AI Toolkit
- **UPI Integration**: Automatic UPI deeplink generation for instant payments
- **Personalized Messages**: Custom message templates with participant names and amounts
- **Delivery Tracking**: Complete tracking of message delivery status and attempts
- **Payment Confirmation**: Process payment confirmations from participants
- **Reminder System**: Send payment reminders to unpaid participants
- **Statistics**: Comprehensive delivery and payment statistics

### Message Templates
- **Payment Requests**: Friendly, personalized payment request messages
- **Reminders**: Escalating reminder messages based on reminder count
- **Confirmations**: Organizer notifications for payment confirmations
- **Completion**: Celebration messages when all payments are complete

## Architecture

```mermaid
graph TB
    PS[Payment Request Service] --> DB[Database Repository]
    PS --> UPI[UPI Service]
    PS --> COMM[Communication Service]
    
    COMM --> SIREN[Siren Client]
    SIREN --> WA[WhatsApp]
    SIREN --> SMS[SMS]
    
    UPI --> LINKS[UPI Deeplinks]
    
    DB --> BILLS[(Bills)]
    DB --> PARTICIPANTS[(Participants)]
    DB --> REQUESTS[(Payment Requests)]
    
    PS --> TEMPLATES[Message Templates]
    PS --> TRACKING[Delivery Tracking]
```

## Usage

### Basic Payment Request Distribution

```python
from app.services.payment_request_service import PaymentRequestService
from app.services.upi_service import UPIService
from app.database.repositories import DatabaseRepository

# Initialize service
db_repository = DatabaseRepository(db_session)
upi_service = UPIService(default_upi_id="your-business@upi")
payment_service = PaymentRequestService(db_repository, upi_service)

# Distribute payment requests
summary = await payment_service.distribute_payment_requests(
    bill_id="bill-uuid",
    organizer_phone="+919876543210",
    custom_message="Please pay by tomorrow evening. Thanks!"
)

print(f"Sent {summary.successful_sends}/{summary.total_participants} requests")
```

### Send Payment Reminders

```python
# Send reminders to all unpaid participants
reminder_summary = await payment_service.send_payment_reminder(
    bill_id="bill-uuid",
    custom_message="Friendly reminder: Please complete your payment when convenient."
)

# Send reminders to specific participants only
reminder_summary = await payment_service.send_payment_reminder(
    bill_id="bill-uuid",
    participant_ids=["participant-uuid-1", "participant-uuid-2"],
    custom_message="Second reminder - please pay soon!"
)
```

### Process Payment Confirmations

```python
# Process when participant replies "DONE" or "PAID"
success = await payment_service.process_payment_confirmation(
    participant_phone="+919876543211",
    bill_id="bill-uuid",
    confirmation_message="DONE - paid via GPay"
)

if success:
    print("Payment confirmed and organizer notified!")
```

### Get Statistics

```python
# Get payment request statistics
stats = await payment_service.get_payment_request_statistics(
    bill_id="bill-uuid",  # Optional: specific bill
    days=30               # Last 30 days
)

print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Confirmation rate: {stats['confirmation_rate']:.1%}")
```

## Message Templates

### Payment Request Message

```
Hi Alice! 👋

You have a bill split payment request:

💰 Amount: ₹500.00
📝 Description: Team Dinner at Restaurant

📋 Note: Please pay by tomorrow evening. Thanks!

Click the link below to pay instantly:
upi://pay?pa=restaurant@upi&am=500.00&tn=Team%20Dinner

Or reply "DONE" once you've completed the payment.

Thanks! 🙏
```

### Payment Reminder Message

```
Hi Bob! Just checking in! 👋

You still have a pending payment for:

💰 Amount: ₹300.00
📝 Description: Movie Night

📋 Note: Hope you enjoyed the movie!

You can pay using this link:
upi://pay?pa=movies@upi&am=300.00&tn=Movie%20Night

Or reply "DONE" if you've already paid.

Thanks for your patience! 🙏
```

### Organizer Confirmation Message

```
✅ Payment requests sent successfully!

📋 Bill: Team Dinner at Restaurant
💰 Total Amount: ₹1500.00
👥 Participants: 3

📊 Delivery Summary:
✅ Successful: 3
❌ Failed: 0
📱 WhatsApp: 3
💬 SMS: 0

I'll notify you when participants confirm their payments.

You can check payment status anytime by asking 'show bill status'.
```

## Data Models

### PaymentRequestResult

```python
@dataclass
class PaymentRequestResult:
    participant_id: str
    participant_name: str
    phone_number: str
    amount: Decimal
    success: bool
    delivery_method: Optional[DeliveryMethod]
    fallback_used: bool
    upi_link: str
    message_sent: str
    error: Optional[str] = None
    payment_request_id: Optional[str] = None
```

### DistributionSummary

```python
@dataclass
class DistributionSummary:
    bill_id: str
    total_participants: int
    successful_sends: int
    failed_sends: int
    whatsapp_sends: int
    sms_sends: int
    results: List[PaymentRequestResult]
    started_at: datetime
    completed_at: datetime
```

## Error Handling

The service implements comprehensive error handling:

### Delivery Failures
- **WhatsApp Failure**: Automatically falls back to SMS
- **SMS Failure**: Logs error and marks as failed
- **Network Issues**: Retries with exponential backoff
- **Invalid Phone Numbers**: Validates and reports errors

### Data Validation
- **Missing Contacts**: Reports missing participant information
- **Invalid Amounts**: Validates payment amounts
- **Bill Not Found**: Handles non-existent bills gracefully
- **Already Paid**: Skips participants who have already paid

### Recovery Mechanisms
- **Partial Failures**: Continues processing other participants
- **Retry Logic**: Automatic retry for transient failures
- **Graceful Degradation**: Provides fallback options when services are unavailable

## Database Integration

### Tables Used
- **bills**: Bill information and status
- **bill_participants**: Participant amounts and payment status
- **contacts**: Participant contact information (encrypted)
- **payment_requests**: Payment request tracking and delivery status

### Key Operations
- **Create Payment Requests**: Store UPI links and tracking information
- **Update Delivery Status**: Track WhatsApp/SMS delivery attempts
- **Confirm Payments**: Mark participants as paid and update timestamps
- **Statistics Queries**: Generate delivery and payment analytics

## Security Features

### Data Protection
- **Encrypted Storage**: Contact information encrypted at rest
- **No Payment Credentials**: Never stores actual payment details
- **Secure UPI Links**: Properly formatted and validated UPI deeplinks
- **Access Control**: Users can only access their own bills

### Privacy Compliance
- **Data Minimization**: Only stores necessary information
- **Retention Policies**: Automatic cleanup of old data
- **User Consent**: Clear consent for data storage and processing

## Configuration

### Environment Variables

```bash
# UPI Configuration
DEFAULT_UPI_ID=your-business@upi

# Siren Configuration
SIREN_API_KEY=your-siren-api-key
SIREN_BASE_URL=https://api.siren.ai
SIREN_WEBHOOK_SECRET=your-webhook-secret

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost/billsplitter
```

### Service Configuration

```python
# Custom UPI ID for your business
upi_service = UPIService(default_upi_id="mybusiness@paytm")

# Custom message templates
payment_service.templates["payment_request"] = custom_template

# Delivery retry configuration
payment_service.max_retries = 3
payment_service.retry_delay = 2.0
```

## Testing

### Unit Tests
```bash
# Run payment request service tests
python -m pytest tests/test_payment_request_service.py -v

# Run with coverage
python -m pytest tests/test_payment_request_service.py --cov=app.services.payment_request_service
```

### Integration Tests
```bash
# Run simple integration test
python test_payment_request_simple.py

# Run full validation suite
python validate_payment_request_service.py
```

### Mock Testing
The service includes comprehensive mocks for testing:
- **MockDatabaseRepository**: In-memory database simulation
- **MockCommunicationService**: Simulated message delivery
- **MockUPIService**: UPI link generation testing

## Performance Considerations

### Concurrent Processing
- **Bulk Operations**: Process multiple participants concurrently
- **Rate Limiting**: Respect API rate limits (5 concurrent requests)
- **Timeout Handling**: Proper timeout configuration for external services

### Scalability
- **Database Indexing**: Optimized queries with proper indexes
- **Connection Pooling**: Efficient database connection management
- **Caching**: Cache frequently accessed data

### Monitoring
- **Delivery Metrics**: Track success rates and delivery times
- **Error Logging**: Comprehensive error logging and alerting
- **Performance Metrics**: Monitor response times and throughput

## Troubleshooting

### Common Issues

#### Messages Not Delivering
1. Check Siren API credentials and configuration
2. Verify phone number formats (+91XXXXXXXXXX)
3. Check API rate limits and quotas
4. Verify webhook configuration for delivery confirmations

#### UPI Links Not Working
1. Validate UPI ID format (user@bank)
2. Check amount formatting (decimal with 2 places)
3. Verify UPI app compatibility
4. Test with different UPI apps

#### Database Errors
1. Check database connection and credentials
2. Verify table schemas and migrations
3. Check for encryption key configuration
4. Monitor database connection pool

### Debug Mode
Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('app.services.payment_request_service').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Rich Media Messages**: Support for images and documents
- **Payment Status Webhooks**: Real-time payment confirmations
- **Multi-language Support**: Localized message templates
- **Advanced Analytics**: Detailed payment behavior analytics
- **Scheduled Reminders**: Automatic reminder scheduling

### Integration Opportunities
- **Payment Gateways**: Direct integration with payment processors
- **Banking APIs**: Real-time payment verification
- **Notification Services**: Push notifications and email alerts
- **CRM Integration**: Customer relationship management features

## Support

For issues, questions, or contributions:

1. **Documentation**: Check this guide and inline code comments
2. **Examples**: Review the examples in `examples/payment_request_service_example.py`
3. **Tests**: Run the test suite to verify functionality
4. **Logs**: Check application logs for detailed error information

The Payment Request Distribution Service is designed to be robust, scalable, and user-friendly, providing a complete solution for automated bill splitting and payment collection.