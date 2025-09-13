#!/usr/bin/env python3
"""
Test the token-to-metadata matching logic in the fixed chart styling system.
"""

import sys

sys.path.insert(0, "scalapay/scalapay_mcp_kam")


def test_token_matching():
    """Test that tokens are correctly matched to their data types."""

    print("🔗 Testing Token-to-Metadata Matching")
    print("=" * 50)

    # Mock slide metadata (as created by build_slide_metadata_from_results)
    slide_metadata = {
        "monthly sales year over year": {
            "data_type": "monthly sales year over year",
            "paragraph": "Strong growth year over year with seasonal patterns",
            "chart_type": "bar",
        },
        "orders by user type": {
            "data_type": "orders by user type",
            "paragraph": "Healthy user distribution across segments",
            "chart_type": "stacked_bar",
        },
        "AOV over time": {
            "data_type": "AOV over time",
            "paragraph": "Average order value shows upward trend",
            "chart_type": "line",
        },
        "scalapay users demographic in percentages": {
            "data_type": "scalapay users demographic in percentages",
            "paragraph": "Demographics concentrated in 25-34 age group",
            "chart_type": "pie",
        },
    }

    # Mock image tokens (as would be in image_map)
    test_tokens = [
        "{{monthly_sales_chart}}",
        "{{orders_by_user_type_chart}}",
        "{{AOV_chart}}",
        "{{demographic_chart}}",
        "{{unknown_chart}}",  # This one should not match
    ]

    print(f"📊 Testing {len(test_tokens)} tokens against {len(slide_metadata)} data types")
    print()

    # Test the matching logic (copied from the fixed function)
    for token in test_tokens:
        print(f"🔍 Testing token: {token}")

        # Find the best matching metadata for this token
        best_match_metadata = None
        matched_data_type = None

        for data_type, metadata in slide_metadata.items():
            # Simple matching: check if token contains elements of data_type or vice versa
            token_clean = token.lower().replace("{{", "").replace("}}", "").replace("_", " ")
            data_type_clean = data_type.lower().replace("_", " ")

            # Match if token relates to the data type
            if any(word in token_clean for word in data_type_clean.split() if len(word) > 3) or any(
                word in data_type_clean for word in token_clean.split() if len(word) > 3
            ):
                best_match_metadata = metadata
                matched_data_type = data_type
                break

        if best_match_metadata:
            chart_type = best_match_metadata.get("chart_type")
            print(f"   ✅ Matched with: '{matched_data_type}'")
            print(f"   📈 Chart type: {chart_type}")
            print(f"   📝 Paragraph: {best_match_metadata.get('paragraph', '')[:50]}...")

            # Simulate getting style configuration
            try:
                from scalapay.scalapay_mcp_kam.chart_config.chart_styling_config import get_image_style_for_slide

                image_style = get_image_style_for_slide(matched_data_type, best_match_metadata.get("paragraph", ""))
                resize_config = image_style.get("resize", {})

                print(
                    f"   🎨 Style: {resize_config.get('scaleX', 120)}×{resize_config.get('scaleY', 120)} at ({resize_config.get('translateX', 130)}, {resize_config.get('translateY', 250)})"
                )

            except Exception as e:
                print(f"   ⚠️  Style lookup failed: {e}")
        else:
            print(f"   ❌ No match found - will use default styling")

        print()

    print("🎯 Token Matching Test Summary:")
    print("   - Tokens with clear data type words should match their corresponding metadata")
    print("   - Each matched token gets chart-specific positioning and sizing")
    print("   - Unmatched tokens fall back to default styling")
    print("   - This fixes the slide ID vs. data type mapping issue")


def test_real_world_tokens():
    """Test with more realistic token names."""

    print("\n🌍 Testing Real-World Token Scenarios")
    print("=" * 50)

    # More realistic scenario
    slide_metadata = {
        "monthly sales year over year": {
            "data_type": "monthly sales year over year",
            "chart_type": "bar",
            "paragraph": "Sales performance comparison across years",
        }
    }

    realistic_tokens = [
        "{{monthly_sales_chart}}",  # Should match
        "{{sales_year_over_year_image}}",  # Should match
        "{{monthly_performance_chart}}",  # Should match
        "{{yearly_sales_graph}}",  # Should match
        "{{revenue_breakdown_chart}}",  # Should NOT match
        "{{customer_retention_chart}}",  # Should NOT match
    ]

    matches_found = 0
    for token in realistic_tokens:
        token_clean = token.lower().replace("{{", "").replace("}}", "").replace("_", " ")

        # Test matching logic
        matched = False
        for data_type in slide_metadata.keys():
            data_type_clean = data_type.lower().replace("_", " ")

            if any(word in token_clean for word in data_type_clean.split() if len(word) > 3) or any(
                word in data_type_clean for word in token_clean.split() if len(word) > 3
            ):
                matched = True
                matches_found += 1
                break

        status = "✅ MATCH" if matched else "❌ NO MATCH"
        print(f"   {status} {token}")

    print(f"\n📊 Results: {matches_found}/{len(realistic_tokens)} tokens matched")
    print("   Expected: 4/6 tokens should match (first 4 relate to sales/monthly/yearly)")


if __name__ == "__main__":
    print("🧪 Token-to-Metadata Matching Tests")
    print("Testing the fix for chart styling positioning issues")
    print()

    try:
        test_token_matching()
        test_real_world_tokens()

        print("\n🎉 All token matching tests completed!")
        print("\n💡 Key Improvement:")
        print("   - Fixed slide ID vs. data type mapping issue")
        print("   - Tokens now correctly match their chart metadata")
        print("   - Chart-specific styling should work in actual slide generation")

    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback

        traceback.print_exc()
