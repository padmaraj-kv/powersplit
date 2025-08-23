"""
Database factory for creating repository instances
"""
from sqlalchemy.orm import Session
from app.database.repositories import (
    SQLUserRepository, SQLContactRepository, SQLBillRepository,
    SQLPaymentRepository, SQLConversationRepository
)
from app.interfaces.repositories import (
    UserRepository, ContactRepository, BillRepository,
    PaymentRepository, ConversationRepository
)


class DatabaseFactory:
    """Factory for creating database repository instances"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user_repository(self) -> UserRepository:
        """Create user repository instance"""
        return SQLUserRepository(self.db)
    
    def create_contact_repository(self) -> ContactRepository:
        """Create contact repository instance"""
        return SQLContactRepository(self.db)
    
    def create_bill_repository(self) -> BillRepository:
        """Create bill repository instance"""
        return SQLBillRepository(self.db)
    
    def create_payment_repository(self) -> PaymentRepository:
        """Create payment repository instance"""
        return SQLPaymentRepository(self.db)
    
    def create_conversation_repository(self) -> ConversationRepository:
        """Create conversation repository instance"""
        return SQLConversationRepository(self.db)


def create_database_factory(db: Session) -> DatabaseFactory:
    """Create database factory instance"""
    return DatabaseFactory(db)