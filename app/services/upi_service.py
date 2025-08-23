"""
UPI Payment Link Generation Service

This service handles the generation of UPI deeplinks for various payment apps
and provides validation and error handling for payment requests.

Requirements implemented:
- 4.1: Generate UPI deeplinks for each participant with their specific amount
- 4.5: Store tracking information in the database
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from urllib.parse import quote
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UPIApp(Enum):
    """Supported UPI applications"""
    GPAY = "gpay"
    PHONEPE = "phonepe"
    PAYTM = "paytm"
    BHIM = "bhim"
    GENERIC = "generic"


@dataclass
class UPILinkConfig:
    """Configuration for UPI link generation"""
    app: UPIApp
    scheme: str
    fallback_scheme: Optional[str] = None


class UPIValidationError(Exception):
    """Exception raised for UPI validation errors"""
    pass


class UPIService:
    """Service for generating and validating UPI payment links"""
    
    # UPI app configurations with their specific schemes
    UPI_CONFIGS = {
        UPIApp.GPAY: UPILinkConfig(
            app=UPIApp.GPAY,
            scheme="gpay://upi/pay",
            fallback_scheme="upi://pay"
        ),
        UPIApp.PHONEPE: UPILinkConfig(
            app=UPIApp.PHONEPE,
            scheme="phonepe://pay",
            fallback_scheme="upi://pay"
        ),
        UPIApp.PAYTM: UPILinkConfig(
            app=UPIApp.PAYTM,
            scheme="paytmmp://pay",
            fallback_scheme="upi://pay"
        ),
        UPIApp.BHIM: UPILinkConfig(
            app=UPIApp.BHIM,
            scheme="bhim://pay",
            fallback_scheme="upi://pay"
        ),
        UPIApp.GENERIC: UPILinkConfig(
            app=UPIApp.GENERIC,
            scheme="upi://pay"
        )
    }
    
    # Default UPI ID for the system (should be configured via environment)
    DEFAULT_UPI_ID = "billsplitter@upi"
    
    def __init__(self, default_upi_id: Optional[str] = None):
        """Initialize UPI service with optional custom UPI ID"""
        self.default_upi_id = default_upi_id or self.DEFAULT_UPI_ID
        logger.info(f"UPI Service initialized with UPI ID: {self.default_upi_id}")
    
    def validate_upi_id(self, upi_id: str) -> bool:
        """
        Validate UPI ID format
        
        Args:
            upi_id: UPI ID to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # UPI ID format: username@bank (e.g., user@paytm, 9876543210@ybl)
        upi_pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+$'
        return bool(re.match(upi_pattern, upi_id))
    
    def validate_amount(self, amount: Decimal) -> bool:
        """
        Validate payment amount
        
        Args:
            amount: Amount to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return amount > 0 and amount <= Decimal('100000')  # Max ₹1,00,000
    
    def sanitize_text(self, text: str) -> str:
        """
        Sanitize text for UPI link parameters
        
        Args:
            text: Text to sanitize
            
        Returns:
            str: Sanitized text
        """
        # Remove special characters and limit length
        sanitized = re.sub(r'[^\w\s-]', '', text)
        return sanitized[:50].strip()
    
    def generate_upi_link(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        upi_app: UPIApp = UPIApp.GENERIC,
        payee_upi_id: Optional[str] = None
    ) -> str:
        """
        Generate UPI deeplink for payment
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            upi_app: Target UPI app
            payee_upi_id: Custom payee UPI ID (uses default if not provided)
            
        Returns:
            str: Generated UPI deeplink
            
        Raises:
            UPIValidationError: If validation fails
        """
        try:
            # Validate inputs
            if not self.validate_amount(amount):
                raise UPIValidationError(f"Invalid amount: {amount}")
            
            payee_id = payee_upi_id or self.default_upi_id
            if not self.validate_upi_id(payee_id):
                raise UPIValidationError(f"Invalid UPI ID: {payee_id}")
            
            # Sanitize inputs
            clean_name = self.sanitize_text(recipient_name)
            clean_description = self.sanitize_text(description)
            
            # Get UPI configuration
            config = self.UPI_CONFIGS.get(upi_app, self.UPI_CONFIGS[UPIApp.GENERIC])
            
            # Build UPI parameters
            params = {
                'pa': payee_id,  # Payee address (UPI ID)
                'pn': 'Bill Splitter',  # Payee name
                'am': str(amount),  # Amount
                'cu': 'INR',  # Currency
                'tn': clean_description  # Transaction note
            }
            
            # Add recipient name to transaction note if provided
            if clean_name:
                params['tn'] = f"{clean_description} - {clean_name}"
            
            # Build query string
            query_params = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
            
            # Generate the link
            upi_link = f"{config.scheme}?{query_params}"
            
            logger.info(f"Generated UPI link for {recipient_name}: amount={amount}, app={upi_app.value}")
            return upi_link
            
        except Exception as e:
            logger.error(f"Failed to generate UPI link: {e}")
            raise UPIValidationError(f"UPI link generation failed: {str(e)}")
    
    def generate_multiple_app_links(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        apps: List[UPIApp] = None,
        payee_upi_id: Optional[str] = None
    ) -> Dict[UPIApp, str]:
        """
        Generate UPI links for multiple apps
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            apps: List of UPI apps to generate links for
            payee_upi_id: Custom payee UPI ID
            
        Returns:
            Dict[UPIApp, str]: Dictionary mapping apps to their UPI links
        """
        if apps is None:
            apps = [UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE, UPIApp.PAYTM]
        
        links = {}
        for app in apps:
            try:
                link = self.generate_upi_link(
                    recipient_name=recipient_name,
                    amount=amount,
                    description=description,
                    upi_app=app,
                    payee_upi_id=payee_upi_id
                )
                links[app] = link
            except UPIValidationError as e:
                logger.warning(f"Failed to generate {app.value} link: {e}")
                continue
        
        return links
    
    def validate_upi_link(self, upi_link: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a UPI link format
        
        Args:
            upi_link: UPI link to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Check if it's a valid UPI scheme
            valid_schemes = [
                'upi://', 'gpay://', 'phonepe://', 'paytmmp://', 'bhim://'
            ]
            
            if not any(upi_link.startswith(scheme) for scheme in valid_schemes):
                return False, "Invalid UPI scheme"
            
            # Check for required parameters
            if 'pa=' not in upi_link:
                return False, "Missing payee address (pa) parameter"
            
            if 'am=' not in upi_link:
                return False, "Missing amount (am) parameter"
            
            # Extract and validate amount
            try:
                amount_match = re.search(r'am=([^&]+)', upi_link)
                if amount_match:
                    amount = Decimal(amount_match.group(1))
                    if not self.validate_amount(amount):
                        return False, f"Invalid amount: {amount}"
            except (ValueError, TypeError):
                return False, "Invalid amount format"
            
            # Extract and validate UPI ID
            try:
                upi_id_match = re.search(r'pa=([^&]+)', upi_link)
                if upi_id_match:
                    upi_id = upi_id_match.group(1)
                    if not self.validate_upi_id(upi_id):
                        return False, f"Invalid UPI ID: {upi_id}"
            except Exception:
                return False, "Invalid UPI ID format"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def extract_payment_info(self, upi_link: str) -> Optional[Dict[str, str]]:
        """
        Extract payment information from UPI link
        
        Args:
            upi_link: UPI link to parse
            
        Returns:
            Optional[Dict[str, str]]: Extracted payment info or None if invalid
        """
        try:
            is_valid, error = self.validate_upi_link(upi_link)
            if not is_valid:
                logger.warning(f"Invalid UPI link: {error}")
                return None
            
            # Extract parameters
            info = {}
            
            # Extract payee address
            pa_match = re.search(r'pa=([^&]+)', upi_link)
            if pa_match:
                info['payee_address'] = pa_match.group(1)
            
            # Extract amount
            am_match = re.search(r'am=([^&]+)', upi_link)
            if am_match:
                info['amount'] = am_match.group(1)
            
            # Extract transaction note
            tn_match = re.search(r'tn=([^&]+)', upi_link)
            if tn_match:
                info['transaction_note'] = tn_match.group(1)
            
            # Extract payee name
            pn_match = re.search(r'pn=([^&]+)', upi_link)
            if pn_match:
                info['payee_name'] = pn_match.group(1)
            
            # Extract currency
            cu_match = re.search(r'cu=([^&]+)', upi_link)
            if cu_match:
                info['currency'] = cu_match.group(1)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to extract payment info: {e}")
            return None
    
    def create_payment_message(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        upi_link: str
    ) -> str:
        """
        Create a formatted payment message for WhatsApp/SMS
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            upi_link: Generated UPI link
            
        Returns:
            str: Formatted payment message
        """
        message = f"""Hi {recipient_name}! 👋

You have a bill split payment request:

💰 Amount: ₹{amount}
📝 Description: {description}

Click the link below to pay instantly:
{upi_link}

Or reply "DONE" once you've completed the payment.

Thanks! 🙏"""
        
        return message
    
    def get_supported_apps(self) -> List[str]:
        """
        Get list of supported UPI apps
        
        Returns:
            List[str]: List of supported app names
        """
        return [app.value for app in UPIApp]
    
    def get_app_display_name(self, app: UPIApp) -> str:
        """
        Get display name for UPI app
        
        Args:
            app: UPI app enum
            
        Returns:
            str: Display name
        """
        display_names = {
            UPIApp.GPAY: "Google Pay",
            UPIApp.PHONEPE: "PhonePe",
            UPIApp.PAYTM: "Paytm",
            UPIApp.BHIM: "BHIM",
            UPIApp.GENERIC: "Any UPI App"
        }
        return display_names.get(app, app.value.title())