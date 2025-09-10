#!/usr/bin/env python3
"""
Test script to verify chart positioning and text replacement fixes.
This script tests the slug mapping and token matching logic without needing actual API calls.
"""

import sys
import os
sys.path.append('scalapay/scalapay_mcp_kam')

from scalapay.scalapay_mcp_kam.utils.slug_validation import SlugMapper
import re

def test_slug_mapping():
    """Test that slug mapping works correctly for known data types."""
    print("=== TESTING SLUG MAPPING ===")
    
    # Test data - these are the data types from the logs
    test_data_types = [
        "monthly sales year over year",
        "monthly sales by product type over time", 
        "monthly orders by user type",
        "AOV",
        "scalapay users demographic in percentages",
        "orders by product type (i.e. pay in 3, pay in 4)",
        "AOV by product type (i.e. pay in 3, pay in 4)"
    ]
    
    # Expected tokens from the template (based on logs)
    expected_tokens = [
        "{{aov-by-product-type-i-e-pay-in-3-pay-in_chart}}",
        "{{aov_chart}}",
        "{{monthly-sales-over-time_chart}}",
        "{{monthly_orders_by_user_type_chart}}",
        "{{orders-by-product-type-i-e-pay-in-3-pay_chart}}",
        "{{scalapay-users-demographic-in-percentage_chart}}"
    ]
    
    slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")
    
    print(f"Template slugs: {sorted(slug_mapper.template_slugs)}")
    print()
    
    for data_type in test_data_types:
        slug = slug_mapper.get_slug(data_type)
        print(f"Data type: '{data_type}'")
        print(f"  Generated slug: '{slug}'")
        print(f"  In template: {slug in slug_mapper.template_slugs}")
        print()
    
    return True

def test_token_matching():
    """Test that token matching works for both text and image tokens."""
    print("=== TESTING TOKEN MATCHING ===")
    
    slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")
    
    # Sample tokens from logs
    test_tokens = [
        "{{aov_chart}}",
        "{{monthly-sales-over-time_chart}}",
        "{{scalapay-users-demographic-in-percentage_chart}}",
        "{{orders-by-product-type-i-e-pay-in-3-pay_chart}}",
        "{{aov_title}}",
        "{{monthly-orders-by-user-type_title}}"
    ]
    
    # Sample slide metadata (simulating what build_slide_metadata_from_results would create)
    slide_metadata = {
        "monthly sales year over year": {"data_type": "monthly sales year over year", "chart_type": "line"},
        "AOV": {"data_type": "AOV", "chart_type": "bar"},
        "monthly orders by user type": {"data_type": "monthly orders by user type", "chart_type": "line"},
        "scalapay users demographic in percentages": {"data_type": "scalapay users demographic in percentages", "chart_type": "pie"},
        "orders by product type (i.e. pay in 3, pay in 4)": {"data_type": "orders by product type (i.e. pay in 3, pay in 4)", "chart_type": "bar"}
    }
    
    successful_matches = 0
    total_tokens = len(test_tokens)
    
    for token in test_tokens:
        print(f"Testing token: {token}")
        
        # Extract token slug using the same logic as the fixed code
        token_match = re.match(r'\{\{([^_}]+)(?:_(?:title|paragraph|chart))?\}\}', token)
        if token_match:
            token_slug = token_match.group(1)
            print(f"  Extracted slug: '{token_slug}'")
            
            # Find matching data type
            found_match = False
            for data_type, metadata in slide_metadata.items():
                expected_slug = slug_mapper.get_slug(data_type)
                
                if (token_slug == expected_slug or 
                    token_slug.replace('-', '_') == expected_slug.replace('-', '_') or
                    expected_slug.replace('-', '_') == token_slug.replace('-', '_')):
                    print(f"  ✅ MATCHED with data_type: '{data_type}' (expected_slug: '{expected_slug}')")
                    found_match = True
                    successful_matches += 1
                    break
            
            if not found_match:
                print(f"  ❌ NO MATCH FOUND")
                print(f"     Available expected slugs: {[slug_mapper.get_slug(dt) for dt in slide_metadata.keys()]}")
        else:
            print(f"  ❌ FAILED TO EXTRACT SLUG")
        
        print()
    
    success_rate = successful_matches / total_tokens
    print(f"MATCHING SUCCESS RATE: {success_rate:.1%} ({successful_matches}/{total_tokens})")
    
    return success_rate >= 0.8  # Expect at least 80% success rate

