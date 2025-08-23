"""
Payment Service Implementation

This service handles payment request generation, UPI link creation,
and payment tracking for the bill splitting system.

Requirements implemented:
- 4.1: Generate UPI deeplinks for each participant with their specific amount
- 4.5: Store tracking information in the database
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from uuid import UUID

from app.interfaces.services import PaymentServiceInterface
from app.interfaces.repositories import PaymentRepository
from app.services.upi_service import UPIService, UPIApp, UPIValidationError
from app.models.schemas import Participant, PaymentRequest
from app.models.enums import PaymentStatus

logger = logging.getLogger(__name__)


class PaymentService(PaymentServiceInterface):
    """Payment service implementation with UPI integration"""
    
    def __init__(
        self,
        upi_service: UPIService,
        payment_repository: PaymentRepository,
        default_upi_id: Optional[str] = None
    ):
        """
        Initialize payment service
        
        Args:
            upi_service: UPI service for link generation
            payment_repository: Repository for payment data
            default_upi_id: Default UPI ID for payments
        """
        self.upi_service = upi_service
        self.payment_repository = payment_repository
        self.default_upi_id = default_upi_id
        logger.info("Payment service initialized")
    
    async def generate_upi_link(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        upi_app: Optional[str] = None,
        payee_upi_id: Optional[str] = None
    ) -> str:
        """
        Generate UPI deeplink with support for multiple apps
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            upi_app: Target UPI app (optional)
            payee_upi_id: Custom payee UPI ID (optional)
            
        Returns:
            str: Generated UPI deeplink
            
        Raises:
            UPIValidationError: If validation fails
        """
        try:
            # Convert string app to enum if provided
            app_enum = UPIApp.GENERIC
            if upi_app:
                try:
                    app_enum = UPIApp(upi_app.lower())
                except ValueError:
                    logger.warning(f"Unknown UPI app: {upi_app}, using generic")
                    app_enum = UPIApp.GENERIC
            
            # Use provided UPI ID or default
            upi_id = payee_upi_id or self.default_upi_id
            
            # Generate the link
            link = self.upi_service.generate_upi_link(
                recipient_name=recipient_name,
                amount=amount,
                description=description,
                upi_app=app_enum,
                payee_upi_id=upi_id
            )
            
            logger.info(f"Generated UPI link for {recipient_name}: amount={amount}")
            return link
            
        except UPIValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate UPI link: {e}")
            raise UPIValidationError(f"UPI link generation failed: {str(e)}")
    
    async def generate_multiple_upi_links(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        apps: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Generate UPI links for multiple apps
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            apps: List of UPI app names (optional)
            
        Returns:
            Dict[str, str]: Dictionary mapping app names to UPI links
        """
        try:
            # Convert string apps to enums
            app_enums = []
            if apps:
                for app in apps:
                    try:
                        app_enums.append(UPIApp(app.lower()))
                    except ValueError:
                        logger.warning(f"Unknown UPI app: {app}, skipping")
            else:
                # Use default apps
                app_enums = [UPIApp.GENERIC, UPIApp.GPAY, UPIApp.PHONEPE, UPIApp.PAYTM]
            
            # Generate links for each app
            links = self.upi_service.generate_multiple_app_links(
                recipient_name=recipient_name,
                amount=amount,
                description=description,
                apps=app_enums,
                payee_upi_id=self.default_upi_id
            )
            
            # Convert enum keys back to strings
            string_links = {app.value: link for app, link in links.items()}
            
            logger.info(f"Generated {len(string_links)} UPI links for {recipient_name}")
            return string_links
            
        except Exception as e:
            logger.error(f"Failed to generate multiple UPI links: {e}")
            raise UPIValidationError(f"Multiple UPI link generation failed: {str(e)}")
    
    async def validate_upi_link(self, upi_link: str) -> Tuple[bool, Optional[str]]:
        """
        Validate UPI link format and parameters
        
        Args:
            upi_link: UPI link to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            return self.upi_service.validate_upi_link(upi_link)
        except Exception as e:
            logger.error(f"UPI link validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def create_payment_message(
        self,
        recipient_name: str,
        amount: Decimal,
        description: str,
        upi_link: str
    ) -> str:
        """
        Create formatted payment message for WhatsApp/SMS
        
        Args:
            recipient_name: Name of the person who should pay
            amount: Amount to be paid
            description: Payment description
            upi_link: Generated UPI link
            
        Returns:
            str: Formatted payment message
        """
        try:
            return self.upi_service.create_payment_message(
                recipient_name=recipient_name,
                amount=amount,
                description=description,
                upi_link=upi_link
            )
        except Exception as e:
            logger.error(f"Failed to create payment message: {e}")
            # Return a basic message as fallback
            return f"Hi {recipient_name}! Please pay ₹{amount} for {description}. Link: {upi_link}"
    
    async def create_payment_requests(
        self,
        bill_id: str,
        participants: List[Participant]
    ) -> List[PaymentRequest]:
        """
        Create payment requests for all participants
        
        Args:
            bill_id: Bill ID
            participants: List of participants with amounts
            
        Returns:
            List[PaymentRequest]: Created payment requests
        """
        try:
            payment_requests = []
            
            for participant in participants:
                # Generate UPI link for participant
                upi_link = await self.generate_upi_link(
                    recipient_name=participant.name,
                    amount=participant.amount_owed,
                    description=f"Bill payment - {bill_id[:8]}"
                )
                
                # Validate the generated link
                is_valid, error = await self.validate_upi_link(upi_link)
                if not is_valid:
                    logger.error(f"Generated invalid UPI link for {participant.name}: {error}")
                    raise UPIValidationError(f"Invalid UPI link generated: {error}")
                
                # Create payment request in database
                if participant.contact_id:
                    payment_request = await self.payment_repository.create_payment_request(
                        participant_id=UUID(participant.contact_id),
                        upi_link=upi_link
                    )
                    
                    # Convert to schema model
                    request_schema = PaymentRequest(
                        id=str(payment_request.id),
                        bill_id=bill_id,
                        participant_id=participant.contact_id,
                        amount=participant.amount_owed,
                        upi_link=upi_link,
                        status=PaymentStatus.PENDING
                    )
                    
                    payment_requests.append(request_schema)
                    logger.info(f"Created payment request for {participant.name}: ₹{participant.amount_owed}")
                else:
                    logger.warning(f"No contact ID for participant {participant.name}, skipping payment request")
            
            logger.info(f"Created {len(payment_requests)} payment requests for bill {bill_id}")
            return payment_requests
            
        except UPIValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create payment requests: {e}")
            raise Exception(f"Payment request creation failed: {str(e)}")
    
    async def send_payment_requests(self, requests: List[PaymentRequest]) -> Dict[str, Any]:
        """
        Send payment requests to participants
        
        Note: This method prepares the requests but doesn't actually send them.
        The actual sending is handled by the communication service.
        
        Args:
            requests: List of payment requests to send
            
        Returns:
            Dict[str, Any]: Summary of prepared requests
        """
        try:
            prepared_messages = []
            
            for request in requests:
                # Create payment message
                message = await self.create_payment_message(
                    recipient_name=f"Participant {request.participant_id[:8]}",
                    amount=request.amount,
                    description="Bill payment",
                    upi_link=request.upi_link
                )
                
                prepared_messages.append({
                    "request_id": request.id,
                    "participant_id": request.participant_id,
                    "amount": str(request.amount),
                    "upi_link": request.upi_link,
                    "message": message
                })
            
            logger.info(f"Prepared {len(prepared_messages)} payment messages for sending")
            
            return {
                "prepared_count": len(prepared_messages),
                "messages": prepared_messages,
                "status": "prepared"
            }
            
        except Exception as e:
            logger.error(f"Failed to prepare payment requests: {e}")
            raise Exception(f"Payment request preparation failed: {str(e)}")
    
    async def confirm_payment(self, request_id: str) -> bool:
        """
        Confirm payment received
        
        Args:
            request_id: Payment request ID
            
        Returns:
            bool: True if confirmation successful
        """
        try:
            # Update payment request status in database
            success = await self.payment_repository.confirm_payment(UUID(request_id))
            
            if success:
                logger.info(f"Payment confirmed for request {request_id}")
            else:
                logger.warning(f"Failed to confirm payment for request {request_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to confirm payment: {e}")
            return False
    
    async def get_payment_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get payment request status
        
        Args:
            request_id: Payment request ID
            
        Returns:
            Optional[Dict[str, Any]]: Payment status information
        """
        try:
            payment_request = await self.payment_repository.get_payment_request(UUID(request_id))
            
            if payment_request:
                return {
                    "id": str(payment_request.id),
                    "status": payment_request.status,
                    "amount": str(payment_request.bill_participant.amount_owed),
                    "whatsapp_sent": payment_request.whatsapp_sent,
                    "sms_sent": payment_request.sms_sent,
                    "created_at": payment_request.created_at.isoformat(),
                    "confirmed_at": payment_request.confirmed_at.isoformat() if payment_request.confirmed_at else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get payment status: {e}")
            return None
    
    async def resend_payment_request(self, request_id: str) -> bool:
        """
        Resend payment request
        
        Args:
            request_id: Payment request ID
            
        Returns:
            bool: True if resend successful
        """
        try:
            # Get payment request
            payment_request = await self.payment_repository.get_payment_request(UUID(request_id))
            
            if not payment_request:
                logger.warning(f"Payment request not found: {request_id}")
                return False
            
            # Reset delivery flags to allow resending
            await self.payment_repository.reset_delivery_status(UUID(request_id))
            
            logger.info(f"Reset delivery status for payment request {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resend payment request: {e}")
            return False
    
    async def get_supported_upi_apps(self) -> List[Dict[str, str]]:
        """
        Get list of supported UPI apps
        
        Returns:
            List[Dict[str, str]]: List of supported apps with display names
        """
        try:
            apps = []
            for app in UPIApp:
                apps.append({
                    "code": app.value,
                    "display_name": self.upi_service.get_app_display_name(app)
                })
            
            return apps
            
        except Exception as e:
            logger.error(f"Failed to get supported UPI apps: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on payment service
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            # Test UPI link generation
            test_link = self.upi_service.generate_upi_link(
                recipient_name="Health Check",
                amount=Decimal("1"),
                description="Test"
            )
            
            # Test link validation
            is_valid, error = self.upi_service.validate_upi_link(test_link)
            
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "upi_service": "operational" if is_valid else f"error: {error}",
                "supported_apps": len(self.upi_service.get_supported_apps()),
                "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                    "health", logging.INFO, "", 0, "", (), None
                )) if logger.handlers else "unknown"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "unknown"
            }