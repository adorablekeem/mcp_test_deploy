"""
Configuration settings for Scalapay MCP KAM system.
Includes feature flags and environment-based configuration.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class EnhancedParagraphConfig:
    """Configuration for LLM-processed paragraph feature."""

    enabled: bool = False
    llm_model: str = "gpt-4o"
    max_slide_paragraph_words: int = 80
    enable_speaker_notes: bool = True
    fallback_on_error: bool = True
    parallel_processing: bool = True
    max_processing_time_seconds: int = 30


class Config:
    """Main configuration class for the application."""

    def __init__(self):
        self.enhanced_paragraph_processing = EnhancedParagraphConfig(
            enabled=os.getenv("ENABLE_LLM_PARAGRAPHS", "false").lower() == "true",
            llm_model=os.getenv("PARAGRAPH_LLM_MODEL", "gpt-4o"),
            max_slide_paragraph_words=int(os.getenv("MAX_SLIDE_WORDS", "80")),
            enable_speaker_notes=os.getenv("ENABLE_SPEAKER_NOTES", "true").lower() == "true",
            fallback_on_error=os.getenv("FALLBACK_ON_LLM_ERROR", "true").lower() == "true",
            parallel_processing=os.getenv("PARALLEL_LLM_PROCESSING", "true").lower() == "true",
            max_processing_time_seconds=int(os.getenv("MAX_LLM_PROCESSING_TIME", "30")),
        )

        # General application settings
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.google_credentials_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", "./scalapay/scalapay_mcp_kam/credentials.json"
        )
        self.default_template_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
        self.default_folder_id = "1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "enhanced_paragraph_processing": {
                "enabled": self.enhanced_paragraph_processing.enabled,
                "llm_model": self.enhanced_paragraph_processing.llm_model,
                "max_slide_paragraph_words": self.enhanced_paragraph_processing.max_slide_paragraph_words,
                "enable_speaker_notes": self.enhanced_paragraph_processing.enable_speaker_notes,
                "fallback_on_error": self.enhanced_paragraph_processing.fallback_on_error,
                "parallel_processing": self.enhanced_paragraph_processing.parallel_processing,
                "max_processing_time_seconds": self.enhanced_paragraph_processing.max_processing_time_seconds,
            },
            "debug_mode": self.debug_mode,
            "google_credentials_path": self.google_credentials_path,
            "default_template_id": self.default_template_id,
            "default_folder_id": self.default_folder_id,
        }


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def reload_config() -> Config:
    """Reload configuration from environment variables."""
    global config
    config = Config()
    return config
