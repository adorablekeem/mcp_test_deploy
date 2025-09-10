# Fix Plan: Chart Import Issues - Slug and Placeholder Matching

## Problem Analysis

The LLM-processed paragraph feature is working (structured text is generated), but charts are not being imported correctly into Google Slides due to slug-to-placeholder matching issues.

## Current Issue Identification

### **Root Cause Analysis**

Based on code analysis, the problem stems from inconsistencies between:

1. **Generated Chart Data Keys** from `mcp_tool_run()`:
   ```
   "monthly sales year over year"
   "monthly sales by product type over time"
   "monthly orders by user type" 
   "AOV"
   "scalapay users demographic in percentages"
   "orders by product type (i.e. pay in 3, pay in 4)"
   "AOV by product type (i.e. pay in 3, pay in 4)"
   ```

2. **Slug Generation Logic** in `_slug()` function:
   - Has hardcoded special cases that may not match all data keys
   - Uses length truncation (`max_len: int = 40`) which may cut off important identifiers
   - Different slug generation between original and enhanced functions

3. **Template Placeholder Format**: `{{{slug_chart}}}`
   - Must exactly match what exists in the Google Slides template
   - Case-sensitive and format-sensitive matching

## Technical Investigation Findings

### **Current Slug Generation Issues:**

1. **Inconsistent Special Case Handling**:
   ```python
   # test_fill_template_sections.py:42-47
   if "scalapay users demographic in percentages" in s:
       return "scalapay-users-demographic-in-percentage"  # singular vs plural!
   elif "orders by product type i.e. pay in 3, pay in 4" in s:
       return "orders-by-product-type-i-e-pay-in-3-pay-"  # truncated!
   ```

2. **Length Truncation Problems**:
   - `max_len = 40` may truncate important distinguishing parts
   - "AOV by product type (i.e. pay in 3, pay in 4)" becomes "aov-by-product-type-i-e-pay-in-3-pay-in-"

3. **Missing Validation**:
   - No verification that generated slugs match template placeholders
   - No debugging output to show slug-to-placeholder mapping
   - No fallback when placeholders don't exist in template

### **Template Processing Flow Issues:**

1. **Token Generation Mismatch**:
   ```python
   # tools_agent_kam_local.py:320
   image_map[f"{{{{{slug}_chart}}}}"] = url
   ```
   
2. **Multiple Slug Generation Points**:
   - Original: `test_fill_template_sections.py:_slug()`
   - Enhanced: Uses same function but in different contexts
   - Potential for inconsistency between text and image token generation

## Comprehensive Fix Strategy

### **Phase 1: Debugging & Validation Tools** (Immediate)

#### **1.1 Enhanced Logging System**
```python
def debug_slug_mapping(results_dict: Dict[str, Any], template_id: str) -> Dict[str, Any]:
    """Debug function to validate slug-to-placeholder mapping."""
    
    logger.info("=== SLUG MAPPING DEBUG ===")
    
    # Get actual template placeholders
    template_placeholders = get_template_placeholders(template_id)
    logger.info(f"Template placeholders found: {template_placeholders}")
    
    # Generate slugs for each data key
    mapping_report = {}
    for data_key in results_dict.keys():
        slug = _slug(data_key)
        expected_tokens = {
            "title": f"{{{{{slug}_title}}}}}",
            "paragraph": f"{{{{{slug}_paragraph}}}}}",  
            "chart": f"{{{{{slug}_chart}}}}}"
        }
        
        matches = {
            token_type: token in template_placeholders 
            for token_type, token in expected_tokens.items()
        }
        
        mapping_report[data_key] = {
            "slug": slug,
            "expected_tokens": expected_tokens,
            "template_matches": matches,
            "all_match": all(matches.values())
        }
        
        logger.info(f"Data Key: '{data_key}'")
        logger.info(f"  Generated Slug: '{slug}'")
        logger.info(f"  Template Matches: {matches}")
        logger.warning(f"  ❌ MISMATCH!" if not all(matches.values()) else f"  ✅ All tokens match")
    
    return mapping_report

def get_template_placeholders(template_id: str) -> List[str]:
    """Extract all placeholder tokens from Google Slides template."""
    try:
        slides_service = build("slides", "v1")
        presentation = slides_service.presentations().get(presentationId=template_id).execute()
        
        placeholders = []
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            content = text_element['textRun'].get('content', '')
                            # Find all {{...}} patterns
                            import re
                            found_placeholders = re.findall(r'\{\{\{.*?\}\}\}', content)
                            placeholders.extend(found_placeholders)
        
        return list(set(placeholders))  # Remove duplicates
    except Exception as e:
        logger.error(f"Failed to extract template placeholders: {e}")
        return []
```

