#!/usr/bin/env python3
"""
Comprehensive test suite for fixed chart sizing implementation.
Tests configuration loading, chart type detection, sizing calculations, and error handling.
"""

import os
import sys

sys.path.append("scalapay/scalapay_mcp_kam")

from typing import Any, Dict, Optional

import pytest
from scalapay.scalapay_mcp_kam.chart_config.chart_styling_config import (
    CHART_STYLE_CONFIGS,
    ChartType,
    detect_chart_type_from_data_type,
    get_image_style_for_slide,
    select_style_config,
)
from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_image_positioning_fix import (
    build_width_height_sizing_request,
    match_image_to_chart_config,
)
from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_with_styling import (
    build_slide_metadata_from_results,
    get_default_chart_config,
)


class TestConfigurationLoading:
    """Test that all chart configurations load without errors."""

    def test_configuration_imports(self):
        """Test that CHART_STYLE_CONFIGS imports successfully."""
        assert CHART_STYLE_CONFIGS is not None
        assert len(CHART_STYLE_CONFIGS) > 0

        # Verify all expected chart types are present
        expected_types = [ChartType.BAR, ChartType.STACKED_BAR, ChartType.LINE, ChartType.PIE]
        for chart_type in expected_types:
            assert chart_type in CHART_STYLE_CONFIGS
            assert "default" in CHART_STYLE_CONFIGS[chart_type]

    def test_configuration_structure(self):
        """Test that all configurations have required structure."""
        for chart_type, configs in CHART_STYLE_CONFIGS.items():
            for config_name, slide_config in configs.items():
                assert slide_config.image_style is not None

                # Check that image style has required attributes
                image_style = slide_config.image_style
                assert hasattr(image_style, "width")
                assert hasattr(image_style, "height")
                assert hasattr(image_style, "translate_x")
                assert hasattr(image_style, "translate_y")
                assert hasattr(image_style, "replace_method")

    def test_no_invalid_parameters(self):
        """Test that no configurations use invalid parameters."""
        for chart_type, configs in CHART_STYLE_CONFIGS.items():
            for config_name, slide_config in configs.items():
                image_style = slide_config.image_style

                # These parameters should not exist (they were causing errors)
                assert not hasattr(image_style, "scale_x")
                assert not hasattr(image_style, "scale_y")
                assert not hasattr(image_style, "scaleX")
                assert not hasattr(image_style, "scaleY")


class TestChartTypeDetection:
    """Test that data types map to correct chart types."""

    def test_chart_type_detection(self):
        """Test chart type detection from data type strings."""
        test_cases = [
            ("AOV", ChartType.LINE),
            ("average order value", ChartType.LINE),
            ("monthly sales year over year", ChartType.BAR),
            ("user type analysis", ChartType.STACKED_BAR),
            ("product type breakdown", ChartType.STACKED_BAR),
            ("scalapay users demographic in percentages", ChartType.PIE),
            ("percentage breakdown", ChartType.PIE),
            ("unknown data type", ChartType.BAR),  # Default fallback
        ]

        for data_type, expected_type in test_cases:
            detected_type = detect_chart_type_from_data_type(data_type)
            assert (
                detected_type == expected_type
            ), f"Failed for '{data_type}': expected {expected_type}, got {detected_type}"


class TestSizingCalculations:
    """Test width/height calculations for each chart type."""

    def test_chart_type_specific_sizing(self):
        """Test that each chart type gets different, appropriate sizing."""
        test_cases = [
            ("AOV", ChartType.LINE, 640, 300),  # Wide for trends
            ("monthly sales", ChartType.BAR, 580, 320),  # Wide for labels
            ("demographics", ChartType.PIE, 400, 400),  # Square for pie
            ("user analysis", ChartType.STACKED_BAR, 580, 380),  # Taller for stacking
        ]

        for data_type, chart_type, expected_width, expected_height in test_cases:
            style_config = get_image_style_for_slide(data_type, "", chart_type)
            resize_config = style_config.get("resize", {})

            width = resize_config.get("width")
            height = resize_config.get("height")

            assert width is not None, f"No width found for {data_type}"
            assert height is not None, f"No height found for {data_type}"
            assert width == expected_width, f"Wrong width for {data_type}: expected {expected_width}, got {width}"
            assert height == expected_height, f"Wrong height for {data_type}: expected {expected_height}, got {height}"

    def test_sizing_request_generation(self):
        """Test that sizing requests are generated correctly."""
        test_image_id = "test_image_123"
        target_width = 600
        target_height = 400
        data_type = "test_chart"

        request = build_width_height_sizing_request(test_image_id, target_width, target_height, data_type)

        # Verify request structure
        assert "updatePageElementSize" in request
        update_request = request["updatePageElementSize"]

        assert update_request["objectId"] == test_image_id
        assert "size" in update_request

        size = update_request["size"]
        assert size["width"]["magnitude"] == target_width
        assert size["width"]["unit"] == "PT"
        assert size["height"]["magnitude"] == target_height
        assert size["height"]["unit"] == "PT"


