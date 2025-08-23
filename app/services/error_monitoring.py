"""
Error monitoring and logging system for comprehensive error tracking
Implements requirements 7.4, 7.5 for error logging and monitoring
"""
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum

from app.models.enums import ErrorType
from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels for monitoring and alerting"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorEvent:
    """Structured error event for monitoring and analysis"""
    id: str
    timestamp: datetime
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    service: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class ErrorMetrics:
    """Error metrics collection and analysis"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.error_events: deque = deque(maxlen=window_size)
        self.error_counts: Dict[ErrorType, int] = defaultdict(int)
        self.service_errors: Dict[str, int] = defaultdict(int)
        self.hourly_errors: Dict[str, int] = defaultdict(int)
        self.user_errors: Dict[str, int] = defaultdict(int)
    
    def add_error(self, error_event: ErrorEvent) -> None:
        """Add error event to metrics collection"""
        self.error_events.append(error_event)
        self.error_counts[error_event.error_type] += 1
        self.service_errors[error_event.service] += 1
        
        # Track hourly error rates
        hour_key = error_event.timestamp.strftime("%Y-%m-%d-%H")
        self.hourly_errors[hour_key] += 1
        
        # Track user-specific errors (if user_id available)
        if error_event.user_id:
            self.user_errors[error_event.user_id] += 1
    
    def get_error_rate(self, time_window: timedelta = timedelta(hours=1)) -> float:
        """Calculate error rate within time window"""
        cutoff_time = datetime.now() - time_window
        recent_errors = [e for e in self.error_events if e.timestamp >= cutoff_time]
        
        if not recent_errors:
            return 0.0
        
        # Calculate errors per minute
        window_minutes = time_window.total_seconds() / 60
        return len(recent_errors) / window_minutes
    
    def get_top_error_types(self, limit: int = 5) -> List[tuple]:
        """Get most common error types"""
        return sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def get_service_error_distribution(self) -> Dict[str, int]:
        """Get error distribution by service"""
        return dict(self.service_errors)
    
    def get_error_trends(self, hours: int = 24) -> Dict[str, int]:
        """Get error trends over specified hours"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        trends = {}
        
        for i in range(hours):
            hour = current_hour - timedelta(hours=i)
            hour_key = hour.strftime("%Y-%m-%d-%H")
            trends[hour_key] = self.hourly_errors.get(hour_key, 0)
        
        return trends


