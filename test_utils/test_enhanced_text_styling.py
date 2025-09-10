#!/usr/bin/env python3
"""
Standalone test script for enhanced_batch_text_replace_with_styling.
Test the styling system without running the full slide generation flow.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any

# Add the project to Python path
sys.path.insert(0, 'scalapay/scalapay_mcp_kam')

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Mock Google Slides service for testing
class MockSlidesService:
    """Mock Google Slides service for testing without actual API calls."""
    
    def __init__(self):
        self.call_count = 0
        self.requests_received = []
        
    def presentations(self):
        return self
        
    def get(self, presentationId):
        return self
        
    def batchUpdate(self, presentationId, body):
        return self
        
    def execute(self):
        self.call_count += 1
        
        # Mock presentation structure
        if 'get' in str(self):
            return {
                "slides": [
                    {"objectId": "slide_1"},
                    {"objectId": "slide_2"},  
                    {"objectId": "slide_3"}
                ]
            }
        
        # Mock batch update response
        self.requests_received.append({
            "call": self.call_count,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {"replies": [{"createSlide": {"objectId": f"response_{self.call_count}"}}]}


def create_mock_alfred_results() -> Dict[str, Any]:
    """Create mock Alfred results for testing styling."""
    return {
        "monthly sales year over year": {
            "alfred_raw": "Sales data showing strong growth year over year",
            "slides_struct": {
                "structured_data": {
                    "Jan": {"2023": 100, "2024": 150},
                    "Feb": {"2023": 120, "2024": 180}
                },
                "paragraph": "Monthly sales show consistent growth year over year with particularly strong performance in Q1. The data indicates seasonal patterns with peak performance during January and February."
            }
        },
        "orders by user type": {
            "alfred_raw": "User segmentation analysis",
            "slides_struct": {
                "structured_data": {
                    "Jan": {"New": 50, "Returning": 30, "Network": 20},
                    "Feb": {"New": 60, "Returning": 40, "Network": 25}
                },
                "paragraph": "Orders by user type show healthy distribution across customer segments. Network users represent the largest segment, indicating strong cross-merchant loyalty."
            }
        },
        "AOV over time": {
            "alfred_raw": "Average order value trends",
            "slides_struct": {
                "structured_data": {
                    "Jan": 95.5, "Feb": 102.3, "Mar": 98.7, "Apr": 105.2
                },
                "paragraph": "Average order value demonstrates upward trend over time with seasonal fluctuations. Q2 shows particularly strong performance with values exceeding $100."
            }
        },
        "scalapay users demographic in percentages": {
            "alfred_raw": "Demographic breakdown data",
            "slides_struct": {
                "structured_data": {
                    "Age Groups": {"18-24": 25, "25-34": 35, "35-44": 25, "45+": 15},
                    "Gender": {"Male": 30, "Female": 70}
                },
                "paragraph": "User demographics show strong concentration in the 25-34 age group with predominantly female users. This aligns with the fashion and lifestyle focus of many Scalapay merchants."
            }
        }
    }


def create_test_text_map() -> Dict[str, str]:
    """Create test text replacement map."""
    return {
        "{{monthly_sales_title}}": "Monthly Sales Performance Year-over-Year",
        "{{user_type_title}}": "Order Distribution by User Type",
        "{{aov_title}}": "Average Order Value Trends",
        "{{demographics_title}}": "Scalapay User Demographics",
        "{{company_name}}": "Scalapay Analytics Report",
        "{{date_range}}": "January 2023 - April 2024",
        "{{summary_text}}": "Key insights and performance metrics"
    }


async def test_enhanced_text_styling():
    """Test the enhanced text styling functionality."""
    
    print("🧪 Testing Enhanced Text Styling System")
    print("=" * 50)
    
    # Create test data
    mock_service = MockSlidesService()
    presentation_id = "test_presentation_12345"
    text_map = create_test_text_map()
    alfred_results = create_mock_alfred_results()
    
    print(f"📝 Test Setup:")
    print(f"   - Presentation ID: {presentation_id}")
    print(f"   - Text replacements: {len(text_map)} tokens")
    print(f"   - Alfred results: {len(alfred_results)} chart types")
    print(f"   - Mock slides: 3 slides")
    
    # Test 1: With styling enabled (default)
    print(f"\n🎨 Test 1: Enhanced styling ENABLED")
    try:
        from scalapay.scalapay_mcp_kam.batch_operations_styled_wrapper import enhanced_batch_text_replace_with_styling
        
        result = await enhanced_batch_text_replace_with_styling(
            mock_service, 
            presentation_id, 
            text_map,
            results=alfred_results,
            enable_styling=True,
            correlation_id="test_styling_enabled"
        )
        
        print(f"   ✅ SUCCESS!")
        print(f"   - Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   - Replacements processed: {result.get('replacements_processed', 0)}")
        print(f"   - Slides processed: {result.get('slides_processed', 0)}")
        print(f"   - Styles applied: {result.get('styles_applied', 0)}")
        print(f"   - API calls: {result.get('api_calls', 0)}")
        print(f"   - Processing time: {result.get('processing_time', 0):.2f}s")
        
        # Check if styling was actually applied
        if result.get('processing_mode', '').startswith('styled'):
            print(f"   🎯 Chart-specific styling was APPLIED")
        else:
            print(f"   ⚠️  Styling was NOT applied - fell back to: {result.get('processing_mode')}")
            
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: With styling disabled
    print(f"\n📝 Test 2: Enhanced styling DISABLED")
    try:
        result = await enhanced_batch_text_replace_with_styling(
            mock_service,
            presentation_id, 
            text_map,
            results=alfred_results,
            enable_styling=False,  # Explicitly disable styling
            correlation_id="test_styling_disabled"
        )
        
        print(f"   ✅ SUCCESS!")
        print(f"   - Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   - Styles applied: {result.get('styles_applied', 0)}")
        
        if result.get('styles_applied', 0) == 0:
            print(f"   🎯 Styling correctly DISABLED")
        else:
            print(f"   ⚠️  Unexpected: {result.get('styles_applied')} styles applied")
            
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
    
    # Test 3: Without Alfred results (should fallback)
    print(f"\n🔄 Test 3: Without Alfred results (fallback test)")
    try:
        result = await enhanced_batch_text_replace_with_styling(
            mock_service,
            presentation_id,
            text_map,
            results=None,  # No results provided
            enable_styling=True,
            correlation_id="test_no_results"
        )
        
        print(f"   ✅ SUCCESS!")
        print(f"   - Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   - Styles applied: {result.get('styles_applied', 0)}")
        
        if 'no_styling' in result.get('processing_mode', '') or result.get('styles_applied', 0) == 0:
            print(f"   🎯 Correctly fell back to standard operations")
        
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
    
    # Test 4: Chart type detection
    print(f"\n🔍 Test 4: Chart type detection")
    try:
        from scalapay.scalapay_mcp_kam.config.chart_styling_config import (
            detect_chart_type_from_data_type, select_style_config
        )
        
        test_cases = [
            "monthly sales year over year",
            "orders by user type", 
            "AOV over time",
            "scalapay users demographic in percentages"
        ]
        
        for data_type in test_cases:
            chart_type = detect_chart_type_from_data_type(data_type)
            style_config = select_style_config(data_type, alfred_results.get(data_type, {}).get('slides_struct', {}).get('paragraph', ''))
            
            print(f"   '{data_type[:30]}...' → {chart_type.value}")
            print(f"     Image style: {style_config.image_style.scale_x}x{style_config.image_style.scale_y} at ({style_config.image_style.translate_x}, {style_config.image_style.translate_y})")
        
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
    
    # Test 5: Mock service verification
    print(f"\n📊 Mock Service Statistics:")
    print(f"   - Total API calls made: {mock_service.call_count}")
    print(f"   - Requests received: {len(mock_service.requests_received)}")
    
    print(f"\n✅ All tests completed!")


async def test_image_styling():
    """Quick test for image styling as well."""
    print(f"\n🖼️  Bonus Test: Image Styling")
    
    try:
        from scalapay.scalapay_mcp_kam.batch_operations_styled_wrapper import enhanced_batch_image_replace_with_styling
        
        mock_service = MockSlidesService()
        image_map = {
            "{{monthly_sales_chart}}": "https://example.com/chart1.png",
            "{{user_type_chart}}": "https://example.com/chart2.png"
        }
        alfred_results = create_mock_alfred_results()
        
        result = await enhanced_batch_image_replace_with_styling(
            mock_service,
            "test_presentation",
            image_map,
            results=alfred_results,
            enable_styling=True,
            correlation_id="test_image_styling"
        )
        
        print(f"   ✅ Image styling test SUCCESS!")
        print(f"   - Processing mode: {result.get('processing_mode', 'unknown')}")
        print(f"   - Styles applied: {result.get('styles_applied', 0)}")
        
    except Exception as e:
        print(f"   ❌ Image styling test FAILED: {e}")


if __name__ == "__main__":
    print("🚀 Starting Enhanced Text Styling Tests")
    print("This script tests the chart-specific styling system without Google API calls.")
    print()
    
    try:
        # Run the tests
        asyncio.run(test_enhanced_text_styling())
        asyncio.run(test_image_styling())
        
        print(f"\n🎉 Test completed successfully!")
        print(f"📖 Check the output above to see how styling detection and application works.")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()