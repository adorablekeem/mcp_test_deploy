"""
Unified Alfred Data Processing Pipeline
Consolidates all data processing logic for consistent behavior across sequential and concurrent modes.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from ..agents.agent_alfred_rigid import RigidAlfredAgent, mcp_tool_run_rigid
from ..agents.agent_matplot_rigid_integrated import mcp_matplot_run_rigid_integrated
from ..data_schemas.alfred_schema_registry import DataRequirement, alfred_validator
from ..prompts.alfred_rigid_prompts import alfred_prompt_builder
from ..utils.concurrency_utils import ConcurrencyManager, create_correlation_id

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for Alfred data processing pipeline"""

    # Validation settings
    max_validation_retries: int = 3
    enable_fallback: bool = True
    strict_mode: bool = True

    # Concurrency settings
    batch_size: int = 3
    max_concurrent_batches: int = 2
    enable_concurrent_processing: bool = True

    # Processing settings
    enable_data_normalization: bool = True
    enable_schema_enforcement: bool = True
    enable_retry_logic: bool = True

    # Monitoring settings
    enable_metrics_collection: bool = True
    log_validation_details: bool = True

    # Compatibility settings
    maintain_backward_compatibility: bool = True
    legacy_fallback_enabled: bool = False

    # Chart generation settings
    enable_integrated_chart_generation: bool = True
    chart_generation_timeout: int = 300  # 5 minutes per chart


@dataclass
class ProcessingResult:
    """Result of pipeline processing"""

    data_type: str
    success: bool
    alfred_raw: Optional[Dict[str, Any]] = None
    slides_struct: Optional[Dict[str, Any]] = None
    normalized_months: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = field(default_factory=list)
    processing_metadata: Dict[str, Any] = field(default_factory=dict)
    chart_type: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class PipelineMetrics:
    """Comprehensive pipeline metrics"""

    total_requests: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    fallback_used: int = 0
    retry_attempts: int = 0
    processing_time: float = 0.0
    schema_enforcement_rate: float = 0.0
    data_consistency_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "fallback_used": self.fallback_used,
            "retry_attempts": self.retry_attempts,
            "processing_time": self.processing_time,
            "success_rate": self.successful_validations / self.total_requests if self.total_requests > 0 else 0.0,
            "schema_enforcement_rate": self.schema_enforcement_rate,
            "data_consistency_score": self.data_consistency_score,
        }


