# UPI Service Documentation

## Overview

The UPI Service provides comprehensive UPI (Unified Payments Interface) payment link generation and validation functionality for the Bill Splitting Agent. It supports multiple UPI applications and handles payment request creation with proper validation and error handling.

## Features

- **Multi-App Support**: Generate UPI links for Google Pay, PhonePe, Paytm, BHIM, and generic UPI apps
- **Link Validation**: Comprehensive validation of UPI links and parameters
- **Error Handling**: Robust error handling with detailed error messages
- **Message Creation**: Formatted payment messages for WhatsApp/SMS delivery
- **Security**: Input sanitization and validation to prevent malicious inputs

## Requirements Implemented

- **Requirement 4.1**: Generate UPI deeplinks for each participant with their specific amount
- **Requirement 4.5**: Store tracking information in the database

## Architecture

### UPI Service (`app/services/upi_service.py`)

The core UPI service handles:
- UPI link generation for different apps
- Link validation and parameter extraction
- Text sanitization and input validation
- Payment message formatting

### Payment Service (`app/services/payment_service.py`)

The payment service integrates UPI functionality with the database:
- Creates payment requests with UPI links
- Manages payment tracking and confirmation
- Handles payment status updates
- Provides health checks and monitoring

## Supported UPI Apps

| App | Scheme | Display Name |
|-----|--------|--------------|
| Generic | `upi://pay` | Any UPI App |
| Google Pay | `gpay://upi/pay` | Google Pay |
| PhonePe | `phonepe://pay` | PhonePe |
| Paytm | `paytmmp://pay` | Paytm |
| BHIM | `bhim://pay` | BHIM |

## Usage Examples

### Basic UPI Link Generation

```python
from app.services.upi_service import UPIService, UPIApp
from decimal import Decimal

# Initialize service
upi_service = UPIService(default_upi_id="merchant@upi")

# Generate basic UPI link
link = upi_service.generate_upi_link(
    recipient_name="John Doe",
    amount=Decimal("250.50"),
    description="Dinner bill split"
)
# Result: upi://pay?pa=merchant%40upi&am=250.50&cu=INR&pn=Bill%20Splitter&tn=Dinner%20bill%20split%20-%20John%20Doe
```

### App-Specific Links

```python
# Generate Google Pay specific link
gpay_link = upi_service.generate_upi_link(
    recipient_name="Jane Smith",
    amount=Decimal("100"),
    description="Coffee",
    upi_app=UPIApp.GPAY
)
# Result: gpay://upi/pay?pa=merchant%40upi&am=100&cu=INR&pn=Bill%20Splitter&tn=Coffee%20-%20Jane%20Smith
```

### Multiple App Links

```python
# Generate links for multiple apps
multi_links = upi_service.generate_multiple_app_links(
    recipient_name="Bob Wilson",
    amount=Decimal("300"),
    description="Movie tickets",
    apps=[UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE]
)
# Result: Dictionary with app-specific links
```

### Link Validation

```python
# Validate UPI link
is_valid, error = upi_service.validate_upi_link(
    "upi://pay?pa=test@upi&am=100&cu=INR&tn=Test"
)
if is_valid:
    print("Valid UPI link")
else:
    print(f"Invalid link: {error}")
```

### Payment Message Creation

```python
# Create formatted payment message
message = upi_service.create_payment_message(
    recipient_name="Alice Brown",
    amount=Decimal("175.75"),
    description="Grocery shopping",
    upi_link="upi://pay?pa=store@upi&am=175.75"
)
# Result: Formatted WhatsApp/SMS message with payment details
```

## Payment Service Integration

### Creating Payment Requests

```python
from app.services.payment_service import PaymentService

# Initialize payment service
payment_service = PaymentService(
    upi_service=upi_service,
    payment_repository=payment_repo,
    default_upi_id="billsplitter@upi"
)

# Create payment requests for participants
payment_requests = await payment_service.create_payment_requests(
    bill_id="bill-123",
    participants=participants_list
)
```

### Payment Confirmation

```python
# Confirm payment received
success = await payment_service.confirm_payment("request-id-123")
if success:
    print("Payment confirmed successfully")
```

## Validation Rules

### UPI ID Validation
- Format: `username@bank` (e.g., `user@paytm`, `9876543210@ybl`)
- Must contain exactly one `@` symbol
- Username and bank parts must be non-empty
- Only alphanumeric characters, dots, hyphens, and underscores allowed

### Amount Validation
- Must be positive (> 0)
- Maximum amount: ₹1,00,000
- Supports decimal values (e.g., 250.50)

