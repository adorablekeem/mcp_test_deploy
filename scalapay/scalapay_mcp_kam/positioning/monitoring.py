"""
Comprehensive monitoring and error handling for the positioning system.
Provides metrics, alerting, and performance tracking capabilities.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .feature_flags import get_feature_manager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""

    timestamp: float
    operation: str
    mode: str  # 'clean' or 'legacy'
    success: bool
    execution_time: float
    correlation_id: str
    error_message: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""

    metric: str
    operator: str  # 'gt', 'lt', 'eq'
    value: float
    window_seconds: int = 300  # 5 minutes
    min_samples: int = 5
    enabled: bool = True


class PositioningMonitor:
    """Comprehensive monitoring system for positioning operations."""

    def __init__(self, max_metrics_history: int = 10000):
        self.metrics_history: deque = deque(maxlen=max_metrics_history)
        self.feature_manager = get_feature_manager()

        # Alert configuration
        self.alert_thresholds = {
            "error_rate_high": AlertThreshold("error_rate", "gt", 10.0),
            "execution_time_high": AlertThreshold("avg_execution_time", "gt", 30.0),
            "clean_mode_failures": AlertThreshold("clean_failures_per_minute", "gt", 3.0, window_seconds=60),
            "api_calls_excessive": AlertThreshold("api_calls_per_minute", "gt", 100.0, window_seconds=60),
        }

        # Alert callbacks
        self.alert_callbacks: List[Callable] = []

        # Current session stats
        self.session_stats = defaultdict(int)
        self.session_start = time.time()

    def record_metric(
        self,
        operation: str,
        mode: str,
        success: bool,
        execution_time: float,
        correlation_id: str,
        error_message: Optional[str] = None,
        **details,
    ):
        """Record a performance metric."""

        metric = PerformanceMetric(
            timestamp=time.time(),
            operation=operation,
            mode=mode,
            success=success,
            execution_time=execution_time,
            correlation_id=correlation_id,
            error_message=error_message,
            details=details,
        )

        self.metrics_history.append(metric)

        # Update session stats
        self.session_stats[f"{mode}_{operation}_total"] += 1
        if success:
            self.session_stats[f"{mode}_{operation}_success"] += 1
        else:
            self.session_stats[f"{mode}_{operation}_failure"] += 1

        self.session_stats[f"{mode}_{operation}_time"] += execution_time

        # Check for alerts
        self._check_alerts()

        # Log significant events
        if not success:
            logger.error(
                f"Operation failed: {operation} ({mode}) - {error_message} "
                f"[{correlation_id}] in {execution_time:.2f}s"
            )
        elif self.feature_manager.flags.enable_detailed_logging:
            logger.debug(f"Operation completed: {operation} ({mode}) " f"[{correlation_id}] in {execution_time:.2f}s")

    def get_metrics_summary(
        self,
        window_seconds: Optional[int] = None,
        operation_filter: Optional[str] = None,
        mode_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""

        # Filter metrics by time window
        if window_seconds:
            cutoff_time = time.time() - window_seconds
            filtered_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        else:
            filtered_metrics = list(self.metrics_history)

        # Apply additional filters
        if operation_filter:
            filtered_metrics = [m for m in filtered_metrics if m.operation == operation_filter]
        if mode_filter:
            filtered_metrics = [m for m in filtered_metrics if m.mode == mode_filter]

        if not filtered_metrics:
            return {"message": "No metrics found for specified filters"}

        # Calculate statistics
        total_requests = len(filtered_metrics)
        successful_requests = sum(1 for m in filtered_metrics if m.success)
        failed_requests = total_requests - successful_requests

        execution_times = [m.execution_time for m in filtered_metrics]
        avg_execution_time = sum(execution_times) / len(execution_times)
        min_execution_time = min(execution_times)
        max_execution_time = max(execution_times)

        # Group by mode and operation
        mode_stats = defaultdict(lambda: defaultdict(int))
        operation_stats = defaultdict(lambda: defaultdict(int))

        for metric in filtered_metrics:
            mode_stats[metric.mode]["total"] += 1
            mode_stats[metric.mode]["success" if metric.success else "failure"] += 1
            mode_stats[metric.mode]["total_time"] += metric.execution_time

            operation_stats[metric.operation]["total"] += 1
            operation_stats[metric.operation]["success" if metric.success else "failure"] += 1
            operation_stats[metric.operation]["total_time"] += metric.execution_time

        # Calculate mode averages
        for mode, stats in mode_stats.items():
            if stats["total"] > 0:
                stats["avg_time"] = stats["total_time"] / stats["total"]
                stats["success_rate"] = (stats.get("success", 0) / stats["total"]) * 100

        # Calculate operation averages
        for operation, stats in operation_stats.items():
            if stats["total"] > 0:
                stats["avg_time"] = stats["total_time"] / stats["total"]
                stats["success_rate"] = (stats.get("success", 0) / stats["total"]) * 100

        return {
            "summary": {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": (successful_requests / total_requests) * 100,
                "avg_execution_time": avg_execution_time,
                "min_execution_time": min_execution_time,
                "max_execution_time": max_execution_time,
                "window_seconds": window_seconds,
                "time_range": {
                    "start": min(m.timestamp for m in filtered_metrics),
                    "end": max(m.timestamp for m in filtered_metrics),
                },
            },
            "by_mode": dict(mode_stats),
            "by_operation": dict(operation_stats),
            "recent_errors": [
                {
                    "timestamp": m.timestamp,
                    "operation": m.operation,
                    "mode": m.mode,
                    "error": m.error_message,
                    "correlation_id": m.correlation_id,
                    "execution_time": m.execution_time,
                }
                for m in filtered_metrics[-10:]
                if not m.success
            ],
        }

    def _check_alerts(self):
        """Check all alert thresholds and trigger alerts if needed."""

        current_time = time.time()

        for alert_name, threshold in self.alert_thresholds.items():
            if not threshold.enabled:
                continue

            try:
                # Get metrics within the alert window
                window_start = current_time - threshold.window_seconds
                window_metrics = [m for m in self.metrics_history if m.timestamp >= window_start]

                if len(window_metrics) < threshold.min_samples:
                    continue

                # Calculate the metric value
                metric_value = self._calculate_alert_metric(threshold.metric, window_metrics)

                # Check threshold
                if self._check_threshold(metric_value, threshold.operator, threshold.value):
                    self._trigger_alert(alert_name, threshold, metric_value, window_metrics)

            except Exception as e:
                logger.error(f"Error checking alert {alert_name}: {e}")

    def _calculate_alert_metric(self, metric_name: str, metrics: List[PerformanceMetric]) -> float:
        """Calculate alert metric value from metrics list."""

        if metric_name == "error_rate":
            if not metrics:
                return 0.0
            failures = sum(1 for m in metrics if not m.success)
            return (failures / len(metrics)) * 100

        elif metric_name == "avg_execution_time":
            if not metrics:
                return 0.0
            return sum(m.execution_time for m in metrics) / len(metrics)

        elif metric_name == "clean_failures_per_minute":
            clean_failures = sum(1 for m in metrics if m.mode == "clean" and not m.success)
            window_minutes = len(set(int(m.timestamp // 60) for m in metrics))
            return clean_failures / max(window_minutes, 1)

        elif metric_name == "api_calls_per_minute":
            # Estimate API calls based on successful operations
            api_calls = sum(m.details.get("api_calls", 1) for m in metrics if m.success)
            window_minutes = len(set(int(m.timestamp // 60) for m in metrics))
            return api_calls / max(window_minutes, 1)

        return 0.0

    def _check_threshold(self, value: float, operator: str, threshold: float) -> bool:
        """Check if value meets threshold condition."""

        if operator == "gt":
            return value > threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "eq":
            return abs(value - threshold) < 0.001

        return False

    def _trigger_alert(
        self,
        alert_name: str,
        threshold: AlertThreshold,
        current_value: float,
        triggering_metrics: List[PerformanceMetric],
    ):
        """Trigger an alert."""

        alert_data = {
            "alert_name": alert_name,
            "threshold": asdict(threshold),
            "current_value": current_value,
            "timestamp": time.time(),
            "metrics_count": len(triggering_metrics),
            "recent_errors": [m.error_message for m in triggering_metrics[-5:] if not m.success and m.error_message],
        }

        logger.warning(
            f"ALERT: {alert_name} - {threshold.metric} = {current_value:.2f} "
            f"({threshold.operator} {threshold.value}) over {threshold.window_seconds}s window"
        )

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                asyncio.create_task(callback(alert_data))
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        # Check if we should trigger automatic fallback
        if alert_name in ["error_rate_high", "clean_mode_failures"] and current_value > 15.0:
            logger.critical(f"Critical alert {alert_name}: triggering emergency fallback")
            self.feature_manager.emergency_rollback(f"Automatic fallback due to {alert_name}")

    def add_alert_callback(self, callback: Callable):
        """Add a callback function to be called when alerts trigger."""
        self.alert_callbacks.append(callback)

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of the positioning system."""

        recent_metrics = self.get_metrics_summary(window_seconds=300)  # Last 5 minutes

        # Determine health status
        if not recent_metrics.get("summary"):
            health_status = "unknown"
            issues = ["No recent metrics available"]
        else:
            summary = recent_metrics["summary"]
            success_rate = summary.get("success_rate", 0)
            avg_time = summary.get("avg_execution_time", 0)

            issues = []

            if success_rate < 90:
                issues.append(f"Low success rate: {success_rate:.1f}%")
            if avg_time > 30:
                issues.append(f"High average execution time: {avg_time:.1f}s")

            health_status = "healthy" if not issues else ("degraded" if success_rate > 50 else "critical")

        return {
            "status": health_status,
            "timestamp": time.time(),
            "session_duration": time.time() - self.session_start,
            "issues": issues,
            "recent_metrics": recent_metrics,
            "feature_flags": {
                "mode": self.feature_manager.flags.positioning_mode.value,
                "rollout_percentage": self.feature_manager.flags.rollout_percentage,
                "fallback_enabled": self.feature_manager.flags.enable_fallback_on_error,
            },
            "alerts": {
                name: {"enabled": threshold.enabled, "threshold": threshold.value}
                for name, threshold in self.alert_thresholds.items()
            },
        }

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""

        if format == "json":
            return json.dumps([asdict(m) for m in self.metrics_history], indent=2)
        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
                ["timestamp", "operation", "mode", "success", "execution_time", "correlation_id", "error_message"]
            )

            # Data
            for metric in self.metrics_history:
                writer.writerow(
                    [
                        metric.timestamp,
                        metric.operation,
                        metric.mode,
                        metric.success,
                        metric.execution_time,
                        metric.correlation_id,
                        metric.error_message or "",
                    ]
                )

            return output.getvalue()

        raise ValueError(f"Unsupported export format: {format}")


