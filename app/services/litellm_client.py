"""
LiteLLM client for text processing and intent recognition
"""
import litellm
import asyncio
import json
from typing import Optional, Dict, Any, List
from decimal import Decimal
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
                timeout=self.timeout
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
                items = []
                for item_data in bill_json.get("items", []):
                    items.append(BillItem(
                        name=item_data["name"],
                        amount=Decimal(str(item_data["amount"])),
                        quantity=item_data.get("quantity", 1)
                    ))
                
                bill_data = BillData(
                    total_amount=Decimal(str(bill_json["total_amount"])),
                    description=bill_json.get("description", "Bill from text"),
                    items=items,
                    currency=bill_json.get("currency", "INR"),
                    merchant=bill_json.get("merchant")
                )
                
                logger.info(f"Successfully extracted bill from text: ₹{bill_data.total_amount}")
                return bill_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LiteLLM response as JSON: {e}")
                raise LiteLLMError("Failed to parse bill information from text")
                
        except Exception as e:
            if isinstance(e, LiteLLMError):
                raise
            logger.error(f"LiteLLM API error: {e}")
            raise LiteLLMError(f"Failed to process text: {e}")
    
    async def recognize_intent(self, text: str, current_step: ConversationStep) -> Dict[str, Any]:
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
                timeout=self.timeout
            )
            
            if not response.choices or not response.choices[0].message.content:
                return {"intent": "general_question", "confidence": 0.0, "entities": {}, "next_action": "ask_clarification"}
            
            response_text = response.choices[0].message.content.strip()
            
            try:
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()
                
                intent_data = json.loads(response_text)
                logger.info(f"Recognized intent: {intent_data.get('intent')} (confidence: {intent_data.get('confidence')})")
                return intent_data
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse intent recognition response: {response_text}")
                return {"intent": "general_question", "confidence": 0.0, "entities": {}, "next_action": "ask_clarification"}
                
        except Exception as e:
            logger.error(f"Intent recognition error: {e}")
            return {"intent": "general_question", "confidence": 0.0, "entities": {}, "next_action": "ask_clarification"}
    
    async def generate_clarifying_questions(self, bill_data: BillData, missing_info: List[str]) -> List[str]:
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
                timeout=self.timeout
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
    
    async def validate_bill_data(self, bill_data: BillData) -> ValidationResult:
        """
        Validate extracted bill data for completeness and accuracy
        
        Args:
            bill_data: Bill data to validate
            
        Returns:
            ValidationResult with validation status and issues
        """
        errors = []
        warnings = []
        
        # Basic validation
        if bill_data.total_amount <= 0:
            errors.append("Total amount must be greater than zero")
        
        if not bill_data.description or bill_data.description.strip() == "":
            warnings.append("Bill description is empty")
        
        # Validate items sum matches total (if items are provided)
        if bill_data.items:
            items_total = sum(item.amount * item.quantity for item in bill_data.items)
            if abs(items_total - bill_data.total_amount) > Decimal('0.01'):
                warnings.append(f"Items total (₹{items_total}) doesn't match bill total (₹{bill_data.total_amount})")
        
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
                timeout=self.timeout
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
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
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
                timeout=5.0
            )
            return bool(response.choices and response.choices[0].message.content)
            
        except Exception as e:
            logger.warning(f"LiteLLM health check failed: {e}")
            return False