class ErrorMonitor:
    """
    Comprehensive error monitoring system
    Tracks, analyzes, and alerts on application errors
    """
    
    def __init__(self):
        self.metrics = ErrorMetrics()
        self.alert_thresholds = {
            ErrorSeverity.LOW: 10,      # errors per hour
            ErrorSeverity.MEDIUM: 5,    # errors per hour
            ErrorSeverity.HIGH: 2,      # errors per hour
            ErrorSeverity.CRITICAL: 1   # errors per hour
        }
        self.alert_callbacks: List[Callable] = []
        self.error_patterns: Dict[str, int] = defaultdict(int)
    
    async def log_error(self, error: Exception, context: Dict[str, Any]) -> str:
        """
        Log error with comprehensive context and monitoring
        Returns error event ID for tracking
        """
        try:
            # Generate unique error ID
            error_id = self._generate_error_id()
            
            # Classify error
            error_type = self._classify_error(error)
            severity = self._determine_severity(error, context)
            
            # Create error event
            error_event = ErrorEvent(
                id=error_id,
                timestamp=datetime.now(),
                error_type=error_type,
                severity=severity,
                message=str(error),
                service=context.get("service", "unknown"),
                user_id=context.get("user_id"),
                request_id=context.get("request_id"),
                stack_trace=context.get("stack_trace"),
                context=context
            )
            
            # Add to metrics
            self.metrics.add_error(error_event)
            
            # Log structured error
            await self._log_structured_error(error_event)
            
            # Check for patterns and alerts
            await self._check_error_patterns(error_event)
            await self._check_alert_thresholds(error_event)
            
            return error_id
            
        except Exception as e:
            logger.critical(f"Error monitoring system failed: {e}")
            return "monitoring_failed"
    
    async def resolve_error(self, error_id: str, resolution_notes: str = "") -> bool:
        """Mark error as resolved"""
        try:
            # Find error event
            for error_event in self.metrics.error_events:
                if error_event.id == error_id:
                    error_event.resolved = True
                    error_event.resolution_time = datetime.now()
                    
                    logger.info(f"Error {error_id} resolved: {resolution_notes}")
                    return True
            
            logger.warning(f"Error {error_id} not found for resolution")
            return False
            
        except Exception as e:
            logger.error(f"Failed to resolve error {error_id}: {e}")
            return False
    
    def add_alert_callback(self, callback: Callable[[ErrorEvent], None]) -> None:
        """Add callback for error alerts"""
        self.alert_callbacks.append(callback)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary for monitoring dashboard"""
        return {
            "total_errors": len(self.metrics.error_events),
            "error_rate_1h": self.metrics.get_error_rate(timedelta(hours=1)),
            "error_rate_24h": self.metrics.get_error_rate(timedelta(hours=24)),
            "top_error_types": self.metrics.get_top_error_types(),
            "service_distribution": self.metrics.get_service_error_distribution(),
            "error_trends": self.metrics.get_error_trends(24),
            "unresolved_critical": self._count_unresolved_by_severity(ErrorSeverity.CRITICAL),
            "unresolved_high": self._count_unresolved_by_severity(ErrorSeverity.HIGH),
            "last_updated": datetime.now().isoformat()
        }
    
    def get_user_error_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get error history for specific user"""
        user_errors = [
            asdict(event) for event in self.metrics.error_events
            if event.user_id == user_id
        ]
        
        # Sort by timestamp (most recent first)
        user_errors.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return user_errors[:limit]
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error into application error type"""
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Database-related errors
        if any(keyword in error_str for keyword in ["database", "connection", "sqlalchemy", "psycopg"]):
            return ErrorType.DATABASE
        
        # External service errors
        if any(keyword in error_str for keyword in ["timeout", "connection", "http", "api", "service"]):
            return ErrorType.EXTERNAL_SERVICE
        
        # Validation errors
        if any(keyword in error_str for keyword in ["validation", "invalid", "format", "required"]):
            return ErrorType.VALIDATION
        
        # Input processing errors
        if any(keyword in error_str for keyword in ["parse", "extract", "process", "decode"]):
            return ErrorType.INPUT_PROCESSING
        
        # Default to business logic error
        return ErrorType.BUSINESS_LOGIC
    
    def _determine_severity(self, error: Exception, context: Dict[str, Any]) -> ErrorSeverity:
        """Determine error severity based on error type and context"""
        error_type = self._classify_error(error)
        
        # Critical errors
        if any(keyword in str(error).lower() for keyword in ["critical", "fatal", "corruption"]):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if error_type == ErrorType.DATABASE and "connection" in str(error).lower():
            return ErrorSeverity.HIGH
        
        if context.get("affects_multiple_users", False):
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if error_type == ErrorType.EXTERNAL_SERVICE:
            return ErrorSeverity.MEDIUM
        
        if context.get("user_facing", True):
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW
    
    async def _log_structured_error(self, error_event: ErrorEvent) -> None:
        """Log error in structured format for analysis"""
        try:
            structured_log = {
                "event_type": "error",
                "error_id": error_event.id,
                "timestamp": error_event.timestamp.isoformat(),
                "error_type": error_event.error_type.value,
                "severity": error_event.severity.value,
                "message": error_event.message,
                "service": error_event.service,
                "user_id": error_event.user_id,
                "request_id": error_event.request_id,
                "context": error_event.context
            }
            
            # Log at appropriate level based on severity
            if error_event.severity == ErrorSeverity.CRITICAL:
                logger.critical(f"CRITICAL ERROR: {json.dumps(structured_log)}")
            elif error_event.severity == ErrorSeverity.HIGH:
                logger.error(f"HIGH SEVERITY ERROR: {json.dumps(structured_log)}")
            elif error_event.severity == ErrorSeverity.MEDIUM:
                logger.warning(f"MEDIUM SEVERITY ERROR: {json.dumps(structured_log)}")
            else:
                logger.info(f"LOW SEVERITY ERROR: {json.dumps(structured_log)}")
            
        except Exception as e:
            logger.error(f"Failed to log structured error: {e}")
    
    async def _check_error_patterns(self, error_event: ErrorEvent) -> None:
        """Check for error patterns that might indicate systemic issues"""
        try:
            # Create pattern key
            pattern_key = f"{error_event.error_type.value}:{error_event.service}"
            self.error_patterns[pattern_key] += 1
            
            # Check for concerning patterns
            pattern_count = self.error_patterns[pattern_key]
            
            if pattern_count >= 5:  # 5 similar errors
                logger.warning(f"Error pattern detected: {pattern_key} occurred {pattern_count} times")
                
                # Create pattern alert
                pattern_alert = ErrorEvent(
                    id=f"pattern_{self._generate_error_id()}",
                    timestamp=datetime.now(),
                    error_type=ErrorType.BUSINESS_LOGIC,
                    severity=ErrorSeverity.HIGH,
                    message=f"Error pattern detected: {pattern_key}",
                    service="error_monitor",
                    context={"pattern_count": pattern_count, "pattern_key": pattern_key}
                )
                
                await self._trigger_alerts(pattern_alert)
            
        except Exception as e:
            logger.error(f"Failed to check error patterns: {e}")
    
    async def _check_alert_thresholds(self, error_event: ErrorEvent) -> None:
        """Check if error rates exceed alert thresholds"""
        try:
            current_rate = self.metrics.get_error_rate(timedelta(hours=1))
            threshold = self.alert_thresholds.get(error_event.severity, 10)
            
            if current_rate > threshold:
                logger.warning(f"Error rate threshold exceeded: {current_rate:.2f} errors/min "
                             f"(threshold: {threshold/60:.2f} errors/min)")
                
                # Create threshold alert
                threshold_alert = ErrorEvent(
                    id=f"threshold_{self._generate_error_id()}",
                    timestamp=datetime.now(),
                    error_type=ErrorType.BUSINESS_LOGIC,
                    severity=ErrorSeverity.HIGH,
                    message=f"Error rate threshold exceeded: {current_rate:.2f} errors/min",
                    service="error_monitor",
                    context={"current_rate": current_rate, "threshold": threshold}
                )
                
                await self._trigger_alerts(threshold_alert)
            
        except Exception as e:
            logger.error(f"Failed to check alert thresholds: {e}")
    
    async def _trigger_alerts(self, error_event: ErrorEvent) -> None:
        """Trigger registered alert callbacks"""
        try:
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(error_event)
                    else:
                        callback(error_event)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")
        except Exception as e:
            logger.error(f"Failed to trigger alerts: {e}")
    
    def _count_unresolved_by_severity(self, severity: ErrorSeverity) -> int:
        """Count unresolved errors by severity"""
        return sum(1 for event in self.metrics.error_events 
                  if event.severity == severity and not event.resolved)
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid
        return str(uuid.uuid4())[:12]


# Global error monitor instance
error_monitor = ErrorMonitor()


class HealthChecker:
    """
    System health monitoring and reporting
    Implements requirement 7.5 for monitoring system
    """
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, Dict[str, Any]] = {}
    
    def register_health_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function"""
        self.health_checks[name] = check_func
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        for name, check_func in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    check_result = await check_func()
                else:
                    check_result = check_func()
                
                results["checks"][name] = {
                    "status": "healthy",
                    "details": check_result,
                    "last_checked": datetime.now().isoformat()
                }
                
            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_checked": datetime.now().isoformat()
                }
                results["overall_status"] = "degraded"
        
        # Store results for comparison
        self.last_check_results = results
        
        return results
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        return {
            "error_summary": error_monitor.get_error_summary(),
            "health_status": await self.run_health_checks(),
            "uptime": self._get_uptime(),
            "memory_usage": self._get_memory_usage(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_uptime(self) -> Dict[str, Any]:
        """Get application uptime information"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time
            
            return {
                "started_at": create_time.isoformat(),
                "uptime_seconds": uptime.total_seconds(),
                "uptime_human": str(uptime)
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            return {"error": str(e)}
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": process.memory_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            return {"error": str(e)}


# Global health checker instance
health_checker = HealthChecker()


# Default alert callback for logging
async def default_alert_callback(error_event: ErrorEvent) -> None:
    """Default alert callback that logs alerts"""
    logger.warning(f"ALERT: {error_event.severity.value.upper()} - {error_event.message}")


# Register default alert callback
error_monitor.add_alert_callback(default_alert_callback)