"""
Gemini Vision client for bill image processing
"""
import google.generativeai as genai
import asyncio
from typing import Optional, Dict, Any, List
from decimal import Decimal
from PIL import Image
import io
import json
from app.core.config import settings
from app.models.schemas import BillData, BillItem
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini API errors"""
    pass


class GeminiVisionClient:
    """Client for Gemini Vision API for bill image processing"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro-vision')
        self.text_model = genai.GenerativeModel('gemini-pro')
        
    async def extract_bill_from_image(self, image_data: bytes) -> BillData:
        """
        Extract bill information from image using Gemini Vision
        
        Args:
            image_data: Image file bytes
            
        Returns:
            BillData object with extracted information
            
        Raises:
            GeminiError: If extraction fails
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Prepare the prompt for bill extraction
            prompt = """
            Analyze this bill/receipt image and extract the following information in JSON format:
            
            {
                "total_amount": <total amount as number>,
                "description": "<brief description of the bill>",
                "merchant": "<merchant/restaurant name>",
                "items": [
                    {
                        "name": "<item name>",
                        "amount": <item amount as number>,
                        "quantity": <quantity as number>
                    }
                ],
                "currency": "<currency code, default INR>",
                "date": "<date in ISO format if visible, null otherwise>"
            }
            
            Rules:
            - Extract only visible information
            - If total amount is not clear, sum up individual items
            - Use "INR" as default currency for Indian bills
            - Set quantity to 1 if not specified
            - If no items are visible, use empty array
            - Be accurate with numbers and amounts
            - If merchant name is not clear, use "Unknown Merchant"
            """
            
            logger.info("Sending image to Gemini Vision for bill extraction")
            
            # Generate content using Gemini Vision
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, image]
            )
            
            if not response.text:
                raise GeminiError("No response from Gemini Vision API")
            
            # Parse the JSON response
            try:
                # Extract JSON from response (handle potential markdown formatting)
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3].strip()
                
                bill_json = json.loads(response_text)
                
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
                    description=bill_json.get("description", "Bill from image"),
                    items=items,
                    currency=bill_json.get("currency", "INR"),
                    merchant=bill_json.get("merchant")
                )
                
                logger.info(f"Successfully extracted bill: ₹{bill_data.total_amount} from {bill_data.merchant}")
                return bill_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
                logger.error(f"Response text: {response.text}")
                raise GeminiError("Failed to parse bill information from image")
                
        except Exception as e:
            if isinstance(e, GeminiError):
                raise
            logger.error(f"Gemini Vision API error: {e}")
            raise GeminiError(f"Failed to process bill image: {e}")
    
    async def validate_image_quality(self, image_data: bytes) -> Dict[str, Any]:
        """
        Validate if image is suitable for bill extraction
        
        Args:
            image_data: Image file bytes
            
        Returns:
            Dictionary with validation results
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Basic image validation
            width, height = image.size
            file_size = len(image_data)
            
            validation_result = {
                "is_valid": True,
                "issues": [],
                "suggestions": [],
                "image_info": {
                    "width": width,
                    "height": height,
                    "file_size": file_size,
                    "format": image.format
                }
            }
            
            # Check image size
            if width < 300 or height < 300:
                validation_result["issues"].append("Image resolution is too low")
                validation_result["suggestions"].append("Please use a higher resolution image")
                validation_result["is_valid"] = False
            
            # Check file size
            if file_size > 10 * 1024 * 1024:  # 10MB
                validation_result["issues"].append("Image file is too large")
                validation_result["suggestions"].append("Please compress the image or use a smaller file")
                validation_result["is_valid"] = False
            
            # Use Gemini to check if image contains a bill/receipt
            prompt = """
            Look at this image and determine if it contains a bill, receipt, or invoice.
            Respond with only "YES" if it clearly shows a bill/receipt with amounts and items.
            Respond with "NO" if it doesn't appear to be a bill or receipt.
            """
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, image]
            )
            
            if response.text and "NO" in response.text.upper():
                validation_result["issues"].append("Image does not appear to contain a bill or receipt")
                validation_result["suggestions"].append("Please upload an image of a bill, receipt, or invoice")
                validation_result["is_valid"] = False
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Image validation error: {e}")
            return {
                "is_valid": False,
                "issues": ["Failed to validate image"],
                "suggestions": ["Please try uploading the image again"],
                "image_info": {}
            }
    
    async def enhance_bill_description(self, bill_data: BillData) -> str:
        """
        Generate a better description for the bill using Gemini
        
        Args:
            bill_data: Extracted bill data
            
        Returns:
            Enhanced description
        """
        try:
            prompt = f"""
            Based on this bill information, create a concise, user-friendly description:
            
            Merchant: {bill_data.merchant or 'Unknown'}
            Total: ₹{bill_data.total_amount}
            Items: {len(bill_data.items)} items
            Current description: {bill_data.description}
            
            Generate a brief, natural description that a user would understand.
            Examples: "Dinner at Pizza Hut", "Grocery shopping at Big Bazaar", "Coffee at Starbucks"
            
            Respond with only the description, no additional text.
            """
            
            response = await asyncio.to_thread(
                self.text_model.generate_content,
                prompt
            )
            
            if response.text:
                enhanced_description = response.text.strip()
                logger.info(f"Enhanced bill description: {enhanced_description}")
                return enhanced_description
            else:
                return bill_data.description
                
        except Exception as e:
            logger.warning(f"Failed to enhance bill description: {e}")
            return bill_data.description
    
    async def health_check(self) -> bool:
        """
        Check if Gemini API is available
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test with text model
            response = await asyncio.to_thread(
                self.text_model.generate_content,
                "Hello"
            )
            return bool(response.text)
            
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False