"""
Slug validation and template matching utilities for Google Slides integration.
Fixes chart import issues by ensuring slug-to-placeholder matching.
"""

import re
import logging
import unicodedata
import string
from typing import Dict, List, Set, Any, Optional, Tuple
from difflib import SequenceMatcher
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def get_template_placeholders(template_id: str) -> List[str]:
    """Extract all placeholder tokens from Google Slides template."""
    try:
        slides_service = build("slides", "v1")
        presentation = slides_service.presentations().get(presentationId=template_id).execute()
        
        placeholders = []
        logger.debug(f"Analyzing template {template_id} for placeholders...")
        
        for slide_idx, slide in enumerate(presentation.get('slides', [])):
            logger.debug(f"Checking slide {slide_idx}: {slide.get('objectId', 'unknown')}")
            
            for element_idx, element in enumerate(slide.get('pageElements', [])):
                if 'shape' in element and 'text' in element['shape']:
                    text_elements = element['shape']['text'].get('textElements', [])
                    for text_element in text_elements:
                        if 'textRun' in text_element:
                            content = text_element['textRun'].get('content', '')
                            if content.strip():
                                # Find all {{...}} patterns (the actual format used in templates)
                                found_placeholders = re.findall(r'\{\{[^}]+\}\}', content)
                                if found_placeholders:
                                    logger.debug(f"  Found placeholders in element {element_idx}: {found_placeholders}")
                                placeholders.extend(found_placeholders)
        
        unique_placeholders = list(set(placeholders))
        logger.info(f"Template {template_id} contains {len(unique_placeholders)} unique placeholders:")
        for placeholder in sorted(unique_placeholders):
            logger.info(f"  - {placeholder}")
        
        return unique_placeholders
        
    except Exception as e:
        logger.error(f"Failed to extract template placeholders from {template_id}: {e}")
        return []


def extract_slugs_from_placeholders(placeholders: List[str]) -> Set[str]:
    """Extract slug patterns from placeholder tokens."""
    slugs = set()
    
    for placeholder in placeholders:
        # Match patterns like {{slug_title}}, {{slug_paragraph}}, {{slug_chart}}
        match = re.match(r'\{\{([^_}]+)_(?:title|paragraph|chart)\}\}', placeholder)
        if match:
            slugs.add(match.group(1))
        else:
            logger.debug(f"Placeholder doesn't match expected pattern: {placeholder}")
    
    logger.info(f"Extracted {len(slugs)} unique slug patterns: {sorted(slugs)}")
    return slugs


def find_best_slug_match(generated_slug: str, expected_slugs: Set[str], threshold: float = 0.7) -> Optional[str]:
    """Find best matching slug from template using similarity."""
    if not expected_slugs:
        return None
    
    best_match = None
    best_ratio = 0.0
    
    for expected_slug in expected_slugs:
        ratio = SequenceMatcher(None, generated_slug, expected_slug).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = expected_slug
    
    if best_ratio >= threshold:
        logger.debug(f"Found match for '{generated_slug}': '{best_match}' (similarity: {best_ratio:.2f})")
        return best_match
    else:
        logger.warning(f"No good match for '{generated_slug}' (best: '{best_match}' at {best_ratio:.2f})")
        return None


def _slug_enhanced(s: str, template_slugs: Set[str] = None, max_len: int = 60) -> str:
    """
    Enhanced slug generation with template validation.
    """
    # Handle known problematic cases first (based on actual template analysis)
    known_mappings = {
        "scalapay users demographic in percentages": "scalapay-users-demographic-in-percentage",
        "monthly sales over time": "monthly-sales-over-time",
        "monthly sales year over year": "monthly-sales-over-time",
        "monthly sales by product type over time": "monthly-sales-by-product-type-over-time",
        "orders by product type (i.e. pay in 3, pay in 4)": "orders-by-product-type-i-e-pay-in-3-pay", 
        "AOV by product type (i.e. pay in 3, pay in 4)": "aov-by-product-type-i-e-pay-in-3-pay-in",
        "monthly orders by user type": "monthly-orders-by-user-type",
        "AOV": "aov"
    }
    
    if s in known_mappings:
        candidate = known_mappings[s]
        if template_slugs is None or candidate in template_slugs:
            return candidate
    
    # Standard slug processing with increased length
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if ord(c) < 128)
    s = s.lower().strip()
    
    # Replace parentheses and special chars
    s = s.replace("(", "").replace(")", "")
    s = s.replace(",", "").replace(".", "")
    
    # Convert to slug format
    valid = f"{string.ascii_lowercase}{string.digits}-"
    s = s.replace(" ", "-")
    s = "".join(ch if ch in valid else "-" for ch in s)
    
    # Collapse multiple hyphens
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-")
    
    # Apply length limit but try to keep meaningful parts
    if len(s) > max_len:
        parts = s.split("-")
        result = ""
        for part in parts:
            if len(result + "-" + part) <= max_len:
                result = result + "-" + part if result else part
            else:
                break
        s = result or s[:max_len]
    
    return s or "section"