### Text Sanitization
- Removes special characters except alphanumeric, spaces, and hyphens
- Limits length to 50 characters for UPI parameters
- Trims whitespace

## Error Handling

### UPIValidationError
Raised when:
- Invalid UPI ID format
- Invalid amount (zero, negative, or too large)
- UPI link generation fails
- Link validation fails

### Error Recovery
- Graceful degradation when external services fail
- Detailed error messages for debugging
- Logging of all errors with context

## Security Considerations

### Input Sanitization
- All text inputs are sanitized before use
- Special characters are removed or encoded
- Length limits enforced

### Data Protection
- No storage of actual UPI credentials
- UPI IDs are validated but not stored permanently
- Payment links are generated on-demand

### Validation
- Comprehensive validation of all inputs
- UPI link format validation
- Parameter validation (amount, UPI ID, etc.)

## Configuration

### Environment Variables
```bash
# Default UPI ID for the system
DEFAULT_UPI_ID=billsplitter@upi

# Maximum payment amount (optional)
MAX_PAYMENT_AMOUNT=100000
```

### Service Configuration
```python
# Initialize with custom settings
upi_service = UPIService(
    default_upi_id="custom@bank"
)
```

## Testing

### Unit Tests
- Comprehensive test suite in `tests/test_upi_service.py`
- Tests all UPI apps and validation scenarios
- Error handling and edge case testing

### Validation Script
- `validate_upi_service.py` for comprehensive validation
- Tests all functionality with real examples
- Performance and reliability testing

### Example Scripts
- `examples/upi_service_example.py` demonstrates usage
- Real-world scenarios and use cases
- Integration examples

## API Reference

### UPIService Class

#### Methods

##### `generate_upi_link(recipient_name, amount, description, upi_app=None, payee_upi_id=None)`
Generate UPI deeplink for payment.

**Parameters:**
- `recipient_name` (str): Name of the person who should pay
- `amount` (Decimal): Amount to be paid
- `description` (str): Payment description
- `upi_app` (UPIApp, optional): Target UPI app
- `payee_upi_id` (str, optional): Custom payee UPI ID

**Returns:** `str` - Generated UPI deeplink

**Raises:** `UPIValidationError` - If validation fails

##### `validate_upi_link(upi_link)`
Validate UPI link format and parameters.

**Parameters:**
- `upi_link` (str): UPI link to validate

**Returns:** `Tuple[bool, Optional[str]]` - (is_valid, error_message)

##### `create_payment_message(recipient_name, amount, description, upi_link)`
Create formatted payment message for WhatsApp/SMS.

**Parameters:**
- `recipient_name` (str): Name of the person who should pay
- `amount` (Decimal): Amount to be paid
- `description` (str): Payment description
- `upi_link` (str): Generated UPI link

**Returns:** `str` - Formatted payment message

### PaymentService Class

#### Methods

##### `create_payment_requests(bill_id, participants)`
Create payment requests for all participants.

**Parameters:**
- `bill_id` (str): Bill ID
- `participants` (List[Participant]): List of participants with amounts

**Returns:** `List[PaymentRequest]` - Created payment requests

##### `confirm_payment(request_id)`
Confirm payment received.

**Parameters:**
- `request_id` (str): Payment request ID

**Returns:** `bool` - True if confirmation successful

## Monitoring and Health Checks

### Health Check Endpoint
```python
health_status = await payment_service.health_check()
# Returns service status and operational metrics
```

### Logging
- All operations are logged with appropriate levels
- Error logging includes context and stack traces
- Performance metrics for link generation

## Future Enhancements

### Planned Features
- QR code generation for UPI links
- Payment status webhooks
- Advanced analytics and reporting
- Multi-currency support
- Custom UPI app integration

### Performance Optimizations
- Caching of frequently used UPI configurations
- Batch processing for multiple payment requests
- Async processing for large participant lists

## Troubleshooting

### Common Issues

#### Invalid UPI ID Error
- Check UPI ID format: `username@bank`
- Ensure no special characters in username
- Verify bank code is valid

#### Amount Validation Error
- Ensure amount is positive
- Check amount doesn't exceed ₹1,00,000
- Use Decimal type for precise amounts

#### Link Generation Failure
- Verify all required parameters are provided
- Check for special characters in description
- Ensure recipient name is not empty

### Debug Mode
Enable debug logging to see detailed operation logs:
```python
import logging
logging.getLogger('app.services.upi_service').setLevel(logging.DEBUG)
```

## Support

For issues or questions regarding the UPI service:
1. Check the test files for usage examples
2. Review the validation script for comprehensive testing
3. Enable debug logging for detailed operation traces
4. Consult the error messages for specific validation failures