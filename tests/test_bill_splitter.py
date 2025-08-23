"""
Tests for bill splitting calculation engine
Tests requirements 2.1, 2.2, 2.3, 2.4, 2.5
"""
import pytest
from decimal import Decimal
from app.services.bill_splitter import BillSplitter
from app.models.schemas import BillData, Participant, BillItem
from app.models.enums import PaymentStatus


@pytest.fixture
def bill_splitter():
    """Create BillSplitter instance for testing"""
    return BillSplitter()


@pytest.fixture
def sample_bill():
    """Create sample bill data for testing"""
    return BillData(
        total_amount=Decimal('150.00'),
        description="Lunch at Pizza Palace",
        items=[
            BillItem(name="Pizza", amount=Decimal('100.00')),
            BillItem(name="Drinks", amount=Decimal('50.00'))
        ],
        currency="INR"
    )


@pytest.fixture
def sample_participants():
    """Create sample participants for testing"""
    return [
        Participant(
            name="John",
            phone_number="+91 9876543210",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_1"
        ),
        Participant(
            name="Sarah",
            phone_number="+91 9876543211",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_2"
        ),
        Participant(
            name="Mike",
            phone_number="+91 9876543212",
            amount_owed=Decimal('0.00'),
            payment_status=PaymentStatus.PENDING,
            contact_id="contact_3"
        )
    ]


class TestEqualSplits:
    """Test equal split calculations (Requirement 2.1)"""
    
    @pytest.mark.asyncio
    async def test_equal_split_basic(self, bill_splitter, sample_bill, sample_participants):
        """Test basic equal split calculation"""
        result = await bill_splitter.calculate_equal_splits(sample_bill, sample_participants)
        
        assert len(result) == 3
        assert result[0].amount_owed == Decimal('50.00')
        assert result[1].amount_owed == Decimal('50.00')
        assert result[2].amount_owed == Decimal('50.00')
        
        # Verify total matches bill amount
        total = sum(p.amount_owed for p in result)
        assert total == sample_bill.total_amount
    
    @pytest.mark.asyncio
    async def test_equal_split_with_rounding(self, bill_splitter, sample_participants):
        """Test equal split with rounding (e.g., 100/3)"""
        bill = BillData(
            total_amount=Decimal('100.00'),
            description="Test bill",
            currency="INR"
        )
        
        result = await bill_splitter.calculate_equal_splits(bill, sample_participants)
        
        # Should be 33.33, 33.33, 33.34 (first participant gets the extra cent)
        assert result[0].amount_owed == Decimal('33.34')
        assert result[1].amount_owed == Decimal('33.33')
        assert result[2].amount_owed == Decimal('33.33')
        
        # Verify total matches exactly
        total = sum(p.amount_owed for p in result)
        assert total == bill.total_amount
    
    @pytest.mark.asyncio
    async def test_equal_split_single_participant(self, bill_splitter, sample_bill):
        """Test equal split with single participant"""
        participants = [
            Participant(
                name="Solo",
                phone_number="+91 9876543210",
                amount_owed=Decimal('0.00'),
                payment_status=PaymentStatus.PENDING
            )
        ]
        
        result = await bill_splitter.calculate_equal_splits(sample_bill, participants)
        
        assert len(result) == 1
        assert result[0].amount_owed == sample_bill.total_amount
    
    @pytest.mark.asyncio
    async def test_equal_split_empty_participants(self, bill_splitter, sample_bill):
        """Test equal split with no participants raises error"""
        with pytest.raises(ValueError, match="No participants provided"):
            await bill_splitter.calculate_equal_splits(sample_bill, [])
    
    @pytest.mark.asyncio
    async def test_equal_split_zero_amount(self, bill_splitter, sample_participants):
        """Test equal split with zero bill amount raises error"""
        bill = BillData(
            total_amount=Decimal('0.00'),
            description="Zero bill",
            currency="INR"
        )
        
        with pytest.raises(ValueError, match="Bill total amount must be positive"):
            await bill_splitter.calculate_equal_splits(bill, sample_participants)


