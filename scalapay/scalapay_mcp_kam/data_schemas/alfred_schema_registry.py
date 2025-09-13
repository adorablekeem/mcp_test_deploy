"""
Alfred Data Schema Registry - Rigid data gathering logic implementation
Based on workflow analysis and optimization plan for consistent Alfred responses.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class ChartType(Enum):
    """Chart types supported by the system"""

    TIME_SERIES = "time_series"
    BAR_CHART = "bar"
    STACKED_BAR = "stacked_bar"
    LINE_CHART = "line"
    PIE_CHART = "pie"
    DEMOGRAPHIC = "demographic"
    COMPARISON = "comparison"


class DataFormat(Enum):
    """Expected data format patterns"""

    MONTH_YEAR_VALUE = "month_year_value"  # {"Jan": {"2023": 45, "2024": 67}}
    MONTH_CATEGORIES = "month_categories"  # {"Oct-22": {"Network": 162, "Returning": 18}}
    CATEGORY_PERCENTAGE = "category_percentage"  # {"18-24": 2, "25-34": 6}
    TIME_VALUE = "time_value"  # {"2023-01": 45.6, "2023-02": 52.1}
    NESTED_CATEGORIES = "nested_categories"  # {"Age %": {"18-24": 2}, "Gender %": {"M": 3}}


@dataclass
class ValidationRule:
    """Individual validation rule for data fields"""

    field_path: str
    rule_type: str  # "required", "numeric", "range", "pattern", "enum"
    rule_value: Any = None
    error_message: str = ""

    def validate(self, data: Dict[str, Any]) -> tuple[bool, str]:
        """Execute validation rule on data"""
        try:
            value = self._get_nested_value(data, self.field_path)

            if self.rule_type == "required":
                if value is None:
                    return False, f"Required field missing: {self.field_path}"

            elif self.rule_type == "numeric":
                if not isinstance(value, (int, float)):
                    return False, f"Field {self.field_path} must be numeric, got {type(value).__name__}"

            elif self.rule_type == "range":
                min_val, max_val = self.rule_value
                if not (min_val <= value <= max_val):
                    return False, f"Field {self.field_path} must be between {min_val} and {max_val}"

            elif self.rule_type == "pattern":
                if not re.match(self.rule_value, str(value)):
                    return False, f"Field {self.field_path} doesn't match pattern {self.rule_value}"

            elif self.rule_type == "enum":
                if value not in self.rule_value:
                    return False, f"Field {self.field_path} must be one of {self.rule_value}"

            return True, ""
        except Exception as e:
            return False, f"Validation error for {self.field_path}: {str(e)}"

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested dictionary value by dot-separated path"""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current