#### **1.2 Slug Generation Validator**
```python
def validate_and_fix_slug_mapping(data_keys: List[str], template_id: str) -> Dict[str, str]:
    """
    Validate slug generation against template and provide corrections.
    Returns mapping of data_key -> corrected_slug
    """
    template_placeholders = get_template_placeholders(template_id)
    
    # Extract expected slug patterns from template
    expected_slugs = set()
    import re
    for placeholder in template_placeholders:
        match = re.match(r'\{\{\{([^_}]+)_(?:title|paragraph|chart)\}\}\}', placeholder)
        if match:
            expected_slugs.add(match.group(1))
    
    logger.info(f"Expected slugs from template: {sorted(expected_slugs)}")
    
    corrections = {}
    for data_key in data_keys:
        generated_slug = _slug(data_key)
        
        if generated_slug not in expected_slugs:
            # Find best match from template
            best_match = find_best_slug_match(generated_slug, expected_slugs)
            if best_match:
                corrections[data_key] = best_match
                logger.warning(f"Slug correction: '{data_key}' -> '{generated_slug}' -> '{best_match}'")
            else:
                logger.error(f"No template match found for: '{data_key}' (slug: '{generated_slug}')")
        else:
            logger.info(f"Slug OK: '{data_key}' -> '{generated_slug}'")
    
    return corrections

def find_best_slug_match(generated_slug: str, expected_slugs: set) -> str:
    """Find best matching slug from template using similarity."""
    from difflib import SequenceMatcher
    
    best_match = None
    best_ratio = 0.0
    
    for expected_slug in expected_slugs:
        ratio = SequenceMatcher(None, generated_slug, expected_slug).ratio()
        if ratio > best_ratio and ratio > 0.7:  # 70% similarity threshold
            best_ratio = ratio
            best_match = expected_slug
    
    return best_match
```

### **Phase 2: Improved Slug Generation** (Core Fix)

#### **2.1 Template-Driven Slug Mapping**
```python
# Enhanced slug generation with template validation
class SlugMapper:
    def __init__(self, template_id: str):
        self.template_id = template_id
        self.template_slugs = self._extract_template_slugs()
        self.slug_corrections = self._build_correction_map()
    
    def _extract_template_slugs(self) -> Set[str]:
        """Extract all slug patterns from template."""
        placeholders = get_template_placeholders(self.template_id)
        slugs = set()
        
        import re
        for placeholder in placeholders:
            match = re.match(r'\{\{\{([^_}]+)_(?:title|paragraph|chart)\}\}\}', placeholder)
            if match:
                slugs.add(match.group(1))
        
        return slugs
    
    def _build_correction_map(self) -> Dict[str, str]:
        """Build known corrections for common data keys."""
        # Known mappings based on analysis
        return {
            "monthly sales year over year": "monthly-sales-over-time",
            "monthly sales by product type over time": "monthly-sales-by-product-type-over-time", 
            "monthly orders by user type": "monthly-orders-by-user-type",
            "AOV": "aov",
            "scalapay users demographic in percentages": "scalapay-users-demographic-in-percentage",
            "orders by product type (i.e. pay in 3, pay in 4)": "orders-by-product-type-i-e-pay-in-3-pay-",
            "AOV by product type (i.e. pay in 3, pay in 4)": "aov-by-product-type-i-e-pay-in-3-pay-in-"
        }
    
    def get_slug(self, data_key: str) -> str:
        """Get correct slug for data key with template validation."""
        # First check known corrections
        if data_key in self.slug_corrections:
            corrected_slug = self.slug_corrections[data_key]
            if corrected_slug in self.template_slugs:
                return corrected_slug
        
        # Generate slug normally
        generated_slug = _slug(data_key)
        
        # Validate against template
        if generated_slug in self.template_slugs:
            return generated_slug
        
        # Try to find best match
        best_match = find_best_slug_match(generated_slug, self.template_slugs)
        if best_match:
            logger.warning(f"Using template match '{best_match}' for data key '{data_key}'")
            return best_match
        
        # Fallback with warning
        logger.error(f"No template match for '{data_key}' (slug: '{generated_slug}')")
        return generated_slug
```

