"""
LiteLLM client for text processing and intent recognition
"""

import litellm
import asyncio
import json
import base64
from typing import Optional, Dict, Any, List
from decimal import Decimal
from io import BytesIO
from app.core.config import settings
from app.models.schemas import BillData, BillItem, ValidationResult
from app.models.enums import ConversationStep
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LiteLLMError(Exception):
    """Base exception for LiteLLM errors"""

    pass


class LiteLLMClient:
    """Client for LiteLLM text processing and intent recognition"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        # Configure LiteLLM to use Gemini
        litellm.api_key = self.api_key
        self.model = "gemini/gemini-pro"
        self.vision_model = "gemini/gemini-pro-vision"
        self.timeout = 30.0

    async def extract_bill_from_text(self, text: str) -> BillData:
        """
        Extract bill information from text using LiteLLM

        Args:
            text: User's text message containing bill information

        Returns:
            BillData object with extracted information

        Raises:
            LiteLLMError: If extraction fails
        """
        try:
            prompt = f"""
            Extract bill information from this text and return it in JSON format:
            
            Text: "{text}"
            
            Return JSON in this exact format:
            {{
                "total_amount": <total amount as number>,
                "description": "<brief description>",
                "merchant": "<merchant name if mentioned>",
                "items": [
                    {{
                        "name": "<item name>",
                        "amount": <amount as number>,
                        "quantity": <quantity as number>
                    }}
                ],
                "currency": "INR"
            }}
            
            Rules:
            - If total amount is not mentioned, sum up individual items
            - If no items are mentioned, create items based on context
            - Use "INR" as currency for Indian context
            - Set quantity to 1 if not specified
            - If merchant is not mentioned, use null
            - Be conservative with amounts - only extract clear numbers
            - If unclear, ask for clarification by setting total_amount to 0
            """

            logger.info(f"Processing text for bill extraction: {text[:100]}...")

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LiteLLMError("No response from LiteLLM API")

            response_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                bill_json = json.loads(response_text)

                # Handle case where extraction is unclear
                if bill_json.get("total_amount", 0) <= 0:
                    raise LiteLLMError("Could not extract clear bill amount from text")

                # Convert to BillData object
                items: List[BillItem] = []
                for item_data in bill_json.get("items", []):
                    items.append(
                        BillItem(
                            name=item_data["name"],
                            amount=Decimal(str(item_data["amount"])),
                            quantity=item_data.get("quantity", 1),
                        )
                    )

                bill_data = BillData(
                    total_amount=Decimal(str(bill_json["total_amount"])),
                    description=bill_json.get("description", "Bill from text"),
                    items=items,
                    currency=bill_json.get("currency", "INR"),
                    merchant=bill_json.get("merchant"),
                )

                logger.info(
                    f"Successfully extracted bill from text: ₹{bill_data.total_amount}"
                )
                return bill_data

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LiteLLM response as JSON: {e}")
                raise LiteLLMError("Failed to parse bill information from text")

        except Exception as e:
            if isinstance(e, LiteLLMError):
                raise
            logger.error(f"LiteLLM API error: {e}")
            raise LiteLLMError(f"Failed to process text: {e}")

    async def extract_bill_from_image(self, image_data: bytes) -> BillData:
        """
        Extract bill information from an image using LiteLLM with Gemini Vision

        Args:
            image_data: Raw image bytes

        Returns:
            BillData object with extracted information

        Raises:
            LiteLLMError: If extraction fails
        """
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            prompt = """
            Extract bill information from this image and return it in JSON format.
            
            Return JSON in this exact format:
            {
                "total_amount": <total amount as number>,
                "description": "<brief description>",
                "merchant": "<merchant name if mentioned>",
                "items": [
                    {
                        "name": "<item name>",
                        "amount": <amount as number>,
                        "quantity": <quantity as number>
                    }
                ],
                "currency": "INR"
            }
            
            Rules:
            - If total amount is not mentioned, sum up individual items
            - If no items are mentioned, create items based on context
            - Use "INR" as currency for Indian context
            - Set quantity to 1 if not specified
            - If merchant is not mentioned, use null
            - Be conservative with amounts - only extract clear numbers
            """

            logger.info("Processing image for bill extraction")

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LiteLLMError("No response from LiteLLM API for image processing")

            response_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                bill_json = json.loads(response_text)

                # Convert to BillData
                items = []
                for item_data in bill_json.get("items", []):
                    items.append(
                        BillItem(
                            name=item_data.get("name", "Unknown item"),
                            amount=Decimal(str(item_data.get("amount", 0))),
                            quantity=item_data.get("quantity", 1),
                        )
                    )

                bill_data = BillData(
                    total_amount=Decimal(str(bill_json.get("total_amount", 0))),
                    description=bill_json.get("description", "Bill from image"),
                    items=items,
                    currency=bill_json.get("currency", "INR"),
                    merchant=bill_json.get("merchant"),
                )

                logger.info(
                    f"Successfully extracted bill data from image: ₹{bill_data.total_amount}"
                )
                return bill_data

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LiteLLM response: {e}")
                raise LiteLLMError(f"Invalid JSON response: {e}")

        except Exception as e:
            logger.error(f"Error extracting bill data from image: {e}")
            raise LiteLLMError(f"Image extraction failed: {str(e)}")

    async def recognize_intent(
        self, text: str, current_step: ConversationStep
    ) -> Dict[str, Any]:
        """
        Recognize user intent based on text and current conversation step

        Args:
            text: User's message
            current_step: Current conversation step

        Returns:
            Dictionary with intent information
        """
        try:
            prompt = f"""
            Analyze this user message and determine their intent based on the current conversation step.
            
            User message: "{text}"
            Current step: {current_step.value}
            
            Return JSON with:
            {{
                "intent": "<primary intent>",
                "confidence": <confidence 0-1>,
                "entities": {{
                    "amounts": [<list of amounts mentioned>],
                    "names": [<list of names mentioned>],
                    "phone_numbers": [<list of phone numbers>]
                }},
                "next_action": "<suggested next action>"
            }}
            
            Possible intents:
            - "provide_bill_info": User is providing bill details
            - "confirm_bill": User is confirming bill information
            - "modify_bill": User wants to change bill details
            - "provide_contacts": User is providing participant contacts
            - "confirm_splits": User is confirming split amounts
            - "modify_splits": User wants to change splits
            - "query_status": User is asking about bill status
            - "confirm_payment": User is confirming they paid
            - "general_question": General question or unclear intent
            """

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                return {
                    "intent": "general_question",
                    "confidence": 0.0,
                    "entities": {},
                    "next_action": "ask_clarification",
                }

            response_text = response.choices[0].message.content.strip()

            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                intent_data = json.loads(response_text)
                logger.info(
                    f"Recognized intent: {intent_data.get('intent')} (confidence: {intent_data.get('confidence')})"
                )
                return intent_data

            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse intent recognition response: {response_text}"
                )
                return {
                    "intent": "general_question",
                    "confidence": 0.0,
                    "entities": {},
                    "next_action": "ask_clarification",
                }

        except Exception as e:
            logger.error(f"Intent recognition error: {e}")
            return {
                "intent": "general_question",
                "confidence": 0.0,
                "entities": {},
                "next_action": "ask_clarification",
            }

    async def validate_image_quality(self, image_data: bytes) -> Dict[str, Any]:
        """
        Validate image quality for bill extraction

        Args:
            image_data: Raw image bytes

        Returns:
            Dictionary with validation results
        """
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            prompt = """
            Analyze this image of a bill/receipt and check for quality issues.
            Respond with a JSON object containing:
            1. "is_valid": boolean (true if image is usable for bill extraction)
            2. "issues": array of strings (list of quality issues, empty if none)
            3. "suggestions": array of strings (suggestions to improve image quality)
            
            Common issues to check for:
            - Blurriness
            - Poor lighting
            - Glare or reflections
            - Incomplete capture (missing parts)
            - Skewed/tilted perspective
            - Low resolution
            - Obstructions covering text
            """

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                return {"is_valid": True, "issues": [], "suggestions": []}

            response_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                validation_result = json.loads(response_text)
                return {
                    "is_valid": validation_result.get("is_valid", True),
                    "issues": validation_result.get("issues", []),
                    "suggestions": validation_result.get("suggestions", []),
                }
            except json.JSONDecodeError:
                return {"is_valid": True, "issues": [], "suggestions": []}

        except Exception as e:
            logger.warning(f"Image quality validation failed: {e}")
            return {"is_valid": True, "issues": [], "suggestions": []}

    async def generate_clarifying_questions(
        self, bill_data: BillData, missing_info: List[str]
    ) -> List[str]:
        """
        Generate clarifying questions for incomplete bill data

        Args:
            bill_data: Partially extracted bill data
            missing_info: List of missing information fields

        Returns:
            List of clarifying questions
        """
        try:
            prompt = f"""
            Generate helpful clarifying questions for this incomplete bill information:
            
            Current bill data:
            - Total: ₹{bill_data.total_amount if bill_data.total_amount > 0 else 'Unknown'}
            - Description: {bill_data.description}
            - Merchant: {bill_data.merchant or 'Unknown'}
            - Items: {len(bill_data.items)} items
            
            Missing information: {', '.join(missing_info)}
            
            Generate 1-3 specific, friendly questions to get the missing information.
            Return as JSON array of strings.
            
            Example: ["What was the total amount of the bill?", "Which restaurant or store was this from?"]
            """

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                return ["Could you provide more details about the bill?"]

            response_text = response.choices[0].message.content.strip()

            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()

                questions = json.loads(response_text)
                if isinstance(questions, list):
                    return questions
                else:
                    return ["Could you provide more details about the bill?"]

            except json.JSONDecodeError:
                return ["Could you provide more details about the bill?"]

        except Exception as e:
            logger.error(f"Failed to generate clarifying questions: {e}")
            return ["Could you provide more details about the bill?"]

    async def enhance_bill_description(self, bill_data: BillData) -> str:
        """
        Enhance bill description with additional context

        Args:
            bill_data: Extracted bill data

        Returns:
            Enhanced description
        """
        try:
            # Create a prompt with the bill data
            bill_json = bill_data.dict()
            prompt = f"""
            Create a concise but informative description for this bill:
            
            Bill Data: {json.dumps(bill_json, default=str)}
            
            The description should:
            1. Mention the merchant name if available
            2. Include the total amount
            3. Summarize what was purchased
            4. Be 1-2 sentences maximum
            5. Be natural and conversational
            """

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                return bill_data.description

            enhanced_description = response.choices[0].message.content.strip()
            return enhanced_description

        except Exception as e:
            logger.warning(f"Failed to enhance bill description: {e}")
            return bill_data.description

    async def validate_bill_data(self, bill_data: BillData) -> ValidationResult:
        """
        Validate extracted bill data for completeness and accuracy

        Args:
            bill_data: Bill data to validate

        Returns:
            ValidationResult with validation status and issues
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Basic validation
        if bill_data.total_amount <= 0:
            errors.append("Total amount must be greater than zero")

        if not bill_data.description or bill_data.description.strip() == "":
            warnings.append("Bill description is empty")

        # Validate items sum matches total (if items are provided)
        if bill_data.items:
            items_total = sum(item.amount * item.quantity for item in bill_data.items)
            if abs(items_total - bill_data.total_amount) > Decimal("0.01"):
                warnings.append(
                    f"Items total (₹{items_total}) doesn't match bill total (₹{bill_data.total_amount})"
                )

        # Use LiteLLM for semantic validation
        try:
            prompt = f"""
            Validate this bill data for any logical inconsistencies or issues:
            
            Total: ₹{bill_data.total_amount}
            Description: {bill_data.description}
            Merchant: {bill_data.merchant or 'Not specified'}
            Items: {[f"{item.name}: ₹{item.amount} x {item.quantity}" for item in bill_data.items]}
            
            Return JSON with:
            {{
                "issues": [<list of potential issues>],
                "suggestions": [<list of suggestions for improvement>]
            }}
            
            Look for:
            - Unrealistic amounts for the type of merchant
            - Inconsistent item pricing
            - Missing essential information
            """

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout,
            )

            if response.choices and response.choices[0].message.content:
                response_text = response.choices[0].message.content.strip()

                try:
                    if response_text.startswith("```json"):
                        response_text = response_text[7:-3].strip()
                    elif response_text.startswith("```"):
                        response_text = response_text[3:-3].strip()

                    validation_data = json.loads(response_text)
                    warnings.extend(validation_data.get("issues", []))

                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.warning(f"Semantic validation failed: {e}")

        is_valid = len(errors) == 0

        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    async def health_check(self) -> bool:
        """
        Check if LiteLLM/Gemini API is available

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                timeout=5.0,
            )
            return bool(response.choices and response.choices[0].message.content)

        except Exception as e:
            logger.warning(f"LiteLLM health check failed: {e}")
            return False
