"""
Tests for BillQueryService
Tests requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.bill_query_service import BillQueryService
from app.models.database import User, Bill, BillParticipant, Contact, PaymentRequest
from app.models.schemas import BillFilters, BillSummary, BillStatusInfo, BillDetails, ParticipantDetails
from app.models.enums import BillStatus, PaymentStatus


class TestBillQueryService:
    """Test suite for BillQueryService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_payment_service(self):
        """Mock payment request service"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_communication_service(self):
        """Mock communication service"""
        service = AsyncMock()
        service.send_message_with_fallback = AsyncMock(return_value={"success": True, "method": "whatsapp"})
        return service
    
    @pytest.fixture
    def bill_query_service(self, mock_db, mock_payment_service, mock_communication_service):
        """Create BillQueryService instance"""
        return BillQueryService(mock_db, mock_payment_service, mock_communication_service)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user"""
        user = Mock(spec=User)
        user.id = uuid4()
        user.phone_number = "+1234567890"
        user.name = "Test User"
        return user
    
    @pytest.fixture
    def sample_contact(self):
        """Create sample contact"""
        contact = Mock(spec=Contact)
        contact.id = uuid4()
        contact.name = "John Doe"
        contact.phone_number = "+1234567891"
        return contact
    
    @pytest.fixture
    def sample_bill(self, sample_user):
        """Create sample bill"""
        bill = Mock(spec=Bill)
        bill.id = uuid4()
        bill.user_id = sample_user.id
        bill.total_amount = Decimal("100.00")
        bill.description = "Test Bill"
        bill.merchant = "Test Merchant"
        bill.bill_date = datetime.now()
        bill.created_at = datetime.now()
        bill.status = "active"
        bill.currency = "INR"
        bill.items_data = [
            {"name": "Item 1", "amount": 50.00, "quantity": 1},
            {"name": "Item 2", "amount": 50.00, "quantity": 1}
        ]
        return bill
    
    @pytest.fixture
    def sample_participant(self, sample_contact):
        """Create sample bill participant"""
        participant = Mock(spec=BillParticipant)
        participant.id = uuid4()
        participant.contact = sample_contact
        participant.amount_owed = Decimal("50.00")
        participant.payment_status = "pending"
        participant.paid_at = None
        participant.reminder_count = 0
        participant.last_reminder_sent = None
        return participant
    
    @pytest.mark.asyncio
    async def test_get_user_bills_success(self, bill_query_service, mock_db, sample_user, sample_bill, sample_participant):
        """Test successful retrieval of user bills - Requirement 6.1"""
        # Setup
        sample_bill.participants = [sample_participant]
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_bill]
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_user_bills(str(sample_user.id))
        
        # Verify
        assert len(result) == 1
        assert isinstance(result[0], BillSummary)
        assert result[0].id == str(sample_bill.id)
        assert result[0].total_amount == sample_bill.total_amount
        assert result[0].participant_count == 1
        assert result[0].paid_count == 0
        assert result[0].status == BillStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_get_user_bills_with_filters(self, bill_query_service, mock_db, sample_user, sample_bill):
        """Test bill retrieval with filters - Requirement 6.1"""
        # Setup
        sample_bill.participants = []
        filters = BillFilters(
            status=BillStatus.ACTIVE,
            min_amount=Decimal("50.00"),
            max_amount=Decimal("200.00"),
            merchant="Test",
            limit=10,
            offset=0
        )
        
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_bill]
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_user_bills(str(sample_user.id), filters)
        
        # Verify
        assert len(result) == 1
        assert mock_query.filter.call_count >= 4  # Multiple filter calls
    
    @pytest.mark.asyncio
    async def test_get_bill_status_success(self, bill_query_service, mock_db, sample_user, sample_bill, sample_participant):
        """Test successful bill status retrieval - Requirement 6.2"""
        # Setup
        sample_bill.participants = [sample_participant]
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_bill_status(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert result is not None
        assert isinstance(result, BillStatusInfo)
        assert result.id == str(sample_bill.id)
        assert result.total_amount == sample_bill.total_amount
        assert result.total_paid == Decimal("0.00")  # No confirmed payments
        assert result.remaining_amount == sample_bill.total_amount
        assert result.completion_percentage == 0.0
        assert len(result.participants) == 1
    
    @pytest.mark.asyncio
    async def test_get_bill_status_not_found(self, bill_query_service, mock_db, sample_user):
        """Test bill status retrieval when bill not found - Requirement 6.5"""
        # Setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_bill_status(str(sample_user.id), str(uuid4()))
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_bill_details_success(self, bill_query_service, mock_db, sample_user, sample_bill, sample_participant):
        """Test successful bill details retrieval - Requirement 6.3"""
        # Setup
        sample_bill.participants = [sample_participant]
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_bill_details(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert result is not None
        assert isinstance(result, BillDetails)
        assert result.id == str(sample_bill.id)
        assert result.total_amount == sample_bill.total_amount
        assert result.currency == sample_bill.currency
        assert result.merchant == sample_bill.merchant
        assert len(result.items) == 2  # From items_data
        assert len(result.participants) == 1
        assert result.items[0].name == "Item 1"
        assert result.items[0].amount == Decimal("50.00")
    
    @pytest.mark.asyncio
    async def test_get_unpaid_participants(self, bill_query_service, mock_db, sample_user, sample_bill, sample_participant):
        """Test getting unpaid participants"""
        # Setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_participant]
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_unpaid_participants(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert len(result) == 1
        assert isinstance(result[0], ParticipantDetails)
        assert result[0].id == str(sample_participant.id)
        assert result[0].payment_status == PaymentStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_send_payment_reminders_success(self, bill_query_service, mock_db, mock_communication_service, 
                                                sample_user, sample_bill, sample_participant):
        """Test successful payment reminder sending - Requirement 6.4"""
        # Setup
        sample_bill.participants = [sample_participant]
        
        # Mock existing payment request
        payment_request = Mock(spec=PaymentRequest)
        payment_request.id = uuid4()
        payment_request.upi_link = "upi://pay?pa=test@upi&pn=Test&am=50.00"
        
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_query.order_by.return_value = mock_query
        
        # Setup different return values for different queries
        def query_side_effect(model):
            if model == Bill:
                return mock_query
            elif model == PaymentRequest:
                payment_query = Mock()
                payment_query.filter.return_value = payment_query
                payment_query.order_by.return_value = payment_query
                payment_query.first.return_value = payment_request
                return payment_query
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        mock_db.commit = Mock()
        
        # Execute
        result = await bill_query_service.send_payment_reminders(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert result["success"] is True
        assert result["reminded_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["details"]) == 1
        assert result["details"][0]["status"] == "sent"
        mock_communication_service.send_message_with_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_payment_reminders_specific_participants(self, bill_query_service, mock_db, 
                                                              mock_communication_service, sample_user, 
                                                              sample_bill, sample_participant):
        """Test sending reminders to specific participants - Requirement 6.4"""
        # Setup
        participant2 = Mock(spec=BillParticipant)
        participant2.id = uuid4()
        participant2.contact = Mock()
        participant2.contact.name = "Jane Doe"
        participant2.contact.phone_number = "+1234567892"
        participant2.payment_status = "pending"
        participant2.reminder_count = 0
        
        sample_bill.participants = [sample_participant, participant2]
        
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_db.query.return_value = mock_query
        
        # Execute - only remind first participant
        result = await bill_query_service.send_payment_reminders(
            str(sample_user.id), 
            str(sample_bill.id), 
            [str(sample_participant.id)]
        )
        
        # Verify - should only send one reminder
        assert result["reminded_count"] <= 1  # Only one participant should be reminded
    
    @pytest.mark.asyncio
    async def test_send_payment_reminders_no_unpaid_participants(self, bill_query_service, mock_db, 
                                                               sample_user, sample_bill, sample_participant):
        """Test reminder sending when all participants have paid"""
        # Setup - mark participant as paid
        sample_participant.payment_status = "confirmed"
        sample_bill.participants = [sample_participant]
        
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.send_payment_reminders(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert result["success"] is True
        assert result["reminded_count"] == 0
        assert "No participants need reminders" in result["message"]
    
    @pytest.mark.asyncio
    async def test_send_payment_reminders_bill_not_found(self, bill_query_service, mock_db, sample_user):
        """Test reminder sending when bill not found - Requirement 6.5"""
        # Setup
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.send_payment_reminders(str(sample_user.id), str(uuid4()))
        
        # Verify
        assert result["success"] is False
        assert "Bill not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_reminder_message(self, bill_query_service):
        """Test reminder message creation"""
        # Execute
        message = bill_query_service._create_reminder_message(
            "John Doe", 
            Decimal("50.00"), 
            "Test Bill", 
            "upi://pay?pa=test@upi", 
            1
        )
        
        # Verify
        assert "Reminder:" in message
        assert "John Doe" in message
        assert "₹50.00" in message
        assert "Test Bill" in message
        assert "upi://pay?pa=test@upi" in message
    
    @pytest.mark.asyncio
    async def test_create_reminder_message_multiple_reminders(self, bill_query_service):
        """Test reminder message for multiple reminders"""
        # Execute
        message = bill_query_service._create_reminder_message(
            "John Doe", 
            Decimal("50.00"), 
            "Test Bill", 
            "upi://pay?pa=test@upi", 
            3
        )
        
        # Verify
        assert "Reminder #3:" in message
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_uuid(self, bill_query_service):
        """Test error handling for invalid UUIDs"""
        # Execute
        result = await bill_query_service.get_user_bills("invalid-uuid")
        
        # Verify
        assert result == []
    
    @pytest.mark.asyncio
    async def test_bill_status_with_partial_payments(self, bill_query_service, mock_db, sample_user, 
                                                   sample_bill, sample_participant):
        """Test bill status calculation with partial payments"""
        # Setup - one paid, one unpaid participant
        paid_participant = Mock(spec=BillParticipant)
        paid_participant.id = uuid4()
        paid_participant.contact = Mock()
        paid_participant.contact.name = "Paid User"
        paid_participant.contact.phone_number = "+1234567893"
        paid_participant.amount_owed = Decimal("30.00")
        paid_participant.payment_status = "confirmed"
        paid_participant.paid_at = datetime.now()
        paid_participant.reminder_count = 0
        paid_participant.last_reminder_sent = None
        
        sample_participant.amount_owed = Decimal("70.00")
        sample_bill.participants = [sample_participant, paid_participant]
        
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_bill
        mock_db.query.return_value = mock_query
        
        # Execute
        result = await bill_query_service.get_bill_status(str(sample_user.id), str(sample_bill.id))
        
        # Verify
        assert result is not None
        assert result.total_paid == Decimal("30.00")
        assert result.remaining_amount == Decimal("70.00")
        assert result.completion_percentage == 30.0
        assert len(result.participants) == 2