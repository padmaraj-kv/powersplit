"""
Bill extraction and processing logic with multi-modal input support
Implements requirements 1.1, 1.2, 1.3, 1.4, 1.5
"""
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime

from app.models.schemas import (
    BillData, BillItem, ValidationResult, Message, Response
)
from app.models.enums import MessageType, ConversationStep
from app.interfaces.services import BillExtractorInterface
from app.services.ai_service import AIService, AIServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BillExtractionError(Exception):
    """Exception raised when bill extraction fails"""
    pass


class BillExtractor(BillExtractorInterface):
    """
    Main bill extraction service with multi-modal input support
    Implements requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    def __init__(self, ai_service: Optional[AIService] = None):
        self.ai_service = ai_service or AIService()
        self.min_amount = Decimal('0.01')
        self.max_amount = Decimal('999999.99')
        
    async def extract_bill_data(self, message: Message) -> BillData:
        """
        Extract bill data from multi-modal input
        Implements requirements 1.1, 1.2, 1.3
        
        Args:
            message: User message with bill information
            
        Returns:
            BillData object with extracted information
            
        Raises:
            BillExtractionError: If extraction fails
        """
        logger.info(f"Extracting bill data from {message.message_type} message")
        
        try:
            if message.message_type == MessageType.TEXT:
                bill_data = await self._extract_from_text(message)
            elif message.message_type == MessageType.VOICE:
                bill_data = await self._extract_from_voice(message)
            elif message.message_type == MessageType.IMAGE:
                bill_data = await self._extract_from_image(message)
            else:
                raise BillExtractionError(f"Unsupported message type: {message.message_type}")
            
            # Normalize and validate the extracted data
            normalized_data = await self._normalize_bill_data(bill_data)
            
            logger.info(f"Successfully extracted bill data: ₹{normalized_data.total_amount}")
            return normalized_data
            
        except AIServiceError as e:
            logger.error(f"AI service error during extraction: {e}")
            raise BillExtractionError(f"Failed to process {message.message_type} input: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during extraction: {e}")
            raise BillExtractionError(f"Failed to extract bill information: {e}")
    
    async def validate_bill_data(self, bill_data: BillData) -> ValidationResult:
        """
        Validate extracted bill data with comprehensive checks
        Implements requirement 1.4
        
        Args:
            bill_data: Extracted bill data to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        logger.info("Validating extracted bill data")
        
        try:
            # Use AI service for comprehensive validation
            ai_validation = await self.ai_service.validate_extraction(bill_data)
            
            # Add business logic validation
            business_validation = self._validate_business_rules(bill_data)
            
            # Combine validations
            combined_result = self._combine_validations(ai_validation, business_validation)
            
            logger.info(f"Validation complete: {'Valid' if combined_result.is_valid else 'Invalid'}")
            return combined_result
            
        except Exception as e:
            logger.warning(f"Validation error: {e}")
            # Fallback to basic validation
            return self._validate_business_rules(bill_data)
    
    async def generate_clarifying_questions(self, bill_data: BillData) -> List[str]:
        """
        Generate clarifying questions for incomplete bill data
        Implements requirement 1.4
        
        Args:
            bill_data: Partially extracted bill data
            
        Returns:
            List of clarifying questions to ask the user
        """
        logger.info("Generating clarifying questions for incomplete data")
        
        try:
            # Use AI service to generate intelligent questions
            ai_questions = await self.ai_service.generate_clarifying_questions(bill_data)
            
            if ai_questions:
                logger.info(f"Generated {len(ai_questions)} clarifying questions")
                return ai_questions
            
        except Exception as e:
            logger.warning(f"AI question generation failed: {e}")
        
        # Fallback to rule-based questions
        fallback_questions = self._generate_fallback_questions(bill_data)
        logger.info(f"Generated {len(fallback_questions)} fallback questions")
        return fallback_questions
    
    async def create_bill_summary(self, bill_data: BillData) -> str:
        """
        Create a formatted summary of the bill for user confirmation
        Implements requirement 1.5
        
        Args:
            bill_data: Validated bill data
            
        Returns:
            Formatted bill summary string
        """
        logger.info("Creating bill summary for confirmation")
        
        summary_parts = []
        
        # Header
        summary_parts.append("📋 *Bill Summary*")
        summary_parts.append("")
        
        # Basic information
        if bill_data.merchant:
            summary_parts.append(f"🏪 *Restaurant/Store:* {bill_data.merchant}")
        
        summary_parts.append(f"💰 *Total Amount:* ₹{bill_data.total_amount}")
        
        if bill_data.date:
            date_str = bill_data.date.strftime("%d %b %Y, %I:%M %p")
            summary_parts.append(f"📅 *Date:* {date_str}")
        
        if bill_data.description and bill_data.description != "Bill from text message":
            summary_parts.append(f"📝 *Description:* {bill_data.description}")
        
        # Items breakdown
        if bill_data.items:
            summary_parts.append("")
            summary_parts.append("🛍️ *Items:*")
            
            for item in bill_data.items:
                if item.quantity > 1:
                    summary_parts.append(f"  • {item.name} (x{item.quantity}) - ₹{item.amount}")
                else:
                    summary_parts.append(f"  • {item.name} - ₹{item.amount}")
        
        # Footer
        summary_parts.append("")
        summary_parts.append("Is this information correct? Reply *yes* to continue or *no* to make changes.")
        
        return "\n".join(summary_parts)
    
    async def process_bill_confirmation(self, message: Message, bill_data: BillData) -> Tuple[bool, Optional[str]]:
        """
        Process user's confirmation response for bill data
        Implements requirement 1.5
        
        Args:
            message: User's confirmation message
            bill_data: Bill data being confirmed
            
        Returns:
            Tuple of (is_confirmed, error_message)
        """
        logger.info("Processing bill confirmation response")
        
        try:
            # Use AI service to understand user intent
            intent_data = await self.ai_service.recognize_intent(message, ConversationStep.CONFIRMING_BILL)
            
            intent = intent_data.get("intent", "").lower()
            confidence = intent_data.get("confidence", 0.0)
            
            if intent == "confirm" and confidence > 0.6:
                logger.info("User confirmed bill data")
                return True, None
            elif intent == "modify" and confidence > 0.6:
                logger.info("User wants to modify bill data")
                return False, "What would you like to change about the bill?"
            else:
                # Ambiguous response
                logger.warning(f"Ambiguous confirmation response: {message.content}")
                return False, "I didn't understand your response. Please reply *yes* to confirm or *no* to make changes."
                
        except Exception as e:
            logger.warning(f"Intent recognition failed: {e}")
            
            # Fallback to simple keyword matching
            content_lower = message.content.lower().strip()
            
            if any(word in content_lower for word in ["yes", "ok", "correct", "right", "confirm", "good"]):
                return True, None
            elif any(word in content_lower for word in ["no", "wrong", "change", "modify", "incorrect"]):
                return False, "What would you like to change about the bill?"
            else:
                return False, "Please reply *yes* to confirm the bill details or *no* to make changes."
    
    async def _extract_from_text(self, message: Message) -> BillData:
        """Extract bill data from text message"""
        logger.info("Extracting bill data from text")
        return await self.ai_service.extract_from_text(message.content)
    
    async def _extract_from_voice(self, message: Message) -> BillData:
        """Extract bill data from voice message"""
        logger.info("Extracting bill data from voice")
        
        # Get audio data from message metadata
        audio_data = message.metadata.get("audio_data")
        if not audio_data:
            raise BillExtractionError("No audio data found in voice message")
        
        return await self.ai_service.extract_from_voice(audio_data)
    
    async def _extract_from_image(self, message: Message) -> BillData:
        """Extract bill data from image message"""
        logger.info("Extracting bill data from image")
        
        # Get image data from message metadata
        image_data = message.metadata.get("image_data")
        if not image_data:
            raise BillExtractionError("No image data found in image message")
        
        return await self.ai_service.extract_from_image(image_data)
    
    async def _normalize_bill_data(self, bill_data: BillData) -> BillData:
        """
        Normalize and clean extracted bill data
        """
        logger.info("Normalizing extracted bill data")
        
        # Normalize amount precision
        normalized_amount = bill_data.total_amount.quantize(Decimal('0.01'))
        
        # Clean description
        description = bill_data.description.strip() if bill_data.description else "Bill"
        
        # Normalize items
        normalized_items = []
        for item in bill_data.items:
            normalized_item = BillItem(
                name=item.name.strip(),
                amount=item.amount.quantize(Decimal('0.01')),
                quantity=max(1, item.quantity)
            )
            normalized_items.append(normalized_item)
        
        # Set current time if no date provided
        bill_date = bill_data.date or datetime.now()
        
        return BillData(
            total_amount=normalized_amount,
            description=description,
            items=normalized_items,
            currency=bill_data.currency,
            date=bill_date,
            merchant=bill_data.merchant.strip() if bill_data.merchant else None
        )
    
    def _validate_business_rules(self, bill_data: BillData) -> ValidationResult:
        """
        Validate bill data against business rules
        """
        errors = []
        warnings = []
        
        # Amount validation
        if bill_data.total_amount < self.min_amount:
            errors.append(f"Amount must be at least ₹{self.min_amount}")
        elif bill_data.total_amount > self.max_amount:
            errors.append(f"Amount cannot exceed ₹{self.max_amount}")
        
        # Items validation
        if bill_data.items:
            items_total = sum(item.amount * item.quantity for item in bill_data.items)
            if abs(items_total - bill_data.total_amount) > Decimal('0.01'):
                warnings.append(f"Items total (₹{items_total}) doesn't match bill total (₹{bill_data.total_amount})")
        
        # Description validation
        if not bill_data.description or bill_data.description.strip() == "":
            warnings.append("Bill description is missing")
        
        # Date validation
        if bill_data.date and bill_data.date > datetime.now():
            warnings.append("Bill date is in the future")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _combine_validations(self, ai_validation: ValidationResult, business_validation: ValidationResult) -> ValidationResult:
        """
        Combine AI and business rule validations
        """
        combined_errors = ai_validation.errors + business_validation.errors
        combined_warnings = ai_validation.warnings + business_validation.warnings
        
        return ValidationResult(
            is_valid=ai_validation.is_valid and business_validation.is_valid,
            errors=combined_errors,
            warnings=combined_warnings
        )
    
    def _generate_fallback_questions(self, bill_data: BillData) -> List[str]:
        """
        Generate fallback clarifying questions using rule-based logic
        """
        questions = []
        
        # Check for missing critical information
        if bill_data.total_amount <= 0:
            questions.append("What was the total amount of the bill?")
        
        if not bill_data.merchant:
            questions.append("Which restaurant or store was this bill from?")
        
        if not bill_data.description or bill_data.description == "Bill":
            questions.append("Could you provide a brief description of what this bill is for?")
        
        if not bill_data.items:
            questions.append("What items were included in this bill? (This helps with splitting)")
        
        # If no specific issues found, ask general question
        if not questions:
            questions.append("Could you provide any additional details about this bill?")
        
        return questions[:3]  # Limit to 3 questions to avoid overwhelming user