# Global monitor instance
_monitor = None


def get_monitor() -> PositioningMonitor:
    """Get global positioning monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PositioningMonitor()
    return _monitor


# Context manager for automatic metric recording
@asynccontextmanager
async def monitor_operation(operation: str, mode: str, correlation_id: str, **details):
    """Context manager that automatically records performance metrics."""

    monitor = get_monitor()
    start_time = time.time()
    success = False
    error_message = None

    try:
        yield
        success = True

    except Exception as e:
        error_message = str(e)
        raise

    finally:
        execution_time = time.time() - start_time

        monitor.record_metric(
            operation=operation,
            mode=mode,
            success=success,
            execution_time=execution_time,
            correlation_id=correlation_id,
            error_message=error_message,
            **details,
        )


# Convenience functions
def record_positioning_metric(
    operation: str,
    mode: str,
    success: bool,
    execution_time: float,
    correlation_id: str,
    error_message: Optional[str] = None,
    **details,
):
    """Convenience function to record positioning metrics."""
    get_monitor().record_metric(operation, mode, success, execution_time, correlation_id, error_message, **details)


def get_positioning_health() -> Dict[str, Any]:
    """Convenience function to get positioning system health."""
    return get_monitor().get_health_status()


def export_positioning_metrics(format: str = "json") -> str:
    """Convenience function to export positioning metrics."""
    return get_monitor().export_metrics(format)


# Alert callback example
async def default_alert_callback(alert_data: Dict[str, Any]):
    """Default alert callback that logs alerts."""
    logger.warning(f"Positioning Alert: {json.dumps(alert_data, indent=2)}")


# Initialize default alert callback
get_monitor().add_alert_callback(default_alert_callback)