class TestCustomSplits:
    """Test custom split adjustments (Requirement 2.2)"""
    
    @pytest.mark.asyncio
    async def test_custom_splits_by_name(self, bill_splitter, sample_bill, sample_participants):
        """Test custom splits using participant names"""
        # First calculate equal splits
        equal_participants = await bill_splitter.calculate_equal_splits(sample_bill, sample_participants)
        
        # Apply custom amounts
        custom_amounts = {
            "John": Decimal('60.00'),
            "Sarah": Decimal('40.00'),
            "Mike": Decimal('50.00')
        }
        
        result = await bill_splitter.apply_custom_splits(sample_bill, equal_participants, custom_amounts)
        
        assert result[0].amount_owed == Decimal('60.00')  # John
        assert result[1].amount_owed == Decimal('40.00')  # Sarah
        assert result[2].amount_owed == Decimal('50.00')  # Mike
    
    @pytest.mark.asyncio
    async def test_custom_splits_by_contact_id(self, bill_splitter, sample_bill, sample_participants):
        """Test custom splits using contact IDs"""
        equal_participants = await bill_splitter.calculate_equal_splits(sample_bill, sample_participants)
        
        custom_amounts = {
            "contact_1": Decimal('70.00'),
            "contact_2": Decimal('80.00')
        }
        
        result = await bill_splitter.apply_custom_splits(sample_bill, equal_participants, custom_amounts)
        
        assert result[0].amount_owed == Decimal('70.00')  # John (contact_1)
        assert result[1].amount_owed == Decimal('80.00')  # Sarah (contact_2)
        assert result[2].amount_owed == Decimal('50.00')  # Mike (unchanged)
    
    @pytest.mark.asyncio
    async def test_custom_splits_partial_update(self, bill_splitter, sample_bill, sample_participants):
        """Test custom splits with only some participants updated"""
        equal_participants = await bill_splitter.calculate_equal_splits(sample_bill, sample_participants)
        
        custom_amounts = {
            "John": Decimal('75.00')
        }
        
        result = await bill_splitter.apply_custom_splits(sample_bill, equal_participants, custom_amounts)
        
        assert result[0].amount_owed == Decimal('75.00')  # John (updated)
        assert result[1].amount_owed == Decimal('50.00')  # Sarah (unchanged)
        assert result[2].amount_owed == Decimal('50.00')  # Mike (unchanged)
    
    @pytest.mark.asyncio
    async def test_custom_splits_negative_amount(self, bill_splitter, sample_bill, sample_participants):
        """Test custom splits with negative amount raises error"""
        equal_participants = await bill_splitter.calculate_equal_splits(sample_bill, sample_participants)
        
        custom_amounts = {
            "John": Decimal('-10.00')
        }
        
        with pytest.raises(ValueError, match="Custom amount for John must be positive"):
            await bill_splitter.apply_custom_splits(sample_bill, equal_participants, custom_amounts)


