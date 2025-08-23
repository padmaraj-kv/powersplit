"""
Base classes for conversation step handlers
Separated to avoid circular imports
"""
from typing import Dict, Any, Optional
from app.models.enums import ConversationStep, MessageType
from app.models.schemas import Message, Response, ConversationState


class StepResult:
    """Result of processing a conversation step"""
    
    def __init__(self, 
                 response: Response,
                 next_step: Optional[ConversationStep] = None,
                 context_updates: Optional[Dict[str, Any]] = None):
        self.response = response
        self.next_step = next_step
        self.context_updates = context_updates or {}


class BaseStepHandler:
    """Base class for conversation step handlers"""
    
    def __init__(self, ai_service=None):
        """Initialize step handler with AI service"""
        self.ai_service = ai_service
    
    async def handle_message(self, state: ConversationState, message: Message) -> StepResult:
        """Handle message for this conversation step"""
        raise NotImplementedError("Subclasses must implement handle_message")
    
    async def validate_input(self, message: Message) -> bool:
        """Validate input for this step"""
        return True
    
    async def get_help_message(self) -> str:
        """Get help message for this step"""
        return "I'm not sure how to help with that. Please try again."
    
    def _is_reset_command(self, message: Message) -> bool:
        """Check if message is a reset command"""
        reset_commands = ["reset", "start over", "restart", "begin again", "new bill"]
        return message.content.lower().strip() in reset_commands
    
    def _is_help_command(self, message: Message) -> bool:
        """Check if message is a help command"""
        help_commands = ["help", "?", "what can you do", "commands"]
        return message.content.lower().strip() in help_commands