"""
Feature flag system for safe rollback between positioning implementations.
Allows gradual rollout and instant reversion to legacy system.
"""

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PositioningMode(Enum):
    """Available positioning system modes."""

    LEGACY = "legacy"  # Original complex implementation
    CLEAN = "clean"  # New GoogleApiSupport implementation
    HYBRID = "hybrid"  # Mix of both with fallback
    AUTO = "auto"  # Automatic selection based on template


@dataclass
class FeatureFlags:
    """Feature flags for positioning system."""

    # Core positioning mode
    positioning_mode: PositioningMode = PositioningMode.HYBRID

    # Clean positioning features
    enable_template_discovery: bool = True
    enable_declarative_config: bool = True
    enable_batch_operations: bool = True
    enable_concurrent_uploads: bool = True

    # Safety features
    enable_fallback_on_error: bool = True
    enable_performance_monitoring: bool = True
    enable_detailed_logging: bool = False

    # Rollout controls
    rollout_percentage: float = 0.0  # 0-100, percentage of requests using clean mode
    template_whitelist: list = None  # Only these templates use clean mode
    template_blacklist: list = None  # These templates never use clean mode

    # Performance thresholds for auto-fallback
    max_execution_time_seconds: float = 30.0
    max_error_rate_percentage: float = 5.0

    def __post_init__(self):
        if self.template_whitelist is None:
            self.template_whitelist = []
        if self.template_blacklist is None:
            self.template_blacklist = []


