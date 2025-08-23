# Siren AI Toolkit Integration

This document describes the integration with Siren AI Toolkit for WhatsApp and SMS messaging in the Bill Splitting Agent.

## Overview

The Siren integration provides:
- WhatsApp message sending with SMS fallback
- Webhook handling for incoming messages
- Secure signature validation
- Bulk message sending capabilities
- Delivery status tracking

## Components

### 1. SirenClient (`app/services/siren_client.py`)

Core client for interacting with Siren AI Toolkit API.

**Key Features:**
- WhatsApp and SMS message sending
- Automatic fallback from WhatsApp to SMS
- Phone number formatting and validation
- Webhook signature validation
- Bulk message sending with rate limiting

**Usage:**
```python
from app.services.siren_client import siren_client

# Send WhatsApp message
result = await siren_client.send_whatsapp_message(
    phone_number="+919876543210",
    message="Hello from Bill Splitting Agent!"
)

# Send with fallback
result = await siren_client.send_message_with_fallback(
    phone_number="+919876543210",
    message="This will try WhatsApp first, then SMS"
)
```

### 2. CommunicationService (`app/services/communication_service.py`)

High-level service implementing the CommunicationServiceInterface.

**Key Features:**
- Implements business logic for message delivery
- Delivery attempt logging and statistics
- Phone number validation
- Bulk messaging with concurrency control

**Usage:**
```python
from app.services.communication_service import communication_service

# Send message with automatic fallback
result = await communication_service.send_message_with_fallback(
    phone_number="+919876543210",
    message="Your bill split is ready!"
)

# Get delivery statistics
stats = await communication_service.get_delivery_statistics()
print(f"Success rate: {stats['success_rate']:.2%}")
```

### 3. Webhook Handler (`app/api/routes/webhooks.py`)

FastAPI routes for handling incoming Siren webhooks.

**Endpoints:**
- `POST /api/v1/webhooks/siren/message` - Receive incoming messages
- `POST /api/v1/webhooks/siren/delivery-status` - Receive delivery status updates
- `GET /api/v1/webhooks/siren/health` - Health check for Siren integration

**Security:**
- Webhook signature validation using HMAC-SHA256
- Request body validation
- Error handling and logging

## Configuration

Add these environment variables to your `.env` file:

```env
# Siren AI Toolkit Configuration
SIREN_API_KEY=your-siren-api-key
SIREN_WEBHOOK_SECRET=your-webhook-secret
SIREN_BASE_URL=https://api.siren.ai
```

## Webhook Setup

1. Configure your Siren webhook endpoint to point to:
   ```
   https://your-domain.com/api/v1/webhooks/siren/message
   ```

2. Set the webhook secret in your Siren dashboard and in your `.env` file

3. Ensure your server can receive POST requests on the webhook endpoint

## Message Flow

### Outgoing Messages

1. **WhatsApp First**: Attempt to send via WhatsApp
2. **SMS Fallback**: If WhatsApp fails, automatically try SMS
3. **Logging**: Record all delivery attempts with timestamps
4. **Status Tracking**: Monitor delivery status through webhooks

### Incoming Messages

1. **Webhook Receipt**: Siren sends incoming messages to webhook endpoint
2. **Signature Validation**: Verify webhook authenticity
3. **Message Processing**: Convert to internal message format
4. **Response Generation**: Process message and send response
5. **Background Processing**: Handle complex operations asynchronously

## Error Handling

The integration includes comprehensive error handling:

### Network Errors
- Automatic retry with exponential backoff
- Graceful degradation when services are unavailable
- Detailed error logging for debugging

### API Errors
- Specific error types for WhatsApp and SMS failures
- Fallback mechanisms for service outages
- User-friendly error messages

### Validation Errors
- Phone number format validation
- Webhook signature verification
- Message content validation

## Testing

Run the integration tests:

```bash
python -m pytest tests/test_siren_integration.py -v
```

Run the example script:

```bash
python examples/siren_integration_example.py
```

## Security Considerations

### Webhook Security
- All webhooks must include valid HMAC-SHA256 signatures
- Signatures are verified against the configured webhook secret
- Invalid signatures result in 401 Unauthorized responses

### Data Protection
- Phone numbers are formatted and validated before sending
- No sensitive data is logged in plain text
- API keys are stored securely in environment variables

### Rate Limiting
- Bulk message sending includes concurrency limits
- Automatic backoff for rate limit errors
- Delivery attempt tracking to prevent spam

## Monitoring and Logging

### Delivery Statistics
- Success/failure rates by delivery method
- Phone number specific statistics
- Time-based delivery analytics

### Error Logging
- Detailed error logs with context
- Webhook processing logs
- API interaction logs

### Health Checks
- Siren service connectivity monitoring
- Webhook endpoint health verification
- Integration status reporting

## Requirements Mapping

This integration implements the following requirements:

- **Requirement 1.1**: Text message processing via webhooks
- **Requirement 1.2**: Voice message handling (webhook structure)
- **Requirement 1.3**: Image message handling (webhook structure)
- **Requirement 4.1**: WhatsApp message sending
- **Requirement 4.2**: SMS message sending
- **Requirement 4.3**: Automatic fallback from WhatsApp to SMS

## Future Enhancements

- Message template management
- Rich media message support
- Advanced delivery analytics
- Message scheduling capabilities
- Multi-language support