class TestSplitValidation:
    """Test split validation (Requirement 2.3)"""
    
    @pytest.mark.asyncio
    async def test_validation_valid_splits(self, bill_splitter, sample_bill, sample_participants):
        """Test validation with valid splits"""
        # Set up participants with amounts that match bill total
        sample_participants[0].amount_owed = Decimal('50.00')
        sample_participants[1].amount_owed = Decimal('50.00')
        sample_participants[2].amount_owed = Decimal('50.00')
        
        result = await bill_splitter.validate_splits(sample_bill, sample_participants)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validation_total_mismatch(self, bill_splitter, sample_bill, sample_participants):
        """Test validation with total mismatch"""
        # Set up participants with amounts that don't match bill total
        sample_participants[0].amount_owed = Decimal('40.00')
        sample_participants[1].amount_owed = Decimal('40.00')
        sample_participants[2].amount_owed = Decimal('40.00')  # Total: 120, Bill: 150
        
        result = await bill_splitter.validate_splits(sample_bill, sample_participants)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "don't match bill total" in result.errors[0]
        assert "₹120.00" in result.errors[0]
        assert "₹150.00" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validation_negative_amounts(self, bill_splitter, sample_bill, sample_participants):
        """Test validation with negative amounts"""
        sample_participants[0].amount_owed = Decimal('-10.00')
        sample_participants[1].amount_owed = Decimal('80.00')
        sample_participants[2].amount_owed = Decimal('80.00')
        
        result = await bill_splitter.validate_splits(sample_bill, sample_participants)
        
        assert result.is_valid is False
        assert any("Negative or zero amounts" in error for error in result.errors)
        assert "John" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validation_large_amounts_warning(self, bill_splitter, sample_bill, sample_participants):
        """Test validation with unreasonably large amounts generates warnings"""
        # Set up one participant with very large amount
        sample_participants[0].amount_owed = Decimal('120.00')  # 2.4x equal split
        sample_participants[1].amount_owed = Decimal('15.00')
        sample_participants[2].amount_owed = Decimal('15.00')
        
        result = await bill_splitter.validate_splits(sample_bill, sample_participants)
        
        assert result.is_valid is True  # Still valid, just warning
        assert len(result.warnings) > 0
        assert any("Large amounts detected" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validation_small_amounts_warning(self, bill_splitter, sample_bill, sample_participants):
        """Test validation with very small amounts generates warnings"""
        sample_participants[0].amount_owed = Decimal('149.50')
        sample_participants[1].amount_owed = Decimal('0.25')  # Very small
        sample_participants[2].amount_owed = Decimal('0.25')  # Very small
        
        result = await bill_splitter.validate_splits(sample_bill, sample_participants)
        
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("Very small amounts" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validation_empty_participants(self, bill_splitter, sample_bill):
        """Test validation with no participants"""
        result = await bill_splitter.validate_splits(sample_bill, [])
        
        assert result.is_valid is False
        assert "No participants found" in result.errors[0]


class TestSplitDisplay:
    """Test split display formatting (Requirement 2.4)"""
    
    @pytest.mark.asyncio
    async def test_format_split_display(self, bill_splitter, sample_bill, sample_participants):
        """Test basic split display formatting"""
        # Set up participants with amounts
        sample_participants[0].amount_owed = Decimal('60.00')
        sample_participants[1].amount_owed = Decimal('45.00')
        sample_participants[2].amount_owed = Decimal('45.00')
        
        result = await bill_splitter.format_split_display(sample_bill, sample_participants)
        
        assert "Bill Split Summary" in result
        assert "Lunch at Pizza Palace" in result
        assert "₹150.00" in result
        assert "3 participants" in result
        assert "John: ₹60.00" in result
        assert "Sarah: ₹45.00" in result
        assert "Mike: ₹45.00" in result
        assert "Total splits: ₹150.00" in result
    
    @pytest.mark.asyncio
    async def test_format_split_display_with_status(self, bill_splitter, sample_bill, sample_participants):
        """Test split display with payment status emojis"""
        sample_participants[0].amount_owed = Decimal('50.00')
        sample_participants[0].payment_status = PaymentStatus.CONFIRMED
        sample_participants[1].amount_owed = Decimal('50.00')
        sample_participants[1].payment_status = PaymentStatus.PENDING
        sample_participants[2].amount_owed = Decimal('50.00')
        sample_participants[2].payment_status = PaymentStatus.SENT
        
        result = await bill_splitter.format_split_display(sample_bill, sample_participants)
        
        assert "✅" in result  # Confirmed
        assert "⏳" in result  # Pending
        assert "📤" in result  # Sent
    
    @pytest.mark.asyncio
    async def test_format_split_display_sorted(self, bill_splitter, sample_bill, sample_participants):
        """Test that participants are sorted by amount (highest first)"""
        sample_participants[0].amount_owed = Decimal('30.00')  # John - lowest
        sample_participants[1].amount_owed = Decimal('70.00')  # Sarah - highest
        sample_participants[2].amount_owed = Decimal('50.00')  # Mike - middle
        
        result = await bill_splitter.format_split_display(sample_bill, sample_participants)
        
        lines = result.split('\n')
        amount_lines = [line for line in lines if ': ₹' in line]
        
        # Should be sorted: Sarah (70), Mike (50), John (30)
        assert "Sarah: ₹70.00" in amount_lines[0]
        assert "Mike: ₹50.00" in amount_lines[1]
        assert "John: ₹30.00" in amount_lines[2]
    
    @pytest.mark.asyncio
    async def test_format_split_display_with_difference(self, bill_splitter, sample_bill, sample_participants):
        """Test display shows difference when amounts don't match total"""
        sample_participants[0].amount_owed = Decimal('40.00')
        sample_participants[1].amount_owed = Decimal('40.00')
        sample_participants[2].amount_owed = Decimal('40.00')  # Total: 120, Bill: 150
        
        result = await bill_splitter.format_split_display(sample_bill, sample_participants)
        
        assert "Difference from bill total: ₹30.00" in result


class TestSplitConfirmation:
    """Test split confirmation formatting (Requirement 2.5)"""
    
    @pytest.mark.asyncio
    async def test_format_split_confirmation(self, bill_splitter, sample_bill, sample_participants):
        """Test split confirmation formatting"""
        sample_participants[0].amount_owed = Decimal('50.00')
        sample_participants[1].amount_owed = Decimal('50.00')
        sample_participants[2].amount_owed = Decimal('50.00')
        
        result = await bill_splitter.format_split_confirmation(sample_bill, sample_participants)
        
        assert "Bill Split Summary" in result
        assert "Please confirm these splits" in result
        assert "Reply *yes* to proceed" in result
        assert "Reply *no* or *change* to modify" in result
        assert "John ₹50, Sarah ₹100" in result  # Example format


class TestCustomAmountParsing:
    """Test parsing custom amounts from user messages"""
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_basic(self, bill_splitter, sample_participants):
        """Test basic custom amount parsing"""
        message = "John ₹60, Sarah ₹40, Mike ₹50"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        assert result["John"] == Decimal('60')
        assert result["Sarah"] == Decimal('40')
        assert result["Mike"] == Decimal('50')
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_various_formats(self, bill_splitter, sample_participants):
        """Test parsing various amount formats"""
        message = "John: ₹60.50, Sarah - 40, Mike 35.25"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        assert result["John"] == Decimal('60.50')
        assert result["Sarah"] == Decimal('40')
        assert result["Mike"] == Decimal('35.25')
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_case_insensitive(self, bill_splitter, sample_participants):
        """Test case-insensitive name matching"""
        message = "john ₹60, SARAH ₹40, mike ₹50"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        assert result["John"] == Decimal('60')
        assert result["Sarah"] == Decimal('40')
        assert result["Mike"] == Decimal('50')
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_partial(self, bill_splitter, sample_participants):
        """Test parsing with only some participants mentioned"""
        message = "John ₹75, Sarah ₹25"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        assert result["John"] == Decimal('75')
        assert result["Sarah"] == Decimal('25')
        assert "Mike" not in result
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_invalid_format(self, bill_splitter, sample_participants):
        """Test parsing with invalid amount formats"""
        message = "John ₹abc, Sarah ₹40"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        # Should skip invalid amounts
        assert "John" not in result
        assert result["Sarah"] == Decimal('40')
    
    @pytest.mark.asyncio
    async def test_parse_custom_amounts_unknown_names(self, bill_splitter, sample_participants):
        """Test parsing with unknown participant names"""
        message = "John ₹60, Unknown ₹40, Sarah ₹50"
        
        result = await bill_splitter.parse_custom_amounts(message, sample_participants)
        
        assert result["John"] == Decimal('60')
        assert result["Sarah"] == Decimal('50')
        assert "Unknown" not in result


class TestSplitStatistics:
    """Test split summary statistics"""
    
    @pytest.mark.asyncio
    async def test_get_split_summary_stats(self, bill_splitter, sample_participants):
        """Test split summary statistics calculation"""
        sample_participants[0].amount_owed = Decimal('60.00')
        sample_participants[0].payment_status = PaymentStatus.CONFIRMED
        sample_participants[1].amount_owed = Decimal('40.00')
        sample_participants[1].payment_status = PaymentStatus.PENDING
        sample_participants[2].amount_owed = Decimal('50.00')
        sample_participants[2].payment_status = PaymentStatus.PENDING
        
        result = await bill_splitter.get_split_summary_stats(sample_participants)
        
        assert result["total_participants"] == 3
        assert result["total_amount"] == Decimal('150.00')
        assert result["average_amount"] == Decimal('50.00')
        assert result["min_amount"] == Decimal('40.00')
        assert result["max_amount"] == Decimal('60.00')
        assert result["pending_count"] == 2
        assert result["confirmed_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_split_summary_stats_empty(self, bill_splitter):
        """Test split statistics with empty participants"""
        result = await bill_splitter.get_split_summary_stats([])
        
        assert result == {}