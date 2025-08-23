# ContactManager Documentation

## Overview

The ContactManager is a service responsible for managing participant contacts in the bill splitting system. It handles contact creation, validation, deduplication, and the complete workflow for collecting participant information.

## Features

### Core Functionality
- **Contact Management**: Create, retrieve, and manage user contacts
- **Phone Number Validation**: Validate and format phone numbers for consistency
- **Contact Deduplication**: Prevent duplicate contacts and merge information
- **Auto-population**: Automatically populate participant information from contact history
- **Missing Contact Handling**: Interactive workflow for collecting missing contact information

### Requirements Implementation
- **Requirement 3.1**: Provide contact details for bill participants
- **Requirement 3.2**: Auto-populate contact information from database
- **Requirement 3.3**: Store new contacts in database for future use
- **Requirement 3.4**: Handle missing contact information with user prompts
- **Requirement 3.5**: Validate contact information before processing

## API Reference

### ContactManager Class

#### Constructor
```python
ContactManager(contact_repo: ContactRepository, user_repo: UserRepository)
```

#### Main Methods

##### collect_participants_workflow
```python
async def collect_participants_workflow(
    user_id: str, 
    participants: List[Participant]
) -> Tuple[List[Participant], List[str]]
```
Main workflow for collecting participant contacts with missing contact handling.

**Parameters:**
- `user_id`: ID of the user creating the bill
- `participants`: List of participants with potentially incomplete contact info

**Returns:**
- Tuple of (updated_participants, missing_contact_questions)

##### find_or_create_contact
```python
async def find_or_create_contact(
    user_id: str, 
    name: str, 
    phone_number: str
) -> str
```
Find existing contact or create new one with deduplication.

**Parameters:**
- `user_id`: ID of the user
- `name`: Contact name
- `phone_number`: Contact phone number

**Returns:**
- Contact ID (string)

##### validate_phone_number
```python
def validate_phone_number(phone_number: str) -> bool
```
Validate phone number format.

**Parameters:**
- `phone_number`: Phone number to validate

**Returns:**
- True if valid, False otherwise

**Supported Formats:**
- Indian mobile numbers: `9876543210`, `+919876543210`
- International numbers: `+1234567890`, `+447123456789`

##### format_phone_number
```python
def format_phone_number(phone_number: str) -> str
```
Format phone number to consistent format.

**Parameters:**
- `phone_number`: Raw phone number

**Returns:**
- Formatted phone number

**Formatting Rules:**
- Indian numbers: Adds `+91` prefix if missing
- International numbers: Preserves existing `+` prefix
- Removes spaces, dashes, and other formatting characters

##### validate_participants
```python
async def validate_participants(
    participants: List[Participant]
) -> ValidationResult
```
Validate participant list for completeness and correctness.

**Parameters:**
- `participants`: List of participants to validate

**Returns:**
- ValidationResult with errors and warnings

**Validation Checks:**
- Name is required and not empty
- Phone number is required and valid format
- Amount owed is positive
- No duplicate phone numbers
- No duplicate names (warning only)

##### deduplicate_contacts
```python
async def deduplicate_contacts(
    user_id: str, 
    participants: List[Participant]
) -> List[Participant]
```
Remove duplicate contacts and merge information.

**Parameters:**
- `user_id`: ID of the user
- `participants`: List of participants that may contain duplicates

**Returns:**
- Deduplicated list of participants

##### auto_populate_from_history
```python
async def auto_populate_from_history(
    user_id: str, 
    participant_names: List[str]
) -> List[Participant]
```
Auto-populate participant information from contact history.

**Parameters:**
- `user_id`: ID of the user
- `participant_names`: List of participant names to look up

**Returns:**
- List of participants with auto-populated contact info

##### handle_missing_contacts
```python
async def handle_missing_contacts(
    user_id: str, 
    participants: List[Participant], 
    user_responses: Dict[str, str]
) -> Tuple[List[Participant], List[str]]
```
Handle user responses for missing contact information.

**Parameters:**
- `user_id`: ID of the user
- `participants`: Current participant list
- `user_responses`: User responses to missing contact questions

**Returns:**
- Tuple of (updated_participants, remaining_questions)

## Usage Examples

### Basic Contact Operations
```python
# Initialize ContactManager
contact_manager = ContactManager(contact_repo, user_repo)

# Create or find contact
contact_id = await contact_manager.find_or_create_contact(
    user_id="123", 
    name="John Doe", 
    phone_number="+919876543210"
)

# Get all user contacts
contacts = await contact_manager.get_user_contacts(user_id="123")
```

