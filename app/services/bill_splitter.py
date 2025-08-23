"""
Bill splitting calculation engine
Implements requirements 2.1, 2.2, 2.3, 2.4, 2.5
"""
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from app.models.schemas import BillData, Participant, ValidationResult
from app.models.enums import PaymentStatus

logger = logging.getLogger(__name__)


class BillSplitter:
    """
    Bill splitting calculation engine with equal and custom split support
    Handles split validation and formatting for display
    """
    
    def __init__(self):
        self.precision = Decimal('0.01')  # 2 decimal places for currency
    
    async def calculate_equal_splits(self, bill_data: BillData, participants: List[Participant]) -> List[Participant]:
        """
        Calculate equal splits among all participants (Requirement 2.1)
        
        Args:
            bill_data: The bill information
            participants: List of participants
            
        Returns:
            List of participants with calculated amounts
        """
        try:
            if not participants:
                raise ValueError("No participants provided for split calculation")
            
            if bill_data.total_amount <= 0:
                raise ValueError("Bill total amount must be positive")
            
            participant_count = len(participants)
            
            # Calculate base amount per person
            base_amount = bill_data.total_amount / participant_count
            base_amount = base_amount.quantize(self.precision, rounding=ROUND_HALF_UP)
            
            # Handle rounding differences to ensure total matches exactly
            total_assigned = base_amount * participant_count
            difference = bill_data.total_amount - total_assigned
            
            # Create updated participants list
            updated_participants = []
            
            for i, participant in enumerate(participants):
                # Create new participant with calculated amount
                amount_owed = base_amount
                
                # Add any rounding difference to the first participant
                if i == 0 and difference != 0:
                    amount_owed += difference
                
                updated_participant = Participant(
                    name=participant.name,
                    phone_number=participant.phone_number,
                    amount_owed=amount_owed,
                    payment_status=PaymentStatus.PENDING,
                    contact_id=participant.contact_id
                )
                
                updated_participants.append(updated_participant)
            
            logger.info(f"Calculated equal splits for {participant_count} participants: {base_amount} each")
            return updated_participants
            
        except Exception as e:
            logger.error(f"Error calculating equal splits: {e}")
            raise ValueError(f"Failed to calculate equal splits: {str(e)}")
    
    async def apply_custom_splits(self, bill_data: BillData, participants: List[Participant], 
                                custom_amounts: Dict[str, Decimal]) -> List[Participant]:
        """
        Apply custom split amounts to participants (Requirement 2.2)
        
        Args:
            bill_data: The bill information
            participants: List of participants
            custom_amounts: Dict mapping participant names/IDs to custom amounts
            
        Returns:
            List of participants with custom amounts applied
        """
        try:
            if not participants:
                raise ValueError("No participants provided for custom splits")
            
            updated_participants = []
            
            for participant in participants:
                # Check if custom amount exists for this participant
                custom_amount = None
                
                # Try to find custom amount by name or contact_id
                if participant.name in custom_amounts:
                    custom_amount = custom_amounts[participant.name]
                elif participant.contact_id and participant.contact_id in custom_amounts:
                    custom_amount = custom_amounts[participant.contact_id]
                
                # Use custom amount if provided, otherwise keep existing amount
                amount_owed = custom_amount if custom_amount is not None else participant.amount_owed
                
                # Validate amount is positive
                if amount_owed <= 0:
                    raise ValueError(f"Custom amount for {participant.name} must be positive")
                
                # Round to currency precision
                amount_owed = amount_owed.quantize(self.precision, rounding=ROUND_HALF_UP)
                
                updated_participant = Participant(
                    name=participant.name,
                    phone_number=participant.phone_number,
                    amount_owed=amount_owed,
                    payment_status=participant.payment_status,
                    contact_id=participant.contact_id
                )
                
                updated_participants.append(updated_participant)
            
            logger.info(f"Applied custom splits to {len(custom_amounts)} participants")
            return updated_participants
            
        except Exception as e:
            logger.error(f"Error applying custom splits: {e}")
            raise ValueError(f"Failed to apply custom splits: {str(e)}")
    
    async def validate_splits(self, bill_data: BillData, participants: List[Participant]) -> ValidationResult:
        """
        Validate that split amounts match bill total (Requirement 2.3)
        
        Args:
            bill_data: The bill information
            participants: List of participants with amounts
            
        Returns:
            ValidationResult with validation status and any errors
        """
        try:
            errors = []
            warnings = []
            
            if not participants:
                errors.append("No participants found for validation")
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
            
            # Calculate total of all participant amounts
            total_participant_amount = sum(p.amount_owed for p in participants)
            
            # Check if totals match (within precision tolerance)
            difference = abs(bill_data.total_amount - total_participant_amount)
            tolerance = Decimal('0.01')  # 1 cent tolerance
            
            if difference > tolerance:
                errors.append(
                    f"Split amounts (₹{total_participant_amount}) don't match bill total (₹{bill_data.total_amount}). "
                    f"Difference: ₹{difference}"
                )
            
            # Check for negative amounts
            negative_amounts = [p for p in participants if p.amount_owed <= 0]
            if negative_amounts:
                names = [p.name for p in negative_amounts]
                errors.append(f"Negative or zero amounts found for: {', '.join(names)}")
            
            # Check for unreasonably large amounts (more than 2x the equal split)
            if participants:
                equal_split = bill_data.total_amount / len(participants)
                large_amounts = [p for p in participants if p.amount_owed > equal_split * 2]
                
                if large_amounts:
                    names = [f"{p.name} (₹{p.amount_owed})" for p in large_amounts]
                    warnings.append(f"Large amounts detected for: {', '.join(names)}")
            
            # Check for very small amounts (less than ₹1)
            small_amounts = [p for p in participants if 0 < p.amount_owed < Decimal('1.00')]
            if small_amounts:
                names = [f"{p.name} (₹{p.amount_owed})" for p in small_amounts]
                warnings.append(f"Very small amounts for: {', '.join(names)}")
            
            is_valid = len(errors) == 0
            
            logger.info(f"Split validation result: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}")
            return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
            
        except Exception as e:
            logger.error(f"Error validating splits: {e}")
            return ValidationResult(
                is_valid=False, 
                errors=[f"Validation error: {str(e)}"], 
                warnings=[]
            )
    
    async def format_split_display(self, bill_data: BillData, participants: List[Participant]) -> str:
        """
        Format split information for display to user (Requirement 2.4)
        
        Args:
            bill_data: The bill information
            participants: List of participants with amounts
            
        Returns:
            Formatted string for display
        """
        try:
            if not participants:
                return "No participants found for display"
            
            # Header with bill information
            display_lines = [
                f"💰 **Bill Split Summary**",
                f"📄 {bill_data.description}",
                f"💵 Total: ₹{bill_data.total_amount}",
                f"👥 {len(participants)} participants",
                "",
                "**Individual Amounts:**"
            ]
            
            # Sort participants by amount (highest first) for better readability
            sorted_participants = sorted(participants, key=lambda p: p.amount_owed, reverse=True)
            
            # Add each participant's amount
            for i, participant in enumerate(sorted_participants, 1):
                status_emoji = self._get_payment_status_emoji(participant.payment_status)
                display_lines.append(
                    f"{i}. {participant.name}: ₹{participant.amount_owed} {status_emoji}"
                )
            
            # Add total verification
            total_splits = sum(p.amount_owed for p in participants)
            display_lines.extend([
                "",
                f"**Total splits: ₹{total_splits}**"
            ])
            
            # Add difference warning if amounts don't match exactly
            difference = abs(bill_data.total_amount - total_splits)
            if difference > Decimal('0.01'):
                display_lines.append(f"⚠️ *Difference from bill total: ₹{difference}*")
            
            return "\n".join(display_lines)
            
        except Exception as e:
            logger.error(f"Error formatting split display: {e}")
            return f"Error displaying splits: {str(e)}"
    
    async def format_split_confirmation(self, bill_data: BillData, participants: List[Participant]) -> str:
        """
        Format split information for confirmation step (Requirement 2.5)
        
        Args:
            bill_data: The bill information
            participants: List of participants with amounts
            
        Returns:
            Formatted confirmation message
        """
        try:
            # Get the main display
            main_display = await self.format_split_display(bill_data, participants)
            
            # Add confirmation prompt
            confirmation_lines = [
                main_display,
                "",
                "**Please confirm these splits:**",
                "• Reply *yes* to proceed with payment requests",
                "• Reply *no* or *change* to modify the amounts",
                "• You can also specify custom amounts like: 'John ₹50, Sarah ₹100'"
            ]
            
            return "\n".join(confirmation_lines)
            
        except Exception as e:
            logger.error(f"Error formatting split confirmation: {e}")
            return f"Error displaying confirmation: {str(e)}"
    
    async def parse_custom_amounts(self, message_content: str, participants: List[Participant]) -> Dict[str, Decimal]:
        """
        Parse custom amounts from user message
        
        Args:
            message_content: User's message with custom amounts
            participants: List of current participants
            
        Returns:
            Dictionary mapping participant names to custom amounts
        """
        try:
            custom_amounts = {}
            
            # Simple parsing for amounts like "John ₹50, Sarah ₹100"
            import re
            
            # Pattern to match name and amount combinations
            # Supports formats: "John ₹50", "John 50", "John: ₹50", "John - 50"
            pattern = r'([A-Za-z\s]+)[\s\-:]*[₹]?(\d+(?:\.\d{2})?)'
            matches = re.findall(pattern, message_content)
            
            participant_names = [p.name.lower() for p in participants]
            
            for name_match, amount_str in matches:
                name = name_match.strip()
                
                # Find matching participant (case-insensitive)
                matched_participant = None
                for participant in participants:
                    if participant.name.lower() == name.lower():
                        matched_participant = participant
                        break
                
                if matched_participant:
                    try:
                        amount = Decimal(amount_str)
                        if amount > 0:
                            custom_amounts[matched_participant.name] = amount
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid amount format: {amount_str}")
                        continue
            
            logger.info(f"Parsed {len(custom_amounts)} custom amounts from user message")
            return custom_amounts
            
        except Exception as e:
            logger.error(f"Error parsing custom amounts: {e}")
            return {}
    
    def _get_payment_status_emoji(self, status: PaymentStatus) -> str:
        """Get emoji representation of payment status"""
        status_emojis = {
            PaymentStatus.PENDING: "⏳",
            PaymentStatus.SENT: "📤",
            PaymentStatus.CONFIRMED: "✅",
            PaymentStatus.FAILED: "❌"
        }
        return status_emojis.get(status, "❓")
    
    async def get_split_summary_stats(self, participants: List[Participant]) -> Dict[str, any]:
        """
        Get summary statistics for splits
        
        Returns:
            Dictionary with split statistics
        """
        try:
            if not participants:
                return {}
            
            amounts = [p.amount_owed for p in participants]
            
            return {
                "total_participants": len(participants),
                "total_amount": sum(amounts),
                "average_amount": sum(amounts) / len(amounts),
                "min_amount": min(amounts),
                "max_amount": max(amounts),
                "pending_count": len([p for p in participants if p.payment_status == PaymentStatus.PENDING]),
                "confirmed_count": len([p for p in participants if p.payment_status == PaymentStatus.CONFIRMED])
            }
            
        except Exception as e:
            logger.error(f"Error calculating split statistics: {e}")
            return {}