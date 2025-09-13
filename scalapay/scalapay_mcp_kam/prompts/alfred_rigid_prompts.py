"""
Rigid Alfred Prompt System - Data-specific prompt templates
Based on schema registry for consistent Alfred responses.
"""

import json
from typing import Any, Dict, Optional

from ..data_schemas.alfred_schema_registry import ALFRED_DATA_REQUIREMENTS, ChartType, DataRequirement


class AlfredPromptBuilder:
    """Builder for data-specific Alfred prompts with rigid validation"""

    def __init__(self):
        self.registry = ALFRED_DATA_REQUIREMENTS
        self.base_instruction = """
CRITICAL SYSTEM REQUIREMENTS:
1. You MUST output EXACT JSON format specified below
2. NO additional text, explanations, or markdown formatting
3. ALL numeric values must be actual numbers (int/float), never strings
4. NO null values - use 0 for missing data
5. Follow the EXACT field names and structure provided
6. Paragraph must be analytical and substantive (minimum 50 characters)

VALIDATION CHECKLIST BEFORE RESPONDING:
✓ Output is valid JSON (no syntax errors)
✓ All required fields are present
✓ All numbers are numeric types, not strings
✓ Structure matches template exactly
✓ No extra fields outside the template
✓ Paragraph provides meaningful analysis
"""

    def build_prompt(
        self,
        data_type: str,
        merchant_token: str,
        starting_date: str,
        end_date: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """Build rigid prompt for specific data type"""

        requirement = self.registry.get(data_type)
        if not requirement:
            raise ValueError(f"Unsupported data type: {data_type}")

        # Build data type specific instructions
        specific_instructions = self._build_specific_instructions(requirement)

        # Build exact output template
        output_template = self._build_output_template(requirement)

        # Build validation requirements
        validation_section = self._build_validation_section(requirement)

        # Build transformation hints
        transformation_section = self._build_transformation_section(requirement)

        # Assemble complete prompt
        prompt = f"""{self.base_instruction}

DATA REQUEST: {data_type}
MERCHANT: {merchant_token}
DATE RANGE: {starting_date} to {end_date}
CHART TYPE: {requirement.chart_type.value}

{specific_instructions}

{transformation_section}

EXACT OUTPUT TEMPLATE (DO NOT DEVIATE):
{output_template}

{validation_section}

EXECUTE DATA RETRIEVAL:
Find the exact data for merchant "{merchant_token}" from {starting_date} to {end_date}.
Focus specifically on: {data_type}

Your response must be ONLY the JSON object matching the template above."""

        if additional_context:
            prompt += f"\n\nADDITIONAL CONTEXT: {additional_context}"

        return prompt

    def _build_specific_instructions(self, requirement: DataRequirement) -> str:
        """Build data-type specific instructions"""

        instructions_map = {
            ChartType.TIME_SERIES: """
TIME SERIES DATA REQUIREMENTS:
- Use chronological month ordering (Jan, Feb, Mar, etc.)
- Include multiple years for comparison
- Ensure consistent date formatting
- Fill missing months with 0 values
""",
            ChartType.BAR_CHART: """
BAR CHART DATA REQUIREMENTS:
- Organize data for clear categorical comparison
- Use consistent category naming
- Ensure all values are positive numbers
- Include meaningful category labels
""",
            ChartType.STACKED_BAR: """
STACKED BAR CHART REQUIREMENTS:
- Each time period must have all category breakdowns
- Categories should be consistent across all periods
- Values represent component parts of totals
- Use standardized category names
""",
            ChartType.LINE_CHART: """
LINE CHART DATA REQUIREMENTS:  
- Chronological data points for trend analysis
- Use consistent time intervals
- Values should show progression over time
- Include sufficient data points for trend visibility
""",
            ChartType.PIE_CHART: """
PIE CHART DATA REQUIREMENTS:
- Values represent parts of a whole
- All values should be positive
- Categories should be mutually exclusive
- Include percentage or count breakdowns
""",
            ChartType.DEMOGRAPHIC: """
DEMOGRAPHIC DATA REQUIREMENTS:
- Use standard demographic categories
- Percentages should sum to 100% within each group
- Age ranges: 18-24, 25-34, 35-44, 45-54, 55-64
- Gender: M (Male), F (Female)
""",
        }

        return instructions_map.get(requirement.chart_type, "")

    def _build_output_template(self, requirement: DataRequirement) -> str:
        """Build exact JSON output template"""
        template = json.dumps(requirement.data_structure_template, indent=2, ensure_ascii=False)

        # Add example if available
        if requirement.example_response:
            example = json.dumps(requirement.example_response, indent=2, ensure_ascii=False)
            template += f"\n\nEXAMPLE OUTPUT:\n{example}"

        return template

    def _build_validation_section(self, requirement: DataRequirement) -> str:
        """Build validation requirements section"""

        validation_text = "MANDATORY VALIDATION REQUIREMENTS:\n"

        for rule in requirement.validation_rules:
            if rule.rule_type == "required":
                validation_text += f"✓ Field '{rule.field_path}' must be present\n"
            elif rule.rule_type == "numeric":
                validation_text += f"✓ Field '{rule.field_path}' must be numeric (int/float)\n"
            elif rule.rule_type == "pattern":
                validation_text += f"✓ Field '{rule.field_path}' must match pattern: {rule.rule_value}\n"
            elif rule.rule_type == "range":
                min_val, max_val = rule.rule_value
                validation_text += f"✓ Field '{rule.field_path}' must be between {min_val} and {max_val}\n"

        if requirement.expected_data_size:
            min_size = requirement.expected_data_size.get("min", 0)
            max_size = requirement.expected_data_size.get("max", "unlimited")
            validation_text += f"✓ structured_data must contain {min_size}-{max_size} entries\n"

        return validation_text

    def _build_transformation_section(self, requirement: DataRequirement) -> str:
        """Build transformation hints section"""

        if not requirement.transformation_hints:
            return ""

        hints_text = "DATA TRANSFORMATION REQUIREMENTS:\n"
        for hint in requirement.transformation_hints:
            hints_text += f"• {hint}\n"

        return hints_text

    def get_fallback_prompt(self, data_type: str, original_response: str, errors: list) -> str:
        """Build fallback prompt when initial response fails validation"""

        requirement = self.registry.get(data_type)
        if not requirement:
            return ""

        error_text = "\n".join([f"- {error}" for error in errors])

        return f"""
RESPONSE CORRECTION REQUIRED

Your previous response had these validation errors:
{error_text}

ORIGINAL RESPONSE:
{original_response}

CORRECTION INSTRUCTIONS:
1. Fix the specific errors listed above
2. Ensure output matches the EXACT template structure
3. Convert all string numbers to actual numeric values
4. Add any missing required fields
5. Verify JSON syntax is valid

REQUIRED OUTPUT TEMPLATE:
{json.dumps(requirement.data_structure_template, indent=2)}

CORRECTED RESPONSE (JSON only):
"""

    def get_supported_data_types(self) -> Dict[str, str]:
        """Get mapping of supported data types to chart types"""
        return {data_type: req.chart_type.value for data_type, req in self.registry.items()}


# Specific prompt templates for each data type
RIGID_PROMPT_TEMPLATES = {
    "monthly sales over time": """
MONTHLY SALES TIME SERIES DATA EXTRACTION

CRITICAL OUTPUT FORMAT:
{{
    "structured_data": {{
        "Jan": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Feb": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Mar": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Apr": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "May": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Jun": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Jul": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Aug": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Sep": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Oct": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Nov": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}},
        "Dec": {{"2022": numeric_value, "2023": numeric_value, "2024": numeric_value}}
    }},
    "paragraph": "Comprehensive analysis of monthly sales trends, highlighting seasonal patterns, year-over-year growth, peak performance periods, and business insights."
}}

MANDATORY REQUIREMENTS:
- Month names: EXACTLY "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"  
- Years: EXACTLY "2022", "2023", "2024" (strings for consistency)
- Values: Numbers only (int/float), never strings like "45"
- Missing data: Use 0, never null
- Paragraph: Minimum 80 characters of analytical content
""",
    "monthly orders by user type": """
USER TYPE ORDERS STACKED DATA EXTRACTION

CRITICAL OUTPUT FORMAT:
{{
    "structured_data": {{
        "Oct-22": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}},
        "Nov-22": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}},
        "Dec-22": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}},
        "Jan-23": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}},
        "Feb-23": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}},
        "Mar-23": {{"Network": numeric_value, "Returning": numeric_value, "New": numeric_value}}
    }},
    "paragraph": "Analysis of user type distribution across order periods, showing Network user dominance, returning customer patterns, and new user acquisition trends."
}}

MANDATORY REQUIREMENTS:
- Date format: EXACTLY "MMM-YY" (e.g., "Oct-22", "Nov-22")
- User types: EXACTLY "Network", "Returning", "New" (exact spelling)
- Values: Integer counts >= 0
- Include at least 6 months of data
- Paragraph must explain user type dynamics and trends
""",
    "scalapay users demographic in percentages": """
DEMOGRAPHIC PERCENTAGE BREAKDOWN EXTRACTION

CRITICAL OUTPUT FORMAT:
{{
    "structured_data": {{
        "Age in percentages": {{
            "18-24": numeric_value,
            "25-34": numeric_value,
            "35-44": numeric_value,
            "45-54": numeric_value,
            "55-64": numeric_value
        }},
        "Gender in percentages": {{
            "M": numeric_value,
            "F": numeric_value
        }},
        "Card type in percentages": {{
            "credit": numeric_value,
            "debit": numeric_value,
            "prepaid": numeric_value
        }}
    }},
    "paragraph": "Demographic analysis revealing user age distribution, gender composition, and card type preferences, with insights into target market characteristics."
}}

MANDATORY REQUIREMENTS:
- Age categories: EXACTLY "18-24", "25-34", "35-44", "45-54", "55-64"
- Gender categories: EXACTLY "M", "F" 
- Card types: EXACTLY "credit", "debit", "prepaid"
- Percentages: Integer values that sum to 100 within each category
- All three demographic categories must be present
""",
    "AOV": """
AVERAGE ORDER VALUE TREND EXTRACTION

CRITICAL OUTPUT FORMAT:
{{
    "structured_data": {{
        "2023-01": numeric_value,
        "2023-02": numeric_value,
        "2023-03": numeric_value,
        "2023-04": numeric_value,
        "2023-05": numeric_value,
        "2023-06": numeric_value,
        "2023-07": numeric_value,
        "2023-08": numeric_value,
        "2023-09": numeric_value,
        "2023-10": numeric_value,
        "2023-11": numeric_value,
        "2023-12": numeric_value,
        "2024-01": numeric_value,
        "2024-02": numeric_value,
        "2024-03": numeric_value,
        "2024-04": numeric_value,
        "2024-05": numeric_value,
        "2024-06": numeric_value
    }},
    "paragraph": "Average Order Value trend analysis showing monthly progression, seasonal variations, customer spending patterns, and value optimization opportunities."
}}

MANDATORY REQUIREMENTS:
- Date format: EXACTLY "YYYY-MM" (e.g., "2023-01", "2024-02")
- Values: Float numbers with 2 decimal places representing currency amounts
- Include at least 12 months of chronological data
- Paragraph must analyze AOV trends and business implications
""",
}


# Global prompt builder instance
alfred_prompt_builder = AlfredPromptBuilder()