### Phone Number Validation
```python
# Validate phone numbers
valid = contact_manager.validate_phone_number("+919876543210")  # True
invalid = contact_manager.validate_phone_number("invalid")      # False

# Format phone numbers
formatted = contact_manager.format_phone_number("9876543210")   # "+919876543210"
```

### Participant Workflow
```python
# Define participants
participants = [
    Participant(name="Alice", phone_number="9876543210", amount_owed=100.00),
    Participant(name="Bob", phone_number="", amount_owed=150.00)  # Missing phone
]

# Run collection workflow
updated_participants, missing_questions = await contact_manager.collect_participants_workflow(
    user_id="123", 
    participants=participants
)

# Handle missing contacts
if missing_questions:
    user_responses = {"Bob_phone": "+919876543211"}
    final_participants, remaining = await contact_manager.handle_missing_contacts(
        user_id="123",
        participants=participants,
        user_responses=user_responses
    )
```

### Validation and Deduplication
```python
# Validate participants
validation_result = await contact_manager.validate_participants(participants)
if not validation_result.is_valid:
    print("Validation errors:", validation_result.errors)

# Deduplicate contacts
deduplicated = await contact_manager.deduplicate_contacts(user_id="123", participants)
```

## Error Handling

The ContactManager handles various error scenarios:

### Phone Number Errors
- Invalid format: Returns validation error
- Missing phone number: Adds to missing questions list
- Duplicate phone numbers: Validation error

### Database Errors
- Connection failures: Propagates exception with logging
- Constraint violations: Handles gracefully with error messages

### Validation Errors
- Missing required fields: Clear error messages
- Invalid data formats: Specific validation feedback

## Integration

### With Conversation Flow
The ContactManager integrates with the conversation system through the `ContactCollectionHandler`:

```python
class ContactCollectionHandler(BaseStepHandler):
    def __init__(self, ai_service, contact_manager):
        self.contact_manager = contact_manager
    
    async def handle_message(self, state, message):
        # Use contact_manager for participant collection
        participants, questions = await self.contact_manager.collect_participants_workflow(
            state.user_id, state.participants
        )
```

### With Database
The ContactManager uses repository interfaces for data access:

- `ContactRepository`: For contact CRUD operations
- `UserRepository`: For user-related operations

### With Encryption
Contact information is automatically encrypted when stored through the repository layer using the database models' encryption features.

## Testing

### Unit Tests
- Phone number validation and formatting
- Contact creation and retrieval
- Participant validation logic
- Deduplication algorithms

### Integration Tests
- Database operations with real repositories
- End-to-end workflow testing
- Error handling scenarios

### Example Test
```python
@pytest.mark.asyncio
async def test_contact_workflow():
    contact_manager = ContactManager(mock_contact_repo, mock_user_repo)
    
    participants = [
        Participant(name="Alice", phone_number="9876543210", amount_owed=100.00)
    ]
    
    updated, missing = await contact_manager.collect_participants_workflow(
        "user123", participants
    )
    
    assert len(updated) == 1
    assert len(missing) == 0
    assert updated[0].contact_id is not None
```

## Configuration

The ContactManager uses the following configuration:

### Phone Number Validation
- Supports Indian mobile numbers (10 digits, starting with 6-9)
- Supports international numbers (10-15 digits with country code)
- Automatic formatting with country code prefixes

### Contact Deduplication
- Case-insensitive name matching
- Phone number normalization for duplicate detection
- Preference for existing contact information

## Performance Considerations

### Database Queries
- Efficient contact lookups using indexed phone numbers
- Batch operations for multiple participants
- Minimal database round trips

### Memory Usage
- Processes participants in batches
- Efficient data structures for deduplication
- Minimal object creation overhead

### Caching
- Contact information cached during workflow
- Reduced database queries for repeated operations

## Security

### Data Protection
- Phone numbers encrypted at rest through database models
- No sensitive data in logs
- Secure contact information handling

### Input Validation
- Comprehensive phone number validation
- SQL injection prevention through parameterized queries
- Input sanitization for all user data

## Future Enhancements

### Planned Features
- Contact import from external sources
- Advanced contact matching algorithms
- Contact groups and categories
- Contact sharing between users

### Performance Improvements
- Contact caching layer
- Bulk contact operations
- Optimized database queries

### User Experience
- Smart contact suggestions
- Contact verification workflows
- Enhanced error messages