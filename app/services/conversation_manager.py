"""
Conversation state management service for bill splitting agent
Implements requirements 1.4, 2.5, 3.4, 7.2
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import Message, Response, ConversationState
from app.interfaces.services import ConversationServiceInterface
from app.interfaces.repositories import ConversationRepository
from app.services.state_machine import ConversationStateMachine
from app.services.error_handler import ConversationErrorHandler

logger = logging.getLogger(__name__)


class ConversationManager(ConversationServiceInterface):
    """
    Main conversation orchestrator implementing state management and flow control
    Handles conversation state persistence, validation, and error recovery
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        state_machine: ConversationStateMachine,
        error_handler: ConversationErrorHandler,
    ):
        self.conversation_repo = conversation_repo
        self.state_machine = state_machine
        self.error_handler = error_handler
        self.session_timeout_hours = 24  # Configurable session timeout
        self.max_retry_count = 3

    async def process_message(self, user_id: str, message: Message) -> Response:
        """
        Main conversation orchestrator implementing requirements 1-6
        Processes incoming messages and manages conversation flow
        """
        try:
            # Check for payment confirmations first (can happen from any step)
            payment_response = await self._check_payment_confirmation(message)
            if payment_response:
                return payment_response

            # Get or create conversation state
            state = await self.get_conversation_state(user_id, message.id)

            # Validate state and handle expired sessions
            if await self._is_state_expired(state):
                logger.info(f"Conversation state expired for user {user_id}, resetting")
                state = await self._reset_conversation_state(user_id, message.id)

            # Process message through state machine
            response = await self.state_machine.process_message(state, message)

            # Update conversation state after processing
            await self.update_conversation_state(state)

            return response

        except Exception as e:
            logger.error(f"Error processing message for user {user_id}: {e}")
            return await self.error_handler.handle_conversation_error(
                e, user_id, message
            )

    async def get_conversation_state(
        self, user_id: str, session_id: str
    ) -> ConversationState:
        """
        Get current conversation state with validation and error recovery
        Implements requirement 7.2 for state persistence and retrieval
        """
        try:
            user_uuid = UUID(user_id)

            # Try to get existing state from database
            db_state = await self.conversation_repo.get_conversation_state(
                user_uuid, session_id
            )

            if db_state:
                # Convert database model to Pydantic schema
                state = ConversationState(
                    user_id=str(db_state.user_id),
                    session_id=db_state.session_id,
                    current_step=ConversationStep(db_state.current_step),
                    context=db_state.context or {},
                    retry_count=db_state.retry_count,
                    last_error=db_state.last_error,
                    created_at=db_state.created_at,
                    updated_at=db_state.updated_at,
                )

                # Validate state integrity
                if await self._validate_state(state):
                    return state
                else:
                    logger.warning(f"Invalid state found for user {user_id}, resetting")
                    return await self._reset_conversation_state(user_id, session_id)

            # Create new conversation state
            return await self._create_new_conversation_state(user_id, session_id)

        except Exception as e:
            logger.error(f"Error getting conversation state: {e}")
            # Return default state on error
            return await self._create_new_conversation_state(user_id, session_id)

    async def update_conversation_state(
        self, state: ConversationState
    ) -> ConversationState:
        """
        Update conversation state with validation and error handling
        Implements requirement 7.2 for state persistence
        """
        try:
            # Validate state before saving
            if not await self._validate_state(state):
                raise ValueError(f"Invalid conversation state for user {state.user_id}")

            # Update timestamp
            state.updated_at = datetime.now()

            # Save to database
            user_uuid = UUID(state.user_id)
            # Persist via repository abstraction
            await self.conversation_repo.save_conversation_state(
                ConversationState(
                    user_id=str(user_uuid),
                    session_id=state.session_id,
                    current_step=state.current_step,
                    bill_data=state.bill_data,
                    participants=state.participants,
                    context=state.context,
                    retry_count=state.retry_count,
                    last_error=state.last_error,
                    created_at=state.created_at,
                    updated_at=state.updated_at,
                )
            )

            logger.info(
                f"Updated conversation state for user {state.user_id} to step {state.current_step}"
            )
            return state

        except Exception as e:
            logger.error(f"Error updating conversation state: {e}")
            # Increment retry count on error
            state.retry_count += 1
            state.last_error = str(e)

            if state.retry_count >= self.max_retry_count:
                logger.error(
                    f"Max retries exceeded for user {state.user_id}, resetting state"
                )
                return await self._reset_conversation_state(
                    state.user_id, state.session_id
                )

            raise

    async def reset_conversation(
        self, user_id: str, session_id: str
    ) -> ConversationState:
        """
        Reset conversation state to initial step
        Used for error recovery and user-initiated resets
        """
        return await self._reset_conversation_state(user_id, session_id)

    async def get_conversation_context(
        self, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """
        Get conversation context for debugging and monitoring
        """
        try:
            state = await self.get_conversation_state(user_id, session_id)
            return {
                "current_step": state.current_step.value,
                "retry_count": state.retry_count,
                "last_error": state.last_error,
                "created_at": state.created_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
                "context_keys": list(state.context.keys()) if state.context else [],
            }
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return {"error": str(e)}

    async def cleanup_expired_conversations(self) -> int:
        """
        Clean up expired conversation states
        Should be called periodically by a background task
        """
        try:
            # Fallback: return 0 if repository doesn't support cleanup
            count = 0
            logger.info(f"Cleaned up {count} expired conversation states")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up expired conversations: {e}")
            return 0

    async def _check_payment_confirmation(self, message: Message) -> Optional[Response]:
        """
        Check if message is a payment confirmation and handle it
        This allows payment confirmations to be processed from any conversation step
        Implements requirement 5.1
        """
        try:
            # Import here to avoid circular imports
            from app.services.payment_confirmation_service import (
                PaymentConfirmationService,
            )
            from app.database.repositories import DatabaseRepository
            from app.core.database import get_db

            # Get database session
            db = get_db()
            db_repo = DatabaseRepository(db)

            # Create payment confirmation service
            payment_service = PaymentConfirmationService(db_repo)

            # Extract sender phone from message metadata
            sender_phone = message.metadata.get("sender_phone", "")
            if not sender_phone:
                return None

            # Process potential payment confirmation
            confirmation_result = (
                await payment_service.process_payment_confirmation_message(
                    sender_phone=sender_phone,
                    message_content=message.content,
                    message_timestamp=message.timestamp,
                )
            )

            if confirmation_result.success:
                # Create response for successful confirmation
                response_content = f"✅ Thank you! Your payment of ₹{confirmation_result.amount} has been confirmed."

                if confirmation_result.completion_detected:
                    response_content += (
                        "\n\n🎉 All payments for this bill are now complete!"
                    )

                return Response(content=response_content, message_type=MessageType.TEXT)

            # Check if this is a payment inquiry
            inquiry_response = await payment_service.handle_payment_inquiry(
                sender_phone=sender_phone, message_content=message.content
            )

            if inquiry_response:
                return Response(content=inquiry_response, message_type=MessageType.TEXT)

            # Not a payment-related message
            return None

        except Exception as e:
            logger.error(f"Error checking payment confirmation: {e}")
            return None

    # Private helper methods

    async def _create_new_conversation_state(
        self, user_id: str, session_id: str
    ) -> ConversationState:
        """Create a new conversation state with initial values"""
        state = ConversationState(
            user_id=user_id,
            session_id=session_id,
            current_step=ConversationStep.INITIAL,
            context={"session_started": datetime.now().isoformat(), "message_count": 0},
        )

        # Save initial state to database
        try:
            user_uuid = UUID(user_id)
            await self.conversation_repo.save_conversation_state(
                ConversationState(
                    user_id=str(user_uuid),
                    session_id=session_id,
                    current_step=state.current_step,
                    bill_data=state.bill_data,
                    participants=state.participants,
                    context=state.context,
                    retry_count=state.retry_count,
                    last_error=state.last_error,
                    created_at=state.created_at,
                    updated_at=state.updated_at,
                )
            )
            logger.info(f"Created new conversation state for user {user_id}")
        except Exception as e:
            logger.error(f"Error creating conversation state: {e}")
            # Continue with in-memory state if database fails

        return state

    async def _reset_conversation_state(
        self, user_id: str, session_id: str
    ) -> ConversationState:
        """Reset conversation state to initial step"""
        try:
            # Delete existing state
            user_uuid = UUID(user_id)
            await self.conversation_repo.clear_conversation_state(user_uuid, session_id)
        except Exception as e:
            logger.warning(f"Error deleting old conversation state: {e}")

        # Create new initial state
        return await self._create_new_conversation_state(user_id, session_id)

    async def _validate_state(self, state: ConversationState) -> bool:
        """
        Validate conversation state integrity
        Implements requirement 7.2 for state validation
        """
        try:
            # Check required fields
            if not state.user_id or not state.session_id:
                return False

            # Validate step is in enum
            if state.current_step not in ConversationStep:
                return False

            # Check retry count is reasonable
            if state.retry_count < 0 or state.retry_count > self.max_retry_count * 2:
                return False

            # Validate context structure based on current step
            if not await self._validate_context_for_step(
                state.current_step, state.context
            ):
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating state: {e}")
            return False

    async def _validate_context_for_step(
        self, step: ConversationStep, context: Dict[str, Any]
    ) -> bool:
        """Validate context data for specific conversation step"""
        try:
            if step == ConversationStep.INITIAL:
                return True  # No specific requirements for initial step

            elif step == ConversationStep.EXTRACTING_BILL:
                # Should have input type information
                return "input_type" in context

            elif step == ConversationStep.CONFIRMING_BILL:
                # Should have extracted bill data
                return "bill_data" in context

            elif step == ConversationStep.COLLECTING_CONTACTS:
                # Should have confirmed bill data and participant info
                return "bill_data" in context and "participants" in context

            elif step == ConversationStep.CALCULATING_SPLITS:
                # Should have all contacts collected
                return (
                    "bill_data" in context
                    and "participants" in context
                    and "contacts_complete" in context
                )

            elif step == ConversationStep.CONFIRMING_SPLITS:
                # Should have calculated splits
                return (
                    "bill_data" in context
                    and "participants" in context
                    and "splits_calculated" in context
                )

            elif step == ConversationStep.SENDING_REQUESTS:
                # Should have confirmed splits
                return (
                    "bill_data" in context
                    and "participants" in context
                    and "splits_confirmed" in context
                )

            elif step == ConversationStep.TRACKING_PAYMENTS:
                # Should have sent payment requests
                return "bill_id" in context and "payment_requests" in context

            elif step == ConversationStep.COMPLETED:
                # Should have bill completion info
                return "bill_id" in context

            return True

        except Exception as e:
            logger.error(f"Error validating context for step {step}: {e}")
            return False

    async def _is_state_expired(self, state: Optional[ConversationState]) -> bool:
        """Check if conversation state has expired"""
        if not state:
            return False

        try:
            expiry_time = state.updated_at + timedelta(hours=self.session_timeout_hours)
            return datetime.now() > expiry_time
        except Exception as e:
            logger.error(f"Error checking state expiry: {e}")
            return True  # Consider expired on error for safety
