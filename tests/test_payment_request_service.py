"""
Tests for Payment Request Distribution Service
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
from uuid import uuid4

from app.services.payment_request_service import PaymentRequestService, PaymentRequestResult, DistributionSummary
from app.services.upi_service import UPIService, UPIApp
from app.models.database import Bill, BillParticipant, Contact, User, PaymentRequest
from app.models.enums import DeliveryMethod
from app.database.repositories import DatabaseRepository


class TestPaymentRequestService:
    """Test cases for PaymentRequestService"""
    
    @pytest.fixture
    def mock_db_repository(self):
        """Mock database repository"""
        return Mock(spec=DatabaseRepository)
    
    @pytest.fixture
    def mock_upi_service(self):
        """Mock UPI service"""
        return Mock(spec=UPIService)
    
    @pytest.fixture
    def payment_service(self, mock_db_repository, mock_upi_service):
        """Create payment request service with mocked dependencies"""
        return PaymentRequestService(mock_db_repository, mock_upi_service)
    
    @pytest.fixture
    def sample_bill(self):
        """Create sample bill with participants"""
        user = User(id=uuid4(), phone_number="+919876543210", name="Bill Organizer")
        
        bill = Bill(
            id=uuid4(),
            user_id=user.id,
            user=user,
            total_amount=Decimal("1000.00"),
            description="Dinner at Restaurant",
            status="active"
        )
        
        # Create contacts
        contact1 = Contact(id=uuid4(), user_id=user.id, name="Alice", phone_number="+919876543211")
        contact2 = Contact(id=uuid4(), user_id=user.id, name="Bob", phone_number="+919876543212")
        
        # Create participants
        participant1 = BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contact1.id,
            contact=contact1,
            amount_owed=Decimal("500.00"),
            payment_status="pending"
        )
        
        participant2 = BillParticipant(
            id=uuid4(),
            bill_id=bill.id,
            contact_id=contact2.id,
            contact=contact2,
            amount_owed=Decimal("500.00"),
            payment_status="pending"
        )
        
        bill.participants = [participant1, participant2]
        return bill
    
    @pytest.mark.asyncio
    async def test_distribute_payment_requests_success(self, payment_service, mock_db_repository, mock_upi_service, sample_bill):
        """Test successful payment request distribution"""
        # Setup mocks
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_upi_service.generate_upi_link.return_value = "upi://pay?pa=test@upi&am=500.00"
        
        # Mock payment request creation
        mock_payment_request = PaymentRequest(id=uuid4(), bill_participant_id=sample_bill.participants[0].id)
        mock_db_repository.create_payment_request.return_value = mock_payment_request
        mock_db_repository.update_payment_request.return_value = mock_payment_request
        mock_db_repository.update_bill_participant.return_value = sample_bill.participants[0]
        
        # Mock communication service
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            mock_comm.send_message_with_fallback.return_value = {
                "success": True,
                "final_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False,
                "error": None
            }
            
            # Execute
            result = await payment_service.distribute_payment_requests(
                bill_id=str(sample_bill.id),
                organizer_phone="+919876543210"
            )
            
            # Verify
            assert isinstance(result, DistributionSummary)
            assert result.bill_id == str(sample_bill.id)
            assert result.total_participants == 2
            assert result.successful_sends == 2
            assert result.failed_sends == 0
            assert result.whatsapp_sends == 2
            assert result.sms_sends == 0
            
            # Verify UPI links were generated
            assert mock_upi_service.generate_upi_link.call_count == 2
            
            # Verify messages were sent
            assert mock_comm.send_message_with_fallback.call_count == 3  # 2 participants + 1 organizer confirmation
    
    @pytest.mark.asyncio
    async def test_distribute_payment_requests_with_fallback(self, payment_service, mock_db_repository, mock_upi_service, sample_bill):
        """Test payment request distribution with SMS fallback"""
        # Setup mocks
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_upi_service.generate_upi_link.return_value = "upi://pay?pa=test@upi&am=500.00"
        
        mock_payment_request = PaymentRequest(id=uuid4(), bill_participant_id=sample_bill.participants[0].id)
        mock_db_repository.create_payment_request.return_value = mock_payment_request
        mock_db_repository.update_payment_request.return_value = mock_payment_request
        mock_db_repository.update_bill_participant.return_value = sample_bill.participants[0]
        
        # Mock communication service with fallback
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            mock_comm.send_message_with_fallback.return_value = {
                "success": True,
                "final_method": DeliveryMethod.SMS,
                "fallback_used": True,
                "error": None
            }
            
            # Execute
            result = await payment_service.distribute_payment_requests(
                bill_id=str(sample_bill.id),
                organizer_phone="+919876543210"
            )
            
            # Verify fallback was used
            assert result.successful_sends == 2
            assert result.sms_sends == 2
            assert result.whatsapp_sends == 0
            
            # Check that results indicate fallback was used
            for payment_result in result.results:
                assert payment_result.fallback_used is True
                assert payment_result.delivery_method == DeliveryMethod.SMS
    
    @pytest.mark.asyncio
    async def test_distribute_payment_requests_partial_failure(self, payment_service, mock_db_repository, mock_upi_service, sample_bill):
        """Test payment request distribution with partial failures"""
        # Setup mocks
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_upi_service.generate_upi_link.return_value = "upi://pay?pa=test@upi&am=500.00"
        
        mock_payment_request = PaymentRequest(id=uuid4(), bill_participant_id=sample_bill.participants[0].id)
        mock_db_repository.create_payment_request.return_value = mock_payment_request
        mock_db_repository.update_payment_request.return_value = mock_payment_request
        mock_db_repository.update_bill_participant.return_value = sample_bill.participants[0]
        
        # Mock communication service with mixed results
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            # First call succeeds, second fails
            mock_comm.send_message_with_fallback.side_effect = [
                {
                    "success": True,
                    "final_method": DeliveryMethod.WHATSAPP,
                    "fallback_used": False,
                    "error": None
                },
                {
                    "success": False,
                    "final_method": None,
                    "fallback_used": True,
                    "error": "All delivery methods failed"
                },
                {  # Organizer confirmation
                    "success": True,
                    "final_method": DeliveryMethod.WHATSAPP,
                    "fallback_used": False,
                    "error": None
                }
            ]
            
            # Execute
            result = await payment_service.distribute_payment_requests(
                bill_id=str(sample_bill.id),
                organizer_phone="+919876543210"
            )
            
            # Verify mixed results
            assert result.successful_sends == 1
            assert result.failed_sends == 1
            assert len(result.results) == 2
            
            # Check individual results
            successful_result = next(r for r in result.results if r.success)
            failed_result = next(r for r in result.results if not r.success)
            
            assert successful_result.delivery_method == DeliveryMethod.WHATSAPP
            assert failed_result.error == "All delivery methods failed"
    
    @pytest.mark.asyncio
    async def test_send_payment_reminder(self, payment_service, mock_db_repository, mock_upi_service, sample_bill):
        """Test sending payment reminders"""
        # Setup mocks
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_db_repository.get_latest_payment_request_for_participant.return_value = PaymentRequest(
            id=uuid4(),
            upi_link="upi://pay?pa=test@upi&am=500.00"
        )
        mock_db_repository.update_bill_participant.return_value = sample_bill.participants[0]
        
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            mock_comm.send_message_with_fallback.return_value = {
                "success": True,
                "final_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False,
                "error": None
            }
            
            # Execute
            result = await payment_service.send_payment_reminder(
                bill_id=str(sample_bill.id),
                participant_ids=[str(sample_bill.participants[0].id)],
                custom_message="Please pay soon!"
            )
            
            # Verify
            assert result.total_participants == 1
            assert result.successful_sends == 1
            assert "Please pay soon!" in result.results[0].message_sent
            
            # Verify reminder count would be incremented
            mock_db_repository.update_bill_participant.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_payment_confirmation(self, payment_service, mock_db_repository, sample_bill):
        """Test processing payment confirmation"""
        # Setup mocks
        participant = sample_bill.participants[0]
        mock_db_repository.get_participant_by_phone_and_bill.return_value = participant
        mock_db_repository.update_bill_participant.return_value = participant
        
        mock_payment_request = PaymentRequest(id=uuid4(), status="sent")
        mock_db_repository.get_latest_payment_request_for_participant.return_value = mock_payment_request
        mock_db_repository.update_payment_request.return_value = mock_payment_request
        
        # Mock bill as not fully paid yet
        sample_bill.is_fully_paid = False
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            mock_comm.send_message_with_fallback.return_value = {
                "success": True,
                "final_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False
            }
            
            # Execute
            result = await payment_service.process_payment_confirmation(
                participant_phone="+919876543211",
                bill_id=str(sample_bill.id),
                confirmation_message="DONE"
            )
            
            # Verify
            assert result is True
            mock_db_repository.update_bill_participant.assert_called()
            mock_db_repository.update_payment_request.assert_called()
            
            # Verify organizer was notified
            mock_comm.send_message_with_fallback.assert_called()
    
    def test_create_payment_message(self, payment_service):
        """Test payment message creation"""
        message = payment_service._create_payment_message(
            participant_name="Alice",
            amount=Decimal("500.00"),
            bill_description="Dinner",
            upi_link="upi://pay?pa=test@upi&am=500.00",
            custom_message="Please pay by tomorrow"
        )
        
        assert "Alice" in message
        assert "₹500.00" in message
        assert "Dinner" in message
        assert "upi://pay?pa=test@upi&am=500.00" in message
        assert "Please pay by tomorrow" in message
        assert "DONE" in message
    
    def test_create_reminder_message(self, payment_service):
        """Test reminder message creation"""
        message = payment_service._create_reminder_message(
            participant_name="Bob",
            amount=Decimal("300.00"),
            bill_description="Lunch",
            upi_link="upi://pay?pa=test@upi&am=300.00",
            reminder_count=2,
            custom_message="Second reminder"
        )
        
        assert "Bob" in message
        assert "₹300.00" in message
        assert "Lunch" in message
        assert "Second reminder" in message
        assert "checking in" in message.lower()  # Second reminder prefix
    
    def test_create_organizer_confirmation_message(self, payment_service, sample_bill):
        """Test organizer confirmation message creation"""
        summary = DistributionSummary(
            bill_id=str(sample_bill.id),
            total_participants=2,
            successful_sends=2,
            failed_sends=0,
            whatsapp_sends=2,
            sms_sends=0,
            results=[],
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        
        message = payment_service._create_organizer_confirmation_message(sample_bill, summary)
        
        assert "Payment requests sent successfully" in message
        assert "Dinner at Restaurant" in message
        assert "₹1000.00" in message
        assert "Participants: 2" in message
        assert "Successful: 2" in message
        assert "Failed: 0" in message
        assert "WhatsApp: 2" in message
    
    @pytest.mark.asyncio
    async def test_bill_not_found(self, payment_service, mock_db_repository):
        """Test handling when bill is not found"""
        mock_db_repository.get_bill_with_participants.return_value = None
        
        with pytest.raises(ValueError, match="Bill .* not found"):
            await payment_service.distribute_payment_requests(
                bill_id="nonexistent-bill-id",
                organizer_phone="+919876543210"
            )
    
    @pytest.mark.asyncio
    async def test_no_participants(self, payment_service, mock_db_repository):
        """Test handling when bill has no participants"""
        bill = Bill(id=uuid4(), total_amount=Decimal("100.00"), participants=[])
        mock_db_repository.get_bill_with_participants.return_value = bill
        
        with pytest.raises(ValueError, match="No participants found"):
            await payment_service.distribute_payment_requests(
                bill_id=str(bill.id),
                organizer_phone="+919876543210"
            )
    
    @pytest.mark.asyncio
    async def test_skip_already_paid_participants(self, payment_service, mock_db_repository, mock_upi_service, sample_bill):
        """Test that already paid participants are skipped"""
        # Mark first participant as already paid
        sample_bill.participants[0].payment_status = 'confirmed'
        
        mock_db_repository.get_bill_with_participants.return_value = sample_bill
        mock_upi_service.generate_upi_link.return_value = "upi://pay?pa=test@upi&am=500.00"
        
        mock_payment_request = PaymentRequest(id=uuid4(), bill_participant_id=sample_bill.participants[1].id)
        mock_db_repository.create_payment_request.return_value = mock_payment_request
        mock_db_repository.update_payment_request.return_value = mock_payment_request
        mock_db_repository.update_bill_participant.return_value = sample_bill.participants[1]
        
        with patch('app.services.payment_request_service.communication_service') as mock_comm:
            mock_comm.send_message_with_fallback.return_value = {
                "success": True,
                "final_method": DeliveryMethod.WHATSAPP,
                "fallback_used": False,
                "error": None
            }
            
            # Execute
            result = await payment_service.distribute_payment_requests(
                bill_id=str(sample_bill.id),
                organizer_phone="+919876543210"
            )
            
            # Verify only one participant was processed
            assert result.total_participants == 1
            assert result.successful_sends == 1
            
            # Verify UPI link was generated only once
            mock_upi_service.generate_upi_link.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])