class PositioningFeatureManager:
    """Manages feature flags and mode selection for positioning system."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.getenv(
            "POSITIONING_CONFIG_PATH", "scalapay/scalapay_mcp_kam/positioning/config.json"
        )
        self.flags = self._load_flags()
        self._performance_stats = {
            "clean_mode_requests": 0,
            "clean_mode_successes": 0,
            "clean_mode_failures": 0,
            "clean_mode_total_time": 0.0,
            "legacy_mode_requests": 0,
            "legacy_mode_successes": 0,
            "legacy_mode_failures": 0,
            "legacy_mode_total_time": 0.0,
        }

    def _load_flags(self) -> FeatureFlags:
        """Load feature flags from configuration file or environment."""

        # Try to load from file first
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config_data = json.load(f)

                # Convert string enum values
                if "positioning_mode" in config_data:
                    config_data["positioning_mode"] = PositioningMode(config_data["positioning_mode"])

                return FeatureFlags(**config_data)

            except Exception as e:
                logger.warning(f"Failed to load positioning config from {self.config_path}: {e}")

        # Fall back to environment variables
        env_flags = FeatureFlags(
            positioning_mode=PositioningMode(os.getenv("POSITIONING_MODE", "hybrid")),
            enable_template_discovery=os.getenv("ENABLE_TEMPLATE_DISCOVERY", "true").lower() == "true",
            enable_declarative_config=os.getenv("ENABLE_DECLARATIVE_CONFIG", "true").lower() == "true",
            enable_batch_operations=os.getenv("ENABLE_BATCH_OPERATIONS", "true").lower() == "true",
            enable_concurrent_uploads=os.getenv("ENABLE_CONCURRENT_UPLOADS", "true").lower() == "true",
            enable_fallback_on_error=os.getenv("ENABLE_FALLBACK_ON_ERROR", "true").lower() == "true",
            rollout_percentage=float(os.getenv("CLEAN_POSITIONING_ROLLOUT", "0.0")),
            max_execution_time_seconds=float(os.getenv("MAX_EXECUTION_TIME", "30.0")),
            max_error_rate_percentage=float(os.getenv("MAX_ERROR_RATE", "5.0")),
        )

        return env_flags

    def should_use_clean_positioning(self, template_id: str, correlation_id: Optional[str] = None) -> bool:
        """
        Determine whether to use clean positioning for this request.

        Args:
            template_id: Google Slides template ID
            correlation_id: Request correlation ID for logging

        Returns:
            True if should use clean positioning, False for legacy
        """

        # Force modes
        if self.flags.positioning_mode == PositioningMode.LEGACY:
            logger.debug(f"[{correlation_id}] Using LEGACY mode (forced)")
            return False

        if self.flags.positioning_mode == PositioningMode.CLEAN:
            logger.debug(f"[{correlation_id}] Using CLEAN mode (forced)")
            return True

        # Template blacklist check
        if template_id in self.flags.template_blacklist:
            logger.debug(f"[{correlation_id}] Using LEGACY mode (template blacklisted)")
            return False

        # Template whitelist check
        if self.flags.template_whitelist and template_id in self.flags.template_whitelist:
            logger.debug(f"[{correlation_id}] Using CLEAN mode (template whitelisted)")
            return True

        # Performance-based fallback
        if self._should_fallback_due_to_performance():
            logger.warning(f"[{correlation_id}] Using LEGACY mode (performance fallback)")
            return False

        # Rollout percentage
        if self.flags.rollout_percentage > 0:
            import hashlib

            # Use template_id for consistent rollout (same template always gets same result)
            hash_value = int(hashlib.md5(template_id.encode()).hexdigest()[:8], 16)
            rollout_threshold = (self.flags.rollout_percentage / 100.0) * (2**32)

            use_clean = hash_value < rollout_threshold
            mode = "CLEAN" if use_clean else "LEGACY"
            logger.debug(f"[{correlation_id}] Using {mode} mode (rollout: {self.flags.rollout_percentage}%)")
            return use_clean

        # Default to legacy for safety
        logger.debug(f"[{correlation_id}] Using LEGACY mode (default)")
        return False

    def _should_fallback_due_to_performance(self) -> bool:
        """Check if we should fallback to legacy due to performance issues."""

        clean_requests = self._performance_stats["clean_mode_requests"]
        if clean_requests < 10:  # Need minimum samples
            return False

        # Check error rate
        clean_failures = self._performance_stats["clean_mode_failures"]
        error_rate = (clean_failures / clean_requests) * 100

        if error_rate > self.flags.max_error_rate_percentage:
            logger.warning(f"Clean positioning error rate too high: {error_rate:.1f}%")
            return True

        # Check average execution time
        clean_total_time = self._performance_stats["clean_mode_total_time"]
        avg_time = clean_total_time / clean_requests

        if avg_time > self.flags.max_execution_time_seconds:
            logger.warning(f"Clean positioning too slow: {avg_time:.1f}s average")
            return True

        return False

    def record_performance(self, mode: str, success: bool, execution_time: float, correlation_id: Optional[str] = None):
        """Record performance metrics for monitoring and fallback decisions."""

        mode_key = f"{mode.lower()}_mode"

        self._performance_stats[f"{mode_key}_requests"] += 1
        self._performance_stats[f"{mode_key}_total_time"] += execution_time

        if success:
            self._performance_stats[f"{mode_key}_successes"] += 1
        else:
            self._performance_stats[f"{mode_key}_failures"] += 1

        if self.flags.enable_performance_monitoring:
            logger.info(
                f"[{correlation_id}] {mode.upper()} positioning: " f"success={success}, time={execution_time:.2f}s"
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        stats = self._performance_stats.copy()

        # Calculate derived metrics
        clean_requests = stats["clean_mode_requests"]
        legacy_requests = stats["legacy_mode_requests"]

        if clean_requests > 0:
            stats["clean_success_rate"] = stats["clean_mode_successes"] / clean_requests * 100
            stats["clean_avg_time"] = stats["clean_mode_total_time"] / clean_requests
        else:
            stats["clean_success_rate"] = 0
            stats["clean_avg_time"] = 0

        if legacy_requests > 0:
            stats["legacy_success_rate"] = stats["legacy_mode_successes"] / legacy_requests * 100
            stats["legacy_avg_time"] = stats["legacy_mode_total_time"] / legacy_requests
        else:
            stats["legacy_success_rate"] = 0
            stats["legacy_avg_time"] = 0

        return stats

    def update_flags(self, **kwargs):
        """Update feature flags dynamically (for emergency rollback)."""
        for key, value in kwargs.items():
            if hasattr(self.flags, key):
                setattr(self.flags, key, value)
                logger.info(f"Updated positioning flag: {key} = {value}")

    def emergency_rollback(self, reason: str = "Manual rollback"):
        """Emergency rollback to legacy positioning."""
        self.flags.positioning_mode = PositioningMode.LEGACY
        self.flags.rollout_percentage = 0.0
        logger.critical(f"EMERGENCY ROLLBACK to legacy positioning: {reason}")

    def save_config(self):
        """Save current configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            config_data = {
                "positioning_mode": self.flags.positioning_mode.value,
                "enable_template_discovery": self.flags.enable_template_discovery,
                "enable_declarative_config": self.flags.enable_declarative_config,
                "enable_batch_operations": self.flags.enable_batch_operations,
                "enable_concurrent_uploads": self.flags.enable_concurrent_uploads,
                "enable_fallback_on_error": self.flags.enable_fallback_on_error,
                "enable_performance_monitoring": self.flags.enable_performance_monitoring,
                "enable_detailed_logging": self.flags.enable_detailed_logging,
                "rollout_percentage": self.flags.rollout_percentage,
                "template_whitelist": self.flags.template_whitelist,
                "template_blacklist": self.flags.template_blacklist,
                "max_execution_time_seconds": self.flags.max_execution_time_seconds,
                "max_error_rate_percentage": self.flags.max_error_rate_percentage,
            }

            with open(self.config_path, "w") as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Positioning config saved to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save positioning config: {e}")


# Global feature manager instance
_feature_manager = None


def get_feature_manager() -> PositioningFeatureManager:
    """Get global feature manager instance."""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = PositioningFeatureManager()
    return _feature_manager


# Convenience functions for common operations
def should_use_clean_positioning(template_id: str, correlation_id: Optional[str] = None) -> bool:
    """Convenience function to check if clean positioning should be used."""
    return get_feature_manager().should_use_clean_positioning(template_id, correlation_id)


def record_positioning_performance(
    mode: str, success: bool, execution_time: float, correlation_id: Optional[str] = None
):
    """Convenience function to record performance metrics."""
    get_feature_manager().record_performance(mode, success, execution_time, correlation_id)


def emergency_rollback(reason: str = "Manual rollback"):
    """Convenience function for emergency rollback."""
    get_feature_manager().emergency_rollback(reason)
