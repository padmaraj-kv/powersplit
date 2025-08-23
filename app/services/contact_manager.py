"""
Contact management service for participant handling and contact operations
"""
import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from app.interfaces.repositories import ContactRepository, UserRepository
from app.models.schemas import Participant, ValidationResult
from app.models.database import Contact, User
from app.models.enums import ErrorType

logger = logging.getLogger(__name__)


class ContactManager:
    """
    Service for managing participant contacts with deduplication and validation
    Implements requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    
    def __init__(self, contact_repo: ContactRepository, user_repo: UserRepository):
        self.contact_repo = contact_repo
        self.user_repo = user_repo
    
    async def collect_participants_workflow(self, user_id: str, participants: List[Participant]) -> Tuple[List[Participant], List[str]]:
        """
        Main workflow for collecting participant contacts with missing contact handling
        Implements requirement 3.4 - Create participant collection workflow with missing contact handling
        
        Args:
            user_id: ID of the user creating the bill
            participants: List of participants with potentially incomplete contact info
            
        Returns:
            Tuple of (updated_participants, missing_contact_questions)
        """
        try:
            user_uuid = UUID(user_id)
            updated_participants = []
            missing_contacts = []
            
            for participant in participants:
                # Validate and format phone number
                if participant.phone_number:
                    formatted_phone = self.format_phone_number(participant.phone_number)
                    if not self.validate_phone_number(formatted_phone):
                        missing_contacts.append(f"Please provide a valid phone number for {participant.name}")
                        continue
                    participant.phone_number = formatted_phone
                
                # Try to find or create contact
                contact_id = await self.find_or_create_contact(
                    user_id, participant.name, participant.phone_number
                )
                participant.contact_id = contact_id
                updated_participants.append(participant)
            
            # Generate questions for missing contacts
            missing_questions = self._generate_missing_contact_questions(participants, updated_participants)
            
            logger.info(f"Processed {len(updated_participants)} participants for user {user_id}")
            return updated_participants, missing_questions
            
        except Exception as e:
            logger.error(f"Error in participant collection workflow: {e}")
            raise
    
    async def find_or_create_contact(self, user_id: str, name: str, phone_number: str) -> str:
        """
        Find existing contact or create new one with deduplication
        Implements requirements 3.2 - auto-population and 3.3 - store new contacts
        
        Args:
            user_id: ID of the user
            name: Contact name
            phone_number: Contact phone number
            
        Returns:
            Contact ID (string)
        """
        try:
            user_uuid = UUID(user_id)
            
            # Format phone number for consistency
            formatted_phone = self.format_phone_number(phone_number)
            
            # Try to find existing contact (implements requirement 3.2)
            existing_contact = await self.contact_repo.find_contact_by_phone(user_uuid, formatted_phone)
            
            if existing_contact:
                logger.info(f"Found existing contact {existing_contact.id} for phone {formatted_phone}")
                return str(existing_contact.id)
            
            # Create new contact (implements requirement 3.3)
            new_contact = await self.contact_repo.create_contact(user_uuid, name, formatted_phone)
            logger.info(f"Created new contact {new_contact.id} for {name}")
            return str(new_contact.id)
            
        except Exception as e:
            logger.error(f"Error finding or creating contact: {e}")
            raise
    
    async def get_user_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all contacts for a user
        Implements requirement 3.1 - provide contact details for participants
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of contact dictionaries
        """
        try:
            user_uuid = UUID(user_id)
            contacts = await self.contact_repo.get_user_contacts(user_uuid)
            
            contact_list = []
            for contact in contacts:
                contact_dict = {
                    "id": str(contact.id),
                    "name": contact.name,
                    "phone_number": contact.phone_number,
                    "created_at": contact.created_at.isoformat()
                }
                contact_list.append(contact_dict)
            
            logger.info(f"Retrieved {len(contact_list)} contacts for user {user_id}")
            return contact_list
            
        except Exception as e:
            logger.error(f"Error retrieving user contacts: {e}")
            raise
    
    def validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate phone number format
        Implements requirement 3.3 - contact validation
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not phone_number:
            return False
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_number)
        
        # Check for valid international format
        # Should start with + followed by country code and number
        # Total length should be between 10-15 digits (excluding +)
        if cleaned.startswith('+'):
            digits_only = cleaned[1:]
            if len(digits_only) >= 10 and len(digits_only) <= 15 and digits_only.isdigit():
                return True
        
        # Check for Indian mobile numbers (10 digits starting with 6-9)
        elif len(cleaned) == 10 and cleaned.isdigit() and cleaned[0] in '6789':
            return True
        
        return False
    
    def format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number to consistent format
        Implements requirement 3.3 - phone number formatting
        
        Args:
            phone_number: Raw phone number
            
        Returns:
            Formatted phone number
        """
        if not phone_number:
            return phone_number
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_number)
        
        # If it's already in international format, return as is
        if cleaned.startswith('+'):
            return cleaned
        
        # If it's a 10-digit Indian number, add +91
        if len(cleaned) == 10 and cleaned.isdigit() and cleaned[0] in '6789':
            return f"+91{cleaned}"
        
        # If it starts with 91 and has 12 digits total, add +
        if len(cleaned) == 12 and cleaned.startswith('91') and cleaned[2] in '6789':
            return f"+{cleaned}"
        
        # Return as is if we can't determine format
        return cleaned
    
    async def validate_participants(self, participants: List[Participant]) -> ValidationResult:
        """
        Validate participant list for completeness and correctness
        Implements requirement 3.4 - missing contact handling
        
        Args:
            participants: List of participants to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        if not participants:
            errors.append("At least one participant is required")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        seen_phones = set()
        seen_names = set()
        
        for i, participant in enumerate(participants):
            # Validate name
            if not participant.name or not participant.name.strip():
                errors.append(f"Participant {i+1}: Name is required")
            elif participant.name.strip() in seen_names:
                warnings.append(f"Duplicate name found: {participant.name}")
            else:
                seen_names.add(participant.name.strip())
            
            # Validate phone number
            if not participant.phone_number:
                errors.append(f"Participant {i+1} ({participant.name}): Phone number is required")
            else:
                formatted_phone = self.format_phone_number(participant.phone_number)
                if not self.validate_phone_number(formatted_phone):
                    errors.append(f"Participant {i+1} ({participant.name}): Invalid phone number format")
                elif formatted_phone in seen_phones:
                    errors.append(f"Duplicate phone number found: {formatted_phone}")
                else:
                    seen_phones.add(formatted_phone)
            
            # Validate amount
            if participant.amount_owed <= 0:
                errors.append(f"Participant {i+1} ({participant.name}): Amount must be positive")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
    
    async def deduplicate_contacts(self, user_id: str, participants: List[Participant]) -> List[Participant]:
        """
        Remove duplicate contacts and merge information
        Implements requirement 3.2 - contact deduplication logic
        
        Args:
            user_id: ID of the user
            participants: List of participants that may contain duplicates
            
        Returns:
            Deduplicated list of participants
        """
        try:
            user_uuid = UUID(user_id)
            existing_contacts = await self.contact_repo.get_user_contacts(user_uuid)
            
            # Create lookup maps for existing contacts
            phone_to_contact = {}
            name_to_contact = {}
            
            for contact in existing_contacts:
                phone_to_contact[contact.phone_number] = contact
                name_to_contact[contact.name.lower()] = contact
            
            deduplicated = []
            seen_phones = set()
            
            for participant in participants:
                formatted_phone = self.format_phone_number(participant.phone_number)
                
                # Skip if we've already processed this phone number
                if formatted_phone in seen_phones:
                    continue
                
                # Check if contact exists and update participant info
                if formatted_phone in phone_to_contact:
                    existing_contact = phone_to_contact[formatted_phone]
                    participant.contact_id = str(existing_contact.id)
                    # Use existing contact name if participant name is generic
                    if participant.name.lower() in ['participant', 'person', 'friend']:
                        participant.name = existing_contact.name
                
                deduplicated.append(participant)
                seen_phones.add(formatted_phone)
            
            logger.info(f"Deduplicated {len(participants)} participants to {len(deduplicated)}")
            return deduplicated
            
        except Exception as e:
            logger.error(f"Error deduplicating contacts: {e}")
            raise
    
    def _generate_missing_contact_questions(self, original_participants: List[Participant], 
                                          processed_participants: List[Participant]) -> List[str]:
        """
        Generate questions for missing contact information
        
        Args:
            original_participants: Original participant list
            processed_participants: Successfully processed participants
            
        Returns:
            List of questions for missing contacts
        """
        questions = []
        processed_names = {p.name for p in processed_participants}
        
        for participant in original_participants:
            if participant.name not in processed_names:
                if not participant.phone_number:
                    questions.append(f"What is {participant.name}'s phone number?")
                elif not self.validate_phone_number(self.format_phone_number(participant.phone_number)):
                    questions.append(f"Please provide a valid phone number for {participant.name}")
        
        return questions
    
    async def auto_populate_from_history(self, user_id: str, participant_names: List[str]) -> List[Participant]:
        """
        Auto-populate participant information from contact history
        Implements requirement 3.2 - auto-population logic
        
        Args:
            user_id: ID of the user
            participant_names: List of participant names to look up
            
        Returns:
            List of participants with auto-populated contact info
        """
        try:
            user_uuid = UUID(user_id)
            existing_contacts = await self.contact_repo.get_user_contacts(user_uuid)
            
            # Create name lookup (case-insensitive)
            name_to_contact = {}
            for contact in existing_contacts:
                name_to_contact[contact.name.lower()] = contact
            
            participants = []
            for name in participant_names:
                participant = Participant(
                    name=name,
                    phone_number="",
                    amount_owed=0  # Will be set later during split calculation
                )
                
                # Try to find existing contact
                if name.lower() in name_to_contact:
                    contact = name_to_contact[name.lower()]
                    participant.phone_number = contact.phone_number
                    participant.contact_id = str(contact.id)
                
                participants.append(participant)
            
            logger.info(f"Auto-populated {len(participants)} participants from history")
            return participants
            
        except Exception as e:
            logger.error(f"Error auto-populating from history: {e}")
            raise
    
    async def handle_missing_contacts(self, user_id: str, participants: List[Participant], 
                                    user_responses: Dict[str, str]) -> Tuple[List[Participant], List[str]]:
        """
        Handle user responses for missing contact information
        Implements requirement 3.4 - missing contact handling
        
        Args:
            user_id: ID of the user
            participants: Current participant list
            user_responses: User responses to missing contact questions
            
        Returns:
            Tuple of (updated_participants, remaining_questions)
        """
        try:
            updated_participants = []
            remaining_questions = []
            
            for participant in participants:
                # If participant already has valid contact info, keep as is
                if (participant.phone_number and 
                    self.validate_phone_number(self.format_phone_number(participant.phone_number))):
                    updated_participants.append(participant)
                    continue
                
                # Look for user response for this participant
                response_key = f"{participant.name}_phone"
                if response_key in user_responses:
                    phone_response = user_responses[response_key].strip()
                    formatted_phone = self.format_phone_number(phone_response)
                    
                    if self.validate_phone_number(formatted_phone):
                        participant.phone_number = formatted_phone
                        # Find or create contact
                        contact_id = await self.find_or_create_contact(
                            user_id, participant.name, formatted_phone
                        )
                        participant.contact_id = contact_id
                        updated_participants.append(participant)
                    else:
                        remaining_questions.append(f"Please provide a valid phone number for {participant.name}")
                else:
                    remaining_questions.append(f"What is {participant.name}'s phone number?")
            
            logger.info(f"Processed missing contacts: {len(updated_participants)} complete, {len(remaining_questions)} remaining")
            return updated_participants, remaining_questions
            
        except Exception as e:
            logger.error(f"Error handling missing contacts: {e}")
            raise