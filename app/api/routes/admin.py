"""
Admin API endpoints for monitoring and management
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import get_database
from app.database.repositories import (
    SQLConversationRepository,
    DatabaseRepository,
)
from app.services.error_monitoring import error_monitor, health_checker
from app.services.conversation_factory import get_conversation_factory
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health/comprehensive")
async def comprehensive_health_check():
    """
    Comprehensive health check for all system components
    """
    try:
        health_status = await health_checker.run_health_checks()

        # Add additional service checks
        additional_checks = await run_additional_health_checks()
        health_status.update(additional_checks)

        # Determine overall status
        overall_status = "healthy"
        for _, status in health_status.items():
            if isinstance(status, dict) and status.get("status") == "unhealthy":
                overall_status = "degraded"
                break

        return {
            "overall_status": overall_status,
            "services": health_status,
            "timestamp": datetime.now().isoformat(),
            "environment": settings.environment,
        }

    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


async def run_additional_health_checks() -> Dict[str, Any]:
    """Run additional health checks for services"""
    checks = {}

    try:
        # Check conversation factory
        factory = get_conversation_factory()
        conversation_manager = factory.create_conversation_manager()
        checks["conversation_manager"] = {
            "status": "healthy" if conversation_manager else "unhealthy"
        }
    except Exception as e:
        checks["conversation_manager"] = {"status": "unhealthy", "error": str(e)}

    try:
        # Check database repositories
        db = get_database()
        # Simple query test
        await db.execute("SELECT COUNT(*) FROM users")
        checks["database_repositories"] = {"status": "healthy"}
    except Exception as e:
        checks["database_repositories"] = {"status": "unhealthy", "error": str(e)}

    return checks


@router.get("/metrics/system")
async def get_system_metrics():
    """Get comprehensive system metrics"""
    try:
        metrics = await health_checker.get_system_metrics()

        # Add application-specific metrics
        app_metrics = await get_application_metrics()
        metrics.update(app_metrics)

        return {
            "status": "success",
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


async def get_application_metrics() -> Dict[str, Any]:
    """Get application-specific metrics"""
    try:
        db = get_database()
        db_repo = DatabaseRepository(db)

        # Get payment request statistics
        payment_stats = await db_repo.get_payment_request_statistics(
            since_date=datetime.now() - timedelta(days=7)
        )

        # Get conversation statistics
        conversation_repo = SQLConversationRepository(db)
        active_conversations = len(await conversation_repo.get_active_conversations())

        return {
            "payment_requests": payment_stats,
            "active_conversations": active_conversations,
            "application_version": "1.0.0",
        }

    except Exception as e:
        logger.error(f"Failed to get application metrics: {e}")
        return {"error": str(e)}


@router.get("/errors/detailed")
async def get_detailed_error_report(hours_back: int = Query(default=24, le=168)):
    """Get detailed error report"""
    try:
        error_summary = error_monitor.get_error_summary()

        # Add time-based filtering if needed (not used yet)

        return {
            "status": "success",
            "error_summary": error_summary,
            "period_hours": hours_back,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get error report: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error report")


@router.post("/maintenance/cleanup")
async def run_maintenance_cleanup(
    cleanup_type: str = Query(..., regex="^(conversations|errors|all)$"),
    hours_back: int = Query(default=24, le=168),
):
    """Run maintenance cleanup tasks"""
    try:
        results = {}

        if cleanup_type in ["conversations", "all"]:
            # Cleanup expired conversation states
            db = get_database()
            conversation_repo = SQLConversationRepository(db)
            cleaned_conversations = await conversation_repo.cleanup_expired_states(
                hours=hours_back
            )
            results["conversations_cleaned"] = cleaned_conversations

        if cleanup_type in ["errors", "all"]:
            # Cleanup old error logs (if implemented)
            results["errors_cleaned"] = "Not implemented yet"

        return {
            "status": "success",
            "cleanup_results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Maintenance cleanup failed: {e}")
        raise HTTPException(status_code=500, detail="Maintenance cleanup failed")


@router.get("/configuration")
async def get_configuration_status():
    """Get application configuration status (without sensitive values)"""
    try:
        config_status = {
            "environment": settings.environment,
            "debug_mode": settings.debug,
            "log_level": settings.log_level,
            "database_configured": bool(settings.database_url),
            "siren_configured": bool(
                settings.siren_api_key and settings.siren_webhook_secret
            ),
            "ai_services_configured": {
                "sarvam": bool(settings.sarvam_api_key),
                "gemini": bool(settings.gemini_api_key),
                "litellm": True,
            },
            "security_configured": bool(settings.encryption_key),
        }

        return {
            "status": "success",
            "configuration": config_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get configuration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.post("/services/restart")
async def restart_services(
    service: str = Query(..., regex="^(conversation_factory|all)$")
):
    """Restart specific services"""
    try:
        results = {}

        if service in ["conversation_factory", "all"]:
            # Reset and reinitialize conversation factory
            from app.services.conversation_factory import reset_conversation_factory
            from app.main import initialize_services

            reset_conversation_factory()
            await initialize_services()
            results["conversation_factory"] = "restarted"

        return {
            "status": "success",
            "restart_results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Service restart failed: {e}")
        raise HTTPException(status_code=500, detail="Service restart failed")


@router.get("/database/statistics")
async def get_database_statistics():
    """Get database usage statistics"""
    try:
        db = get_database()

        # Get table counts
        table_stats = {}
        tables = [
            "users",
            "contacts",
            "bills",
            "bill_participants",
            "payment_requests",
            "conversation_states",
        ]

        for table in tables:
            result = await db.execute(f"SELECT COUNT(*) FROM {table}")
            count = result.scalar()
            table_stats[table] = count

        return {
            "status": "success",
            "table_statistics": table_stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get database statistics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve database statistics"
        )
