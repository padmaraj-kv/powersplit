# Bill Extractor Implementation

## Overview

The BillExtractor service is a comprehensive bill extraction and processing system that handles multi-modal input (text, voice, and image) to extract, validate, and confirm bill information. This implementation fulfills task 6 of the bill splitting agent project.

## Features

### Multi-Modal Input Support
- **Text Processing**: Extracts bill information from text messages using AI services
- **Voice Processing**: Converts voice messages to text and extracts bill data
- **Image Processing**: Processes bill photos using computer vision to extract structured data

### Data Validation and Normalization
- Comprehensive validation of extracted bill data
- Business rule validation (amount limits, data consistency)
- Data normalization (precision, formatting, cleanup)
- Intelligent error reporting with user-friendly messages

### Clarifying Questions Generation
- AI-powered question generation for incomplete data
- Fallback rule-based questions when AI services are unavailable
- Context-aware questions based on missing information

### Bill Confirmation and Summary
- User-friendly bill summaries with formatted display
- Intelligent confirmation processing using intent recognition
- Support for various confirmation responses (yes/no/ambiguous)
- Fallback keyword matching when AI services fail

## Architecture

### Class Structure

```python
class BillExtractor(BillExtractorInterface):
    """Main bill extraction service"""
    
    def __init__(self, ai_service: Optional[AIService] = None)
    
    # Core extraction methods
    async def extract_bill_data(self, message: Message) -> BillData
    async def validate_bill_data(self, bill_data: BillData) -> ValidationResult
    async def generate_clarifying_questions(self, bill_data: BillData) -> List[str]
    async def create_bill_summary(self, bill_data: BillData) -> str
    async def process_bill_confirmation(self, message: Message, bill_data: BillData) -> Tuple[bool, Optional[str]]
```

### Dependencies

- **AIService**: Handles AI integrations (Sarvam, Gemini, LiteLLM)
- **Pydantic Models**: Data validation and serialization
- **Logging**: Comprehensive error and operation logging

## Implementation Details

### 1. Multi-Modal Extraction

#### Text Extraction
```python
async def _extract_from_text(self, message: Message) -> BillData:
    """Extract bill data from text message"""
    return await self.ai_service.extract_from_text(message.content)
```

#### Voice Extraction
```python
async def _extract_from_voice(self, message: Message) -> BillData:
    """Extract bill data from voice message"""
    audio_data = message.metadata.get("audio_data")
    if not audio_data:
        raise BillExtractionError("No audio data found in voice message")
    return await self.ai_service.extract_from_voice(audio_data)
```

#### Image Extraction
```python
async def _extract_from_image(self, message: Message) -> BillData:
    """Extract bill data from image message"""
    image_data = message.metadata.get("image_data")
    if not image_data:
        raise BillExtractionError("No image data found in image message")
    return await self.ai_service.extract_from_image(image_data)
```

### 2. Data Validation

#### Business Rules Validation
- Amount validation (minimum/maximum limits)
- Items total vs bill total consistency check
- Required field validation
- Date validation (future date warnings)

#### AI-Enhanced Validation
- Uses AI service for comprehensive validation
- Combines AI validation with business rules
- Provides detailed error messages and warnings

### 3. Clarifying Questions

#### AI-Generated Questions
- Context-aware question generation
- Identifies missing critical information
- Generates natural language questions

#### Fallback Questions
- Rule-based questions when AI fails
- Covers essential missing information
- Limited to 3 questions to avoid overwhelming users

### 4. Bill Summary Creation

#### Formatted Display
```
📋 *Bill Summary*

🏪 *Restaurant/Store:* Pizza Palace
💰 *Total Amount:* ₹150.00
📅 *Date:* 15 Jan 2024, 12:30 PM
📝 *Description:* Lunch at Pizza Palace

🛍️ *Items:*
  • Margherita Pizza - ₹120.00
  • Coke - ₹30.00

Is this information correct? Reply *yes* to continue or *no* to make changes.
```

### 5. Confirmation Processing

#### Intent Recognition
- Uses AI service to understand user intent
- Supports various confirmation patterns
- Handles ambiguous responses gracefully

#### Fallback Processing
- Keyword-based matching when AI fails
- Supports common confirmation words
- Provides clear guidance for unclear responses

## Integration with Step Handlers

### BillExtractionHandler Integration

The BillExtractor is integrated into the conversation flow through the `BillExtractionHandler`:

