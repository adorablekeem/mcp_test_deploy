#!/usr/bin/env python3
"""
Quick fix for slug mapping based on actual template analysis.
This creates a direct mapping without requiring Google API access.
"""

import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)


def get_template_slug_mappings() -> Dict[str, str]:
    """
    Return direct mappings based on actual template analysis from debug output.
    
    From the debug output, the actual template contains these tokens:
    - {{monthly-sales-over-time_title}}
    - {{monthly_sales_chart}}
    - {{monthly_sales_yoy_chart}}
    - {{monthly-orders-by-user-type_title}}
    - {{monthly_orders_by_user_type_chart}}
    - {{monthly-orders-by-user-type_paragraph}}
    - {{orders-by-product-type-i-e-pay-in-3-pay_title}}
    - {{orders_by_product_type_i_e_pay_in_3_pay_in_4_chart}}
    - {{scalapay-users-demographic-in-percentage_title}}
    - {{scalapay_users_demographic_in_percentages_chart}}
    - {{aov_title}}
    - {{average_item_chart}}
    - {{aov-by-product-type-i-e-pay-in-3-pay-in_title}}
    - {{aov_by_product_type_i_e_pay_in_3_pay_in_4_chart}}
    - {{aov-by-product-type-i-e-pay-in-3-pay-in_paragraph}}
    """
    return {
        "monthly sales over time": "monthly-sales-over-time",
        "monthly sales year over year": "monthly_sales_yoy", 
        "monthly sales by product type over time": "monthly-sales-by-product-type-over-time",
        "monthly orders by user type": "monthly-orders-by-user-type",
        "orders by product type (i.e. pay in 3, pay in 4)": "orders-by-product-type-i-e-pay-in-3-pay",
        "scalapay users demographic in percentages": "scalapay-users-demographic-in-percentage",
        "AOV": "aov",
        "AOV by product type (i.e. pay in 3, pay in 4)": "aov-by-product-type-i-e-pay-in-3-pay-in"
    }


def get_template_slugs() -> Set[str]:
    """Extract unique slugs from the known template tokens."""
    template_slugs = {
        "monthly-sales-over-time",
        "monthly_sales", 
        "monthly_sales_yoy",
        "monthly-orders-by-user-type",
        "monthly_orders_by_user_type",
        "orders-by-product-type-i-e-pay-in-3-pay",
        "orders_by_product_type_i_e_pay_in_3_pay_in_4",
        "scalapay-users-demographic-in-percentage",
        "scalapay_users_demographic_in_percentages",
        "aov",
        "average_item",
        "aov-by-product-type-i-e-pay-in-3-pay-in",
        "aov_by_product_type_i_e_pay_in_3_pay_in_4"
    }
    return template_slugs


class OptimizedSlugMapper:
    """Optimized slug mapper that uses known template patterns."""
    
    def __init__(self):
        self.slug_mappings = get_template_slug_mappings()
        self.template_slugs = get_template_slugs()
        logger.info(f"OptimizedSlugMapper initialized with {len(self.template_slugs)} template slugs")
    
    def get_slug(self, data_key: str) -> str:
        """Get the correct slug for a data key."""
        # First check direct mappings
        if data_key in self.slug_mappings:
            mapped_slug = self.slug_mappings[data_key]
            if mapped_slug in self.template_slugs:
                logger.debug(f"Direct mapping: '{data_key}' -> '{mapped_slug}'")
                return mapped_slug
        
        # Fallback to enhanced slug generation
        from scalapay.scalapay_mcp_kam.utils.slug_validation import _slug_enhanced
        generated_slug = _slug_enhanced(data_key, self.template_slugs)
        
        if generated_slug in self.template_slugs:
            logger.debug(f"Generated slug validated: '{data_key}' -> '{generated_slug}'")
            return generated_slug
        
        # Final fallback - use direct mapping even if not validated
        if data_key in self.slug_mappings:
            mapped_slug = self.slug_mappings[data_key]
            logger.warning(f"Using unvalidated mapping: '{data_key}' -> '{mapped_slug}'")
            return mapped_slug
        
        logger.warning(f"No mapping found for '{data_key}', using generated: '{generated_slug}'")
        return generated_slug


def update_slug_validation_files():
    """Update the slug validation utilities to use optimized mappings."""
    
    # Update the utils file to use optimized mappings as fallback
    logger.info("Consider updating utils/slug_validation.py to use OptimizedSlugMapper as fallback")
    
    # For now, just return the mapper for testing
    return OptimizedSlugMapper()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    
    # Test the optimized mapper
    mapper = OptimizedSlugMapper()
    
    test_keys = [
        "monthly sales over time",
        "scalapay users demographic in percentages",
        "orders by product type (i.e. pay in 3, pay in 4)",
        "AOV by product type (i.e. pay in 3, pay in 4)",
        "monthly orders by user type",
        "AOV"
    ]
    
    logger.info("Testing optimized slug mappings:")
    for key in test_keys:
        slug = mapper.get_slug(key)
        valid = slug in mapper.template_slugs
        status = "✅ VALID" if valid else "❌ INVALID"
        logger.info(f"  '{key}' -> '{slug}' {status}")