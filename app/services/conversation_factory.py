"""
Factory for creating conversation management components
Handles dependency injection and service configuration
"""
import logging
from typing import Dict
from app.models.enums import ConversationStep
from app.services.conversation_manager import ConversationManager
from app.services.state_machine import ConversationStateMachine
from app.services.error_handler import ConversationErrorHandler
from app.services.step_handlers import (
    InitialStepHandler, BillExtractionHandler, BillConfirmationHandler,
    ContactCollectionHandler, SplitCalculationHandler, SplitConfirmationHandler,
    PaymentRequestHandler, PaymentTrackingHandler, CompletionHandler
)
from app.services.ai_service import AIService
from app.services.contact_manager import ContactManager
from app.services.bill_splitter import BillSplitter
from app.interfaces.repositories import ConversationRepository, ContactRepository, UserRepository

logger = logging.getLogger(__name__)


class ConversationFactory:
    """
    Factory for creating and configuring conversation management components
    Handles dependency injection and service wiring
    """
    
    def __init__(self, conversation_repo: ConversationRepository, contact_repo: ContactRepository, user_repo: UserRepository):
        self.conversation_repo = conversation_repo
        self.contact_repo = contact_repo
        self.user_repo = user_repo
        self._step_handlers = None
        self._state_machine = None
        self._error_handler = None
        self._conversation_manager = None
        self._ai_service = None
        self._contact_manager = None
        self._bill_splitter = None
    
    def create_conversation_manager(self) -> ConversationManager:
        """Create fully configured conversation manager"""
        if not self._conversation_manager:
            self._conversation_manager = ConversationManager(
                conversation_repo=self.conversation_repo,
                state_machine=self.get_state_machine(),
                error_handler=self.get_error_handler(),
                ai_service=self.get_ai_service()
            )
        return self._conversation_manager
    
    def get_state_machine(self) -> ConversationStateMachine:
        """Get configured state machine"""
        if not self._state_machine:
            self._state_machine = ConversationStateMachine(
                step_handlers=self.get_step_handlers()
            )
        return self._state_machine
    
    def get_error_handler(self) -> ConversationErrorHandler:
        """Get error handler"""
        if not self._error_handler:
            self._error_handler = ConversationErrorHandler()
        return self._error_handler
    
    def get_ai_service(self) -> AIService:
        """Get AI service"""
        if not self._ai_service:
            self._ai_service = AIService()
        return self._ai_service
    
    def get_contact_manager(self) -> ContactManager:
        """Get contact manager"""
        if not self._contact_manager:
            self._contact_manager = ContactManager(self.contact_repo, self.user_repo)
        return self._contact_manager
    
    def get_bill_splitter(self) -> BillSplitter:
        """Get bill splitter"""
        if not self._bill_splitter:
            self._bill_splitter = BillSplitter()
        return self._bill_splitter
    
    def get_step_handlers(self) -> Dict[ConversationStep, any]:
        """Get all step handlers"""
        if not self._step_handlers:
            ai_service = self.get_ai_service()
            contact_manager = self.get_contact_manager()
            bill_splitter = self.get_bill_splitter()
            self._step_handlers = {
                ConversationStep.INITIAL: InitialStepHandler(ai_service=ai_service),
                ConversationStep.EXTRACTING_BILL: BillExtractionHandler(ai_service=ai_service),
                ConversationStep.CONFIRMING_BILL: BillConfirmationHandler(ai_service=ai_service),
                ConversationStep.COLLECTING_CONTACTS: ContactCollectionHandler(ai_service=ai_service, contact_manager=contact_manager),
                ConversationStep.CALCULATING_SPLITS: SplitCalculationHandler(ai_service=ai_service, bill_splitter=bill_splitter),
                ConversationStep.CONFIRMING_SPLITS: SplitConfirmationHandler(ai_service=ai_service, bill_splitter=bill_splitter),
                ConversationStep.SENDING_REQUESTS: PaymentRequestHandler(ai_service=ai_service),
                ConversationStep.TRACKING_PAYMENTS: PaymentTrackingHandler(ai_service=ai_service),
                ConversationStep.COMPLETED: CompletionHandler(ai_service=ai_service)
            }
        return self._step_handlers
    
    def create_step_handler(self, step: ConversationStep):
        """Create individual step handler"""
        handlers = self.get_step_handlers()
        return handlers.get(step)
    
    def reset_factory(self):
        """Reset factory state - useful for testing"""
        self._step_handlers = None
        self._state_machine = None
        self._error_handler = None
        self._conversation_manager = None
        self._ai_service = None
        self._contact_manager = None
        self._bill_splitter = None
        logger.info("Conversation factory reset")


# Global factory instance - will be initialized with dependencies
_conversation_factory = None


def get_conversation_factory() -> ConversationFactory:
    """Get global conversation factory instance"""
    global _conversation_factory
    if not _conversation_factory:
        raise RuntimeError("Conversation factory not initialized. Call initialize_conversation_factory first.")
    return _conversation_factory


def initialize_conversation_factory(conversation_repo: ConversationRepository, contact_repo: ContactRepository, user_repo: UserRepository) -> ConversationFactory:
    """Initialize global conversation factory with dependencies"""
    global _conversation_factory
    _conversation_factory = ConversationFactory(conversation_repo, contact_repo, user_repo)
    logger.info("Conversation factory initialized")
    return _conversation_factory


def reset_conversation_factory():
    """Reset global conversation factory - useful for testing"""
    global _conversation_factory
    if _conversation_factory:
        _conversation_factory.reset_factory()
    _conversation_factory = None
    logger.info("Global conversation factory reset")