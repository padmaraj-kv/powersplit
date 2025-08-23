"""
PostgreSQL database connection and configuration
"""

# ruff: noqa: E501, W291, W293
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from app.core.config import settings
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, cast, Any

logger = logging.getLogger(__name__)

# SQLAlchemy setup with connection pooling
engine = create_engine(
    settings.database_url,
    # Connection pool settings for better performance and reliability
    poolclass=QueuePool,
    pool_size=10,  # Number of connections to maintain in the pool
    max_overflow=20,  # Additional connections that can be created on demand
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Timeout for getting connection from pool
    # Connection arguments for better reliability
    connect_args={
        "connect_timeout": 10,
        "application_name": "bill_splitting_agent",
        "options": "-c timezone=UTC",
        "sslmode": "prefer",  # Use SSL when available
        "target_session_attrs": "read-write",  # Ensure we connect to primary
    },
    echo=settings.debug,
    # Improved error handling
    echo_pool=settings.debug,
)


# Add connection event listeners for better error handling
@event.listens_for(engine, "connect")
def set_postgres_settings(dbapi_connection: Any, connection_record: Any) -> None:
    """Set connection-level settings for PostgreSQL"""
    try:
        with dbapi_connection.cursor() as cursor:
            # Set statement timeout to prevent long-running queries
            cursor.execute("SET statement_timeout = '30s'")
            # Set timezone to UTC for consistency
            cursor.execute("SET timezone = 'UTC'")
            # Enable better error reporting
            cursor.execute("SET log_statement_stats = off")
    except Exception as e:
        logger.warning(f"Failed to set connection settings: {e}")


@event.listens_for(engine, "checkout")
def receive_checkout(
    dbapi_connection: Any, connection_record: Any, connection_proxy: Any
) -> None:
    """Log connection checkout for monitoring"""
    logger.debug("Connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection: Any, connection_record: Any) -> None:
    """Log connection checkin for monitoring"""
    logger.debug("Connection returned to pool")


SessionLocal: sessionmaker = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
Base = declarative_base()


class DatabaseProxy:
    """A thin async-friendly proxy over a synchronous SQLAlchemy Session.

    - For repositories, attribute access proxies to the underlying Session.
    - For simple health checks in routes, provides an async execute method.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name: str):  # passthrough for ORM usage
        return getattr(self._session, name)

    async def execute(self, sql: str):  # used in a few async routes with `await`
        return self._session.execute(text(sql))


def get_db() -> Session:
    """Return a synchronous SQLAlchemy session for use by repositories."""
    return cast(Session, SessionLocal())


def get_database() -> DatabaseProxy:
    """Return a DatabaseProxy compatible with existing call sites."""
    return DatabaseProxy(get_db())


@asynccontextmanager
async def get_db_async() -> AsyncGenerator[Session, None]:
    """Async context manager for database sessions with retry logic"""
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        db = SessionLocal()
        try:
            yield db
            break
        except DisconnectionError as e:
            logger.warning(f"Database disconnection on attempt {attempt + 1}: {e}")
            db.rollback()
            db.close()
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2**attempt))  # Exponential backoff
            else:
                raise
        except SQLAlchemyError as e:
            logger.error(f"Database error on attempt {attempt + 1}: {e}")
            db.rollback()
            db.close()
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            db.rollback()
            db.close()
            raise
        finally:
            if "db" in locals():
                db.close()


async def init_database() -> None:
    """Initialize database connection and create tables with migration support"""
    try:
        logger.info("Starting database initialization...")

        # Test connection with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1 as test"))
                    test_result = result.fetchone()
                    if test_result and test_result[0] == 1:
                        logger.info("Database connection established successfully")

                        # Test database permissions
                        try:
                            conn.execute(
                                text("CREATE TEMP TABLE test_permissions (id INTEGER)")
                            )
                            conn.execute(text("DROP TABLE test_permissions"))
                            logger.info("Database permissions verified")
                        except Exception as perm_error:
                            logger.warning(
                                f"Database permission test failed: {perm_error}"
                            )

                        break
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)  # Exponential backoff

        # Import and run migrations
        from app.database.migrations import migration_manager

        # Check database health
        health_status = await migration_manager.check_database_health()
        logger.info(f"Database health status: {health_status}")

        # Run initial migration if needed
        if health_status.get("missing_tables"):
            logger.info("Running initial database migration...")
            success = await migration_manager.run_migration("initial")
            if not success:
                raise Exception("Initial migration failed")

            # Validate the migration
            logger.info("Validating database schema...")
            validation_success = await migration_manager.run_migration("validate")
            if not validation_success:
                raise Exception("Database schema validation failed")

        # Test encryption functionality
        try:
            from app.database.encryption import encryption

            test_data = "test_encryption_data"
            encrypted = encryption.encrypt(test_data)
            decrypted = encryption.decrypt(encrypted)
            if decrypted != test_data:
                raise Exception("Encryption test failed")
            logger.info("Encryption functionality verified")
        except Exception as e:
            logger.error(f"Encryption test failed: {e}")
            raise

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database() -> None:
    """Properly close database connections"""
    try:
        engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# Database health check function
async def check_database_health() -> Dict[str, str]:
    """Check database health and return status"""
    try:
        from app.database.migrations import migration_manager

        return await migration_manager.check_database_health()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
