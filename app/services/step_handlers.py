"""
Step handlers for conversation flow management
Each handler manages a specific step in the bill splitting process
"""

import logging
from typing import Dict, Any, Optional, List
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import (
    Message,
    Response,
    ConversationState,
    BillData,
    Participant,
    ValidationResult,
)
from app.services.state_machine import BaseStepHandler, StepResult
from app.agents import agent_registry, AgentContext
from app.services.bill_extractor import BillExtractor, BillExtractionError
from app.services.payment_confirmation_service import PaymentConfirmationService

logger = logging.getLogger(__name__)


class InitialStepHandler(BaseStepHandler):
    """
    Handler for initial conversation step
    Welcomes users and processes first bill input
    """

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle initial message from user"""
        try:
            # Check for help or reset commands
            if self._is_help_command(message):
                return StepResult(
                    response=Response(
                        content=await self.get_help_message(),
                        message_type=MessageType.TEXT,
                    )
                )

            # Check if message contains bill information
            if await self._contains_bill_info(message):
                # Move to bill extraction step
                return StepResult(
                    response=Response(
                        content="I see you've sent bill information. Let me process that for you...",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.EXTRACTING_BILL,
                    context_updates={
                        "input_type": message.message_type.value,
                        "original_message": message.content,
                        "processing_started": True,
                    },
                )
            else:
                # Ask for bill information
                return StepResult(
                    response=Response(
                        content="Hi! I'm here to help you split bills with friends. Please send me your bill information - you can type the details, send a photo of the bill, or record a voice message.",
                        message_type=MessageType.TEXT,
                    )
                )

        except Exception as e:
            logger.error(f"Error in initial step handler: {e}")
            return StepResult(
                response=Response(
                    content="Welcome! Please send me your bill information to get started.",
                    message_type=MessageType.TEXT,
                )
            )

    async def get_help_message(self) -> str:
        """Get help message for initial step"""
        return """I can help you split bills with friends! Here's how:

1. Send me your bill information by:
   • Typing the bill details (amount, description, participants)
   • Taking a photo of the bill
   • Recording a voice message with the details

2. I'll help you:
   • Extract the bill information
   • Collect participant contacts
   • Calculate splits
   • Send payment requests via WhatsApp/SMS

