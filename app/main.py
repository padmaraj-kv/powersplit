"""
FastAPI main application entry point for Bill Splitting Agent
Complete application orchestrator with all service integrations
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any
import asyncio

from app.api.routes import webhooks
from app.core.config import settings, validate_configuration
from app.core.database import init_database, get_database
from app.middleware.error_middleware import ErrorHandlingMiddleware
from app.services.error_monitoring import error_monitor, health_checker
from app.services.conversation_factory import (
    initialize_conversation_factory,
    get_conversation_factory,
)
from app.database.repositories import (
    SQLUserRepository,
    SQLContactRepository,
    SQLBillRepository,
    SQLPaymentRepository,
    SQLConversationRepository,
)
from app.utils.logging import setup_logging, get_logger, log_error_with_context

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with complete service initialization"""
    # Startup
    logger.info("Starting Bill Splitting Agent...")
    try:
        # Validate configuration
        validate_configuration()

        # Initialize database
        await init_database()

        # Initialize conversation factory with repositories
        await initialize_services()

        # Register health checks
        await register_health_checks()

        # Initialize webhook handler with conversation manager
        await initialize_webhook_handler()

        # Log successful startup
        logger.info("Application startup completed successfully")

        # Log startup event
        await error_monitor.log_error(
            Exception("Application started successfully"),
            {
                "event_type": "startup",
                "service": "bill-splitting-agent",
                "environment": settings.environment,
                "debug_mode": settings.debug,
                "version": "1.0.0",
            },
        )

    except Exception as e:
        log_error_with_context(
            logger,
            e,
            {
                "event_type": "startup_failure",
                "service": "bill-splitting-agent",
                "critical": True,
            },
        )
        raise

    yield

    # Shutdown
    logger.info("Shutting down Bill Splitting Agent...")
    try:
        # Cleanup conversation factory
        await cleanup_services()

        # Log shutdown event
        await error_monitor.log_error(
            Exception("Application shutdown initiated"),
            {"event_type": "shutdown", "service": "bill-splitting-agent"},
        )
    except Exception as e:
        logger.error(f"Error during shutdown logging: {e}")


async def initialize_services():
    """Initialize all application services and dependencies"""
    try:
        # Get database session
        db = get_database()

        # Create repository instances
        user_repo = SQLUserRepository(db)
        contact_repo = SQLContactRepository(db)
        conversation_repo = SQLConversationRepository(db)

        # Initialize conversation factory with repositories
        factory = initialize_conversation_factory(
            conversation_repo=conversation_repo,
            contact_repo=contact_repo,
            user_repo=user_repo,
        )

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


async def initialize_webhook_handler():
    """Initialize webhook handler with conversation manager"""
    try:
        from app.api.routes.webhooks import webhook_handler

        # Get conversation factory
        factory = get_conversation_factory()

        # Create conversation manager
        conversation_manager = factory.create_conversation_manager()

        # Inject conversation manager into webhook handler
        webhook_handler.conversation_manager = conversation_manager

        logger.info("Webhook handler initialized with conversation manager")

    except Exception as e:
        logger.error(f"Failed to initialize webhook handler: {e}")
        raise


async def cleanup_services():
    """Cleanup services during shutdown"""
    try:
        from app.services.conversation_factory import reset_conversation_factory

        # Reset conversation factory
        reset_conversation_factory()

        # Cleanup expired conversation states
        db = get_database()
        conversation_repo = SQLConversationRepository(db)
        cleaned_count = await conversation_repo.cleanup_expired_states(hours=24)
        logger.info(f"Cleaned up {cleaned_count} expired conversation states")

        logger.info("Services cleanup completed")

    except Exception as e:
        logger.error(f"Error during services cleanup: {e}")