class SlugMapper:
    """Template-driven slug mapping with validation."""
    
    def __init__(self, template_id: str):
        self.template_id = template_id
        
        # Try to get template placeholders via API
        self.template_placeholders = get_template_placeholders(template_id)
        self.template_slugs = extract_slugs_from_placeholders(self.template_placeholders)
        
        # If API fails, use fallback mappings
        if not self.template_slugs:
            logger.warning(f"API access failed for template {template_id}, using fallback mappings")
            self.template_slugs = self._get_fallback_template_slugs()
            self.template_placeholders = self._get_fallback_placeholders()
        
        self.slug_corrections = self._build_correction_map()
        
        logger.info(f"SlugMapper initialized for template {template_id}")
        logger.info(f"Found {len(self.template_slugs)} template slugs: {sorted(self.template_slugs)}")
    
    def _build_correction_map(self) -> Dict[str, str]:
        """Build known corrections for common data keys."""
        # These are the corrections based on actual template analysis
        base_corrections = {
            "monthly sales over time": "monthly-sales-over-time",  # matches {{monthly-sales-over-time_title}}
            "monthly sales year over year": "monthly-sales-over-time",  # matches {{monthly-sales-over-time_chart}}
            "monthly sales by product type over time": "monthly-sales-by-product-type-over-time", 
            "monthly orders by user type": "monthly-orders-by-user-type",  # matches {{monthly-orders-by-user-type_title}}
            "AOV": "aov",  # matches {{aov_title}}
            "scalapay users demographic in percentages": "scalapay-users-demographic-in-percentage",  # matches {{scalapay-users-demographic-in-percentage_title}}
            "orders by product type (i.e. pay in 3, pay in 4)": "orders-by-product-type-i-e-pay-in-3-pay",  # matches {{orders-by-product-type-i-e-pay-in-3-pay_title}}
            "AOV by product type (i.e. pay in 3, pay in 4)": "aov-by-product-type-i-e-pay-in-3-pay-in"  # matches template truncation
        }
        
        # Validate corrections against actual template
        validated_corrections = {}
        for data_key, correction in base_corrections.items():
            if correction in self.template_slugs:
                validated_corrections[data_key] = correction
                logger.debug(f"✅ Validated correction: '{data_key}' -> '{correction}'")
            else:
                # Try to find best match from template
                best_match = find_best_slug_match(correction, self.template_slugs)
                if best_match:
                    validated_corrections[data_key] = best_match
                    logger.warning(f"🔄 Updated correction: '{data_key}' -> '{correction}' -> '{best_match}'")
                else:
                    logger.error(f"❌ No template match for correction: '{data_key}' -> '{correction}'")
        
        return validated_corrections
    
    def _get_fallback_template_slugs(self) -> Set[str]:
        """Fallback template slugs based on actual template analysis."""
        return {
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
    
    def _get_fallback_placeholders(self) -> List[str]:
        """Fallback placeholders based on actual template analysis."""
        placeholders = []
        for slug in self._get_fallback_template_slugs():
            placeholders.extend([
                "{{" + f"{slug}_title" + "}}",
                "{{" + f"{slug}_paragraph" + "}}",
                "{{" + f"{slug}_chart" + "}}"
            ])
        return placeholders
    
    def get_slug(self, data_key: str) -> str:
        """Get correct slug for data key with template validation."""
        # First check known corrections
        if data_key in self.slug_corrections:
            corrected_slug = self.slug_corrections[data_key]
            if corrected_slug in self.template_slugs:
                logger.debug(f"Using known correction: '{data_key}' -> '{corrected_slug}'")
                return corrected_slug
        
        # Generate slug normally
        generated_slug = _slug_enhanced(data_key, self.template_slugs)
        
        # Validate against template
        if generated_slug in self.template_slugs:
            logger.debug(f"Generated slug validated: '{data_key}' -> '{generated_slug}'")
            return generated_slug
        
        # Try to find best match
        best_match = find_best_slug_match(generated_slug, self.template_slugs)
        if best_match:
            logger.warning(f"Using template match '{best_match}' for data key '{data_key}' (generated: '{generated_slug}')")
            return best_match
        
        # Fallback with warning
        logger.error(f"No template match for '{data_key}' (slug: '{generated_slug}'). Using generated slug anyway.")
        return generated_slug
    
    def validate_all_mappings(self, data_keys: List[str]) -> Dict[str, Any]:
        """Validate mappings for all data keys and return detailed report."""
        report = {
            "template_id": self.template_id,
            "total_data_keys": len(data_keys),
            "template_slugs": sorted(self.template_slugs),
            "validation_results": {},
            "issues_found": [],
            "success_rate": 0.0
        }
        
        successful_mappings = 0
        
        for data_key in data_keys:
            slug = self.get_slug(data_key)
            is_valid = slug in self.template_slugs
            
            tokens = {
                "title": "{{" + f"{slug}_title" + "}}",
                "paragraph": "{{" + f"{slug}_paragraph" + "}}",
                "chart": "{{" + f"{slug}_chart" + "}}"
            }
            
            # Check if tokens exist in template
            token_matches = {
                token_type: token in self.template_placeholders 
                for token_type, token in tokens.items()
            }
            
            all_tokens_match = all(token_matches.values())
            
            report["validation_results"][data_key] = {
                "slug": slug,
                "template_match": is_valid,
                "tokens": tokens,
                "token_matches": token_matches,
                "all_tokens_valid": all_tokens_match
            }
            
            if all_tokens_match:
                successful_mappings += 1
            else:
                missing_tokens = [token_type for token_type, matches in token_matches.items() if not matches]
                report["issues_found"].append({
                    "data_key": data_key,
                    "generated_slug": slug,
                    "issue": f"Missing template tokens: {missing_tokens}",
                    "tokens": tokens
                })
        
        report["success_rate"] = successful_mappings / len(data_keys) if data_keys else 0
        
        # Log summary
        logger.info(f"Slug validation summary:")
        logger.info(f"  Success rate: {report['success_rate']:.1%} ({successful_mappings}/{len(data_keys)})")
        if report["issues_found"]:
            logger.warning(f"  Issues found: {len(report['issues_found'])}")
            for issue in report["issues_found"]:
                logger.warning(f"    - {issue['data_key']}: {issue['issue']}")
        
        return report


def debug_slug_mapping(results_dict: Dict[str, Any], template_id: str) -> Dict[str, Any]:
    """Debug function to validate slug-to-placeholder mapping."""
    
    logger.info("=== SLUG MAPPING DEBUG ===")
    
    slug_mapper = SlugMapper(template_id)
    data_keys = list(results_dict.keys())
    
    # Get validation report
    validation_report = slug_mapper.validate_all_mappings(data_keys)
    
    # Additional debugging output
    logger.info(f"Template placeholders found: {len(slug_mapper.template_placeholders)}")
    for placeholder in sorted(slug_mapper.template_placeholders):
        logger.info(f"  - {placeholder}")
    
    logger.info(f"Data keys to process: {len(data_keys)}")
    for data_key in data_keys:
        slug = slug_mapper.get_slug(data_key)
        logger.info(f"  - '{data_key}' -> slug: '{slug}'")
    
    return validation_report


def verify_chart_imports(presentation_id: str, expected_charts: List[str]) -> Dict[str, Any]:
    """Verify that charts were actually imported into the presentation."""
    
    try:
        slides_service = build("slides", "v1")
        presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
        
        imported_images = []
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'image' in element:
                    imported_images.append({
                        "slide_id": slide['objectId'],
                        "image_id": element['objectId'],
                        "source_url": element['image'].get('sourceUrl', ''),
                        "content_url": element['image'].get('contentUrl', '')
                    })
        
        verification_result = {
            "presentation_id": presentation_id,
            "expected_charts": len(expected_charts),
            "imported_images": len(imported_images),
            "success_rate": len(imported_images) / len(expected_charts) if expected_charts else 0,
            "images": imported_images
        }
        
        logger.info(f"Chart import verification:")
        logger.info(f"  Expected: {len(expected_charts)} charts")
        logger.info(f"  Found: {len(imported_images)} images")
        logger.info(f"  Success rate: {verification_result['success_rate']:.1%}")
        
        return verification_result
        
    except Exception as e:
        logger.error(f"Failed to verify chart imports: {e}")
        return {"error": str(e), "imported_images": 0}