Just send me your bill information to get started!"""

    async def _contains_bill_info(self, message: Message) -> bool:
        """Check if message contains bill information"""
        # For now, assume any non-command message in initial step contains bill info
        if message.message_type in [MessageType.IMAGE, MessageType.VOICE]:
            return True

        # Check for bill-related keywords in text
        bill_keywords = [
            "bill",
            "amount",
            "total",
            "split",
            "pay",
            "₹",
            "$",
            "rs",
            "rupees",
        ]
        content_lower = message.content.lower()
        return any(keyword in content_lower for keyword in bill_keywords)


class BillExtractionHandler(BaseStepHandler):
    """
    Handler for bill extraction step
    Processes bill information from various input types using BillExtractor
    Implements requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """

    def __init__(self, bill_extractor: Optional[BillExtractor] = None):
        self.bill_extractor = bill_extractor or BillExtractor()

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle bill extraction from user input"""
        try:
            # Check for reset command
            if self._is_reset_command(message):
                return StepResult(
                    response=Response(
                        content="Starting over. Please send me your bill information.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.INITIAL,
                    context_updates={"reset": True},
                )

            # Check if we're in clarification mode
            if state.context.get("awaiting_clarification"):
                return await self._handle_clarification_response(state, message)

            # Extract bill data using ADK-style agent for text, fallback to extractor
            try:
                if message.message_type == MessageType.TEXT:
                    try:
                        agent = agent_registry.create("llm")
                        context = AgentContext(
                            session_id=message.id,
                            user_id=message.user_id,
                            metadata=message.metadata,
                        )
                        result = await agent.run(message.content, context)
                        bill_dict = (result.metadata or {}).get("bill_data")
                        if bill_dict:
                            bill_data = BillData(**bill_dict)
                        else:
                            bill_data = await self.bill_extractor.extract_bill_data(
                                message
                            )
                    except Exception:
                        bill_data = await self.bill_extractor.extract_bill_data(message)
                else:
                    bill_data = await self.bill_extractor.extract_bill_data(message)

                # Validate the extracted data
                validation_result = await self.bill_extractor.validate_bill_data(
                    bill_data
                )

                if validation_result.is_valid:
                    # Create bill summary for confirmation
                    summary = await self.bill_extractor.create_bill_summary(bill_data)

                    return StepResult(
                        response=Response(
                            content=summary, message_type=MessageType.TEXT
                        ),
                        next_step=ConversationStep.CONFIRMING_BILL,
                        context_updates={
                            "bill_data": bill_data.dict(),
                            "extraction_successful": True,
                            "validation_warnings": validation_result.warnings,
                        },
                    )
                else:
                    # Validation failed - ask for clarification
                    error_message = self._format_validation_errors(validation_result)

                    return StepResult(
                        response=Response(
                            content=error_message, message_type=MessageType.TEXT
                        ),
                        context_updates={
                            "validation_errors": validation_result.errors,
                            "partial_bill_data": bill_data.dict(),
                            "attempt_count": state.context.get("attempt_count", 0) + 1,
                        },
                    )

            except BillExtractionError as e:
                logger.warning(f"Bill extraction failed: {e}")

                # Check if we should ask clarifying questions
                if state.context.get("attempt_count", 0) < 2:
                    questions = await self._generate_clarifying_questions(
                        state, message
                    )

                    return StepResult(
                        response=Response(
                            content=questions, message_type=MessageType.TEXT
                        ),
                        context_updates={
                            "awaiting_clarification": True,
                            "attempt_count": state.context.get("attempt_count", 0) + 1,
                            "last_error": str(e),
                        },
                    )
                else:
                    # Too many attempts - provide fallback instructions
                    return StepResult(
                        response=Response(
                            content=self._get_fallback_instructions(
                                message.message_type
                            ),
                            message_type=MessageType.TEXT,
                        ),
                        context_updates={
                            "extraction_failed": True,
                            "attempt_count": state.context.get("attempt_count", 0) + 1,
                        },
                    )

        except Exception as e:
            logger.error(f"Unexpected error in bill extraction handler: {e}")
            return StepResult(
                response=Response(
                    content="I encountered an error processing your bill. Please try sending the information again.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={
                    "error": str(e),
                    "attempt_count": state.context.get("attempt_count", 0) + 1,
                },
            )

    async def _handle_clarification_response(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle user response to clarifying questions"""
        try:
            # Try to extract bill data from the clarification
            bill_data = await self.bill_extractor.extract_bill_data(message)

            # Merge with any partial data from previous attempts
            if "partial_bill_data" in state.context:
                bill_data = self._merge_bill_data(
                    state.context["partial_bill_data"], bill_data
                )

            # Validate the merged data
            validation_result = await self.bill_extractor.validate_bill_data(bill_data)

            if validation_result.is_valid:
                summary = await self.bill_extractor.create_bill_summary(bill_data)

                return StepResult(
                    response=Response(content=summary, message_type=MessageType.TEXT),
                    next_step=ConversationStep.CONFIRMING_BILL,
                    context_updates={
                        "bill_data": bill_data.dict(),
                        "extraction_successful": True,
                        "awaiting_clarification": False,
                        "validation_warnings": validation_result.warnings,
                    },
                )
            else:
                # Still need more information
                questions = await self.bill_extractor.generate_clarifying_questions(
                    bill_data
                )

                if questions:
                    question_text = "I still need some information:\n\n" + "\n".join(
                        f"• {q}" for q in questions
                    )
                else:
                    question_text = (
                        "Please provide the total bill amount and a brief description."
                    )

                return StepResult(
                    response=Response(
                        content=question_text, message_type=MessageType.TEXT
                    ),
                    context_updates={
                        "partial_bill_data": bill_data.dict(),
                        "validation_errors": validation_result.errors,
                        "attempt_count": state.context.get("attempt_count", 0) + 1,
                    },
                )

        except BillExtractionError as e:
            logger.warning(f"Clarification processing failed: {e}")

            return StepResult(
                response=Response(
                    content="I'm still having trouble understanding the bill information. Please provide the total amount and description in a simple format like: 'Total: ₹150, Lunch at Pizza Palace'",
                    message_type=MessageType.TEXT,
                ),
                context_updates={
                    "attempt_count": state.context.get("attempt_count", 0) + 1
                },
            )

    async def _generate_clarifying_questions(
        self, state: ConversationState, message: Message
    ) -> str:
        """Generate clarifying questions based on extraction failure"""
        try:
            # Try to get partial bill data for question generation
            partial_data = None
            if "partial_bill_data" in state.context:
                partial_data = BillData(**state.context["partial_bill_data"])
            else:
                # Create minimal bill data for question generation
                from decimal import Decimal

                partial_data = BillData(
                    total_amount=Decimal("0.00"),
                    description="",
                    items=[],
                    currency="INR",
                )

            questions = await self.bill_extractor.generate_clarifying_questions(
                partial_data
            )

            if questions:
                intro = "I need some clarification about your bill:"
                question_list = "\n".join(f"• {q}" for q in questions)
                return f"{intro}\n\n{question_list}"
            else:
                return self._get_generic_clarification(message.message_type)

        except Exception as e:
            logger.warning(f"Failed to generate clarifying questions: {e}")
            return self._get_generic_clarification(message.message_type)

    def _get_generic_clarification(self, message_type: MessageType) -> str:
        """Get generic clarification message based on input type"""
        if message_type == MessageType.IMAGE:
            return "I couldn't read the bill clearly from the image. Please try taking a clearer photo or tell me the total amount and description."
        elif message_type == MessageType.VOICE:
            return "I couldn't understand the bill details from your voice message. Please try speaking more clearly or send the information as text."
        else:
            return "I need more information about your bill. Please provide the total amount and a brief description."

    def _get_fallback_instructions(self, message_type: MessageType) -> str:
        """Get fallback instructions when extraction repeatedly fails"""
        base_message = "I'm having trouble processing your bill information. "

        if message_type == MessageType.IMAGE:
            return (
                base_message
                + "Please try:\n• Taking a clearer, well-lit photo\n• Typing the bill details instead\n• Example: 'Total: ₹150, Lunch at Pizza Palace'"
            )
        elif message_type == MessageType.VOICE:
            return (
                base_message
                + "Please try:\n• Speaking more clearly and slowly\n• Typing the bill details instead\n• Example: 'Total: ₹150, Lunch at Pizza Palace'"
            )
        else:
            return (
                base_message
                + "Please provide the bill information in this format:\n'Total: ₹[amount], [description]'\n\nExample: 'Total: ₹150, Lunch at Pizza Palace'"
            )

    def _format_validation_errors(self, validation_result: ValidationResult) -> str:
        """Format validation errors into user-friendly message"""
        if not validation_result.errors:
            return "Please provide more information about your bill."

        error_messages = []
        for error in validation_result.errors:
            if "amount" in error.lower():
                error_messages.append("Please provide a valid bill amount")
            elif "description" in error.lower():
                error_messages.append(
                    "Please provide a description of what the bill is for"
                )
            else:
                error_messages.append(error)

        intro = "I need to clarify a few things about your bill:"
        formatted_errors = "\n".join(f"• {msg}" for msg in error_messages)

        return f"{intro}\n\n{formatted_errors}"

    def _merge_bill_data(
        self, partial_data: Dict[str, Any], new_data: BillData
    ) -> BillData:
        """Merge partial bill data with new extraction results"""
        try:
            # Start with the new data
            merged = new_data.dict()

            # Fill in missing fields from partial data
            for key, value in partial_data.items():
                if key in merged and (not merged[key] or merged[key] == 0):
                    merged[key] = value

            return BillData(**merged)

        except Exception as e:
            logger.warning(f"Failed to merge bill data: {e}")
            return new_data


class BillConfirmationHandler(BaseStepHandler):
    """
    Handler for bill confirmation step
    Implements requirement 1.5
    """

    def __init__(self, bill_extractor: Optional[BillExtractor] = None):
        self.bill_extractor = bill_extractor or BillExtractor()

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle bill confirmation from user"""
        try:
            # Get the bill data from context
            if not state.context.get("bill_data"):
                logger.error("No bill data found in context for confirmation")
                return StepResult(
                    response=Response(
                        content="I don't have any bill information to confirm. Please send me your bill details.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.EXTRACTING_BILL,
                    context_updates={"error": "missing_bill_data"},
                )

            bill_data = BillData(**state.context["bill_data"])

            # Process the confirmation using BillExtractor
            is_confirmed, error_message = (
                await self.bill_extractor.process_bill_confirmation(message, bill_data)
            )

            if is_confirmed:
                # Bill confirmed - move to contact collection
                confirmation_message = "Perfect! ✅ Bill confirmed.\n\n"

                # Add any validation warnings if present
                if state.context.get("validation_warnings"):
                    warnings = state.context["validation_warnings"]
                    if warnings:
                        confirmation_message += (
                            "⚠️ *Note:* " + "; ".join(warnings) + "\n\n"
                        )

                confirmation_message += "Now I need the contact details for everyone who should pay. Please provide names and phone numbers for all participants.\n\n"
                confirmation_message += "You can send them like:\n• John - +91 9876543210\n• Sarah - +91 9876543211"

                return StepResult(
                    response=Response(
                        content=confirmation_message, message_type=MessageType.TEXT
                    ),
                    next_step=ConversationStep.COLLECTING_CONTACTS,
                    context_updates={
                        "bill_confirmed": True,
                        "confirmation_timestamp": message.timestamp.isoformat(),
                    },
                )

            elif error_message:
                # User wants to modify or unclear response
                if "change" in error_message.lower():
                    return StepResult(
                        response=Response(
                            content="No problem! "
                            + error_message
                            + "\n\nPlease send me the corrected bill information.",
                            message_type=MessageType.TEXT,
                        ),
                        next_step=ConversationStep.EXTRACTING_BILL,
                        context_updates={
                            "bill_rejected": True,
                            "rejection_reason": "user_requested_changes",
                        },
                    )
                else:
                    # Ambiguous response - ask for clarification
                    return StepResult(
                        response=Response(
                            content=error_message, message_type=MessageType.TEXT
                        ),
                        context_updates={
                            "clarification_requested": True,
                            "clarification_count": state.context.get(
                                "clarification_count", 0
                            )
                            + 1,
                        },
                    )
            else:
                # Fallback response
                return StepResult(
                    response=Response(
                        content="Please let me know if the bill details are correct by replying *yes* or *no*.",
                        message_type=MessageType.TEXT,
                    ),
                    context_updates={"clarification_requested": True},
                )

        except Exception as e:
            logger.error(f"Error in bill confirmation handler: {e}")

            # Provide helpful fallback response
            return StepResult(
                response=Response(
                    content="I had trouble processing your response. Please confirm if the bill details are correct by replying *yes* or *no*.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"error": str(e), "fallback_used": True},
            )


class ContactCollectionHandler(BaseStepHandler):
    """Handler for collecting participant contacts"""

    def __init__(self, contact_manager=None):
        super().__init__(None)
        self.contact_manager = contact_manager

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle contact collection from user"""
        try:
            if not self.contact_manager:
                # Fallback if contact manager not available
                return StepResult(
                    response=Response(
                        content="Contact collection service not available. Please try again later.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=state.current_step,
                    context_updates={},
                )

            # Get participants from context
            participants = state.participants or []
            if not participants:
                return StepResult(
                    response=Response(
                        content="No participants found. Please go back and confirm your bill first.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.CONFIRMING_BILL,
                    context_updates={},
                )

            # Check if this is the first time collecting contacts
            if not state.context.get("contact_collection_started"):
                # Start contact collection workflow
                updated_participants, missing_questions = (
                    await self.contact_manager.collect_participants_workflow(
                        state.user_id, participants
                    )
                )

                if missing_questions:
                    # Store current progress and ask for missing contacts
                    questions_text = "\n".join([f"• {q}" for q in missing_questions])
                    response_content = f"I need some contact information:\n\n{questions_text}\n\nPlease provide the missing phone numbers."

                    return StepResult(
                        response=Response(
                            content=response_content, message_type=MessageType.TEXT
                        ),
                        next_step=ConversationStep.COLLECTING_CONTACTS,
                        context_updates={
                            "contact_collection_started": True,
                            "missing_questions": missing_questions,
                            "processed_participants": [
                                p.dict() for p in updated_participants
                            ],
                        },
                    )
                else:
                    # All contacts collected successfully
                    return StepResult(
                        response=Response(
                            content=f"Great! I have contact information for all {len(updated_participants)} participants. Let's calculate the splits.",
                            message_type=MessageType.TEXT,
                        ),
                        next_step=ConversationStep.CALCULATING_SPLITS,
                        context_updates={
                            "contacts_collected": True,
                            "final_participants": [
                                p.dict() for p in updated_participants
                            ],
                        },
                    )

            else:
                # Handle user responses to missing contact questions
                missing_questions = state.context.get("missing_questions", [])
                processed_participants = state.context.get("processed_participants", [])

                # Parse user responses (simplified - in real implementation would be more sophisticated)
                user_responses = self._parse_contact_responses(
                    message.content, missing_questions
                )

                # Convert processed participants back to objects
                processed_participant_objects = [
                    Participant(**p) for p in processed_participants
                ]

                # Handle missing contacts with user responses
                final_participants, remaining_questions = (
                    await self.contact_manager.handle_missing_contacts(
                        state.user_id, processed_participant_objects, user_responses
                    )
                )

                if remaining_questions:
                    # Still have missing contacts
                    questions_text = "\n".join([f"• {q}" for q in remaining_questions])
                    response_content = f"I still need:\n\n{questions_text}\n\nPlease provide the missing information."

                    return StepResult(
                        response=Response(
                            content=response_content, message_type=MessageType.TEXT
                        ),
                        next_step=ConversationStep.COLLECTING_CONTACTS,
                        context_updates={
                            "missing_questions": remaining_questions,
                            "processed_participants": [
                                p.dict() for p in final_participants
                            ],
                        },
                    )
                else:
                    # All contacts collected
                    return StepResult(
                        response=Response(
                            content=f"Perfect! I now have contact information for all {len(final_participants)} participants. Let's calculate the splits.",
                            message_type=MessageType.TEXT,
                        ),
                        next_step=ConversationStep.CALCULATING_SPLITS,
                        context_updates={
                            "contacts_collected": True,
                            "final_participants": [
                                p.dict() for p in final_participants
                            ],
                        },
                    )

        except Exception as e:
            logger.error(f"Error in contact collection: {e}")
            return StepResult(
                response=Response(
                    content="Sorry, I encountered an error while collecting contacts. Let me try again.",
                    message_type=MessageType.TEXT,
                ),
                next_step=state.current_step,
                context_updates={"contact_collection_error": str(e)},
            )

    def _parse_contact_responses(
        self, message_content: str, missing_questions: List[str]
    ) -> Dict[str, str]:
        """Parse user responses for missing contact information"""
        responses = {}

        # Simple parsing - look for phone numbers in the message
        import re

        phone_pattern = r"[\+]?[1-9][\d\s\-\(\)]{8,15}"
        phones = re.findall(phone_pattern, message_content)

        # Map phones to questions (simplified approach)
        for i, question in enumerate(missing_questions):
            if i < len(phones):
                # Extract participant name from question
                if "phone number for" in question:
                    name = question.split("phone number for ")[-1].rstrip("?")
                    responses[f"{name}_phone"] = phones[i].strip()

        return responses


class SplitCalculationHandler(BaseStepHandler):
    """
    Handler for calculating bill splits
    Implements requirements 2.1, 2.2, 2.3
    """

    def __init__(self, bill_splitter=None):
        super().__init__(None)
        from app.services.bill_splitter import BillSplitter

        self.bill_splitter = bill_splitter or BillSplitter()

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle split calculation"""
        try:
            # Get bill data and participants from context
            if not state.context.get("bill_data"):
                logger.error("No bill data found in context for split calculation")
                return StepResult(
                    response=Response(
                        content="I don't have bill information. Let's start over.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.INITIAL,
                    context_updates={"error": "missing_bill_data"},
                )

            # Get participants from context (should be set by contact collection)
            participants_data = state.context.get(
                "final_participants"
            ) or state.context.get("participants", [])
            if not participants_data:
                logger.error("No participants found in context for split calculation")
                return StepResult(
                    response=Response(
                        content="I don't have participant information. Let's collect contacts first.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.COLLECTING_CONTACTS,
                    context_updates={"error": "missing_participants"},
                )

            bill_data = BillData(**state.context["bill_data"])
            participants = [Participant(**p) for p in participants_data]

            # Check if user is requesting custom splits
            if await self._is_custom_split_request(message):
                # Parse custom amounts from message
                custom_amounts = await self.bill_splitter.parse_custom_amounts(
                    message.content, participants
                )

                if custom_amounts:
                    # Apply custom splits
                    updated_participants = await self.bill_splitter.apply_custom_splits(
                        bill_data, participants, custom_amounts
                    )

                    # Validate the custom splits
                    validation_result = await self.bill_splitter.validate_splits(
                        bill_data, updated_participants
                    )

                    if validation_result.is_valid:
                        # Custom splits are valid
                        confirmation_display = (
                            await self.bill_splitter.format_split_confirmation(
                                bill_data, updated_participants
                            )
                        )

                        return StepResult(
                            response=Response(
                                content=confirmation_display,
                                message_type=MessageType.TEXT,
                            ),
                            next_step=ConversationStep.CONFIRMING_SPLITS,
                            context_updates={
                                "splits_calculated": True,
                                "split_type": "custom",
                                "calculated_participants": [
                                    p.dict() for p in updated_participants
                                ],
                                "validation_warnings": validation_result.warnings,
                            },
                        )
                    else:
                        # Custom splits have errors
                        error_message = "There are issues with your custom splits:\n\n"
                        error_message += "\n".join(
                            f"• {error}" for error in validation_result.errors
                        )
                        error_message += "\n\nPlease provide corrected amounts or reply 'equal' for equal splits."

                        return StepResult(
                            response=Response(
                                content=error_message, message_type=MessageType.TEXT
                            ),
                            context_updates={
                                "custom_split_errors": validation_result.errors,
                                "attempted_custom_amounts": custom_amounts,
                            },
                        )
                else:
                    # Couldn't parse custom amounts
                    return StepResult(
                        response=Response(
                            content="I couldn't understand the custom amounts. Please use format like:\n'John ₹50, Sarah ₹100'\n\nOr reply 'equal' for equal splits.",
                            message_type=MessageType.TEXT,
                        ),
                        context_updates={"custom_parse_failed": True},
                    )

            else:
                # Default to equal splits (Requirement 2.1)
                updated_participants = await self.bill_splitter.calculate_equal_splits(
                    bill_data, participants
                )

                # Validate the equal splits
                validation_result = await self.bill_splitter.validate_splits(
                    bill_data, updated_participants
                )

                if validation_result.is_valid:
                    # Display the calculated splits for confirmation
                    confirmation_display = (
                        await self.bill_splitter.format_split_confirmation(
                            bill_data, updated_participants
                        )
                    )

                    return StepResult(
                        response=Response(
                            content=confirmation_display, message_type=MessageType.TEXT
                        ),
                        next_step=ConversationStep.CONFIRMING_SPLITS,
                        context_updates={
                            "splits_calculated": True,
                            "split_type": "equal",
                            "calculated_participants": [
                                p.dict() for p in updated_participants
                            ],
                            "validation_warnings": validation_result.warnings,
                        },
                    )
                else:
                    # This shouldn't happen with equal splits, but handle gracefully
                    logger.error(
                        f"Equal split validation failed: {validation_result.errors}"
                    )
                    return StepResult(
                        response=Response(
                            content="I encountered an error calculating equal splits. Please try again or contact support.",
                            message_type=MessageType.TEXT,
                        ),
                        context_updates={
                            "split_calculation_error": validation_result.errors
                        },
                    )

        except Exception as e:
            logger.error(f"Error in split calculation handler: {e}")
            return StepResult(
                response=Response(
                    content="I encountered an error calculating the splits. Let me try again.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"split_calculation_error": str(e)},
            )

    async def _is_custom_split_request(self, message: Message) -> bool:
        """Check if user is requesting custom splits"""
        content_lower = message.content.lower()

        # Check for custom split indicators
        custom_indicators = [
            "₹",
            "rs",
            "rupees",
            "custom",
            "different",
            "change",
            "adjust",
            "more",
            "less",
            "should pay",
            "owes",
            ":",
        ]

        # Check for equal split requests (override custom detection)
        equal_indicators = ["equal", "same", "split equally", "divide equally"]

        if any(indicator in content_lower for indicator in equal_indicators):
            return False

        return any(indicator in content_lower for indicator in custom_indicators)


class SplitConfirmationHandler(BaseStepHandler):
    """
    Handler for confirming calculated splits
    Implements requirements 2.4, 2.5
    """

    def __init__(self, bill_splitter=None):
        super().__init__(None)
        from app.services.bill_splitter import BillSplitter

        self.bill_splitter = bill_splitter or BillSplitter()

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle split confirmation"""
        try:
            # Get calculated participants from context
            if not state.context.get("calculated_participants"):
                logger.error("No calculated participants found in context")
                return StepResult(
                    response=Response(
                        content="I don't have calculated splits. Let me calculate them first.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.CALCULATING_SPLITS,
                    context_updates={"error": "missing_calculated_splits"},
                )

            bill_data = BillData(**state.context["bill_data"])
            calculated_participants = [
                Participant(**p) for p in state.context["calculated_participants"]
            ]

            # Check user response
            content_lower = message.content.lower().strip()

            # Handle confirmation responses
            if await self._is_confirmation_yes(content_lower):
                # User confirmed splits - proceed to payment requests
                confirmation_message = "Perfect! ✅ Splits confirmed.\n\n"

                # Add any validation warnings
                if state.context.get("validation_warnings"):
                    warnings = state.context["validation_warnings"]
                    if warnings:
                        confirmation_message += (
                            "⚠️ *Note:* " + "; ".join(warnings) + "\n\n"
                        )

                confirmation_message += "I'll now generate payment requests and send them to all participants. This may take a moment..."

                return StepResult(
                    response=Response(
                        content=confirmation_message, message_type=MessageType.TEXT
                    ),
                    next_step=ConversationStep.SENDING_REQUESTS,
                    context_updates={
                        "splits_confirmed": True,
                        "final_participants": [
                            p.dict() for p in calculated_participants
                        ],
                        "confirmation_timestamp": message.timestamp.isoformat(),
                    },
                )

            elif await self._is_confirmation_no(content_lower):
                # User wants to modify splits
                return StepResult(
                    response=Response(
                        content="No problem! Let's recalculate the splits.\n\nYou can:\n• Reply 'equal' for equal splits\n• Specify custom amounts like: 'John ₹50, Sarah ₹100'\n• Or tell me what changes you'd like to make",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.CALCULATING_SPLITS,
                    context_updates={
                        "splits_rejected": True,
                        "rejection_reason": "user_requested_changes",
                    },
                )

            elif await self._contains_custom_amounts(message):
                # User provided custom amounts in confirmation step
                custom_amounts = await self.bill_splitter.parse_custom_amounts(
                    message.content, calculated_participants
                )

                if custom_amounts:
                    # Apply the custom amounts
                    updated_participants = await self.bill_splitter.apply_custom_splits(
                        bill_data, calculated_participants, custom_amounts
                    )

                    # Validate the new splits
                    validation_result = await self.bill_splitter.validate_splits(
                        bill_data, updated_participants
                    )

                    if validation_result.is_valid:
                        # Show updated splits for confirmation
                        confirmation_display = (
                            await self.bill_splitter.format_split_confirmation(
                                bill_data, updated_participants
                            )
                        )

                        return StepResult(
                            response=Response(
                                content=f"Updated splits:\n\n{confirmation_display}",
                                message_type=MessageType.TEXT,
                            ),
                            context_updates={
                                "calculated_participants": [
                                    p.dict() for p in updated_participants
                                ],
                                "split_type": "custom_adjusted",
                                "validation_warnings": validation_result.warnings,
                            },
                        )
                    else:
                        # Custom amounts have validation errors
                        error_message = "There are issues with your custom amounts:\n\n"
                        error_message += "\n".join(
                            f"• {error}" for error in validation_result.errors
                        )
                        error_message += "\n\nPlease provide corrected amounts or reply 'yes' to use the previous splits."

                        return StepResult(
                            response=Response(
                                content=error_message, message_type=MessageType.TEXT
                            ),
                            context_updates={
                                "custom_split_errors": validation_result.errors
                            },
                        )
                else:
                    # Couldn't parse custom amounts
                    return StepResult(
                        response=Response(
                            content="I couldn't understand the custom amounts. Please use format like:\n'John ₹50, Sarah ₹100'\n\nOr reply 'yes' to confirm the current splits, or 'no' to recalculate.",
                            message_type=MessageType.TEXT,
                        ),
                        context_updates={"custom_parse_failed": True},
                    )

            else:
                # Ambiguous response - ask for clarification
                current_display = await self.bill_splitter.format_split_display(
                    bill_data, calculated_participants
                )

                clarification_message = f"I need a clear confirmation. Here are the current splits:\n\n{current_display}\n\n"
                clarification_message += "Please reply:\n• *yes* to confirm and send payment requests\n• *no* to modify the splits\n• Or specify custom amounts like 'John ₹50, Sarah ₹100'"

                return StepResult(
                    response=Response(
                        content=clarification_message, message_type=MessageType.TEXT
                    ),
                    context_updates={
                        "clarification_requested": True,
                        "clarification_count": state.context.get(
                            "clarification_count", 0
                        )
                        + 1,
                    },
                )

        except Exception as e:
            logger.error(f"Error in split confirmation handler: {e}")
            return StepResult(
                response=Response(
                    content="I encountered an error processing your confirmation. Please reply 'yes' to confirm the splits or 'no' to modify them.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"confirmation_error": str(e)},
            )

    async def _is_confirmation_yes(self, content_lower: str) -> bool:
        """Check if message is a positive confirmation"""
        yes_indicators = [
            "yes",
            "y",
            "ok",
            "okay",
            "confirm",
            "confirmed",
            "correct",
            "right",
            "good",
            "looks good",
            "perfect",
            "proceed",
            "go ahead",
            "send",
            "✓",
            "✅",
            "👍",
        ]
        return any(indicator in content_lower for indicator in yes_indicators)

    async def _is_confirmation_no(self, content_lower: str) -> bool:
        """Check if message is a negative confirmation"""
        no_indicators = [
            "no",
            "n",
            "nope",
            "wrong",
            "incorrect",
            "change",
            "modify",
            "adjust",
            "different",
            "recalculate",
            "redo",
            "back",
            "❌",
            "👎",
        ]
        return any(indicator in content_lower for indicator in no_indicators)

    async def _contains_custom_amounts(self, message: Message) -> bool:
        """Check if message contains custom amount specifications"""
        content = message.content

        # Look for currency symbols or amount patterns
        import re

        amount_pattern = r"[₹$]\s*\d+|\d+\s*[₹$]|\d+\.\d{2}"

        return bool(re.search(amount_pattern, content))


class PaymentRequestHandler(BaseStepHandler):
    """Handler for sending payment requests"""

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle payment request sending"""
        # Placeholder implementation
        return StepResult(
            response=Response(
                content="Payment request sending not fully implemented yet. Moving to tracking.",
                message_type=MessageType.TEXT,
            ),
            next_step=ConversationStep.TRACKING_PAYMENTS,
            context_updates={"requests_sent": True},
        )


class PaymentTrackingHandler(BaseStepHandler):
    """
    Handler for tracking payment confirmations
    Implements requirements 5.1, 5.2, 5.3, 5.5
    """

    def __init__(
        self,
        ai_service,
        payment_confirmation_service: Optional[PaymentConfirmationService] = None,
    ):
        super().__init__(ai_service)
        self.payment_confirmation_service = payment_confirmation_service

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle payment tracking and status inquiries"""
        try:
            # Check if this is a payment confirmation message
            if self.payment_confirmation_service:
                confirmation_result = await self.payment_confirmation_service.process_payment_confirmation_message(
                    sender_phone=message.metadata.get("sender_phone", ""),
                    message_content=message.content,
                    message_timestamp=message.timestamp,
                )

                if confirmation_result.success:
                    # Payment confirmed successfully
                    response_content = f"✅ Thank you! Your payment of ₹{confirmation_result.amount} has been confirmed."

                    if confirmation_result.completion_detected:
                        response_content += (
                            "\n\n🎉 All payments for this bill are now complete!"
                        )

                    return StepResult(
                        response=Response(
                            content=response_content, message_type=MessageType.TEXT
                        ),
                        next_step=(
                            ConversationStep.COMPLETED
                            if confirmation_result.completion_detected
                            else state.current_step
                        ),
                        context_updates={
                            "payment_confirmed": True,
                            "participant_id": confirmation_result.participant_id,
                            "completion_detected": confirmation_result.completion_detected,
                        },
                    )

            # Check if this is a payment status inquiry
            if self.payment_confirmation_service:
                inquiry_response = (
                    await self.payment_confirmation_service.handle_payment_inquiry(
                        sender_phone=message.metadata.get("sender_phone", ""),
                        message_content=message.content,
                    )
                )

                if inquiry_response:
                    return StepResult(
                        response=Response(
                            content=inquiry_response, message_type=MessageType.TEXT
                        ),
                        context_updates={"inquiry_handled": True},
                    )

            # Check for bill status requests from organizer
            if self._is_status_request(message.content):
                return await self._handle_status_request(state, message)

            # Default response for unrecognized messages in tracking phase
            return StepResult(
                response=Response(
                    content="I'm currently tracking payments for your bill. Participants can reply 'DONE' when they've paid, or you can ask 'show status' to see the current payment status.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"unrecognized_message": message.content},
            )

        except Exception as e:
            logger.error(f"Error in payment tracking handler: {e}")
            return StepResult(
                response=Response(
                    content="I encountered an error while tracking payments. Please try again or contact support if the issue persists.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"error": str(e)},
            )

    def _is_status_request(self, message_content: str) -> bool:
        """Check if message is requesting bill status"""
        status_keywords = [
            "status",
            "show status",
            "bill status",
            "payment status",
            "who paid",
            "who hasn't paid",
            "check payments",
            "update",
        ]

        content_lower = message_content.lower()
        return any(keyword in content_lower for keyword in status_keywords)

    async def _handle_status_request(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle bill status request from organizer"""
        try:
            # Get bill ID from context
            bill_id = state.context.get("bill_id")
            if not bill_id:
                return StepResult(
                    response=Response(
                        content="I don't have bill information available. Please start a new bill splitting session.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.INITIAL,
                )

            # This would need to be implemented with proper bill status retrieval
            # For now, provide a placeholder response
            status_message = """📊 Bill Payment Status

I'm working on retrieving the current payment status. This feature will show:
• Who has paid
• Who still needs to pay  
• Total amount collected
• Remaining amount

Please check back soon or contact participants directly."""

            return StepResult(
                response=Response(
                    content=status_message, message_type=MessageType.TEXT
                ),
                context_updates={"status_requested": True},
            )

        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            return StepResult(
                response=Response(
                    content="Sorry, I couldn't retrieve the bill status right now. Please try again later.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"status_error": str(e)},
            )


class CompletionHandler(BaseStepHandler):
    """
    Handler for completed bills
    Provides final confirmation and cleanup
    """

    async def handle_message(
        self, state: ConversationState, message: Message
    ) -> StepResult:
        """Handle messages after bill completion"""
        try:
            # Check for new bill request
            if self._is_new_bill_request(message.content):
                return StepResult(
                    response=Response(
                        content="Great! Let's start a new bill. Please send me the bill information - you can type the details, send a photo, or record a voice message.",
                        message_type=MessageType.TEXT,
                    ),
                    next_step=ConversationStep.INITIAL,
                    context_updates={
                        "new_session": True,
                        "previous_bill_completed": True,
                    },
                )

            # Check for help request
            if self._is_help_command(message):
                return StepResult(
                    response=Response(
                        content=await self.get_help_message(),
                        message_type=MessageType.TEXT,
                    )
                )

            # Default completion response
            return StepResult(
                response=Response(
                    content="Your previous bill has been completed! 🎉\n\nTo split a new bill, just send me the bill information. I can process text, photos, or voice messages.",
                    message_type=MessageType.TEXT,
                ),
                context_updates={"completion_acknowledged": True},
            )

        except Exception as e:
            logger.error(f"Error in completion handler: {e}")
            return StepResult(
                response=Response(
                    content="Your bill is complete! Send me new bill information to start another split.",
                    message_type=MessageType.TEXT,
                )
            )

    def _is_new_bill_request(self, message_content: str) -> bool:
        """Check if message is requesting a new bill split"""
        new_bill_keywords = [
            "new bill",
            "another bill",
            "split another",
            "new split",
            "start over",
            "begin",
            "fresh start",
        ]

        content_lower = message_content.lower()
        return any(keyword in content_lower for keyword in new_bill_keywords)

    async def get_help_message(self) -> str:
        """Get help message for completion step"""
        return """Your previous bill has been completed successfully! 🎉

To split a new bill, you can:
• Type the bill details (amount, description, participants)
• Send a photo of the bill
• Record a voice message with the details

I'll help you through the entire process:
1. Extract bill information
2. Collect participant contacts  
3. Calculate splits
4. Send payment requests
5. Track confirmations

Just send me your new bill information to get started!"""
