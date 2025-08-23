"""
AI Service integration layer with fallback mechanisms
Implements requirements 1.1, 1.2, 1.3, 1.4, 7.1
"""

import asyncio
from typing import Optional, Dict, Any, List
from decimal import Decimal
from app.models.schemas import BillData, BillItem, ValidationResult, Message
from app.models.enums import MessageType, ConversationStep
from app.interfaces.services import AIServiceInterface
from app.clients.sarvam_client import SarvamClient, SarvamError
from app.clients.litellm_client import LiteLLMClient, LiteLLMError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AIServiceError(Exception):
    """Base exception for AI service errors"""

    pass


class AIService(AIServiceInterface):
    """
    Main AI service that coordinates all AI integrations with fallback mechanisms
    Implements requirements 1.1, 1.2, 1.3, 1.4, 7.1
    """

    def __init__(self):
        self.sarvam_client = SarvamClient()
        self.litellm_client = LiteLLMClient()
        self.max_retries = 3
        self.retry_delay = 1.0

    async def extract_from_text(self, text: str) -> BillData:
        """
        Extract bill data from text input with fallback mechanisms
        Implements requirement 1.1

        Args:
            text: User's text message

        Returns:
            BillData object with extracted information

        Raises:
            AIServiceError: If all extraction methods fail
        """
        logger.info(f"Extracting bill data from text: {text[:100]}...")

        # Primary: Use LiteLLM for text processing
        try:
            bill_data = await self._retry_operation(
                self.litellm_client.extract_bill_from_text, text
            )
            logger.info("Successfully extracted bill data using LiteLLM")
            return bill_data

        except Exception as e:
            logger.warning(f"LiteLLM extraction failed: {e}")

            # Fallback: Use basic text parsing
            try:
                bill_data = await self._fallback_text_extraction(text)
                logger.info("Successfully extracted bill data using fallback method")
                return bill_data

            except Exception as fallback_error:
                logger.error(f"All text extraction methods failed: {fallback_error}")
                raise AIServiceError(
                    f"Failed to extract bill information from text: {e}"
                )

    async def extract_from_voice(self, audio_data: bytes) -> BillData:
        """
        Extract bill data from voice input with fallback mechanisms
        Implements requirement 1.2

        Args:
            audio_data: Audio file bytes

        Returns:
            BillData object with extracted information

        Raises:
            AIServiceError: If voice processing fails
        """
        logger.info("Extracting bill data from voice message")

        # Step 1: Convert speech to text using Sarvam AI
        try:
            transcript = await self._retry_operation(
                self.sarvam_client.transcribe_audio, audio_data
            )
            logger.info(f"Successfully transcribed audio: {transcript[:100]}...")

            # Step 2: Extract bill data from transcript
            return await self.extract_from_text(transcript)

        except SarvamError as e:
            logger.error(f"Sarvam transcription failed: {e}")
            raise AIServiceError(f"Failed to process voice message: {e}")

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            raise AIServiceError(f"Failed to process voice message: {e}")

    async def extract_from_image(self, image_data: bytes) -> BillData:
        """
        Extract bill data from image input with fallback mechanisms
        Implements requirement 1.3

        Args:
            image_data: Image file bytes

        Returns:
            BillData object with extracted information

        Raises:
            AIServiceError: If image processing fails
        """
        logger.info("Extracting bill data from image")

        # Step 1: Validate image quality
        try:
            validation = await self.litellm_client.validate_image_quality(image_data)
            if not validation["is_valid"]:
                issues = ", ".join(validation["issues"])
                suggestions = " ".join(validation["suggestions"])
                raise AIServiceError(f"Image quality issues: {issues}. {suggestions}")

        except Exception as e:
            logger.warning(f"Image validation failed: {e}")
            # Continue with extraction even if validation fails

        # Step 2: Extract bill data using LiteLLM Vision
        try:
            bill_data = await self._retry_operation(
                self.litellm_client.extract_bill_from_image, image_data
            )

            # Step 3: Enhance description if possible
            try:
                enhanced_description = (
                    await self.litellm_client.enhance_bill_description(bill_data)
                )
                bill_data.description = enhanced_description
            except Exception as e:
                logger.warning(f"Failed to enhance description: {e}")

            logger.info("Successfully extracted bill data from image")
            return bill_data

        except LiteLLMError as e:
            logger.error(f"LiteLLM Vision extraction failed: {e}")
            raise AIServiceError(f"Failed to process bill image: {e}")

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise AIServiceError(f"Failed to process bill image: {e}")

    async def validate_extraction(self, bill_data: BillData) -> ValidationResult:
        """
        Validate extracted bill data
        Implements requirement 1.4

        Args:
            bill_data: Extracted bill data

        Returns:
            ValidationResult with validation status
        """
        logger.info("Validating extracted bill data")

        try:
            # Use LiteLLM for comprehensive validation
            validation_result = await self._retry_operation(
                self.litellm_client.validate_bill_data, bill_data
            )

            logger.info(
                f"Validation complete: {'Valid' if validation_result.is_valid else 'Invalid'}"
            )
            return validation_result

        except Exception as e:
            logger.warning(f"AI validation failed, using basic validation: {e}")

            # Fallback to basic validation
            return self._basic_validation(bill_data)

    async def recognize_intent(
        self, message: Message, current_step: ConversationStep
    ) -> Dict[str, Any]:
        """
        Recognize user intent from message
        Implements requirement 1.4

        Args:
            message: User message
            current_step: Current conversation step

        Returns:
            Dictionary with intent information
        """
        try:
            intent_data = await self._retry_operation(
                self.litellm_client.recognize_intent, message.content, current_step
            )

            logger.info(f"Recognized intent: {intent_data.get('intent')}")
            return intent_data

        except Exception as e:
            logger.warning(f"Intent recognition failed: {e}")

            # Fallback to basic intent recognition
            return self._basic_intent_recognition(message.content, current_step)

    async def generate_clarifying_questions(self, bill_data: BillData) -> List[str]:
        """
        Generate clarifying questions for incomplete bill data

        Args:
            bill_data: Partially extracted bill data

        Returns:
            List of clarifying questions
        """
        try:
            # Identify missing information
            missing_info = []
            if bill_data.total_amount <= 0:
                missing_info.append("total_amount")
            if not bill_data.merchant:
                missing_info.append("merchant")
            if not bill_data.items:
                missing_info.append("items")

            if not missing_info:
                return []

            questions = await self._retry_operation(
                self.litellm_client.generate_clarifying_questions,
                bill_data,
                missing_info,
            )

            return questions

        except Exception as e:
            logger.warning(f"Failed to generate clarifying questions: {e}")
            return self._basic_clarifying_questions(bill_data)

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all AI services
        Implements requirement 7.1

        Returns:
            Dictionary with health status of each service
        """
        logger.info("Performing AI services health check")

        health_status = {}

        # Check each service concurrently
        tasks = [
            ("sarvam", self.sarvam_client.health_check()),
            ("litellm", self.litellm_client.health_check()),
        ]

        results = await asyncio.gather(
            *[task[1] for task in tasks], return_exceptions=True
        )

        for i, (service_name, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                health_status[service_name] = False
                logger.warning(f"{service_name} health check failed: {result}")
            else:
                health_status[service_name] = result
                logger.info(
                    f"{service_name} health check: {'OK' if result else 'FAILED'}"
                )

        return health_status

    async def _retry_operation(self, operation, *args, **kwargs):
        """
        Retry operation with exponential backoff
        Implements requirement 7.1
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{self.max_retries}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Operation failed after {self.max_retries} attempts: {e}"
                    )

        raise last_exception

    async def _fallback_text_extraction(self, text: str) -> BillData:
        """
        Basic fallback text extraction when AI services fail
        """
        import re

        # Extract amounts using regex
        amount_pattern = r"₹?(\d+(?:\.\d{2})?)"
        amounts = [float(match) for match in re.findall(amount_pattern, text)]

        if not amounts:
            raise AIServiceError("No amount found in text")

        # Use the largest amount as total
        total_amount = max(amounts)

        # Create basic bill data
        return BillData(
            total_amount=Decimal(str(total_amount)),
            description="Bill from text message",
            items=[],
            currency="INR",
        )

    def _basic_validation(self, bill_data: BillData) -> ValidationResult:
        """
        Basic validation when AI validation fails
        """
        errors = []
        warnings = []

        if bill_data.total_amount <= 0:
            errors.append("Total amount must be greater than zero")

        if not bill_data.description:
            warnings.append("Bill description is missing")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _basic_intent_recognition(
        self, text: str, current_step: ConversationStep
    ) -> Dict[str, Any]:
        """
        Basic intent recognition when AI fails
        """
        text_lower = text.lower()

        # Simple keyword-based intent recognition
        if any(
            word in text_lower for word in ["yes", "ok", "correct", "right", "confirm"]
        ):
            return {
                "intent": "confirm",
                "confidence": 0.7,
                "entities": {},
                "next_action": "proceed",
            }
        elif any(word in text_lower for word in ["no", "wrong", "change", "modify"]):
            return {
                "intent": "modify",
                "confidence": 0.7,
                "entities": {},
                "next_action": "ask_changes",
            }
        elif any(word in text_lower for word in ["paid", "done", "completed"]):
            return {
                "intent": "confirm_payment",
                "confidence": 0.8,
                "entities": {},
                "next_action": "update_payment",
            }
        else:
            return {
                "intent": "general_question",
                "confidence": 0.5,
                "entities": {},
                "next_action": "ask_clarification",
            }

    def _basic_clarifying_questions(self, bill_data: BillData) -> List[str]:
        """
        Basic clarifying questions when AI generation fails
        """
        questions = []

        if bill_data.total_amount <= 0:
            questions.append("What was the total amount of the bill?")

        if not bill_data.merchant:
            questions.append("Which restaurant or store was this from?")

        if not bill_data.items:
            questions.append("Could you tell me what items were on the bill?")

        if not questions:
            questions.append("Could you provide more details about the bill?")

        return questions
