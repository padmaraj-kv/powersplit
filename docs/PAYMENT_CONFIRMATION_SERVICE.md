# Payment Confirmation Service

The Payment Confirmation Service handles payment confirmation message processing, status updates, and notifications for bill creators when participants confirm payments.

## Requirements Implemented

- **5.1**: Process payment confirmation messages from participants
- **5.2**: Update payment status in database when confirmations are received  
- **5.3**: Send notifications to bill creator when payments are confirmed
- **5.5**: Detect completion when all payments are confirmed

## Features

### 🔍 Confirmation Detection
- Automatically detects payment confirmation keywords in messages
- Supports multiple confirmation patterns (done, paid, completed, etc.)
- Recognizes emoji confirmations (✅, 👍)
- Case-insensitive pattern matching

### 📊 Status Management
- Updates participant payment status to CONFIRMED
- Records payment timestamp
- Updates payment request status
- Maintains payment history

### 📧 Notifications
- Sends confirmation notifications to bill organizers
- Provides personalized messages with participant details
- Includes payment amount and bill description
- Sends completion notifications when all payments confirmed

### 🎯 Completion Detection
- Automatically detects when all participants have paid
- Updates bill status to completed
- Sends celebration notification to organizer
- Prevents duplicate completion notifications

### ❓ Payment Inquiries
- Handles status inquiries from participants
- Provides current payment status and bill details
- Includes payment links for pending payments
- Responds to various inquiry patterns

## Usage

### Basic Setup

```python
from app.services.payment_confirmation_service import PaymentConfirmationService
from app.database.repositories import DatabaseRepository

# Initialize service
db_repository = DatabaseRepository(db_session)
confirmation_service = PaymentConfirmationService(db_repository)
```

### Process Payment Confirmation

```python
# Process incoming message for payment confirmation
result = await confirmation_service.process_payment_confirmation_message(
    sender_phone="+919876543211",
    message_content="done",
    message_timestamp=datetime.now()
)

if result.success:
    print(f"Payment confirmed for {result.participant_name}")
    print(f"Amount: ₹{result.amount}")
    print(f"Organizer notified: {result.organizer_notified}")
    print(f"Bill completed: {result.completion_detected}")
else:
    print(f"Confirmation failed: {result.error}")
```

### Handle Payment Inquiries

```python
# Handle payment status inquiry
response = await confirmation_service.handle_payment_inquiry(
    sender_phone="+919876543211",
    message_content="what's my bill status?"
)

if response:
    # Send response back to participant
    await send_message(sender_phone, response)
```

## Confirmation Patterns

The service recognizes various confirmation patterns:

### Keywords
- `done`, `paid`, `complete`, `completed`
- `finished`, `confirmed`, `sent`
- `payment done`, `payment made`, `payment sent`
- `money sent`, `money transferred`

### Emojis
- ✅ (checkmark)
- 👍 (thumbs up)

### Phrases
- "I have paid the amount"
- "Payment completed successfully"
- "Money transferred"

## Message Templates

### Payment Confirmation Notification
```
✅ Payment Confirmed!

John Doe has confirmed payment of ₹100.00 for "Team Dinner".

Great! One less person to follow up with. 😊

You can check the status of all payments by asking "show bill status".
```

### Completion Notification
```
🎉 All Payments Complete!

Fantastic news! All 3 participants have confirmed their payments for "Team Dinner".

💰 Total Amount: ₹300.00
✅ All payments confirmed

The bill is now complete. Thanks for using Bill Splitter! 🙏
```

### Payment Status Response
```
📋 Your Bill Status

Bill: Team Dinner
Your Amount: ₹100.00
Status: Sent

You can pay using this link:
upi://pay?pa=alice@upi&pn=Alice&am=100.00

Reply 'DONE' once you've completed the payment.
```

## Integration with Conversation Flow

The service integrates with the conversation manager to handle confirmations from any conversation step:

```python
# In conversation manager
async def process_message(self, user_id: str, message: Message) -> Response:
    # Check for payment confirmations first
    payment_response = await self._check_payment_confirmation(message)
    if payment_response:
        return payment_response
    
    # Continue with normal conversation flow
    # ...
```

## Database Operations