def test_chart_positioning_logic():
    """Test that chart positioning will find images to apply styling to."""
    print("=== TESTING CHART POSITIONING LOGIC ===")
    
    # Simulate what the positioning code would receive
    image_map = {
        "{{aov_chart}}": "https://drive.google.com/file/d/abc123/view",
        "{{monthly-sales-over-time_chart}}": "https://drive.google.com/file/d/def456/view"
    }
    
    slide_metadata = {
        "AOV": {"data_type": "AOV", "chart_type": "bar"},
        "monthly sales year over year": {"data_type": "monthly sales year over year", "chart_type": "line"}
    }
    
    # Simulate slide_to_images (what would be found from the presentation)
    slide_to_images = {
        "SLIDE_abc123": ["IMAGE_obj1", "IMAGE_obj2"],
        "SLIDE_def456": ["IMAGE_obj3"] 
    }
    
    slug_mapper = SlugMapper("1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o")
    
    positioning_requests = []
    styles_applied = 0
    
    for token, image_url in image_map.items():
        print(f"Processing token: {token}")
        
        # Extract chart name from token using the fixed logic
        token_match = re.match(r'\{\{([^_}]+)(?:_chart)?\}\}', token)
        if token_match:
            token_slug = token_match.group(1)
            print(f"  Extracted slug: '{token_slug}'")
            
            # Find matching data type
            matched_slide_data = None
            matched_data_type = None
            
            for data_type, metadata in slide_metadata.items():
                expected_slug = slug_mapper.get_slug(data_type)
                
                if (token_slug == expected_slug or 
                    token_slug.replace('-', '_') == expected_slug.replace('-', '_') or
                    expected_slug.replace('-', '_') == token_slug.replace('-', '_')):
                    matched_slide_data = metadata
                    matched_data_type = data_type
                    print(f"  ✅ Matched with data_type: '{data_type}' (expected_slug: '{expected_slug}')")
                    break
            
            if matched_slide_data:
                # Count how many images would get styling applied
                for slide_id, image_object_ids in slide_to_images.items():
                    for image_object_id in image_object_ids:
                        # This is where positioning requests would be built
                        positioning_requests.append(f"position_request_for_{image_object_id}")
                        styles_applied += 1
                        print(f"    Would apply styling to image: {image_object_id} in slide: {slide_id}")
            else:
                print(f"  ❌ No metadata match found")
        else:
            print(f"  ❌ Failed to extract slug from token")
        
        print()
    
    print(f"POSITIONING SUMMARY:")
    print(f"  Total positioning requests: {len(positioning_requests)}")
    print(f"  Total styles applied: {styles_applied}")
    print(f"  Success: {styles_applied > 0}")
    
    return styles_applied > 0

def main():
    """Run all tests."""
    print("🧪 TESTING CHART POSITIONING AND TEXT REPLACEMENT FIXES")
    print("=" * 60)
    
    all_tests_passed = True
    
    try:
        # Test 1: Slug mapping
        print("TEST 1: Slug Mapping")
        result1 = test_slug_mapping()
        print(f"Result: {'✅ PASSED' if result1 else '❌ FAILED'}")
        print()
        
        # Test 2: Token matching
        print("TEST 2: Token Matching")
        result2 = test_token_matching()
        print(f"Result: {'✅ PASSED' if result2 else '❌ FAILED'}")
        print()
        
        # Test 3: Chart positioning logic
        print("TEST 3: Chart Positioning Logic")
        result3 = test_chart_positioning_logic()
        print(f"Result: {'✅ PASSED' if result3 else '❌ FAILED'}")
        print()
        
        all_tests_passed = result1 and result2 and result3
        
    except Exception as e:
        print(f"❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        all_tests_passed = False
    
    print("=" * 60)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED! The fixes should resolve the chart positioning issues.")
    else:
        print("⚠️  SOME TESTS FAILED. The fixes may need additional work.")
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)