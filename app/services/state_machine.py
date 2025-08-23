"""
Conversation state machine for managing bill splitting workflow
Implements the conversation flow logic and step transitions
"""
import logging
from typing import Dict, Any, Optional, Callable
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import Message, Response, ConversationState, BillData, Participant
from app.services.base_handlers import BaseStepHandler, StepResult

logger = logging.getLogger(__name__)


class ConversationStateMachine:
    """
    State machine for managing conversation flow and step transitions
    Implements the conversation workflow defined in the design document
    """
    
    def __init__(self, step_handlers: Dict[ConversationStep, Any]):
        self.step_handlers = step_handlers
        self._setup_transition_rules()
    
    def _setup_transition_rules(self):
        """Define valid state transitions"""
        self.valid_transitions = {
            ConversationStep.INITIAL: [
                ConversationStep.EXTRACTING_BILL
            ],
            ConversationStep.EXTRACTING_BILL: [
                ConversationStep.CONFIRMING_BILL,
                ConversationStep.EXTRACTING_BILL,  # Stay for clarification
                ConversationStep.INITIAL  # Reset on error
            ],
            ConversationStep.CONFIRMING_BILL: [
                ConversationStep.COLLECTING_CONTACTS,  # Bill confirmed
                ConversationStep.EXTRACTING_BILL,  # User wants changes
                ConversationStep.INITIAL  # Reset
            ],
            ConversationStep.COLLECTING_CONTACTS: [
                ConversationStep.CALCULATING_SPLITS,  # All contacts collected
                ConversationStep.COLLECTING_CONTACTS,  # Missing contacts
                ConversationStep.INITIAL  # Reset
            ],
            ConversationStep.CALCULATING_SPLITS: [
                ConversationStep.CONFIRMING_SPLITS,  # Splits calculated
                ConversationStep.CALCULATING_SPLITS,  # Custom splits requested
                ConversationStep.COLLECTING_CONTACTS,  # Back to contacts
                ConversationStep.INITIAL  # Reset
            ],
            ConversationStep.CONFIRMING_SPLITS: [
                ConversationStep.SENDING_REQUESTS,  # Splits approved
                ConversationStep.CALCULATING_SPLITS,  # Adjustments needed
                ConversationStep.INITIAL  # Reset
            ],
            ConversationStep.SENDING_REQUESTS: [
                ConversationStep.TRACKING_PAYMENTS,  # Requests sent
                ConversationStep.CONFIRMING_SPLITS,  # Back to splits
                ConversationStep.INITIAL  # Reset on error
            ],
            ConversationStep.TRACKING_PAYMENTS: [
                ConversationStep.COMPLETED,  # All payments confirmed
                ConversationStep.TRACKING_PAYMENTS,  # Partial payments
                ConversationStep.INITIAL  # New bill or reset
            ],
            ConversationStep.COMPLETED: [
                ConversationStep.INITIAL  # Start new conversation
            ]
        }
    
    async def process_message(self, state: ConversationState, message: Message) -> Response:
        """
        Process message through current step handler and manage transitions
        """
        try:
            # Get handler for current step
            handler = self.step_handlers.get(state.current_step)
            if not handler:
                logger.error(f"No handler found for step {state.current_step}")
                return await self._handle_unknown_step(state, message)
            
            # Process message with current step handler
            result = await handler.handle_message(state, message)
            
            # Update conversation state based on handler result
            if result.next_step and result.next_step != state.current_step:
                if await self._is_valid_transition(state.current_step, result.next_step):
                    state.current_step = result.next_step
                    logger.info(f"Transitioned from {state.current_step} to {result.next_step}")
                else:
                    logger.warning(f"Invalid transition from {state.current_step} to {result.next_step}")
                    return Response(
                        content="I encountered an error processing your request. Let's start over.",
                        message_type=MessageType.TEXT
                    )
            
            # Update context with handler results
            if result.context_updates:
                state.context.update(result.context_updates)
            
            # Increment message count
            state.context["message_count"] = state.context.get("message_count", 0) + 1
            
            # Reset retry count on successful processing
            state.retry_count = 0
            state.last_error = None
            
            return result.response
            
        except Exception as e:
            logger.error(f"Error processing message in step {state.current_step}: {e}")
            
            # Increment retry count
            state.retry_count += 1
            state.last_error = str(e)
            
            # Reset to initial step if too many retries
            if state.retry_count >= 3:
                state.current_step = ConversationStep.INITIAL
                state.context = {"error_reset": True}
                return Response(
                    content="I'm having trouble processing your request. Let's start fresh. Please send me your bill information.",
                    message_type=MessageType.TEXT
                )
            
            return Response(
                content="I encountered an error. Please try again or type 'reset' to start over.",
                message_type=MessageType.TEXT
            )
    
    async def _is_valid_transition(self, from_step: ConversationStep, to_step: ConversationStep) -> bool:
        """Check if transition between steps is valid"""
        valid_next_steps = self.valid_transitions.get(from_step, [])
        return to_step in valid_next_steps
    
    async def _handle_unknown_step(self, state: ConversationState, message: Message) -> Response:
        """Handle unknown or invalid conversation step"""
        logger.error(f"Unknown conversation step: {state.current_step}")
        
        # Reset to initial step
        state.current_step = ConversationStep.INITIAL
        state.context = {"error_reset": True}
        
        return Response(
            content="I'm not sure where we are in our conversation. Let's start over. Please send me your bill information.",
            message_type=MessageType.TEXT
        )
    
    def get_step_description(self, step: ConversationStep) -> str:
        """Get human-readable description of conversation step"""
        descriptions = {
            ConversationStep.INITIAL: "Ready to receive bill information",
            ConversationStep.EXTRACTING_BILL: "Processing bill information",
            ConversationStep.CONFIRMING_BILL: "Confirming bill details",
            ConversationStep.COLLECTING_CONTACTS: "Collecting participant contacts",
            ConversationStep.CALCULATING_SPLITS: "Calculating bill splits",
            ConversationStep.CONFIRMING_SPLITS: "Confirming split amounts",
            ConversationStep.SENDING_REQUESTS: "Sending payment requests",
            ConversationStep.TRACKING_PAYMENTS: "Tracking payment confirmations",
            ConversationStep.COMPLETED: "Bill splitting completed"
        }
        return descriptions.get(step, "Unknown step")
    
    def get_valid_next_steps(self, current_step: ConversationStep) -> list:
        """Get list of valid next steps from current step"""
        return self.valid_transitions.get(current_step, [])