@dataclass
class DataRequirement:
    """Complete data requirement specification for a data type"""

    data_type: str
    chart_type: ChartType
    data_format: DataFormat
    required_fields: List[str]
    data_structure_template: Dict[str, Any]
    validation_rules: List[ValidationRule]
    fallback_schema: Dict[str, Any] = field(default_factory=dict)
    expected_data_size: Dict[str, int] = field(default_factory=dict)  # min/max entries
    transformation_hints: List[str] = field(default_factory=list)
    example_response: Dict[str, Any] = field(default_factory=dict)

    def validate_response(self, response: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate Alfred response against this requirement"""
        errors = []

        # Check required fields
        for field in self.required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")

        # Run validation rules
        for rule in self.validation_rules:
            is_valid, error_msg = rule.validate(response)
            if not is_valid:
                errors.append(error_msg)

        # Check data size constraints
        if "structured_data" in response and self.expected_data_size:
            data = response["structured_data"]
            if isinstance(data, dict):
                data_count = len(data)
                min_size = self.expected_data_size.get("min", 0)
                max_size = self.expected_data_size.get("max", float("inf"))

                if data_count < min_size:
                    errors.append(f"Insufficient data entries: got {data_count}, need at least {min_size}")
                if data_count > max_size:
                    errors.append(f"Too many data entries: got {data_count}, maximum {max_size}")

        return len(errors) == 0, errors

    def apply_fallback_schema(self, partial_response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply fallback schema to incomplete response"""
        fallback_response = self.fallback_schema.copy()

        # Merge any valid data from partial response
        for key, value in partial_response.items():
            if key in self.required_fields and value is not None:
                fallback_response[key] = value

        return fallback_response


# Comprehensive Alfred Data Requirements Registry
ALFRED_DATA_REQUIREMENTS: Dict[str, DataRequirement] = {
    "monthly sales over time": DataRequirement(
        data_type="monthly sales over time",
        chart_type=ChartType.BAR_CHART,
        data_format=DataFormat.MONTH_YEAR_VALUE,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Jan": {"2022": 0, "2023": 0, "2024": 0},
                "Feb": {"2022": 0, "2023": 0, "2024": 0},
                "Mar": {"2022": 0, "2023": 0, "2024": 0},
                "Apr": {"2022": 0, "2023": 0, "2024": 0},
                "May": {"2022": 0, "2023": 0, "2024": 0},
                "Jun": {"2022": 0, "2023": 0, "2024": 0},
                "Jul": {"2022": 0, "2023": 0, "2024": 0},
                "Aug": {"2022": 0, "2023": 0, "2024": 0},
                "Sep": {"2022": 0, "2023": 0, "2024": 0},
                "Oct": {"2022": 0, "2023": 0, "2024": 0},
                "Nov": {"2022": 0, "2023": 0, "2024": 0},
                "Dec": {"2022": 0, "2023": 0, "2024": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
            ValidationRule("paragraph", "pattern", r".{20,}", "Paragraph must be at least 20 characters"),
        ],
        expected_data_size={"min": 8, "max": 15},  # 8-15 months of data
        transformation_hints=[
            "Ensure all numeric values are integers or floats, not strings",
            "Month names should be 3-letter abbreviations: Jan, Feb, Mar, etc.",
            "Years should be 4-digit integers: 2022, 2023, 2024",
            "Missing months should have 0 values, not null",
        ],
        fallback_schema={
            "structured_data": {
                "Jan": {"2023": 0, "2024": 0},
                "Feb": {"2023": 0, "2024": 0},
                "Mar": {"2023": 0, "2024": 0},
            },
            "paragraph": "Sales data analysis unavailable.",
        },
        example_response={
            "structured_data": {
                "Jan": {"2022": 34, "2023": 66, "2024": 38},
                "Feb": {"2022": 31, "2023": 87, "2024": 139},
                "Mar": {"2022": 41, "2023": 45, "2024": 67},
            },
            "paragraph": "Monthly sales show seasonal patterns with February peak performance...",
        },
    ),
    "monthly sales year over year": DataRequirement(
        data_type="monthly sales year over year",
        chart_type=ChartType.BAR_CHART,
        data_format=DataFormat.MONTH_YEAR_VALUE,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Jan": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Feb": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Mar": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Apr": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "May": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Jun": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Jul": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Aug": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Sep": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Oct": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Nov": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
                "Dec": {"2022": 0, "2023": 0, "2024": 0, "2025": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 10, "max": 15},
        transformation_hints=[
            "Include year-over-year comparison in paragraph",
            "Highlight growth trends and seasonal patterns",
            "All values must be numeric (int/float)",
        ],
        fallback_schema={
            "structured_data": {"Jan": {"2023": 0, "2024": 0}, "Feb": {"2023": 0, "2024": 0}},
            "paragraph": "Year-over-year sales analysis unavailable.",
        },
    ),
    "monthly orders by user type": DataRequirement(
        data_type="monthly orders by user type",
        chart_type=ChartType.STACKED_BAR,
        data_format=DataFormat.MONTH_CATEGORIES,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Oct-22": {"Network": 0, "Returning": 0, "New": 0},
                "Nov-22": {"Network": 0, "Returning": 0, "New": 0},
                "Dec-22": {"Network": 0, "Returning": 0, "New": 0},
                "Jan-23": {"Network": 0, "Returning": 0, "New": 0},
                "Feb-23": {"Network": 0, "Returning": 0, "New": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 6, "max": 24},  # 6 months to 2 years of data
        transformation_hints=[
            "Date format: MMM-YY (e.g., Oct-22, Nov-22)",
            "User types: Network, Returning, New (exact spelling)",
            "All order counts must be integers >= 0",
        ],
        fallback_schema={
            "structured_data": {
                "Jan-24": {"Network": 0, "Returning": 0, "New": 0},
                "Feb-24": {"Network": 0, "Returning": 0, "New": 0},
            },
            "paragraph": "User type order analysis unavailable.",
        },
        example_response={
            "structured_data": {
                "Oct-22": {"Network": 162, "Returning": 18, "New": 6},
                "Nov-22": {"Network": 186, "Returning": 31, "New": 9},
                "Dec-22": {"Network": 203, "Returning": 42, "New": 15},
            },
            "paragraph": "Network users consistently represent the majority of orders...",
        },
    ),
    "scalapay users demographic": DataRequirement(
        data_type="scalapay users demographic",
        chart_type=ChartType.PIE_CHART,
        data_format=DataFormat.NESTED_CATEGORIES,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Age in percentages": {"18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55-64": 0},
                "Gender in percentages": {"M": 0, "F": 0},
                "Card type in percentages": {"credit": 0, "debit": 0, "prepaid": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
            ValidationRule("structured_data.Age in percentages", "required"),
            ValidationRule("structured_data.Gender in percentages", "required"),
        ],
        expected_data_size={"min": 2, "max": 4},  # 2-4 demographic categories
        transformation_hints=[
            "All percentages must sum to 100 within each category",
            "Age ranges: 18-24, 25-34, 35-44, 45-54, 55-64",
            "Gender: M (Male), F (Female)",
            "Card types: credit, debit, prepaid",
        ],
        fallback_schema={
            "structured_data": {
                "Age in percentages": {"25-34": 30, "35-44": 40, "45-54": 30},
                "Gender in percentages": {"M": 20, "F": 80},
            },
            "paragraph": "Demographic analysis unavailable.",
        },
    ),
    "scalapay users demographic in percentages": DataRequirement(
        data_type="scalapay users demographic in percentages",
        chart_type=ChartType.PIE_CHART,
        data_format=DataFormat.NESTED_CATEGORIES,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Age in percentages": {"18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55-64": 0},
                "Gender in percentages": {"M": 0, "F": 0},
                "Card type in percentages": {"credit": 0, "debit": 0, "prepaid": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
            ValidationRule("structured_data.Age in percentages", "required"),
            ValidationRule("structured_data.Gender in percentages", "required"),
        ],
        expected_data_size={"min": 2, "max": 4},
        transformation_hints=[
            "Percentages should be integers between 0-100",
            "Each category should sum to 100%",
            "Use standard age brackets and gender categories",
        ],
        fallback_schema={
            "structured_data": {
                "Age in percentages": {"25-34": 35, "35-44": 45, "45-54": 20},
                "Gender in percentages": {"M": 15, "F": 85},
            },
            "paragraph": "User demographic breakdown unavailable.",
        },
    ),
    "AOV": DataRequirement(
        data_type="AOV",
        chart_type=ChartType.LINE_CHART,
        data_format=DataFormat.TIME_VALUE,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "2023-01": 0.0,
                "2023-02": 0.0,
                "2023-03": 0.0,
                "2023-04": 0.0,
                "2023-05": 0.0,
                "2023-06": 0.0,
                "2024-01": 0.0,
                "2024-02": 0.0,
                "2024-03": 0.0,
                "2024-04": 0.0,
                "2024-05": 0.0,
                "2024-06": 0.0,
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 6, "max": 36},  # 6 months to 3 years
        transformation_hints=[
            "Date format: YYYY-MM (e.g., 2023-01, 2024-02)",
            "AOV values should be float with 2 decimal places",
            "Include currency analysis in paragraph",
        ],
        fallback_schema={
            "structured_data": {"2024-01": 45.67, "2024-02": 48.23, "2024-03": 46.89},
            "paragraph": "Average Order Value trend analysis unavailable.",
        },
    ),
    "monthly sales by product type over time": DataRequirement(
        data_type="monthly sales by product type over time",
        chart_type=ChartType.STACKED_BAR,
        data_format=DataFormat.MONTH_CATEGORIES,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={
            "structured_data": {
                "Jan-23": {"Pay in 3": 0, "Pay in 4": 0},
                "Feb-23": {"Pay in 3": 0, "Pay in 4": 0},
                "Mar-23": {"Pay in 3": 0, "Pay in 4": 0},
                "Apr-23": {"Pay in 3": 0, "Pay in 4": 0},
                "May-23": {"Pay in 3": 0, "Pay in 4": 0},
                "Jun-23": {"Pay in 3": 0, "Pay in 4": 0},
            },
            "paragraph": "string",
        },
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 6, "max": 24},
        transformation_hints=[
            "Product types: 'Pay in 3', 'Pay in 4' (exact spelling)",
            "Date format: MMM-YY",
            "Sales values should be numeric",
        ],
        fallback_schema={
            "structured_data": {"Jan-24": {"Pay in 3": 0, "Pay in 4": 0}, "Feb-24": {"Pay in 3": 0, "Pay in 4": 0}},
            "paragraph": "Product type sales analysis unavailable.",
        },
    ),
    "orders by product type (i.e. pay in 3, pay in 4)": DataRequirement(
        data_type="orders by product type (i.e. pay in 3, pay in 4)",
        chart_type=ChartType.PIE_CHART,
        data_format=DataFormat.CATEGORY_PERCENTAGE,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={"structured_data": {"Pay in 3": 0, "Pay in 4": 0}, "paragraph": "string"},
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 2, "max": 3},
        transformation_hints=[
            "Product types: 'Pay in 3', 'Pay in 4'",
            "Values can be counts or percentages",
            "Include total order volume in paragraph",
        ],
        fallback_schema={
            "structured_data": {"Pay in 3": 65, "Pay in 4": 35},
            "paragraph": "Product type distribution analysis unavailable.",
        },
    ),
    "AOV by product type (i.e. pay in 3, pay in 4)": DataRequirement(
        data_type="AOV by product type (i.e. pay in 3, pay in 4)",
        chart_type=ChartType.BAR_CHART,
        data_format=DataFormat.CATEGORY_PERCENTAGE,
        required_fields=["structured_data", "paragraph"],
        data_structure_template={"structured_data": {"Pay in 3": 0.0, "Pay in 4": 0.0}, "paragraph": "string"},
        validation_rules=[
            ValidationRule("structured_data", "required"),
            ValidationRule("paragraph", "required"),
        ],
        expected_data_size={"min": 2, "max": 3},
        transformation_hints=[
            "AOV values should be float with 2 decimal places",
            "Compare AOV differences between product types",
            "Include insights about customer spending behavior",
        ],
        fallback_schema={
            "structured_data": {"Pay in 3": 42.85, "Pay in 4": 67.12},
            "paragraph": "AOV by product type analysis unavailable.",
        },
    ),
}


