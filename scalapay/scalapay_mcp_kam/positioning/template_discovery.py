"""
Template placeholder discovery system with fallback support.
Discovers chart placeholders in Google Slides templates and maps them to chart types.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .feature_flags import get_feature_manager
from .google_api_wrapper import OperationResult, get_api_wrapper

logger = logging.getLogger(__name__)


class PlaceholderType(Enum):
    """Types of placeholders that can be discovered."""

    CHART = "chart"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class PlaceholderInfo:
    """Information about a discovered placeholder."""

    object_id: str
    page_id: str
    placeholder_text: str
    placeholder_type: PlaceholderType
    inner_text: str
    chart_type_hint: Optional[str] = None
    priority: int = 0

    # Size and position information (if available)
    current_width: Optional[float] = None
    current_height: Optional[float] = None
    current_x: Optional[float] = None
    current_y: Optional[float] = None

    # Template-specific metadata
    constraints: Dict[str, Any] = None

    def __post_init__(self):
        if self.constraints is None:
            self.constraints = {}


class ChartTypeDetector:
    """Detects chart types from placeholder text and content patterns."""

    # Chart type detection patterns (ordered by specificity)
    CHART_TYPE_PATTERNS = [
        # Specific chart types first
        (r"monthly.*sales.*year.*over.*year|sales.*yoy", "monthly_sales_yoy", 10),
        (r"monthly.*sales.*over.*time|monthly.*sales.*trend", "monthly_sales_trend", 9),
        (r"monthly.*sales.*by.*product.*type", "monthly_sales_by_product", 8),
        (r"aov.*by.*product.*type|average.*order.*value.*by.*product", "aov_by_product", 8),
        (r"orders.*by.*user.*type|monthly.*orders.*by.*user", "orders_by_user_type", 8),
        (r"orders.*by.*product.*type|orders.*by.*product", "orders_by_product_type", 8),
        (r"scalapay.*users.*demographic|users.*demographic.*percentage", "user_demographics", 8),
        # General chart types
        (r"aov(?:$|[^a-z])|average.*order.*value", "aov", 7),
        (r"monthly.*sales", "monthly_sales", 6),
        (r"monthly.*orders", "monthly_orders", 6),
        (r"demographic.*percentage|demographic.*chart", "demographics", 6),
        (r"product.*type.*chart", "product_type", 5),
        (r"user.*type.*chart", "user_type", 5),
        # Generic patterns
        (r".*sales.*", "sales_chart", 3),
        (r".*orders.*", "orders_chart", 3),
        (r".*demographic.*", "demographic_chart", 3),
        (r".*chart.*|.*graph.*|.*plot.*", "generic_chart", 1),
    ]

    @classmethod
    def detect_chart_type(cls, placeholder_text: str, inner_text: str = "") -> Tuple[str, int]:
        """
        Detect chart type from placeholder text and inner text.

        Args:
            placeholder_text: The placeholder identifier (e.g., "monthly_sales_chart")
            inner_text: The actual text content inside the placeholder

        Returns:
            Tuple of (chart_type, confidence_score)
        """

        # Combine both texts for analysis
        combined_text = f"{placeholder_text} {inner_text}".lower()

        for pattern, chart_type, priority in cls.CHART_TYPE_PATTERNS:
            if re.search(pattern, combined_text):
                logger.debug(f"Detected chart type '{chart_type}' from pattern '{pattern}' in '{combined_text}'")
                return chart_type, priority

        return "unknown", 0


class TemplatePlaceholderAnalyzer:
    """Analyzes Google Slides templates to discover and classify placeholders."""

    def __init__(self, presentation_id: str):
        self.presentation_id = presentation_id
        self.api_wrapper = get_api_wrapper()
        self.feature_manager = get_feature_manager()
        self.placeholders: Dict[str, PlaceholderInfo] = {}
        self.chart_placeholders: Dict[str, PlaceholderInfo] = {}

    def discover_all_placeholders(self, correlation_id: Optional[str] = None) -> OperationResult:
        """
        Discover all placeholders in the template.

        Returns:
            OperationResult with discovered placeholders in details
        """

        # Use API wrapper to get placeholders with fallback support
        api_result = self.api_wrapper.get_all_shapes_placeholders(self.presentation_id, correlation_id)

        if not api_result.success:
            logger.error(f"[{correlation_id}] Failed to discover placeholders: {api_result.error_message}")
            return api_result

        raw_placeholders = api_result.details.get("placeholders", {})

        # Process raw placeholders into structured format
        processed_placeholders = {}
        chart_placeholders = {}

        for object_id, info in raw_placeholders.items():
            if info and info.get("inner_text"):
                inner_text = info["inner_text"]
                page_id = info.get("page_id")

                # Determine placeholder type
                placeholder_type = self._classify_placeholder_type(inner_text)

                # Extract placeholder text (remove braces)
                placeholder_text = inner_text.strip("{}")

                # For chart placeholders, detect the chart type
                chart_type_hint = None
                priority = 0
                if placeholder_type == PlaceholderType.CHART:
                    chart_type_hint, priority = ChartTypeDetector.detect_chart_type(placeholder_text, inner_text)

                placeholder_info = PlaceholderInfo(
                    object_id=object_id,
                    page_id=page_id,
                    placeholder_text=placeholder_text,
                    placeholder_type=placeholder_type,
                    inner_text=inner_text,
                    chart_type_hint=chart_type_hint,
                    priority=priority,
                )

                processed_placeholders[placeholder_text] = placeholder_info

                if placeholder_type == PlaceholderType.CHART:
                    chart_placeholders[placeholder_text] = placeholder_info

        # Store results
        self.placeholders = processed_placeholders
        self.chart_placeholders = chart_placeholders

        # Update API result with processed information
        api_result.details.update(
            {
                "processed_placeholders": processed_placeholders,
                "chart_placeholders": chart_placeholders,
                "chart_count": len(chart_placeholders),
                "total_placeholders": len(processed_placeholders),
            }
        )

        logger.info(
            f"[{correlation_id}] Discovered {len(processed_placeholders)} total placeholders, "
            f"{len(chart_placeholders)} chart placeholders"
        )

        return api_result

    def _classify_placeholder_type(self, inner_text: str) -> PlaceholderType:
        """Classify placeholder type based on inner text."""
        inner_text_lower = inner_text.lower()

        # Chart indicators
        chart_keywords = ["chart", "graph", "plot", "visualization", "aov", "sales", "orders", "demographic"]
        if any(keyword in inner_text_lower for keyword in chart_keywords):
            return PlaceholderType.CHART

        # Text indicators
        text_keywords = ["title", "paragraph", "text", "content", "description"]
        if any(keyword in inner_text_lower for keyword in text_keywords):
            return PlaceholderType.TEXT

        # Image indicators
        image_keywords = ["image", "img", "picture", "photo"]
        if any(keyword in inner_text_lower for keyword in image_keywords):
            return PlaceholderType.IMAGE

        return PlaceholderType.UNKNOWN

    def get_chart_placeholders(self) -> Dict[str, PlaceholderInfo]:
        """Get only chart placeholders."""
        return self.chart_placeholders.copy()

    def find_placeholder_for_chart_type(
        self, chart_data_type: str, correlation_id: Optional[str] = None
    ) -> Optional[PlaceholderInfo]:
        """
        Find the best matching placeholder for a chart data type.

        Args:
            chart_data_type: The type of chart data (e.g., "monthly_sales", "aov")
            correlation_id: Request correlation ID for logging

        Returns:
            Best matching PlaceholderInfo or None if no match found
        """

        if not self.chart_placeholders:
            logger.warning(f"[{correlation_id}] No chart placeholders discovered yet")
            return None

        # Normalize chart data type for matching
        normalized_data_type = chart_data_type.lower().replace(" ", "_").replace("-", "_")

        # Try exact matches first
        for placeholder_text, placeholder_info in self.chart_placeholders.items():
            normalized_placeholder = placeholder_text.lower().replace(" ", "_").replace("-", "_")

            if normalized_data_type in normalized_placeholder or normalized_placeholder in normalized_data_type:
                logger.debug(f"[{correlation_id}] Exact match: '{chart_data_type}' -> '{placeholder_text}'")
                return placeholder_info

        # Try chart type hint matches
        best_match = None
        best_priority = -1

        for placeholder_text, placeholder_info in self.chart_placeholders.items():
            if placeholder_info.chart_type_hint:
                hint_normalized = placeholder_info.chart_type_hint.lower().replace(" ", "_").replace("-", "_")

                # Check if chart data type matches the detected type
                if (
                    normalized_data_type in hint_normalized
                    or hint_normalized in normalized_data_type
                    or self._chart_types_similar(normalized_data_type, hint_normalized)
                ):
                    if placeholder_info.priority > best_priority:
                        best_match = placeholder_info
                        best_priority = placeholder_info.priority

        if best_match:
            logger.debug(
                f"[{correlation_id}] Type hint match: '{chart_data_type}' -> '{best_match.placeholder_text}' "
                f"(hint: {best_match.chart_type_hint}, priority: {best_priority})"
            )
            return best_match

        # Fallback: return highest priority chart placeholder
        if self.chart_placeholders:
            fallback = max(self.chart_placeholders.values(), key=lambda p: p.priority)
            logger.info(
                f"[{correlation_id}] Fallback match: '{chart_data_type}' -> '{fallback.placeholder_text}' "
                f"(priority: {fallback.priority})"
            )
            return fallback

        logger.warning(f"[{correlation_id}] No suitable placeholder found for chart type: {chart_data_type}")
        return None

    def _chart_types_similar(self, type1: str, type2: str) -> bool:
        """Check if two chart types are similar enough to match."""

        # Define similar chart type groups
        similarity_groups = [
            {"monthly_sales", "sales_chart", "monthly_sales_trend", "monthly_sales_yoy"},
            {"aov", "average_order_value", "aov_by_product"},
            {"orders", "orders_chart", "monthly_orders", "orders_by_user_type", "orders_by_product_type"},
            {"demographics", "demographic_chart", "user_demographics"},
            {"product_type", "orders_by_product_type", "aov_by_product"},
            {"user_type", "orders_by_user_type"},
        ]

        for group in similarity_groups:
            if type1 in group and type2 in group:
                return True

        return False


class ChartPlaceholderMapper:
    """Maps chart data types to discovered template placeholders."""

    def __init__(self, analyzer: TemplatePlaceholderAnalyzer):
        self.analyzer = analyzer
        self.mappings: Dict[str, PlaceholderInfo] = {}  # Cache mappings

    def get_mapping_for_charts(
        self, chart_data_types: List[str], correlation_id: Optional[str] = None
    ) -> Dict[str, Optional[PlaceholderInfo]]:
        """
        Get placeholder mappings for multiple chart data types.

        Args:
            chart_data_types: List of chart data type strings
            correlation_id: Request correlation ID for logging

        Returns:
            Dictionary mapping chart_data_type -> PlaceholderInfo (or None if no match)
        """

        mappings = {}
        used_placeholders = set()  # Track to avoid conflicts

        # Sort chart types by priority (more specific types first)
        sorted_types = sorted(chart_data_types, key=lambda dt: self._get_chart_type_priority(dt), reverse=True)

        for chart_data_type in sorted_types:
            # Check cache first
            if chart_data_type in self.mappings:
                cached_placeholder = self.mappings[chart_data_type]

                # Only use cached if not already assigned to another chart
                if cached_placeholder and cached_placeholder.object_id not in used_placeholders:
                    mappings[chart_data_type] = cached_placeholder
                    used_placeholders.add(cached_placeholder.object_id)
                    continue

            # Find new mapping
            placeholder = self.analyzer.find_placeholder_for_chart_type(chart_data_type, correlation_id)

            # Only use if not already assigned
            if placeholder and placeholder.object_id not in used_placeholders:
                mappings[chart_data_type] = placeholder
                used_placeholders.add(placeholder.object_id)
                self.mappings[chart_data_type] = placeholder  # Cache for future use
            else:
                mappings[chart_data_type] = None
                logger.warning(
                    f"[{correlation_id}] No available placeholder for '{chart_data_type}' "
                    f"(found but already used: {placeholder is not None})"
                )

        logger.info(
            f"[{correlation_id}] Mapped {sum(1 for p in mappings.values() if p is not None)} "
            f"out of {len(chart_data_types)} chart types to placeholders"
        )

        return mappings

    def _get_chart_type_priority(self, chart_data_type: str) -> int:
        """Get priority score for chart data type (higher = more specific)."""

        # Prioritize more specific chart types
        specific_patterns = [
            ("monthly.*sales.*year.*over.*year", 10),
            ("aov.*by.*product.*type", 9),
            ("orders.*by.*user.*type", 9),
            ("orders.*by.*product.*type", 9),
            ("scalapay.*users.*demographic", 9),
            ("monthly.*sales.*over.*time", 8),
            ("aov", 7),
            ("monthly.*sales", 6),
            ("monthly.*orders", 6),
            ("demographic", 5),
        ]

        data_type_lower = chart_data_type.lower()

        for pattern, priority in specific_patterns:
            if re.search(pattern, data_type_lower):
                return priority

        return 1  # Default priority
