"""
Test cases for concurrent template processing functionality.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, patch, AsyncMock
from scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent import (
    upload_single_image_concurrent,
    process_speaker_notes_concurrent,
    run_validation_concurrent,
    fill_template_for_all_sections_new_enhanced_with_fallback
)
from scalapay.scalapay_mcp_kam.utils.concurrency_config import ConcurrencyConfig

logger = logging.getLogger(__name__)

@pytest.fixture
def mock_section():
    """Mock section data for testing."""
    return {
        "title": "Test Chart",
        "slug": "test-chart",
        "chart_path": "/tmp/test_chart.png",
        "slide_paragraph": "Test slide content",
        "key_insights": ["Insight 1", "Insight 2"]
    }

@pytest.fixture
def mock_concurrency_config():
    """Mock concurrency configuration."""
    return ConcurrencyConfig(
        enable_concurrent_slides_processing=True,
        max_concurrent_slides_processing=2,
        slides_batch_size=1,
        retry_attempts=1,
        retry_delay=0.1
    )

@pytest.mark.asyncio
async def test_upload_single_image_concurrent_success(mock_section):
    """Test successful concurrent image upload."""
    mock_drive = Mock()
    
    with patch('scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent.upload_png', return_value="test_file_id"), \
         patch('scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent.make_file_public'):
        
        result = await upload_single_image_concurrent(
            mock_drive, mock_section, "test_folder"
        )
        
        assert result["success"] is True
        assert result["file_id"] == "test_file_id"
        assert result["slug"] == "test-chart"
        assert "image_url" in result

@pytest.mark.asyncio
async def test_upload_single_image_concurrent_failure(mock_section):
    """Test error handling in concurrent image upload."""
    mock_drive = Mock()
    
    with patch('scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent.upload_png', side_effect=Exception("Upload failed")):
        
        result = await upload_single_image_concurrent(
            mock_drive, mock_section, "test_folder"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Upload failed" in result["error"]

@pytest.mark.asyncio
async def test_process_speaker_notes_concurrent():
    """Test concurrent speaker notes processing."""
    mock_slides_service = Mock()
    sections = [{"title": "Test 1"}, {"title": "Test 2"}]
    
    with patch('scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent.add_speaker_notes_to_slides', 
               new_callable=AsyncMock, return_value={"notes_added": 2}):
        
        result = await process_speaker_notes_concurrent(
            mock_slides_service, "test_presentation_id", sections,
            batch_size=1, max_concurrent=2
        )
        
        assert result["notes_added"] >= 0
        assert "errors" in result
        assert "batches_processed" in result

@pytest.mark.asyncio
async def test_run_validation_concurrent():
    """Test concurrent validation processing."""
    mock_results = {"test": "data"}
    uploaded_files = ["file1", "file2"]
    
    with patch('scalapay.scalapay_mcp_kam.utils.slug_validation.debug_slug_mapping', 
               return_value={"success_rate": 0.8}), \
         patch('scalapay.scalapay_mcp_kam.utils.slug_validation.verify_chart_imports',
               return_value={"success_rate": 0.9}):
        
        result = await run_validation_concurrent(
            mock_results, "template_id", "presentation_id", uploaded_files
        )
        
        assert "validation_report" in result
        assert "chart_verification" in result
        assert result["validation_report"]["success_rate"] == 0.8
        assert result["chart_verification"]["success_rate"] == 0.9

@pytest.mark.asyncio
async def test_fallback_to_sequential_processing(mock_concurrency_config):
    """Test fallback to sequential processing when concurrent fails."""
    mock_drive = Mock()
    mock_slides = Mock()
    mock_results = {"test": "data"}
    mock_llm_processor = Mock()
    
    with patch('scalapay.scalapay_mcp_kam.tools_agent_kam_concurrent.fill_template_for_all_sections_new_enhanced_concurrent',
               side_effect=Exception("Concurrent processing failed")), \
         patch('scalapay.scalapay_mcp_kam.tools_agent_kam_local.fill_template_for_all_sections_new_enhanced',
               new_callable=AsyncMock, return_value={"presentation_id": "test_id", "concurrent_processing_enabled": False}):
        
        result = await fill_template_for_all_sections_new_enhanced_with_fallback(
            mock_drive, mock_slides, mock_results,
            template_id="template_id",
            folder_id="folder_id", 
            llm_processor=mock_llm_processor,
            enable_concurrent_processing=True
        )
        
        assert result["presentation_id"] == "test_id"
        assert result.get("concurrent_processing_enabled", False) is False

def test_concurrency_config_integration():
    """Test integration with concurrency configuration."""
    config = ConcurrencyConfig()
    
    # Test default values
    assert config.enable_concurrent_slides_processing is True
    assert config.max_concurrent_slides_processing == 3
    assert config.slides_batch_size == 2
    
    # Test environment variable parsing would go here
    # (requires setting environment variables in test setup)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])