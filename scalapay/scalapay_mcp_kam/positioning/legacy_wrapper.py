"""
Legacy function wrapper to avoid circular imports.
This module provides access to legacy functions without creating import cycles.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_legacy_positioning_function():
    """Get legacy positioning function dynamically."""
    try:
        from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_image_positioning_fix import (
            apply_chart_specific_positioning_correctly,
        )

        return apply_chart_specific_positioning_correctly
    except ImportError as e:
        logger.error(f"Failed to import legacy positioning function: {e}")
        return None


def get_legacy_template_function():
    """Get legacy template processing function dynamically."""
    try:
        # Import the function from a stable location
        from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import (
            batch_text_replace,
            copy_file,
            make_file_public,
            upload_png,
        )

        # Return a dictionary of utility functions
        return {
            "copy_file": copy_file,
            "upload_png": upload_png,
            "make_file_public": make_file_public,
            "batch_text_replace": batch_text_replace,
        }
    except ImportError as e:
        logger.error(f"Failed to import legacy template functions: {e}")
        return None


async def mock_legacy_fill_template(drive, slides, results, template_id, folder_id, verbose=False):
    """
    Mock legacy template processing for when we can't import the real one.
    This is a simplified version that avoids circular imports.
    """
    import time

    logger.warning("Using mock legacy template processing - this should not be used in production!")
    logger.info(f"Template ID: {template_id}, Folder ID: {folder_id}")

    # Try to use the actual template_id if provided, otherwise generate a realistic one
    presentation_id = (
        template_id
        if template_id and template_id != "mock_presentation_id"
        else f"fallback_presentation_{int(time.time())}"
    )

    # Mock response that matches expected format
    return {
        "presentation_id": presentation_id,
        "sections_rendered": len(results),
        "uploaded_images": [],
        "llm_processing_enabled": False,
        "speaker_notes_enabled": False,
        "notes_added": 0,
        "concurrent_processing_enabled": False,
        "processing_time": 1.0,
        "mock_mode": True,
        "warning": "Mock mode active - results may not reflect actual presentation operations",
    }