```python
class BillExtractionHandler(BaseStepHandler):
    def __init__(self, bill_extractor: Optional[BillExtractor] = None):
        self.bill_extractor = bill_extractor or BillExtractor()
    
    async def handle_message(self, state: ConversationState, message: Message) -> StepResult:
        # Uses BillExtractor for all extraction and validation logic
        bill_data = await self.bill_extractor.extract_bill_data(message)
        validation_result = await self.bill_extractor.validate_bill_data(bill_data)
        # ... rest of the flow
```

### BillConfirmationHandler Integration

```python
class BillConfirmationHandler(BaseStepHandler):
    def __init__(self, bill_extractor: Optional[BillExtractor] = None):
        self.bill_extractor = bill_extractor or BillExtractor()
    
    async def handle_message(self, state: ConversationState, message: Message) -> StepResult:
        # Uses BillExtractor for confirmation processing
        is_confirmed, error_message = await self.bill_extractor.process_bill_confirmation(message, bill_data)
        # ... handle confirmation result
```

## Error Handling

### Exception Hierarchy
- `BillExtractionError`: Base exception for extraction failures
- Graceful degradation when AI services are unavailable
- Comprehensive error logging for debugging

### Fallback Mechanisms
- Rule-based extraction when AI fails
- Basic validation when AI validation fails
- Keyword matching for confirmations
- Generic clarifying questions

## Testing

### Unit Tests
- Comprehensive test coverage in `tests/test_bill_extractor.py`
- Tests for all extraction methods
- Validation testing with various scenarios
- Confirmation processing tests
- Error handling tests

### Integration Tests
- End-to-end flow testing in `tests/test_bill_extraction_integration.py`
- Step handler integration tests
- Multi-modal input testing
- Error scenario testing

### Validation Script
- `validate_bill_extractor.py`: Standalone validation script
- Tests basic functionality without external dependencies
- Useful for development and debugging

## Usage Examples

### Basic Usage
```python
from app.services.bill_extractor import BillExtractor
from app.models.schemas import Message
from app.models.enums import MessageType

extractor = BillExtractor()

# Extract from text
message = Message(
    id="msg_001",
    user_id="user_123",
    content="Bill from Pizza Palace for ₹150",
    message_type=MessageType.TEXT,
    timestamp=datetime.now(),
    metadata={}
)

bill_data = await extractor.extract_bill_data(message)
validation = await extractor.validate_bill_data(bill_data)
summary = await extractor.create_bill_summary(bill_data)
```

### Advanced Usage
See `examples/bill_extractor_example.py` for comprehensive usage examples including:
- Multi-modal extraction examples
- Validation and error handling
- Confirmation processing
- Error scenarios

## Requirements Fulfilled

This implementation fulfills the following requirements from the specification:

- **Requirement 1.1**: Text message processing and bill extraction
- **Requirement 1.2**: Voice message processing with speech-to-text
- **Requirement 1.3**: Image processing for bill photo extraction
- **Requirement 1.4**: Data validation and clarifying questions
- **Requirement 1.5**: Bill confirmation and summary display

## Configuration

### Environment Variables
The BillExtractor relies on AI services that require configuration:
- Sarvam AI API keys for voice processing
- Gemini API keys for image processing
- LiteLLM configuration for text processing

### Customization
- Minimum/maximum amount limits can be configured
- Validation rules can be extended
- Question generation can be customized
- Summary formatting can be modified

## Performance Considerations

### Async Operations
- All operations are async for non-blocking execution
- Concurrent processing where possible
- Efficient error handling and recovery

### Caching
- AI service responses can be cached for repeated queries
- Validation results can be cached for similar bill data
- Question templates can be pre-generated

### Resource Management
- Proper cleanup of resources
- Memory-efficient processing of large images/audio
- Connection pooling for AI service calls

## Future Enhancements

### Planned Features
- Support for additional input formats (PDF, CSV)
- Multi-language support for international bills
- Receipt categorization and tagging
- Historical bill pattern recognition

### Optimization Opportunities
- Response caching for improved performance
- Batch processing for multiple bills
- Advanced validation rules based on merchant patterns
- Machine learning for improved extraction accuracy

## Troubleshooting

### Common Issues
1. **AI Service Unavailable**: Falls back to rule-based processing
2. **Invalid Image Quality**: Provides specific guidance for better photos
3. **Unclear Voice Audio**: Suggests text input as alternative
4. **Ambiguous Confirmations**: Asks for clearer yes/no responses

### Debugging
- Comprehensive logging at all levels
- Error context preservation
- Validation result details
- Performance metrics tracking

## Conclusion

The BillExtractor implementation provides a robust, scalable solution for multi-modal bill extraction and processing. It successfully integrates AI services with fallback mechanisms, provides comprehensive validation, and offers an excellent user experience through intelligent question generation and confirmation processing.