### Required Repository Methods
- `find_active_participants_by_phone()` - Find participants by phone number
- `update_bill_participant()` - Update participant payment status
- `get_latest_payment_request_for_participant()` - Get payment request
- `update_payment_request()` - Update payment request status
- `get_bill_with_participants()` - Get bill with all participants
- `update_bill()` - Update bill status

### Status Updates
1. **Participant Status**: `SENT` → `CONFIRMED`
2. **Payment Request Status**: `sent` → `confirmed`
3. **Bill Status**: `active` → `completed` (when all paid)

## Error Handling

### Common Scenarios
- **No active participants found**: Returns error message
- **Non-confirmation message**: Ignores message
- **Already confirmed payment**: Acknowledges but doesn't duplicate
- **Database errors**: Logs error and returns failure result
- **Communication failures**: Logs error but continues processing

### Error Response Structure
```python
PaymentConfirmationResult(
    success=False,
    participant_id=None,
    participant_name=None,
    amount=None,
    bill_id=None,
    bill_description=None,
    organizer_notified=False,
    completion_detected=False,
    error="Error description"
)
```

## Testing

### Unit Tests
- Confirmation pattern detection
- Payment status updates
- Notification sending
- Completion detection
- Error handling scenarios

### Integration Tests
- End-to-end confirmation workflow
- Database transaction handling
- Communication service integration
- Multiple participant scenarios

### Example Test
```python
async def test_payment_confirmation():
    # Setup test data
    service = PaymentConfirmationService(mock_db)
    
    # Test confirmation processing
    result = await service.process_payment_confirmation_message(
        sender_phone="+919876543211",
        message_content="done",
        message_timestamp=datetime.now()
    )
    
    assert result.success
    assert result.participant_name == "John Doe"
    assert result.organizer_notified
```

## Performance Considerations

### Optimization Strategies
- **Efficient participant lookup**: Index on phone numbers
- **Batch notifications**: Group multiple confirmations
- **Caching**: Cache active participants for frequent lookups
- **Async processing**: Non-blocking database operations

### Monitoring
- Track confirmation processing times
- Monitor notification delivery rates
- Alert on high error rates
- Log completion detection events

## Security

### Data Protection
- Phone numbers are encrypted in database
- No sensitive payment data stored
- Secure message transmission
- Input validation and sanitization

### Access Control
- Participants can only confirm their own payments
- Organizers receive notifications for their bills only
- No cross-bill data leakage

## Future Enhancements

### Planned Features
- **Partial payment confirmations**: Handle split confirmations
- **Payment proof uploads**: Accept payment screenshots
- **Reminder automation**: Auto-send reminders for pending payments
- **Analytics dashboard**: Payment confirmation statistics
- **Multi-language support**: Confirmation patterns in different languages

### API Extensions
- REST endpoints for confirmation status
- Webhook notifications for external systems
- Bulk confirmation processing
- Payment confirmation analytics

## Troubleshooting

### Common Issues

**Confirmations not detected**
- Check confirmation patterns
- Verify phone number matching
- Ensure participant is active

**Notifications not sent**
- Check communication service status
- Verify organizer phone number
- Check delivery method fallbacks

**Completion not detected**
- Verify all participants confirmed
- Check bill status updates
- Review completion logic

### Debug Information
```python
# Get confirmation statistics
stats = await service.get_payment_confirmation_statistics(
    bill_id="bill-123",
    days=30
)
print(f"Confirmations: {stats['total_confirmations']}")
print(f"Completion rate: {stats['completion_rate']}")
```

## Related Services

- **Payment Request Service**: Sends initial payment requests
- **Communication Service**: Handles message delivery
- **Bill Splitter Service**: Calculates payment amounts
- **Conversation Manager**: Orchestrates overall flow

## Configuration

### Environment Variables
```bash
# Confirmation service settings
CONFIRMATION_PATTERN_TIMEOUT=30  # Pattern matching timeout (seconds)
NOTIFICATION_RETRY_COUNT=3       # Notification delivery retries
COMPLETION_NOTIFICATION_DELAY=5  # Delay before completion notification (seconds)
```

### Service Configuration
```python
# Configure confirmation service
service = PaymentConfirmationService(
    db_repository=db_repo,
    notification_timeout=30,
    retry_count=3
)
```