async def register_health_checks():
    """Register health check functions"""

    async def database_health():
        """Check database connectivity"""
        try:
            from app.core.database import get_database

            db = get_database()
            # Simple query to test connection
            await db.execute("SELECT 1")
            return {"status": "healthy", "response_time_ms": 0}
        except Exception as e:
            raise Exception(f"Database unhealthy: {e}")

    def memory_health():
        """Check memory usage"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            if memory.percent > 90:
                raise Exception(f"High memory usage: {memory.percent}%")
            return {
                "memory_percent": memory.percent,
                "available_gb": memory.available / 1024**3,
            }
        except ImportError:
            return {"status": "psutil not available"}

    async def external_services_health():
        """Check external services connectivity"""
        try:
            # This would check Siren, AI services, etc.
            # For now, return basic status
            return {"siren": "not_tested", "ai_services": "not_tested"}
        except Exception as e:
            raise Exception(f"External services check failed: {e}")

    # Register health checks
    health_checker.register_health_check("database", database_health)
    health_checker.register_health_check("memory", memory_health)
    health_checker.register_health_check("external_services", external_services_health)


app = FastAPI(
    title="Bill Splitting Agent",
    description="""
    Intelligent WhatsApp-based bill splitting system that helps users split bills among friends and family.
    
    ## Features
    - **Multi-modal Input**: Process text, voice, and image messages for bill information
    - **AI-Powered Extraction**: Uses Sarvam, Gemini, and LiteLLM APIs for intelligent bill parsing
    - **Automated Calculations**: Smart bill splitting with customizable distribution
    - **Contact Management**: Handles participant contact collection and deduplication
    - **Payment Integration**: Generates UPI payment links and tracks confirmations
    - **WhatsApp/SMS Integration**: Uses Siren AI Toolkit for message delivery with fallback
    - **Conversation Management**: Maintains context across multi-step interactions
    - **Error Recovery**: Comprehensive error handling with graceful degradation
    
    ## API Endpoints
    - **Webhooks**: `/api/v1/webhooks/` - Siren webhook handlers
    - **Bills**: `/api/v1/bills/` - Bill management and queries
    - **Admin**: `/api/v1/admin/` - Administrative functions and monitoring
    - **Health**: `/health` - Basic health check
    - **Metrics**: `/metrics` - Application metrics
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Add error handling middleware
app.add_middleware(ErrorHandlingMiddleware)

# Include only webhook routes (single-ingress design)
app.include_router(webhooks.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Bill Splitting Agent",
        "version": "1.0.0",
        "description": "Intelligent WhatsApp-based bill splitting system",
        "status": "operational",
        "environment": settings.environment,
        "endpoints": {
            "health": "/health",
            "detailed_health": "/health/detailed",
            "metrics": "/metrics",
            "webhooks": "/api/v1/webhooks/",
            "documentation": (
                "/docs" if not settings.is_production else "disabled_in_production"
            ),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "bill-splitting-agent",
        "version": "1.0.0",
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with comprehensive system status"""
    try:
        health_status = await health_checker.run_health_checks()
        return health_status
    except Exception as e:
        log_error_with_context(
            logger, e, {"endpoint": "/health/detailed", "service": "health_check"}
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.get("/metrics")
async def get_metrics():
    """Get application metrics and error statistics"""
    try:
        return await health_checker.get_system_metrics()
    except Exception as e:
        log_error_with_context(
            logger, e, {"endpoint": "/metrics", "service": "metrics"}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to retrieve metrics",
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.get("/errors/summary")
async def get_error_summary():
    """Get error summary for monitoring dashboard"""
    try:
        return error_monitor.get_error_summary()
    except Exception as e:
        log_error_with_context(
            logger, e, {"endpoint": "/errors/summary", "service": "error_monitoring"}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to retrieve error summary",
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "type": "not_found",
                "message": f"Endpoint {request.url.path} not found",
                "timestamp": datetime.now().isoformat(),
                "suggestions": [
                    "Check the URL path",
                    "Refer to API documentation",
                    "Use /health endpoint to verify service status",
                ],
            }
        },
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    """Custom 405 handler"""
    return JSONResponse(
        status_code=405,
        content={
            "error": {
                "type": "method_not_allowed",
                "message": f"Method {request.method} not allowed for {request.url.path}",
                "timestamp": datetime.now().isoformat(),
                "suggestions": [
                    "Check the HTTP method",
                    "Refer to API documentation for allowed methods",
                ],
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    # Get uvicorn configuration from settings
    uvicorn_config = settings.get_uvicorn_config()

    logger.info(f"Starting server with configuration: {uvicorn_config}")

    uvicorn.run("app.main:app", **uvicorn_config)
