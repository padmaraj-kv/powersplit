"""
Tests for Payment Confirmation Service
Tests requirements 5.1, 5.2, 5.3, 5.5
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.payment_confirmation_service import PaymentConfirmationService, PaymentConfirmationResult
from app.models.database import Bill, BillParticipant, PaymentRequest, Contact, User
from app.models.enums import PaymentStatus
from app.database.repositories import DatabaseRepository


class TestPaymentConfirmationService:
    """Test payment confirmation service functionality"""
    
    @pytest.fixture
    def mock_db_repository(self):
        """Create mock database repository"""
        return Mock(spec=DatabaseRepository)
    
    @pytest.fixture
    def payment_confirmation_service(self, mock_db_repository):
        """Create payment confirmation service with mocked dependencies"""
        return PaymentConfirmationService(mock_db_repository)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user"""
        user = Mock(spec=User)
        user.id = uuid4()
        user.phone_number = "+919876543210"
        user.name = "Bill Organizer"
        return user
    
    @pytest.fixture
    def sample_contact(self):
        """Create sample contact"""
        contact = Mock(spec=Contact)
        contact.id = uuid4()
        contact.name = "John Doe"
        contact.phone_number = "+919876543211"
        return contact
    
    @pytest.fixture
    def sample_bill(self, sample_user):
        """Create sample bill"""
        bill = Mock(spec=Bill)
        bill.id = uuid4()
        bill.user_id = sample_user.id
        bill.user = sample_user
        bill.total_amount = Decimal('150.00')
        bill.description = "Lunch at Pizza Palace"
        bill.status = 'active'
        bill.participants = []
        return bill
    
    @pytest.fixture
    def sample_participant(self, sample_bill, sample_contact):
        """Create sample bill participant"""
        participant = Mock(spec=BillParticipant)
        participant.id = uuid4()
        participant.bill_id = sample_bill.id
        participant.bill = sample_bill
        participant.contact_id = sample_contact.id
        participant.contact = sample_contact
        participant.amount_owed = Decimal('50.00')
        participant.payment_status = PaymentStatus.SENT
        participant.paid_at = None
        return participant
    
    @pytest.fixture
    def sample_payment_request(self, sample_participant):
        """Create sample payment request"""
        payment_request = Mock(spec=PaymentRequest)
        payment_request.id = uuid4()
        payment_request.bill_participant_id = sample_participant.id
        payment_request.upi_link = "upi://pay?pa=test@upi&pn=Test&am=50.00"
        payment_request.status = 'sent'
        payment_request.mark_as_confirmed = Mock()
        return payment_request
    
    @pytest.mark.asyncio
    async def test_is_confirmation_message_positive_cases(self, payment_confirmation_service):
        """Test confirmation message detection - positive cases"""
        confirmation_messages = [
            "done",
            "DONE",
            "paid",
            "Payment done",
            "I have paid the amount",
            "Money sent ✅",
            "Completed the payment",
            "Payment made successfully",
            "👍 paid",
            "finished paying"
        ]
        
        for message in confirmation_messages:
            assert payment_confirmation_service._is_confirmation_message(message), f"Should detect '{message}' as confirmation"
    
    @pytest.mark.asyncio
    async def test_is_confirmation_message_negative_cases(self, payment_confirmation_service):
        """Test confirmation message detection - negative cases"""
        non_confirmation_messages = [
            "hello",
            "how much do I owe?",
            "what's the bill about?",
            "can you send the link again?",
            "I will pay tomorrow",
            "payment pending",
            "not done yet"
        ]
        
        for message in non_confirmation_messages:
            assert not payment_confirmation_service._is_confirmation_message(message), f"Should not detect '{message}' as confirmation"
    
    @pytest.mark.asyncio
    async def test_process_payment_confirmation_success(
        self, 
        payment_confirmation_service, 
        mock_db_repository,
        sample_participant,
        sample_bill,
        sample_payment_request
    ):
        """Test successful payment confirmation processing"""
        # Setup mocks
        sample_bill.participants = [sample_participant]
        sample_bill.is_fully_paid = False
        
        mock_db_repository.find_active_participants_by_phone.return_value = [sample_participant]
        mock_db_repository.update_bill_participant = AsyncMock(return_value=sample_participant)
        mock_db_repository.get_latest_payment_request_for_participant.return_value = sample_payment_request
        mock_db_repository.update_payment_request = AsyncMock(return_value=sample_payment_request)
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        
        # Mock communication service
        with patch.object(payment_confirmation_service, 'communication') as mock_comm:
            mock_comm.send_message_with_fallback = AsyncMock(return_value={"success": True})
            
            # Test payment confirmation
            result = await payment_confirmation_service.process_payment_confirmation_message(
                sender_phone="+919876543211",
                message_content="done",
                message_timestamp=datetime.now()
            )
        
        # Verify result
        assert result.success
        assert result.participant_id == str(sample_participant.id)
        assert result.participant_name == "John Doe"
        assert result.amount == Decimal('50.00')
        assert result.organizer_notified
        
        # Verify participant status was updated
        assert sample_participant.payment_status == PaymentStatus.CONFIRMED
        mock_db_repository.update_bill_participant.assert_called_once()
        
        # Verify payment request was updated
        sample_payment_request.mark_as_confirmed.assert_called_once()
        mock_db_repository.update_payment_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_payment_confirmation_no_active_participants(
        self, 
        payment_confirmation_service, 
        mock_db_repository
    ):
        """Test payment confirmation when no active participants found"""
        # Setup mocks
        mock_db_repository.find_active_participants_by_phone.return_value = []
        
        # Test payment confirmation
        result = await payment_confirmation_service.process_payment_confirmation_message(
            sender_phone="+919876543211",
            message_content="done",
            message_timestamp=datetime.now()
        )
        
        # Verify result
        assert not result.success
        assert "No active bill participants found" in result.error
    
    @pytest.mark.asyncio
    async def test_process_payment_confirmation_not_confirmation_message(
        self, 
        payment_confirmation_service, 
        mock_db_repository
    ):
        """Test processing non-confirmation message"""
        # Test with non-confirmation message
        result = await payment_confirmation_service.process_payment_confirmation_message(
            sender_phone="+919876543211",
            message_content="hello there",
            message_timestamp=datetime.now()
        )
        
        # Verify result
        assert not result.success
        assert "does not indicate payment confirmation" in result.error
    
    @pytest.mark.asyncio
    async def test_completion_detection(
        self, 
        payment_confirmation_service, 
        mock_db_repository,
        sample_participant,
        sample_bill,
        sample_payment_request
    ):
        """Test completion detection when all payments are confirmed"""
        # Setup - create multiple participants, all but one confirmed
        participant2 = Mock(spec=BillParticipant)
        participant2.payment_status = PaymentStatus.CONFIRMED
        
        sample_bill.participants = [sample_participant, participant2]
        sample_bill.is_fully_paid = True  # Will be True after our participant confirms
        
        mock_db_repository.find_active_participants_by_phone.return_value = [sample_participant]
        mock_db_repository.update_bill_participant = AsyncMock(return_value=sample_participant)
        mock_db_repository.get_latest_payment_request_for_participant.return_value = sample_payment_request
        mock_db_repository.update_payment_request = AsyncMock(return_value=sample_payment_request)
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_db_repository.update_bill = AsyncMock(return_value=sample_bill)
        
        # Mock communication service
        with patch.object(payment_confirmation_service, 'communication') as mock_comm:
            mock_comm.send_message_with_fallback = AsyncMock(return_value={"success": True})
            
            # Test payment confirmation
            result = await payment_confirmation_service.process_payment_confirmation_message(
                sender_phone="+919876543211",
                message_content="paid",
                message_timestamp=datetime.now()
            )
        
        # Verify completion was detected
        assert result.success
        assert result.completion_detected
        
        # Verify bill status was updated to completed
        assert sample_bill.status == 'completed'
        mock_db_repository.update_bill.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_payment_inquiry(
        self, 
        payment_confirmation_service, 
        mock_db_repository,
        sample_participant,
        sample_bill,
        sample_payment_request
    ):
        """Test handling payment status inquiries"""
        # Setup mocks
        sample_bill.participants = [sample_participant]
        mock_db_repository.find_active_participants_by_phone.return_value = [sample_participant]
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_db_repository.get_latest_payment_request_for_participant.return_value = sample_payment_request
        
        # Test inquiry handling
        response = await payment_confirmation_service.handle_payment_inquiry(
            sender_phone="+919876543211",
            message_content="what's my bill status?"
        )
        
        # Verify response
        assert response is not None
        assert "Your Bill Status" in response
        assert "Lunch at Pizza Palace" in response
        assert "₹50.00" in response
        assert sample_payment_request.upi_link in response
    
    @pytest.mark.asyncio
    async def test_handle_payment_inquiry_no_active_bills(
        self, 
        payment_confirmation_service, 
        mock_db_repository
    ):
        """Test handling inquiry when no active bills found"""
        # Setup mocks
        mock_db_repository.find_active_participants_by_phone.return_value = []
        
        # Test inquiry handling
        response = await payment_confirmation_service.handle_payment_inquiry(
            sender_phone="+919876543211",
            message_content="what's my status?"
        )
        
        # Verify response
        assert response is not None
        assert "don't have any active bill information" in response
    
    @pytest.mark.asyncio
    async def test_handle_non_inquiry_message(
        self, 
        payment_confirmation_service, 
        mock_db_repository
    ):
        """Test handling non-inquiry message"""
        # Test with non-inquiry message
        response = await payment_confirmation_service.handle_payment_inquiry(
            sender_phone="+919876543211",
            message_content="hello there"
        )
        
        # Verify no response for non-inquiry
        assert response is None
    
    @pytest.mark.asyncio
    async def test_create_payment_notification_message(self, payment_confirmation_service):
        """Test payment notification message creation"""
        message = payment_confirmation_service._create_payment_notification_message(
            participant_name="John Doe",
            amount=Decimal('50.00'),
            bill_description="Lunch at Pizza Palace"
        )
        
        assert "✅ Payment Confirmed!" in message
        assert "John Doe" in message
        assert "₹50.00" in message
        assert "Lunch at Pizza Palace" in message
        assert "show bill status" in message
    
    @pytest.mark.asyncio
    async def test_create_completion_notification_message(self, payment_confirmation_service, sample_bill):
        """Test completion notification message creation"""
        sample_bill.participants = [Mock(), Mock()]  # 2 participants
        
        message = payment_confirmation_service._create_completion_notification_message(sample_bill)
        
        assert "🎉 All Payments Complete!" in message
        assert "2 participants" in message
        assert "₹150.00" in message
        assert "Lunch at Pizza Palace" in message
        assert "Thanks for using Bill Splitter!" in message
    
    @pytest.mark.asyncio
    async def test_already_confirmed_payment(
        self, 
        payment_confirmation_service, 
        mock_db_repository,
        sample_participant,
        sample_bill
    ):
        """Test processing confirmation for already confirmed payment"""
        # Setup - participant already confirmed
        sample_participant.payment_status = PaymentStatus.CONFIRMED
        sample_bill.participants = [sample_participant]
        
        mock_db_repository.find_active_participants_by_phone.return_value = [sample_participant]
        
        # Test payment confirmation
        result = await payment_confirmation_service.process_payment_confirmation_message(
            sender_phone="+919876543211",
            message_content="done",
            message_timestamp=datetime.now()
        )
        
        # Verify result
        assert result.success
        assert "already confirmed" in result.error
        assert not result.organizer_notified  # Should not notify again
    
    @pytest.mark.asyncio
    async def test_error_handling_in_confirmation_processing(
        self, 
        payment_confirmation_service, 
        mock_db_repository,
        sample_participant
    ):
        """Test error handling during confirmation processing"""
        # Setup mocks to raise exception
        mock_db_repository.find_active_participants_by_phone.return_value = [sample_participant]
        mock_db_repository.update_bill_participant = AsyncMock(side_effect=Exception("Database error"))
        
        # Test payment confirmation
        result = await payment_confirmation_service.process_payment_confirmation_message(
            sender_phone="+919876543211",
            message_content="done",
            message_timestamp=datetime.now()
        )
        
        # Verify error handling
        assert not result.success
        assert "Database error" in result.error


if __name__ == "__main__":
    pytest.main([__file__])