class AlfredSchemaValidator:
    """Validator for Alfred responses using schema registry"""

    def __init__(self):
        self.registry = ALFRED_DATA_REQUIREMENTS

    def get_requirement(self, data_type: str) -> Optional[DataRequirement]:
        """Get data requirement for a data type"""
        return self.registry.get(data_type)

    def validate_response(
        self, data_type: str, response: Dict[str, Any]
    ) -> tuple[bool, List[str], Optional[Dict[str, Any]]]:
        """
        Validate Alfred response against schema requirements

        Returns:
            - is_valid: boolean
            - errors: list of error messages
            - corrected_response: response with corrections applied (if possible)
        """
        requirement = self.get_requirement(data_type)
        if not requirement:
            return False, [f"Unknown data type: {data_type}"], None

        is_valid, errors = requirement.validate_response(response)

        if not is_valid:
            # Attempt to apply corrections
            corrected_response = self._attempt_corrections(response, requirement, errors)
            return False, errors, corrected_response

        return True, [], response

    def _attempt_corrections(
        self, response: Dict[str, Any], requirement: DataRequirement, errors: List[str]
    ) -> Dict[str, Any]:
        """Attempt to correct common response issues"""
        corrected = response.copy()

        # Apply fallback schema for missing fields
        for field in requirement.required_fields:
            if field not in corrected:
                if field in requirement.fallback_schema:
                    corrected[field] = requirement.fallback_schema[field]

        # Attempt numeric conversion for structured_data
        if "structured_data" in corrected:
            corrected["structured_data"] = self._convert_to_numeric(corrected["structured_data"])

        return corrected

    def _convert_to_numeric(self, data: Any) -> Any:
        """Recursively convert string numbers to numeric values"""
        if isinstance(data, dict):
            return {k: self._convert_to_numeric(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_numeric(item) for item in data]
        elif isinstance(data, str):
            try:
                # Try integer first
                if "." not in data:
                    return int(data)
                else:
                    return float(data)
            except (ValueError, TypeError):
                return data
        else:
            return data

    def get_supported_data_types(self) -> List[str]:
        """Get list of all supported data types"""
        return list(self.registry.keys())

    def get_chart_type(self, data_type: str) -> Optional[ChartType]:
        """Get expected chart type for data type"""
        requirement = self.get_requirement(data_type)
        return requirement.chart_type if requirement else None

    def get_example_response(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Get example response for data type"""
        requirement = self.get_requirement(data_type)
        return requirement.example_response if requirement else None


# Global validator instance
alfred_validator = AlfredSchemaValidator()