#### **2.2 Enhanced Slug Generation Function**
```python
def _slug_enhanced(s: str, template_slugs: Set[str] = None, max_len: int = 60) -> str:
    """
    Enhanced slug generation with template validation.
    """
    # Handle known problematic cases first
    known_mappings = {
        "scalapay users demographic in percentages": "scalapay-users-demographic-in-percentage",
        "monthly sales year over year": "monthly-sales-over-time",
        "monthly sales by product type over time": "monthly-sales-by-product-type-over-time",
        "orders by product type (i.e. pay in 3, pay in 4)": "orders-by-product-type-i-e-pay-in-3-pay-in-4", 
        "AOV by product type (i.e. pay in 3, pay in 4)": "aov-by-product-type-i-e-pay-in-3-pay-in-4"
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
```

### **Phase 3: Template Processing Enhancement** (Integration)

#### **3.1 Enhanced build_text_and_image_maps**
```python
async def build_text_and_image_maps_enhanced_with_validation(
    results: Dict[str, Any], 
    llm_processor,
    template_id: str,
    presentation_context: dict = None
) -> tuple[Dict[str, str], List[Dict[str, str]], Dict[str, str], Dict[str, Any]]:
    """
    Enhanced version with slug validation and debugging.
    """
    
    # Initialize slug mapper with template validation
    slug_mapper = SlugMapper(template_id)
    
    # Debug mapping before processing
    mapping_debug = debug_slug_mapping(results, template_id)
    
    sections = []
    text_map = {}
    notes_map = {}
    
    for title, payload in results.items():
        full_paragraph = _pick_paragraph(payload)
        chart_path = _pick_chart_path(payload)
        
        if full_paragraph and chart_path:
            structured_data = payload.get("slides_struct", {}).get("structured_data", {})
            
            # Use validated slug generation
            slug = slug_mapper.get_slug(title)
            
            # Build slide context
            slide_context = {
                "slide_index": len(sections) + 1,
                "total_slides": len(results),
                "chart_type": _infer_chart_type(title, structured_data),
                "validated_slug": slug  # Include validated slug in context
            }
            if presentation_context:
                slide_context.update(presentation_context)
            
            try:
                # LLM processing for slide-optimized content
                optimized_content = await process_slide_paragraph(
                    title, full_paragraph, structured_data, slide_context, llm_processor
                )
                
                # Build token maps with validated slugs
                text_map[f"{{{{{slug}_title}}}}"] = title
                text_map[f"{{{{{slug}_paragraph}}}}"] = optimized_content.slide_paragraph
                
                # Create comprehensive notes content
                notes_content = f"Full Analysis:\n{optimized_content.full_paragraph}"
                if optimized_content.key_insights:
                    notes_content += f"\n\nKey Insights:\n" + "\n".join(f"• {insight}" for insight in optimized_content.key_insights)
                if optimized_content.presenter_notes_addition:
                    notes_content += f"\n\nAdditional Context:\n{optimized_content.presenter_notes_addition}"
                
                notes_map[f"{{{{{slug}_notes}}}}"] = notes_content
                
                sections.append({
                    "title": title,
                    "slide_paragraph": optimized_content.slide_paragraph,
                    "full_paragraph": optimized_content.full_paragraph,
                    "chart_path": chart_path,
                    "slug": slug,  # Use validated slug
                    "notes_content": notes_content,
                    "key_insights": optimized_content.key_insights or [],
                    "original_slug": _slug(title),  # Keep original for debugging
                    "slug_validated": slug in slug_mapper.template_slugs
                })
                
                logger.info(f"✅ Section processed: '{title}' -> slug: '{slug}' (validated: {slug in slug_mapper.template_slugs})")
                
            except Exception as e:
                logger.warning(f"Enhanced processing failed for '{title}': {e}. Using fallback.")
                # Fallback logic remains the same but uses validated slug
                slug = slug_mapper.get_slug(title)
                # ... rest of fallback logic
        else:
            logger.debug(f"Skipping section '{title}' (missing paragraph or chart_path)")

    if not sections:
        raise RuntimeError("No renderable sections (need both paragraph and chart_path).")
    
    return text_map, sections, notes_map, mapping_debug
```

### **Phase 4: Runtime Validation & Monitoring** (Production)

