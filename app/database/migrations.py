"""
Database migration utilities and scripts
"""
import logging
from typing import List, Dict, Any
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import engine, Base
from app.models.database import User, Contact, Bill, BillParticipant, PaymentRequest, ConversationState

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations and schema updates"""
    
    def __init__(self):
        self.engine = engine
        
    async def create_tables(self) -> bool:
        """Create all database tables with proper constraints and indexes"""
        try:
            logger.info("Creating database tables...")
            
            # Create all tables defined in models
            Base.metadata.create_all(bind=self.engine)
            logger.info("Base tables created")
            
            # Add additional constraints and indexes
            await self._add_constraints()
            logger.info("Database constraints added")
            
            await self._add_indexes()
            logger.info("Database indexes created")
            
            # Validate table creation
            validation_result = await self._validate_schema()
            if not validation_result['valid']:
                logger.error(f"Schema validation failed: {validation_result['errors']}")
                return False
            
            logger.info("Database tables created and validated successfully")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to create tables: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during table creation: {e}")
            return False
    
    async def _add_constraints(self):
        """Add database constraints for data integrity"""
        constraints = [
            # Unique constraint for user phone numbers
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS users_phone_unique UNIQUE (phone_number);",
            
            # Unique constraint for user-contact pairs
            "ALTER TABLE contacts ADD CONSTRAINT IF NOT EXISTS contacts_user_phone_unique UNIQUE (user_id, phone_number);",
            
            # Unique constraint for user-session pairs in conversation states
            "ALTER TABLE conversation_states ADD CONSTRAINT IF NOT EXISTS conv_state_user_session_unique UNIQUE (user_id, session_id);",
            
            # Check constraint for positive amounts
            "ALTER TABLE bills ADD CONSTRAINT IF NOT EXISTS bills_amount_positive CHECK (total_amount > 0);",
            "ALTER TABLE bill_participants ADD CONSTRAINT IF NOT EXISTS participants_amount_positive CHECK (amount_owed > 0);",
            
            # Check constraint for valid payment status
            """ALTER TABLE bill_participants ADD CONSTRAINT IF NOT EXISTS participants_status_valid 
               CHECK (payment_status IN ('pending', 'sent', 'confirmed', 'failed'));""",
            
            # Check constraint for valid bill status
            """ALTER TABLE bills ADD CONSTRAINT IF NOT EXISTS bills_status_valid 
               CHECK (status IN ('active', 'completed', 'cancelled'));""",
            
            # Check constraint for valid conversation steps
            """ALTER TABLE conversation_states ADD CONSTRAINT IF NOT EXISTS conv_step_valid 
               CHECK (current_step IN ('initial', 'extracting_bill', 'confirming_bill', 
                                     'collecting_contacts', 'calculating_splits', 
                                     'confirming_splits', 'sending_requests', 
                                     'tracking_payments', 'completed'));""",
        ]
        
        with self.engine.connect() as conn:
            for constraint in constraints:
                try:
                    conn.execute(text(constraint))
                    conn.commit()
                except SQLAlchemyError as e:
                    logger.warning(f"Constraint already exists or failed: {e}")
    
    async def _add_indexes(self):
        """Add database indexes for performance optimization"""
        indexes = [
            # Performance indexes for common queries
            "CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone_number);",
            "CREATE INDEX IF NOT EXISTS idx_contacts_user_id ON contacts (user_id);",
            "CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts (phone_number);",
            "CREATE INDEX IF NOT EXISTS idx_bills_user_id ON bills (user_id);",
            "CREATE INDEX IF NOT EXISTS idx_bills_status ON bills (status);",
            "CREATE INDEX IF NOT EXISTS idx_bills_created_at ON bills (created_at);",
            "CREATE INDEX IF NOT EXISTS idx_bill_participants_bill_id ON bill_participants (bill_id);",
            "CREATE INDEX IF NOT EXISTS idx_bill_participants_contact_id ON bill_participants (contact_id);",
            "CREATE INDEX IF NOT EXISTS idx_bill_participants_status ON bill_participants (payment_status);",
            "CREATE INDEX IF NOT EXISTS idx_payment_requests_participant_id ON payment_requests (bill_participant_id);",
            "CREATE INDEX IF NOT EXISTS idx_payment_requests_created_at ON payment_requests (created_at);",
            "CREATE INDEX IF NOT EXISTS idx_conv_states_user_id ON conversation_states (user_id);",
            "CREATE INDEX IF NOT EXISTS idx_conv_states_session_id ON conversation_states (session_id);",
            "CREATE INDEX IF NOT EXISTS idx_conv_states_step ON conversation_states (current_step);",
        ]
        
        with self.engine.connect() as conn:
            for index in indexes:
                try:
                    conn.execute(text(index))
                    conn.commit()
                except SQLAlchemyError as e:
                    logger.warning(f"Index already exists or failed: {e}")
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database connection and table status"""
        try:
            with self.engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1 as health_check"))
                health_check = result.fetchone()
                
                # Check if all required tables exist
                inspector = inspect(self.engine)
                existing_tables = inspector.get_table_names()
                
                required_tables = [
                    'users', 'contacts', 'bills', 'bill_participants', 
                    'payment_requests', 'conversation_states'
                ]
                
                missing_tables = [table for table in required_tables if table not in existing_tables]
                
                return {
                    'status': 'healthy' if not missing_tables else 'missing_tables',
                    'connection': 'ok' if health_check else 'failed',
                    'existing_tables': existing_tables,
                    'missing_tables': missing_tables,
                    'required_tables': required_tables
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'connection': 'failed',
                'error': str(e)
            }
    
    async def _validate_schema(self) -> Dict[str, Any]:
        """Validate database schema after creation"""
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()
            
            required_tables = [
                'users', 'contacts', 'bills', 'bill_participants', 
                'payment_requests', 'conversation_states'
            ]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            # Check for required columns in each table
            validation_errors = []
            
            if 'users' in existing_tables:
                user_columns = [col['name'] for col in inspector.get_columns('users')]
                required_user_cols = ['id', 'phone_number', 'name', 'created_at', 'updated_at']
                missing_user_cols = [col for col in required_user_cols if col not in user_columns]
                if missing_user_cols:
                    validation_errors.append(f"Users table missing columns: {missing_user_cols}")
            
            if 'bills' in existing_tables:
                bill_columns = [col['name'] for col in inspector.get_columns('bills')]
                required_bill_cols = ['id', 'user_id', 'total_amount', 'status', 'created_at']
                missing_bill_cols = [col for col in required_bill_cols if col not in bill_columns]
                if missing_bill_cols:
                    validation_errors.append(f"Bills table missing columns: {missing_bill_cols}")
            
            return {
                'valid': len(missing_tables) == 0 and len(validation_errors) == 0,
                'missing_tables': missing_tables,
                'errors': validation_errors
            }
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"]
            }
    
    async def run_migration(self, migration_name: str) -> bool:
        """Run a specific migration by name"""
        migrations = {
            'initial': self.create_tables,
            'add_constraints': self._add_constraints,
            'add_indexes': self._add_indexes,
            'validate': self._validate_schema,
        }
        
        if migration_name not in migrations:
            logger.error(f"Unknown migration: {migration_name}")
            logger.info(f"Available migrations: {list(migrations.keys())}")
            return False
        
        try:
            logger.info(f"Starting migration: {migration_name}")
            
            if migration_name == 'validate':
                result = await migrations[migration_name]()
                if result['valid']:
                    logger.info("Schema validation passed")
                    return True
                else:
                    logger.error(f"Schema validation failed: {result}")
                    return False
            else:
                await migrations[migration_name]()
                logger.info(f"Migration '{migration_name}' completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Migration '{migration_name}' failed: {e}")
            return False
    
    async def backup_schema(self) -> Dict[str, Any]:
        """Create a backup of current schema structure"""
        try:
            inspector = inspect(self.engine)
            schema_backup = {
                'tables': {},
                'indexes': {},
                'constraints': {}
            }
            
            for table_name in inspector.get_table_names():
                schema_backup['tables'][table_name] = {
                    'columns': inspector.get_columns(table_name),
                    'foreign_keys': inspector.get_foreign_keys(table_name),
                    'primary_key': inspector.get_pk_constraint(table_name),
                    'unique_constraints': inspector.get_unique_constraints(table_name),
                    'check_constraints': inspector.get_check_constraints(table_name),
                }
                schema_backup['indexes'][table_name] = inspector.get_indexes(table_name)
            
            logger.info("Schema backup created successfully")
            return schema_backup
            
        except Exception as e:
            logger.error(f"Failed to create schema backup: {e}")
            return {}


# Migration instance for use throughout the application
migration_manager = MigrationManager()