class AlfredDataPipeline:
    """Unified data processing pipeline for Alfred responses"""

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.validator = alfred_validator
        self.prompt_builder = alfred_prompt_builder
        self.metrics = PipelineMetrics()
        self.start_time = None

    async def process_data_requests(
        self,
        requests_list: List[str],
        merchant_token: str,
        starting_date: str,
        end_date: str,
        correlation_id: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Main pipeline entry point for processing multiple data requests.

        This method provides a unified interface that:
        1. Validates all requested data types
        2. Processes requests using rigid validation
        3. Applies data normalization and standardization
        4. Returns consistently formatted results
        """

        corr_id = correlation_id or create_correlation_id()
        self.start_time = time.time()

        logger.info(f"[{corr_id}] Starting unified Alfred pipeline for {len(requests_list)} requests")

        # Phase 1: Request Validation
        validated_requests, validation_errors = self._validate_requests(requests_list, corr_id)

        if not validated_requests and self.config.strict_mode:
            return self._build_error_response("No valid data types in request list", validation_errors, corr_id)

        # Phase 2: Data Retrieval with Rigid Validation
        raw_results = await self._retrieve_data_with_validation(
            validated_requests, merchant_token, starting_date, end_date, corr_id
        )

        # Phase 3: Data Processing and Normalization
        processed_results = await self._process_and_normalize_data(raw_results, corr_id)

        # Phase 4: Chart Generation with Rigid Integration
        processed_results = await self._generate_charts_with_rigid_integration(processed_results, corr_id)

        # Phase 5: Quality Assurance and Metrics Collection
        final_results = self._apply_quality_assurance(processed_results, corr_id)

        # Phase 6: Response Assembly
        return self._assemble_final_response(final_results, corr_id)

    async def _generate_charts_with_rigid_integration(
        self, processed_results: Dict[str, ProcessingResult], correlation_id: str
    ) -> Dict[str, ProcessingResult]:
        """Generate charts using the rigid-integrated plotting system."""

        if not self.config.enable_integrated_chart_generation:
            logger.info(f"[{correlation_id}] Chart generation disabled, skipping")
            return processed_results

        logger.info(f"[{correlation_id}] Starting rigid-integrated chart generation")

        # Build results dict in format expected by mcp_matplot_run
        chart_input = {}
        for data_type, result in processed_results.items():
            if result.success and result.slides_struct:
                chart_input[data_type] = {
                    "slides_struct": result.slides_struct,
                    "alfred_raw": result.alfred_raw,
                    "processing_metadata": result.processing_metadata,
                    "chart_type": result.chart_type,
                    "schema_version": result.schema_version,
                    "errors": result.validation_errors,
                }

        if not chart_input:
            logger.warning(f"[{correlation_id}] No data available for chart generation")
            return processed_results

        try:
            # Generate charts using rigid-integrated system
            chart_results = await mcp_matplot_run_rigid_integrated(
                results_dict=chart_input, verbose=self.config.log_validation_details
            )

            # Update processed results with chart paths
            charts_generated = 0
            for data_type, chart_result in chart_results.items():
                if data_type in processed_results:
                    result = processed_results[data_type]

                    # Add chart information to processing metadata
                    if "chart_path" in chart_result:
                        result.processing_metadata["chart_path"] = chart_result["chart_path"]
                        result.processing_metadata["chart_generated"] = True
                        charts_generated += 1
                    else:
                        result.processing_metadata["chart_generated"] = False

                    # Add any chart generation errors
                    if chart_result.get("errors"):
                        result.validation_errors.extend(chart_result["errors"])
                        result.processing_metadata["chart_errors"] = chart_result["errors"]

            logger.info(f"[{correlation_id}] Generated {charts_generated}/{len(chart_input)} charts successfully")

        except Exception as e:
            logger.error(f"[{correlation_id}] Chart generation failed: {e}")
            # Add chart generation failure to all results
            for result in processed_results.values():
                result.processing_metadata["chart_generation_error"] = str(e)
                result.processing_metadata["chart_generated"] = False

        return processed_results

    def _validate_requests(self, requests_list: List[str], correlation_id: str) -> Tuple[List[str], List[str]]:
        """Validate all requested data types against schema registry"""

        validated_requests = []
        validation_errors = []

        for data_type in requests_list:
            requirement = self.validator.get_requirement(data_type)
            if requirement:
                validated_requests.append(data_type)
                logger.debug(f"[{correlation_id}] Validated data type: {data_type}")
            else:
                error_msg = f"Unsupported data type: {data_type}"
                validation_errors.append(error_msg)
                logger.warning(f"[{correlation_id}] {error_msg}")

        logger.info(f"[{correlation_id}] Validated {len(validated_requests)}/{len(requests_list)} data types")

        return validated_requests, validation_errors

    async def _retrieve_data_with_validation(
        self, requests_list: List[str], merchant_token: str, starting_date: str, end_date: str, correlation_id: str
    ) -> Dict[str, Any]:
        """Retrieve data using rigid Alfred agent with comprehensive validation"""

        logger.info(f"[{correlation_id}] Starting rigid data retrieval for {len(requests_list)} requests")

        if self.config.enable_concurrent_processing:
            # Use concurrent rigid processing
            results = await mcp_tool_run_rigid(
                requests_list=requests_list,
                merchant_token=merchant_token,
                starting_date=starting_date,
                end_date=end_date,
                batch_size=self.config.batch_size,
                max_concurrent_batches=self.config.max_concurrent_batches,
                max_validation_retries=self.config.max_validation_retries,
                enable_fallback=self.config.enable_fallback,
                strict_mode=self.config.strict_mode,
            )
        else:
            # Use sequential rigid processing
            rigid_agent = RigidAlfredAgent(
                max_validation_retries=self.config.max_validation_retries,
                enable_fallback=self.config.enable_fallback,
                strict_mode=self.config.strict_mode,
            )

            results = {}
            for data_type in requests_list:
                result = await rigid_agent.process_data_request(
                    data_type, merchant_token, starting_date, end_date, f"{correlation_id}_{data_type}"
                )
                results[data_type] = result

        # Update metrics from processing results
        if "__processing_summary__" in results:
            summary = results["__processing_summary__"]
            self.metrics.total_requests = summary["total_requests"]
            self.metrics.successful_validations = summary["successful_requests"]
            self.metrics.failed_validations = summary["failed_requests"]

            validation_metrics = summary.get("validation_metrics", {})
            self.metrics.retry_attempts = validation_metrics.get("retry_attempts", 0)
            self.metrics.fallback_used = validation_metrics.get("fallback_used", 0)

        logger.info(f"[{correlation_id}] Completed rigid data retrieval")

        return results

    async def _process_and_normalize_data(
        self, raw_results: Dict[str, Any], correlation_id: str
    ) -> Dict[str, ProcessingResult]:
        """Process and normalize data from Alfred responses"""

        logger.info(f"[{correlation_id}] Starting data processing and normalization")

        processed_results = {}

        for data_type, raw_result in raw_results.items():
            if data_type.startswith("__"):  # Skip metadata entries
                continue

            try:
                # Get data requirement for normalization rules
                requirement = self.validator.get_requirement(data_type)

                # Extract core data
                alfred_raw = raw_result.get("alfred_raw", {})
                slides_struct = raw_result.get("slides_struct", {})
                validation_result = raw_result.get("validation_result")

                # Apply data normalization if enabled
                normalized_data = alfred_raw
                normalized_months = None

                if self.config.enable_data_normalization and requirement:
                    normalized_data, normalized_months = self._normalize_data_structure(
                        alfred_raw, requirement, correlation_id
                    )

                # Build processing result
                processing_result = ProcessingResult(
                    data_type=data_type,
                    success=raw_result.get("processing_success", False),
                    alfred_raw=alfred_raw,
                    slides_struct=normalized_data,  # Use normalized data for slides
                    normalized_months=normalized_months,
                    validation_errors=raw_result.get("errors", []),
                    processing_metadata={
                        "validation_attempts": getattr(validation_result, "validation_attempts", 1)
                        if validation_result
                        else 1,
                        "fallback_used": raw_result.get("processing_success", True) == False and alfred_raw,
                        "schema_enforced": self.config.enable_schema_enforcement,
                        "processing_timestamp": datetime.now().isoformat(),
                    },
                    chart_type=requirement.chart_type.value if requirement else "unknown",
                    schema_version=f"v1.0_{requirement.data_format.value}" if requirement else "unknown",
                )

                processed_results[data_type] = processing_result

                logger.debug(f"[{correlation_id}] Processed data type: {data_type}")

            except Exception as e:
                logger.error(f"[{correlation_id}] Processing failed for {data_type}: {str(e)}")

                processed_results[data_type] = ProcessingResult(
                    data_type=data_type,
                    success=False,
                    validation_errors=[f"Processing error: {str(e)}"],
                    processing_metadata={
                        "processing_error": str(e),
                        "processing_timestamp": datetime.now().isoformat(),
                    },
                )

        logger.info(f"[{correlation_id}] Completed data processing for {len(processed_results)} results")

        return processed_results

    def _normalize_data_structure(
        self, data: Dict[str, Any], requirement: DataRequirement, correlation_id: str
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Apply data normalization based on schema requirements"""

        normalized_data = data.copy()
        normalized_months = None

        try:
            # Apply chart-type specific normalization
            if requirement.chart_type.name == "TIME_SERIES":
                normalized_months = self._normalize_time_series_data(data, correlation_id)
            elif requirement.chart_type.name == "STACKED_BAR":
                normalized_data = self._normalize_stacked_bar_data(data, correlation_id)
            elif requirement.chart_type.name == "PIE_CHART":
                normalized_data = self._normalize_pie_chart_data(data, correlation_id)
            elif requirement.chart_type.name == "LINE_CHART":
                normalized_data = self._normalize_line_chart_data(data, correlation_id)

            # Apply transformation hints
            for hint in requirement.transformation_hints:
                normalized_data = self._apply_transformation_hint(normalized_data, hint, correlation_id)

        except Exception as e:
            logger.warning(f"[{correlation_id}] Normalization failed: {str(e)}")

        return normalized_data, normalized_months

    def _normalize_time_series_data(self, data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Normalize time series data for consistent month handling"""

        structured_data = data.get("structured_data", {})
        if not structured_data:
            return {}

        # Standardize month names to 3-letter abbreviations
        month_mapping = {
            "January": "Jan",
            "February": "Feb",
            "March": "Mar",
            "April": "Apr",
            "May": "May",
            "June": "Jun",
            "July": "Jul",
            "August": "Aug",
            "September": "Sep",
            "October": "Oct",
            "November": "Nov",
            "December": "Dec",
        }

        normalized_months = {}
        for month, values in structured_data.items():
            normalized_month = month_mapping.get(month, month)
            if isinstance(values, dict):
                # Ensure all year values are numeric
                normalized_values = {}
                for year, value in values.items():
                    try:
                        normalized_values[str(year)] = float(value) if value != 0 else 0
                    except (ValueError, TypeError):
                        normalized_values[str(year)] = 0
                normalized_months[normalized_month] = normalized_values
            else:
                normalized_months[normalized_month] = values

        return normalized_months

    def _normalize_stacked_bar_data(self, data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Normalize stacked bar chart data"""
        # Ensure consistent category naming and numeric values
        return data  # Placeholder for now

    def _normalize_pie_chart_data(self, data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Normalize pie chart data"""
        # Ensure percentages sum to 100 and consistent categories
        return data  # Placeholder for now

    def _normalize_line_chart_data(self, data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Normalize line chart data"""
        # Ensure chronological ordering and numeric values
        return data  # Placeholder for now

    def _apply_transformation_hint(self, data: Dict[str, Any], hint: str, correlation_id: str) -> Dict[str, Any]:
        """Apply specific transformation hint to data"""
        # Apply transformation based on hint text
        return data  # Placeholder for now

    def _apply_quality_assurance(
        self, processed_results: Dict[str, ProcessingResult], correlation_id: str
    ) -> Dict[str, ProcessingResult]:
        """Apply quality assurance checks and calculate consistency metrics"""

        logger.debug(f"[{correlation_id}] Applying quality assurance checks")

        total_results = len(processed_results)
        successful_results = sum(1 for result in processed_results.values() if result.success)

        # Calculate data consistency score
        consistency_score = 0.0
        if total_results > 0:
            schema_enforced = sum(
                1 for result in processed_results.values() if result.processing_metadata.get("schema_enforced", False)
            )
            consistency_score = schema_enforced / total_results

        # Update pipeline metrics
        self.metrics.schema_enforcement_rate = consistency_score
        self.metrics.data_consistency_score = successful_results / total_results if total_results > 0 else 0.0

        logger.info(
            f"[{correlation_id}] QA complete: {successful_results}/{total_results} successful, consistency: {consistency_score:.2%}"
        )

        return processed_results

    def _assemble_final_response(
        self, processed_results: Dict[str, ProcessingResult], correlation_id: str
    ) -> Dict[str, Any]:
        """Assemble final response in expected format"""

        if self.start_time:
            self.metrics.processing_time = time.time() - self.start_time

        logger.info(f"[{correlation_id}] Assembling final response for {len(processed_results)} results")

        final_response = {}

        # Convert processing results to expected format
        for data_type, result in processed_results.items():
            entry = {"errors": result.validation_errors}

            if result.success:
                entry.update(
                    {
                        "alfred_raw": result.alfred_raw,
                        "slides_struct": result.slides_struct,
                        "processing_metadata": result.processing_metadata,
                        "chart_type": result.chart_type,
                        "schema_version": result.schema_version,
                    }
                )

                # Add normalized months if available
                if result.normalized_months:
                    entry["normalized_months"] = result.normalized_months

            final_response[data_type] = entry

        # Add pipeline metadata
        final_response["__pipeline_metadata__"] = {
            "processing_mode": "rigid_validation",
            "pipeline_version": "v1.0",
            "metrics": self.metrics.to_dict(),
            "correlation_id": correlation_id,
            "config": {
                "validation_enabled": self.config.enable_schema_enforcement,
                "concurrent_processing": self.config.enable_concurrent_processing,
                "strict_mode": self.config.strict_mode,
                "fallback_enabled": self.config.enable_fallback,
            },
        }

        logger.info(f"[{correlation_id}] Pipeline processing complete in {self.metrics.processing_time:.2f}s")

        return final_response

    def _build_error_response(self, error_message: str, errors: List[str], correlation_id: str) -> Dict[str, Any]:
        """Build error response for pipeline failures"""

        return {
            "error": error_message,
            "errors": errors,
            "__pipeline_metadata__": {
                "processing_mode": "error",
                "pipeline_version": "v1.0",
                "correlation_id": correlation_id,
                "processing_time": time.time() - self.start_time if self.start_time else 0.0,
            },
        }


# Global pipeline instance with default configuration
default_pipeline = AlfredDataPipeline()


# Convenience functions for different use cases
async def process_alfred_requests_unified(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    config: PipelineConfig = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Unified entry point for Alfred data processing.

    This function provides a single interface that replaces both
    mcp_tool_run and mcp_tool_run_concurrent with consistent behavior.
    """

    pipeline = AlfredDataPipeline(config or PipelineConfig())

    return await pipeline.process_data_requests(
        requests_list=requests_list,
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
        **kwargs,
    )


async def process_alfred_requests_backward_compatible(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str = None,  # Ignored in new system
    **kwargs,
) -> Dict[str, Any]:
    """
    Backward compatible interface that matches the original mcp_tool_run signature
    but uses the new unified pipeline system.
    """

    # Create configuration from kwargs
    config = PipelineConfig()

    # Map common kwargs to config
    if "use_concurrent" in kwargs:
        config.enable_concurrent_processing = kwargs["use_concurrent"]
    if "batch_size" in kwargs:
        config.batch_size = kwargs["batch_size"]
    if "max_concurrent_batches" in kwargs:
        config.max_concurrent_batches = kwargs["max_concurrent_batches"]

    return await process_alfred_requests_unified(
        requests_list=requests_list,
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
        config=config,
    )
