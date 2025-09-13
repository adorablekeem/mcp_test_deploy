"""
Configuration settings for concurrent processing optimization.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrent processing features."""

    # Data retrieval concurrency settings
    enable_concurrent_data_retrieval: bool = True
    max_concurrent_batches: int = 2
    batch_size: int = 3
    data_retrieval_max_steps: int = 15

    # Chart generation concurrency settings
    enable_concurrent_chart_generation: bool = True
    max_concurrent_charts: int = 4
    chart_generation_max_steps: int = 15

    # Slides processing concurrency settings (conservative defaults to prevent API overload)
    enable_concurrent_slides_processing: bool = True
    max_concurrent_slides_processing: int = 2  # Reduced from 3 to prevent timeouts
    slides_batch_size: int = 1  # Reduced from 2 to be more conservative

    # Batch operations concurrency settings (NEW - slide-level parallelism)
    enable_concurrent_batch_operations: bool = True
    max_concurrent_slides: int = 3  # Max slides processed simultaneously
    slides_api_batch_size: int = 5  # Operations per API call

    # Context optimization settings
    use_simplified_schemas: bool = True
    verbose_logging: bool = False

    # Retry and reliability settings
    retry_attempts: int = 2
    retry_delay: float = 1.0

    # Fallback settings
    enable_fallback_to_sequential: bool = True

    @classmethod
    def from_env(cls) -> "ConcurrencyConfig":
        """Create configuration from environment variables."""
        return cls(
            enable_concurrent_data_retrieval=_parse_bool_env("SCALAPAY_ENABLE_CONCURRENT_DATA_RETRIEVAL", True),
            max_concurrent_batches=int(os.getenv("SCALAPAY_MAX_CONCURRENT_BATCHES", "2")),
            batch_size=int(os.getenv("SCALAPAY_BATCH_SIZE", "3")),
            data_retrieval_max_steps=int(os.getenv("SCALAPAY_DATA_RETRIEVAL_MAX_STEPS", "15")),
            enable_concurrent_chart_generation=_parse_bool_env("SCALAPAY_ENABLE_CONCURRENT_CHART_GENERATION", True),
            max_concurrent_charts=int(os.getenv("SCALAPAY_MAX_CONCURRENT_CHARTS", "4")),
            chart_generation_max_steps=int(os.getenv("SCALAPAY_CHART_GENERATION_MAX_STEPS", "15")),
            enable_concurrent_slides_processing=_parse_bool_env("SCALAPAY_ENABLE_CONCURRENT_SLIDES_PROCESSING", True),
            max_concurrent_slides_processing=int(os.getenv("SCALAPAY_MAX_CONCURRENT_SLIDES_PROCESSING", "2")),
            slides_batch_size=int(os.getenv("SCALAPAY_SLIDES_BATCH_SIZE", "1")),
            enable_concurrent_batch_operations=_parse_bool_env("SCALAPAY_ENABLE_CONCURRENT_BATCH_OPERATIONS", True),
            max_concurrent_slides=int(os.getenv("SCALAPAY_MAX_CONCURRENT_SLIDES", "3")),
            slides_api_batch_size=int(os.getenv("SCALAPAY_SLIDES_API_BATCH_SIZE", "5")),
            use_simplified_schemas=_parse_bool_env("SCALAPAY_USE_SIMPLIFIED_SCHEMAS", True),
            verbose_logging=_parse_bool_env("SCALAPAY_VERBOSE_LOGGING", False),
            retry_attempts=int(os.getenv("SCALAPAY_RETRY_ATTEMPTS", "2")),
            retry_delay=float(os.getenv("SCALAPAY_RETRY_DELAY_SECONDS", "1.0")),
            enable_fallback_to_sequential=_parse_bool_env("SCALAPAY_ENABLE_FALLBACK_TO_SEQUENTIAL", True),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "enable_concurrent_data_retrieval": self.enable_concurrent_data_retrieval,
            "max_concurrent_batches": self.max_concurrent_batches,
            "batch_size": self.batch_size,
            "data_retrieval_max_steps": self.data_retrieval_max_steps,
            "enable_concurrent_chart_generation": self.enable_concurrent_chart_generation,
            "max_concurrent_charts": self.max_concurrent_charts,
            "chart_generation_max_steps": self.chart_generation_max_steps,
            "enable_concurrent_slides_processing": self.enable_concurrent_slides_processing,
            "max_concurrent_slides_processing": self.max_concurrent_slides_processing,
            "slides_batch_size": self.slides_batch_size,
            "enable_concurrent_batch_operations": self.enable_concurrent_batch_operations,
            "max_concurrent_slides": self.max_concurrent_slides,
            "slides_api_batch_size": self.slides_api_batch_size,
            "use_simplified_schemas": self.use_simplified_schemas,
            "verbose_logging": self.verbose_logging,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "enable_fallback_to_sequential": self.enable_fallback_to_sequential,
        }


def _parse_bool_env(env_var: str, default: bool) -> bool:
    """Parse boolean environment variable with default fallback."""
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on", "enabled")


def get_concurrency_config() -> ConcurrencyConfig:
    """Get the current concurrency configuration."""
    return ConcurrencyConfig.from_env()
