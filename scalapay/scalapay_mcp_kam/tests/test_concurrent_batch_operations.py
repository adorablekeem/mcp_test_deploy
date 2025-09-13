"""
Test cases for concurrent batch operations (text and image replacement).
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from scalapay.scalapay_mcp_kam.batch_operations_concurrent import (
    concurrent_batch_replace_shapes_with_images_and_resize,
    concurrent_batch_replace_shapes_with_images_and_resize_with_fallback,
    concurrent_batch_text_replace,
    concurrent_batch_text_replace_with_fallback,
    process_single_slide_images_concurrent,
    process_single_slide_text_concurrent,
)
from scalapay.scalapay_mcp_kam.utils.concurrency_config import ConcurrencyConfig

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_slides_service():
    """Mock Google Slides API service."""
    service = Mock()

    # Mock presentation structure
    presentation_data = {"slides": [{"objectId": "slide1"}, {"objectId": "slide2"}, {"objectId": "slide3"}]}

    service.presentations().get().execute.return_value = presentation_data
    service.presentations().batchUpdate().execute.return_value = {"replies": []}

    return service


@pytest.fixture
def mock_text_map():
    """Mock text replacement map."""
    return {
        "{{title_1}}": "Monthly Sales Overview",
        "{{paragraph_1}}": "Sales increased by 15% this month...",
        "{{title_2}}": "Revenue Analysis",
        "{{paragraph_2}}": "Revenue metrics show positive trends...",
    }


@pytest.fixture
def mock_image_map():
    """Mock image replacement map."""
    return {
        "{{chart_1}}": "https://drive.google.com/uc?export=view&id=chart1",
        "{{chart_2}}": "https://drive.google.com/uc?export=view&id=chart2",
        "{{chart_3}}": "https://drive.google.com/uc?export=view&id=chart3",
    }


@pytest.fixture
def mock_concurrency_config():
    """Mock concurrency configuration."""
    return ConcurrencyConfig(enable_concurrent_batch_operations=True, max_concurrent_slides=2, slides_api_batch_size=3)


@pytest.mark.asyncio
async def test_concurrent_batch_text_replace_success(mock_slides_service, mock_text_map):
    """Test successful concurrent text replacement."""
    result = await concurrent_batch_text_replace(
        mock_slides_service, "test_presentation_id", mock_text_map, max_concurrent_slides=2, batch_size=2
    )

    assert result["success"] is True
    assert result["slides_processed"] == 3  # All 3 slides processed
    assert result["replacements_processed"] > 0
    assert "correlation_id" in result
    assert result["processing_time"] > 0


@pytest.mark.asyncio
async def test_concurrent_batch_text_replace_empty_map(mock_slides_service):
    """Test text replacement with empty text map."""
    result = await concurrent_batch_text_replace(
        mock_slides_service, "test_presentation_id", {}, max_concurrent_slides=2, batch_size=2
    )

    assert result["replacements_processed"] == 0
    assert result["slides_processed"] == 0
    assert result["api_calls"] == 0


@pytest.mark.asyncio
async def test_process_single_slide_text_concurrent(mock_slides_service, mock_text_map):
    """Test text processing for a single slide."""
    result = await process_single_slide_text_concurrent(
        mock_slides_service, "test_presentation_id", "slide1", mock_text_map, batch_size=2
    )

    assert result["success"] is True
    assert result["replacements_made"] >= 0
    assert result["api_calls"] >= 0
    assert "correlation_id" in result


@pytest.mark.asyncio
async def test_concurrent_batch_image_replace_success(mock_slides_service, mock_image_map):
    """Test successful concurrent image replacement."""
    with patch(
        "scalapay.scalapay_mcp_kam.batch_operations_concurrent.find_element_ids_for_tokens_sync",
        return_value={"{{chart_1}}": ["slide1:element1"], "{{chart_2}}": ["slide2:element2"]},
    ):
        result = await concurrent_batch_replace_shapes_with_images_and_resize(
            mock_slides_service, "test_presentation_id", mock_image_map, max_concurrent_slides=2, batch_size=2
        )

        assert result["success"] is True
        assert result["replacements_processed"] >= 0
        assert "correlation_id" in result
        assert result["processing_time"] > 0


@pytest.mark.asyncio
async def test_concurrent_batch_image_replace_with_resize(mock_slides_service, mock_image_map):
    """Test concurrent image replacement with resize transformations."""
    resize_params = {
        "mode": "ABSOLUTE",
        "scaleX": 120,
        "scaleY": 120,
        "unit": "PT",
        "translateX": 100,
        "translateY": 200,
    }

    with patch(
        "scalapay.scalapay_mcp_kam.batch_operations_concurrent.find_element_ids_for_tokens_sync",
        return_value={"{{chart_1}}": ["slide1:element1"]},
    ):
        result = await concurrent_batch_replace_shapes_with_images_and_resize(
            mock_slides_service, "test_presentation_id", mock_image_map, resize=resize_params, max_concurrent_slides=2
        )

        assert result["success"] is True
        assert result["transformations_applied"] >= 0
        assert "transformation_results" in result


@pytest.mark.asyncio
async def test_process_single_slide_images_concurrent(mock_slides_service, mock_image_map):
    """Test image processing for a single slide."""
    token_to_ids = {"{{chart_1}}": ["slide1:element1"], "{{chart_2}}": ["slide1:element2"]}

    result = await process_single_slide_images_concurrent(
        mock_slides_service, "test_presentation_id", "slide1", mock_image_map, token_to_ids, batch_size=2
    )

    assert result["success"] is True
    assert result["replacements_made"] >= 0
    assert result["api_calls"] >= 0
    assert "correlation_id" in result


@pytest.mark.asyncio
async def test_concurrent_text_replace_with_fallback_success(mock_slides_service, mock_text_map):
    """Test text replacement with fallback - concurrent succeeds."""
    with patch("scalapay.scalapay_mcp_kam.utils.concurrency_config.get_concurrency_config") as mock_config:
        mock_config.return_value.enable_concurrent_batch_operations = True

        result = await concurrent_batch_text_replace_with_fallback(
            mock_slides_service, "test_presentation_id", mock_text_map, enable_concurrent=True
        )

        assert result["success"] is True
        assert "fallback_used" not in result  # Should not fall back


@pytest.mark.asyncio
async def test_concurrent_text_replace_with_fallback_disabled(mock_slides_service, mock_text_map):
    """Test text replacement with fallback - concurrent disabled."""
    with patch("scalapay.scalapay_mcp_kam.utils.concurrency_config.get_concurrency_config") as mock_config:
        mock_config.return_value.enable_concurrent_batch_operations = False

        with patch("scalapay.scalapay_mcp_kam.tests.test_fill_template_sections.batch_text_replace") as mock_batch:
            result = await concurrent_batch_text_replace_with_fallback(
                mock_slides_service, "test_presentation_id", mock_text_map, enable_concurrent=False
            )

            assert result["success"] is True
            assert result["sequential_used"] is True
            mock_batch.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_image_replace_with_fallback_failure(mock_slides_service, mock_image_map):
    """Test image replacement with fallback - concurrent fails."""
    with patch("scalapay.scalapay_mcp_kam.utils.concurrency_config.get_concurrency_config") as mock_config:
        mock_config.return_value.enable_concurrent_batch_operations = True

        with patch(
            "scalapay.scalapay_mcp_kam.batch_operations_concurrent.concurrent_batch_replace_shapes_with_images_and_resize",
            side_effect=Exception("Concurrent processing failed"),
        ):
            with patch(
                "scalapay.scalapay_mcp_kam.tests.test_fill_template_sections.batch_replace_shapes_with_images_and_resize"
            ) as mock_batch:
                result = await concurrent_batch_replace_shapes_with_images_and_resize_with_fallback(
                    mock_slides_service, "test_presentation_id", mock_image_map, enable_concurrent=True
                )

                assert result["success"] is True
                assert result["fallback_used"] is True
                mock_batch.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_operations_error_isolation(mock_slides_service):
    """Test that errors in one slide don't affect other slides."""
    text_map = {"{{token}}": "replacement"}

    # Mock one slide to fail
    original_execute = mock_slides_service.presentations().batchUpdate().execute
    call_count = 0

    def failing_execute():
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First slide fails
            raise Exception("API error for slide 1")
        return {"replies": []}

    mock_slides_service.presentations().batchUpdate().execute = failing_execute

    result = await concurrent_batch_text_replace(
        mock_slides_service, "test_presentation_id", text_map, max_concurrent_slides=3, batch_size=1
    )

    # Should have some successful slides despite one failure
    assert result["slides_total"] == 3
    assert result["slides_processed"] >= 2  # At least 2 slides should succeed
    assert len(result["errors"]) >= 1  # Should have error from failed slide


def test_concurrency_config_integration():
    """Test integration with concurrency configuration."""
    config = ConcurrencyConfig()

    # Test new batch operation fields
    assert hasattr(config, "enable_concurrent_batch_operations")
    assert hasattr(config, "max_concurrent_slides")
    assert hasattr(config, "slides_api_batch_size")

    # Test default values
    assert config.enable_concurrent_batch_operations is True
    assert config.max_concurrent_slides == 3
    assert config.slides_api_batch_size == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