class TestTokenMatching:
    """Test that image tokens match correct configurations."""

    def test_token_matching_logic(self):
        """Test token-to-chart matching."""
        # Mock slide metadata
        slide_metadata = {
            "AOV": {"data_type": "AOV", "chart_type": "line", "paragraph": ""},
            "monthly sales year over year": {
                "data_type": "monthly sales year over year",
                "chart_type": "bar",
                "paragraph": "",
            },
            "scalapay users demographic in percentages": {
                "data_type": "scalapay users demographic in percentages",
                "chart_type": "pie",
                "paragraph": "",
            },
        }

        test_cases = [
            ("{{aov_chart}}", "AOV"),
            ("{{monthly-sales-over-time_chart}}", "monthly sales year over year"),  # Uses actual slug mapping
            ("{{scalapay-users-demographic-in-percentage_chart}}", "scalapay users demographic in percentages"),
        ]

        for token, expected_data_type in test_cases:
            match_result = match_image_to_chart_config(token, slide_metadata)

            assert match_result is not None, f"No match found for token: {token}"
            assert (
                match_result["data_type"] == expected_data_type
            ), f"Wrong match for {token}: expected {expected_data_type}, got {match_result['data_type']}"

    def test_token_matching_no_match(self):
        """Test handling of tokens that don't match any configuration."""
        slide_metadata = {"known_type": {"data_type": "known_type", "chart_type": "bar"}}

        # Token that won't match anything
        match_result = match_image_to_chart_config("{{unknown_chart}}", slide_metadata)
        assert match_result is None


class TestErrorHandling:
    """Test fallbacks when configuration fails."""

    def test_default_config_generation(self):
        """Test that default configuration is valid."""
        default_config = get_default_chart_config()

        required_keys = ["width", "height", "translateX", "translateY", "mode", "unit"]
        for key in required_keys:
            assert key in default_config, f"Missing required key: {key}"

        # Verify reasonable values
        assert 200 <= default_config["width"] <= 800
        assert 200 <= default_config["height"] <= 600
        assert default_config["mode"] == "ABSOLUTE"
        assert default_config["unit"] == "PT"

    def test_slide_metadata_building(self):
        """Test building slide metadata from Alfred results."""
        # Mock Alfred results
        mock_results = {
            "AOV": {"slides_struct": {"paragraph": "Test paragraph"}, "data": [1, 2, 3]},
            "monthly sales": {"alfred_raw": '{"paragraph": "Sales data"}', "data": [4, 5, 6]},
        }

        metadata = build_slide_metadata_from_results(mock_results)

        assert "AOV" in metadata
        assert "monthly sales" in metadata

        # Check structure
        aov_meta = metadata["AOV"]
        assert aov_meta["data_type"] == "AOV"
        assert aov_meta["paragraph"] == "Test paragraph"
        assert aov_meta["chart_type"] == "line"  # Should auto-detect


class TestIntegration:
    """Integration tests for complete sizing workflow."""

    def test_end_to_end_sizing(self):
        """Test complete flow from data type to sizing request."""
        # Simulate complete workflow
        data_type = "monthly sales year over year"
        paragraph = "Sales trends over time"

        # Step 1: Detect chart type
        chart_type = detect_chart_type_from_data_type(data_type)
        assert chart_type == ChartType.BAR

        # Step 2: Get style configuration
        style_config = get_image_style_for_slide(data_type, paragraph, chart_type)
        assert style_config is not None
        assert "resize" in style_config

        # Step 3: Extract sizing info
        resize_config = style_config["resize"]
        width = resize_config.get("width")
        height = resize_config.get("height")

        assert width is not None
        assert height is not None

        # Step 4: Build sizing request
        request = build_width_height_sizing_request("test_image", width, height, data_type)
        assert "updatePageElementSize" in request

        # Step 5: Verify final values
        size = request["updatePageElementSize"]["size"]
        assert size["width"]["magnitude"] == width
        assert size["height"]["magnitude"] == height

    def test_different_chart_types_different_sizes(self):
        """Test that different chart types get different sizes."""
        chart_configs = {}

        # Get configurations for different chart types
        test_data_types = [("AOV", ChartType.LINE), ("monthly sales", ChartType.BAR), ("demographics", ChartType.PIE)]

        for data_type, chart_type in test_data_types:
            config = get_image_style_for_slide(data_type, "", chart_type)
            resize_config = config.get("resize", {})
            chart_configs[chart_type] = (resize_config.get("width"), resize_config.get("height"))

        # Verify all configurations are different
        configs_list = list(chart_configs.values())
        assert len(set(configs_list)) == len(configs_list), "Chart types should have different sizes"


def run_all_tests():
    """Run all tests and report results."""
    print("🧪 RUNNING CHART SIZING TESTS")
    print("=" * 50)

    test_classes = [
        TestConfigurationLoading,
        TestChartTypeDetection,
        TestSizingCalculations,
        TestTokenMatching,
        TestErrorHandling,
        TestIntegration,
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        class_name = test_class.__name__
        print(f"\n📋 {class_name}")

        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith("test_")]

        for test_method in test_methods:
            total_tests += 1
            try:
                getattr(test_instance, test_method)()
                print(f"  ✅ {test_method}")
                passed_tests += 1
            except Exception as e:
                print(f"  ❌ {test_method}: {e}")
                failed_tests.append(f"{class_name}.{test_method}: {e}")

    print("\n" + "=" * 50)
    print(f"📊 TEST RESULTS:")
    print(f"   Total tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {len(failed_tests)}")
    print(f"   Success rate: {passed_tests/total_tests:.1%}")

    if failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for failure in failed_tests:
            print(f"   {failure}")

    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! Chart sizing system is working correctly.")
        return True
    else:
        print(f"\n⚠️  {len(failed_tests)} tests failed. Review implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
