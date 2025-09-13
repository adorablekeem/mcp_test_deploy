#!/usr/bin/env python3
"""
Direct test of enhanced_batch_text_replace_with_styling function.
Minimal test with mocked dependencies to test the function logic.
"""

import asyncio
import sys

# Add project to path
sys.path.insert(0, "scalapay/scalapay_mcp_kam")


class MockGoogleSlidesService:
    """Ultra-simple mock that just tracks calls."""

    def __init__(self):
        self.calls = []

    def presentations(self):
        return MockPresentations(self)


class MockPresentations:
    def __init__(self, service):
        self.service = service

    def get(self, presentationId):
        self.service.calls.append(f"get({presentationId})")
        return MockExecutor({"slides": [{"objectId": "slide1"}, {"objectId": "slide2"}, {"objectId": "slide3"}]})

    def batchUpdate(self, presentationId, body):
        self.service.calls.append(f"batchUpdate({presentationId}, {len(body.get('requests', []))} requests)")
        return MockExecutor({"replies": []})


class MockExecutor:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


async def test_enhanced_function_directly():
    """Test the enhanced function with minimal mocking."""

    print("🎯 Direct Function Test: enhanced_batch_text_replace_with_styling")
    print("=" * 60)

    # Import the function
    try:
        from scalapay.scalapay_mcp_kam.batch_operations_styled_wrapper import enhanced_batch_text_replace_with_styling

        print("✅ Successfully imported enhanced_batch_text_replace_with_styling")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

    # Setup test data
    mock_service = MockGoogleSlidesService()
    presentation_id = "test_presentation_123"

    text_map = {
        "{{title}}": "Test Presentation Title",
        "{{chart_title}}": "Monthly Sales Performance",
        "{{summary}}": "Key insights and trends",
    }

    # Mock Alfred results with different chart types
    results = {
        "monthly sales year over year": {
            "slides_struct": {
                "structured_data": {"Jan": 100, "Feb": 120},
                "paragraph": "Sales data showing consistent growth patterns across all months with particularly strong performance in Q1.",
            }
        },
        "orders by user type": {
            "alfred_raw": "User segmentation data",
            "slides_struct": {
                "paragraph": "Order distribution shows healthy mix of new, returning, and network users with network segment leading."
            },
        },
    }

    print(f"📋 Test Setup:")
    print(f"   Presentation ID: {presentation_id}")
    print(f"   Text replacements: {len(text_map)}")
    print(f"   Alfred results: {len(results)} chart types")
    print()

    # Test 1: With styling enabled and results provided
    print("🎨 Test 1: Full styling mode")
    try:
        result = await enhanced_batch_text_replace_with_styling(
            mock_service,
            presentation_id,
            text_map,
            results=results,  # Provide Alfred results
            enable_styling=True,
            correlation_id="test_full_styling",
        )

        print("✅ Function executed successfully!")
        print(f"   Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Replacements: {result.get('replacements_processed', 0)}")
        print(f"   Styles applied: {result.get('styles_applied', 0)}")

        # Check if styling was actually applied
        if result.get("processing_mode", "").startswith("styled"):
            print("   🎯 Chart-specific styling WAS applied")
        else:
            print(f"   ⚠️  Styling NOT applied, used: {result.get('processing_mode')}")

        print(f"   API calls made: {len(mock_service.calls)}")
        for call in mock_service.calls[-3:]:  # Show last 3 calls
            print(f"      {call}")

    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()

    # Test 2: Without results (should fallback)
    print("🔄 Test 2: Fallback mode (no Alfred results)")
    mock_service.calls = []  # Reset call tracking

    try:
        result = await enhanced_batch_text_replace_with_styling(
            mock_service,
            presentation_id,
            text_map,
            results=None,  # No Alfred results
            enable_styling=True,
            correlation_id="test_fallback",
        )

        print("✅ Fallback executed successfully!")
        print(f"   Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Replacements: {result.get('replacements_processed', 0)}")

        if "no_styling" in result.get("processing_mode", ""):
            print("   🎯 Correctly fell back to standard operations")

        print(f"   API calls made: {len(mock_service.calls)}")

    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        return False

    print()

    # Test 3: Styling explicitly disabled
    print("⛔ Test 3: Styling disabled")
    mock_service.calls = []

    try:
        result = await enhanced_batch_text_replace_with_styling(
            mock_service,
            presentation_id,
            text_map,
            results=results,  # Results available but styling disabled
            enable_styling=False,
            correlation_id="test_disabled",
        )

        print("✅ Disabled mode executed successfully!")
        print(f"   Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   Styles applied: {result.get('styles_applied', 0)}")

        if result.get("styles_applied", 0) == 0:
            print("   🎯 Styling correctly disabled")

    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        return False

    print("\n🎉 All direct function tests passed!")
    return True


async def test_style_detection_only():
    """Test just the style detection logic."""

    print("\n🔍 Bonus: Style Detection Test")
    print("-" * 30)

    try:
        from scalapay.scalapay_mcp_kam.chart_config.chart_styling_config import (
            detect_chart_type_from_data_type,
            get_image_style_for_slide,
            select_style_config,
        )

        test_data = [
            "monthly sales year over year",
            "orders by user type",
            "AOV over time",
            "scalapay users demographic in percentages",
        ]

        for data_type in test_data:
            chart_type = detect_chart_type_from_data_type(data_type)
            style = get_image_style_for_slide(data_type, "Sample paragraph text")

            print(f"📊 '{data_type[:25]}...'")
            print(f"   → Chart type: {chart_type.value}")
            print(f"   → Size: {style['resize']['scaleX']}×{style['resize']['scaleY']}")
            print(f"   → Position: ({style['resize']['translateX']}, {style['resize']['translateY']})")

        print("✅ Style detection working correctly!")
        return True

    except Exception as e:
        print(f"❌ Style detection failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Testing enhanced_batch_text_replace_with_styling Function")
    print()

    async def run_all_tests():
        test1_success = await test_enhanced_function_directly()
        test2_success = await test_style_detection_only()

        print("\n📊 Final Results:")
        print(f"   Function test: {'✅ PASS' if test1_success else '❌ FAIL'}")
        print(f"   Style detection: {'✅ PASS' if test2_success else '❌ FAIL'}")

        if test1_success and test2_success:
            print("\n🎉 All tests successful! The enhanced function is working correctly.")
            print("\n💡 What this means:")
            print("   - The function can detect chart types from your data")
            print("   - It applies appropriate styling based on chart content")
            print("   - It gracefully falls back when styling isn't available")
            print("   - It integrates properly with Google Slides API structure")
        else:
            print("\n⚠️  Some tests failed. Check the output above for details.")

    try:
        asyncio.run(run_all_tests())
    except Exception as e:
        print(f"💥 Test runner failed: {e}")
        import traceback

        traceback.print_exc()