#### **4.1 Pre-Processing Validation**
```python
def validate_template_compatibility(data_keys: List[str], template_id: str) -> Dict[str, Any]:
    """Validate that all data keys can be properly mapped to template placeholders."""
    
    validation_report = {
        "template_id": template_id,
        "total_data_keys": len(data_keys),
        "validation_results": {},
        "issues_found": [],
        "success_rate": 0.0
    }
    
    slug_mapper = SlugMapper(template_id)
    successful_mappings = 0
    
    for data_key in data_keys:
        slug = slug_mapper.get_slug(data_key)
        is_valid = slug in slug_mapper.template_slugs
        
        validation_report["validation_results"][data_key] = {
            "slug": slug,
            "template_match": is_valid,
            "tokens": {
                "title": f"{{{{{slug}_title}}}}}",
                "paragraph": f"{{{{{slug}_paragraph}}}}}",
                "chart": f"{{{{{slug}_chart}}}}}"
            }
        }
        
        if is_valid:
            successful_mappings += 1
        else:
            validation_report["issues_found"].append({
                "data_key": data_key,
                "generated_slug": slug,
                "issue": "No matching template placeholder found"
            })
    
    validation_report["success_rate"] = successful_mappings / len(data_keys)
    
    return validation_report
```

#### **4.2 Post-Processing Verification**
```python
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
                        "source_url": element['image'].get('sourceUrl', '')
                    })
        
        return {
            "presentation_id": presentation_id,
            "expected_charts": len(expected_charts),
            "imported_images": len(imported_images),
            "success_rate": len(imported_images) / len(expected_charts) if expected_charts else 0,
            "images": imported_images
        }
        
    except Exception as e:
        logger.error(f"Failed to verify chart imports: {e}")
        return {"error": str(e), "imported_images": 0}
```

## Implementation Roadmap

### **Phase 1: Immediate Debugging** (Day 1)
1. Add debug logging to current slug generation
2. Implement template placeholder extraction
3. Run validation against current template
4. Identify exact mismatches

### **Phase 2: Slug Generation Fix** (Day 2)
1. Implement SlugMapper class with template validation  
2. Update slug generation in all processing functions
3. Add known mapping corrections
4. Test with actual data keys

### **Phase 3: Enhanced Processing Integration** (Day 3)
1. Update build_text_and_image_maps functions
2. Add validation to fill_template_for_all_sections
3. Implement pre and post-processing validation
4. Add comprehensive error reporting

### **Phase 4: Production Monitoring** (Day 4)
1. Add runtime validation checks
2. Implement success rate monitoring  
3. Add alerts for mapping failures
4. Create troubleshooting documentation

## Success Metrics

1. **Chart Import Success Rate**: Target 100% of expected charts imported
2. **Slug Validation Success**: All data keys map to valid template placeholders
3. **Error Reduction**: Zero "placeholder not found" errors in logs
4. **Debugging Visibility**: Clear logging shows slug generation and validation results

## Risk Mitigation

1. **Backward Compatibility**: Keep original slug generation as fallback
2. **Graceful Degradation**: Continue processing even with some mapping failures
3. **Template Validation**: Verify template structure before processing
4. **Comprehensive Logging**: Detailed debugging output for troubleshooting

This plan addresses the root cause of chart import issues through systematic validation, improved slug generation, and comprehensive debugging tools while maintaining backward compatibility and production reliability.

---

## ✅ **RESOLVED ISSUE UPDATE** (Latest)

### **Template Matching Fix Applied**

**Issue**: The slug validation system was mapping `"monthly sales year over year"` to `"monthly-sales-year-over-year"`, but the actual Google Slides template contains the token `{{monthly_sales_yoy_chart}}`.

**Root Cause**: Inconsistency between slug generation logic and actual template placeholders.

**Fix Applied**:
1. **Updated `utils/slug_validation.py`**:
   - Changed mapping from `"monthly sales year over year": "monthly-sales-year-over-year"` to `"monthly sales year over year": "monthly_sales_yoy"`
   - Removed invalid fallback slug `"monthly-sales-year-over-year"` 
   - Updated comment to reflect correct template token `{{monthly_sales_yoy_chart}}`

2. **Validation Confirmed**:
   - Both `SlugMapper` and `OptimizedSlugMapper` now correctly return `"monthly_sales_yoy"`
   - Template validation confirms slug exists in template slugs set
   - `find_element_ids_for_tokens()` function will now find matching tokens in template

**Technical Details**:
- The fix ensures consistency between slug generation and the actual Google Slides template format
- Template uses underscore format (`monthly_sales_yoy`) rather than hyphen format (`monthly-sales-year-over-year`)
- Both slug validation systems now produce identical, validated results

**Testing Results**:
```
Data key: monthly sales year over year
Generated slug: monthly_sales_yoy  
Is in template slugs: True ✅
```

This fix resolves the "❌ No template match for correction" error and ensures proper chart import for the "monthly sales year over year" data type.

---

*Generated by technical analysis of Scalapay MCP KAM chart import issues*