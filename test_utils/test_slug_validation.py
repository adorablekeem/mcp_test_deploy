#!/usr/bin/env python3
"""
Test script to validate slug mapping fix for chart imports.
Run this script to test the slug validation and template matching functionality.
"""

import logging
import json
from scalapay.scalapay_mcp_kam.utils.slug_validation import (
    SlugMapper, debug_slug_mapping, _slug_enhanced
)
from scalapay.scalapay_mcp_kam.config import get_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def test_slug_validation():
    """Test the slug validation fix with sample data."""
    
    config = get_config()
    template_id = config.default_template_id
    
    # Sample data similar to actual Alfred results
    sample_results = {
        "monthly sales over time": {
            "slides_struct": {
                "paragraph": "Monthly sales have shown consistent growth over the past 12 months with strong performance in Q4.",
                "structured_data": {"Jan": {"2024": 1000, "2025": 1200}}
            },
            "chart_path": "./plots/monthly_sales_over_time_test.png"
        },
        "scalapay users demographic in percentages": {
            "slides_struct": {
                "paragraph": "User demographics show a balanced distribution across age groups with 25-34 being the largest segment.",
                "structured_data": {"25-34": 35, "35-44": 28}
            },
            "chart_path": "./plots/scalapay_users_demographic_test.png"
        },
        "orders by product type (i.e. pay in 3, pay in 4)": {
            "slides_struct": {
                "paragraph": "Pay in 3 continues to dominate order volume with 65% market share.",
                "structured_data": {"Pay in 3": 65, "Pay in 4": 35}
            },
            "chart_path": "./plots/orders_by_product_type_test.png"
        },
        "AOV by product type (i.e. pay in 3, pay in 4)": {
            "slides_struct": {
                "paragraph": "Average order values vary significantly between product types.",
                "structured_data": {"Pay in 3": 150, "Pay in 4": 280}
            },
            "chart_path": "./plots/aov_by_product_type_test.png"
        },
        "monthly orders by user type": {
            "slides_struct": {
                "paragraph": "New users consistently represent 40% of monthly orders.",
                "structured_data": {"New": 40, "Returning": 60}
            },
            "chart_path": "./plots/monthly_orders_by_user_type_test.png"
        },
        "AOV": {
            "slides_struct": {
                "paragraph": "Overall average order value has increased by 12% year over year.",
                "structured_data": {"2024": 180, "2025": 202}
            },
            "chart_path": "./plots/aov_test.png"
        }
    }
    
    logger.info("=" * 60)
    logger.info("TESTING SLUG VALIDATION FIX")
    logger.info("=" * 60)
    
    # Test 1: Initialize SlugMapper
    logger.info("Test 1: Initializing SlugMapper...")
    try:
        slug_mapper = SlugMapper(template_id)
        logger.info(f"✅ SlugMapper initialized successfully")
        logger.info(f"Found {len(slug_mapper.template_slugs)} template slugs")
    except Exception as e:
        logger.error(f"❌ SlugMapper initialization failed: {e}")
        return False
    
    # Test 2: Test individual slug mappings
    logger.info("\nTest 2: Testing individual slug mappings...")
    for data_key in sample_results.keys():
        try:
            slug = slug_mapper.get_slug(data_key)
            is_valid = slug in slug_mapper.template_slugs
            status = "✅ VALID" if is_valid else "❌ INVALID"
            logger.info(f"  '{data_key}' -> '{slug}' {status}")
        except Exception as e:
            logger.error(f"  '{data_key}' -> ERROR: {e}")
    
    # Test 3: Run comprehensive validation
    logger.info("\nTest 3: Running comprehensive validation...")
    try:
        validation_report = debug_slug_mapping(sample_results, template_id)
        logger.info(f"✅ Validation complete")
        logger.info(f"Success rate: {validation_report['success_rate']:.1%}")
        logger.info(f"Issues found: {len(validation_report['issues_found'])}")
        
        if validation_report['issues_found']:
            logger.warning("Issues detected:")
            for issue in validation_report['issues_found']:
                logger.warning(f"  - {issue['data_key']}: {issue['issue']}")
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return False
    
    # Test 4: Test enhanced slug function
    logger.info("\nTest 4: Testing enhanced slug generation...")
    test_cases = [
        "monthly sales over time",
        "scalapay users demographic in percentages", 
        "orders by product type (i.e. pay in 3, pay in 4)",
        "AOV by product type (i.e. pay in 3, pay in 4)",
        "monthly orders by user type",
        "AOV"
    ]
    
    for test_case in test_cases:
        old_slug = _slug_enhanced(test_case, max_len=40)  # Old way
        new_slug = _slug_enhanced(test_case, slug_mapper.template_slugs, max_len=60)  # New way
        match_status = "✅ MATCH" if new_slug in slug_mapper.template_slugs else "❌ NO MATCH"
        logger.info(f"  '{test_case}' -> '{new_slug}' {match_status}")
    
    logger.info("\n" + "=" * 60)
    logger.info("SLUG VALIDATION TEST COMPLETE")
    logger.info("=" * 60)
    
    return validation_report['success_rate'] >= 0.8  # 80% success rate threshold


if __name__ == "__main__":
    success = test_slug_validation()
    if success:
        logger.info("🎉 Slug validation fix test PASSED")
        exit(0)
    else:
        logger.error("💥 Slug validation fix test FAILED")
        exit(1)