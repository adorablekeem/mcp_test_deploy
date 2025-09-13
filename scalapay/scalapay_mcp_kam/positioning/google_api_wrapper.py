"""
Safe wrapper around GoogleApiSupport with fallback to legacy implementation.
Provides error handling, monitoring, and compatibility with existing code.
"""

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

# Import existing dependencies for fallback
from scalapay.scalapay_mcp_kam.tests.test_fill_template_sections import batch_text_replace, make_file_public, upload_png

# Feature flags
from .feature_flags import get_feature_manager, record_positioning_performance

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Result of a positioning operation with detailed information."""

    success: bool
    mode_used: str  # "clean" or "legacy"
    execution_time: float
    api_calls_made: int = 0
    objects_processed: int = 0
    error_message: Optional[str] = None
    fallback_used: bool = False
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class GoogleApiWrapper:
    """Safe wrapper around GoogleApiSupport with fallback capabilities."""

    def __init__(self):
        self.feature_manager = get_feature_manager()
        self._googleapi_available = self._check_googleapi_availability()
        self._slides_service = None

    def _check_googleapi_availability(self) -> bool:
        """Check if GoogleApiSupport is available and properly configured."""
        try:
            # Try to import and test basic functionality
            from GoogleApiSupport import auth, slides

            # Test if we can get the service (this will fail if credentials are missing)
            service = auth.get_service("slides")
            logger.info("GoogleApiSupport is available and configured")
            return True

        except ImportError as e:
            logger.warning(f"GoogleApiSupport not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"GoogleApiSupport configuration issue: {e}")
            return False

    @contextmanager
    def _operation_timing(self, operation_name: str, correlation_id: Optional[str] = None):
        """Context manager for timing operations and recording performance."""
        start_time = time.time()
        operation_result = OperationResult(success=False, mode_used="unknown", execution_time=0.0)

        try:
            yield operation_result

        except Exception as e:
            operation_result.success = False
            operation_result.error_message = str(e)
            logger.error(f"[{correlation_id}] {operation_name} failed: {e}")
            raise

        finally:
            operation_result.execution_time = time.time() - start_time

            # Record performance metrics
            if operation_result.mode_used != "unknown":
                record_positioning_performance(
                    mode=operation_result.mode_used,
                    success=operation_result.success,
                    execution_time=operation_result.execution_time,
                    correlation_id=correlation_id,
                )

    def get_all_shapes_placeholders(
        self, presentation_id: str, correlation_id: Optional[str] = None
    ) -> OperationResult:
        """
        Get all shape placeholders with fallback support.
        """
        with self._operation_timing("get_shapes_placeholders", correlation_id) as result:
            if self._googleapi_available and self.feature_manager.flags.enable_template_discovery:
                # Try GoogleApiSupport first
                try:
                    from GoogleApiSupport import slides

                    result.mode_used = "clean"
                    placeholders = slides.get_all_shapes_placeholders(presentation_id)
                    result.success = True
                    result.api_calls_made = 1
                    result.objects_processed = len(placeholders)
                    result.details = {"placeholders": placeholders}

                    logger.debug(f"[{correlation_id}] Found {len(placeholders)} placeholders using GoogleApiSupport")
                    return result

                except Exception as e:
                    logger.warning(f"[{correlation_id}] GoogleApiSupport placeholder discovery failed: {e}")

                    if not self.feature_manager.flags.enable_fallback_on_error:
                        raise

            # Fallback to legacy implementation
            result.mode_used = "legacy"
            result.fallback_used = True

            # Use existing legacy function (if available)
            try:
                # Import legacy function
                from scalapay.scalapay_mcp_kam.concurrency_utils.batch_operations_image_positioning_fix import (
                    find_image_object_ids_in_slide,
                )
                from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

                # Get presentation data using legacy approach
                slides_service = connection_manager.get_service_sync()
                presentation = slides_service.presentations().get(presentationId=presentation_id).execute()

                # Build placeholder mapping using legacy logic
                placeholders = {}
                for slide in presentation.get("slides", []):
                    slide_id = slide["objectId"]

                    for element in slide.get("pageElements", []):
                        if "shape" in element and "text" in element["shape"]:
                            text_elements = element["shape"]["text"].get("textElements", [])
                            for text_elem in text_elements:
                                if "textRun" in text_elem:
                                    content = text_elem["textRun"]["content"].strip()
                                    if content.startswith("{{") and content.endswith("}}"):
                                        placeholders[element["objectId"]] = {"inner_text": content, "page_id": slide_id}

                result.success = True
                result.api_calls_made = 1
                result.objects_processed = len(placeholders)
                result.details = {"placeholders": placeholders}

                logger.info(f"[{correlation_id}] Found {len(placeholders)} placeholders using legacy method")
                return result

            except Exception as e:
                result.success = False
                result.error_message = f"Legacy placeholder discovery failed: {str(e)}"
                logger.error(f"[{correlation_id}] Legacy placeholder discovery failed: {e}")
                raise

    def batch_replace_shape_with_image(
        self,
        image_mapping: Dict[str, str],
        presentation_id: str,
        pages: Optional[List[str]] = None,
        fill: bool = False,
        enable_custom_sizing: bool = False,
        sizing_config: Optional[Dict[str, Dict[str, Any]]] = None,
        correlation_id: Optional[str] = None,
    ) -> OperationResult:
        """
        Batch replace shapes with images using a manual create/delete approach to preserve positioning.

        Args:
            image_mapping: Dictionary mapping placeholder text to image URLs
            presentation_id: Google Slides presentation ID
            pages: Optional list of page IDs to limit operation
            fill: (Not used in this implementation)
            enable_custom_sizing: (Not used in this implementation)
            sizing_config: (Not used in this implementation)
            correlation_id: For tracking operations
        """
        with self._operation_timing("batch_replace_shapes", correlation_id) as result:
            if not self._googleapi_available:
                # Fallback or error if GoogleApiSupport is not available
                result.success = False
                result.error_message = "GoogleApiSupport is not available for batch_replace_shape_with_image"
                logger.error(f"[{correlation_id}] GoogleApiSupport not available.")
                # Optionally, you could redirect to the legacy implementation here if desired
                raise NotImplementedError("Legacy fallback for manual image replacement is not implemented.")

            try:
                from GoogleApiSupport import slides

                result.mode_used = "clean_manual_positioning"

                # 1. Get presentation info to find placeholders
                presentation_info_result = self._get_presentation_info_sync(presentation_id, correlation_id)
                if not presentation_info_result.success:
                    raise Exception(f"Failed to get presentation info: {presentation_info_result.error_message}")

                presentation = presentation_info_result.details
                slides_info = presentation.get("slides", [])

                placeholders_to_replace = {}

                for slide in slides_info:
                    page_id = slide["objectId"]
                    # If pages are specified, only process those pages
                    if pages and page_id not in pages:
                        continue

                    for element in slide.get("pageElements", []):
                        if "shape" in element and "text" in element["shape"]:
                            raw_text = "".join(
                                text_element["textRun"]["content"]
                                for text_element in element["shape"]["text"].get("textElements", [])
                                if "textRun" in text_element
                            )

                            placeholder_text = raw_text.strip()
                            if placeholder_text.startswith("{{") and placeholder_text.endswith("}}"):
                                key = placeholder_text[2:-2]
                                if key in image_mapping:
                                    if key not in placeholders_to_replace:
                                        placeholders_to_replace[key] = []
                                    placeholders_to_replace[key].append({"element": element, "page_id": page_id})

                # 2. Build batch update requests for creating images and deleting placeholders
                requests = []
                for placeholder_text, url in image_mapping.items():
                    if placeholder_text in placeholders_to_replace:
                        for item in placeholders_to_replace[placeholder_text]:
                            element = item["element"]
                            page_id = item["page_id"]

                            # Request to create the new image with the placeholder's size and transform
                            create_image_request = {
                                "createImage": {
                                    "url": url,
                                    "elementProperties": {
                                        "pageObjectId": page_id,
                                        "size": element["size"],
                                        "transform": element["transform"],
                                    },
                                }
                            }
                            requests.append(create_image_request)

                            # Request to delete the old placeholder shape
                            delete_object_request = {"deleteObject": {"objectId": element["objectId"]}}
                            requests.append(delete_object_request)

                # 3. Execute the batch update
                if requests:
                    response = slides.execute_batch_update(requests, presentation_id)
                    logger.info(f"[{correlation_id}] Executed {len(requests)} requests for image replacement.")
                else:
                    response = None
                    logger.info(f"[{correlation_id}] No matching placeholders found for image replacement.")

                result.success = True
                result.api_calls_made = 1 if requests else 0
                result.objects_processed = len(requests) // 2  # Each replacement is 2 requests
                result.details = {"api_response": response}

                logger.info(
                    f"[{correlation_id}] Replaced {result.objects_processed} images using manual create/delete method."
                )
                return result

            except Exception as e:
                logger.error(f"[{correlation_id}] Manual image replacement failed: {e}")
                result.success = False
                result.error_message = str(e)
                if not self.feature_manager.flags.enable_fallback_on_error:
                    raise

                # If fallback is enabled, you might call the legacy implementation here
                # For now, we just let the exception be handled by the context manager
                raise

    def batch_text_replace(
        self,
        text_mapping: Dict[str, str],
        presentation_id: str,
        pages: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> OperationResult:
        """
        Batch replace text using clean or legacy approach.
        """
        with self._operation_timing("batch_text_replace", correlation_id) as result:
            if self._googleapi_available:
                # Try GoogleApiSupport first
                try:
                    from GoogleApiSupport import slides

                    result.mode_used = "clean"

                    response = slides.batch_text_replace(
                        text_mapping=text_mapping, presentation_id=presentation_id, pages=pages
                    )

                    result.success = True
                    result.api_calls_made = 1
                    result.objects_processed = len(text_mapping)
                    result.details = {"api_response": response}

                    logger.debug(
                        f"[{correlation_id}] Replaced {len(text_mapping)} text placeholders using GoogleApiSupport"
                    )
                    return result

                except Exception as e:
                    logger.warning(f"[{correlation_id}] GoogleApiSupport text replace failed: {e}")

                    if not self.feature_manager.flags.enable_fallback_on_error:
                        raise

            # Fallback to legacy implementation
            result.mode_used = "legacy"
            result.fallback_used = True

            try:
                # Use existing legacy function
                from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

                slides = connection_manager.get_service_sync()

                response = batch_text_replace(slides, presentation_id, text_mapping)

                result.success = True
                result.api_calls_made = 1
                result.objects_processed = len(text_mapping)
                result.details = {"api_response": response}

                logger.debug(f"[{correlation_id}] Replaced {len(text_mapping)} text placeholders using legacy method")
                return result

            except Exception as e:
                result.success = False
                result.error_message = f"Legacy text replace failed: {str(e)}"
                logger.error(f"[{correlation_id}] Legacy text replace failed: {e}")
                raise

    async def upload_and_publish_images(
        self,
        chart_mappings: Dict[str, str],  # data_type -> local_file_path
        folder_id: Optional[str] = None,
        max_concurrent: int = 3,
        correlation_id: Optional[str] = None,
    ) -> OperationResult:
        """
        Upload images concurrently and make them public.
        Returns mapping of data_type -> public_url.
        """
        with self._operation_timing("upload_and_publish", correlation_id) as result:
            try:
                if self.feature_manager.flags.enable_concurrent_uploads:
                    # Concurrent upload approach
                    result.mode_used = "clean"

                    async def upload_single_image(data_type: str, file_path: str) -> Tuple[str, str]:
                        """Upload single image and return (data_type, public_url)."""
                        loop = asyncio.get_event_loop()

                        # Upload in thread pool to avoid blocking
                        pretty_name = f"{data_type.replace(' ', '_')}_{int(time.time())}.png"
                        # Get drive service for upload
                        from google.oauth2 import service_account

                        credentials_path = os.getenv(
                            "GOOGLE_APPLICATION_CREDENTIALS", "./scalapay/scalapay_mcp_kam/credentials.json"
                        )
                        credentials = service_account.Credentials.from_service_account_file(credentials_path)
                        from googleapiclient.discovery import build

                        drive = build("drive", "v3", credentials=credentials)

                        file_id = await loop.run_in_executor(None, upload_png, drive, file_path, pretty_name, folder_id)

                        # Make public in thread pool
                        await loop.run_in_executor(None, make_file_public, drive, file_id)

                        # Generate public URL
                        public_url = f"https://drive.google.com/uc?id={file_id}"

                        return data_type, public_url

                    # Create semaphore to limit concurrent uploads
                    semaphore = asyncio.Semaphore(max_concurrent)

                    async def upload_with_semaphore(data_type: str, file_path: str):
                        async with semaphore:
                            return await upload_single_image(data_type, file_path)

                    # Execute all uploads concurrently
                    upload_tasks = [
                        upload_with_semaphore(data_type, file_path) for data_type, file_path in chart_mappings.items()
                    ]

                    upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

                    # Process results
                    successful_uploads = {}
                    failed_uploads = []

                    for result_item in upload_results:
                        if isinstance(result_item, Exception):
                            failed_uploads.append(str(result_item))
                        else:
                            data_type, public_url = result_item
                            successful_uploads[data_type] = public_url

                    result.success = len(failed_uploads) == 0
                    result.api_calls_made = len(successful_uploads) * 2  # Upload + permission per image
                    result.objects_processed = len(successful_uploads)
                    result.details = {"successful_uploads": successful_uploads, "failed_uploads": failed_uploads}

                    logger.info(
                        f"[{correlation_id}] Concurrent upload: {len(successful_uploads)} successful, "
                        f"{len(failed_uploads)} failed"
                    )

                else:
                    # Sequential upload approach (legacy)
                    result.mode_used = "legacy"

                    successful_uploads = {}
                    failed_uploads = []
                    api_calls = 0

                    for data_type, file_path in chart_mappings.items():
                        try:
                            pretty_name = f"{data_type.replace(' ', '_')}_{int(time.time())}.png"
                            # Get drive service for upload
                            from google.oauth2 import service_account

                            credentials_path = os.getenv(
                                "GOOGLE_APPLICATION_CREDENTIALS", "./scalapay/scalapay_mcp_kam/credentials.json"
                            )
                            credentials = service_account.Credentials.from_service_account_file(credentials_path)
                            from googleapiclient.discovery import build

                            drive = build("drive", "v3", credentials=credentials)

                            file_id = upload_png(drive, file_path, name=pretty_name, parent_folder_id=folder_id)
                            api_calls += 1

                            make_file_public(drive, file_id)
                            api_calls += 1

                            public_url = f"https://drive.google.com/uc?id={file_id}"
                            successful_uploads[data_type] = public_url

                        except Exception as e:
                            failed_uploads.append(f"{data_type}: {str(e)}")

                    result.success = len(failed_uploads) == 0
                    result.api_calls_made = api_calls
                    result.objects_processed = len(successful_uploads)
                    result.details = {"successful_uploads": successful_uploads, "failed_uploads": failed_uploads}

                    logger.info(
                        f"[{correlation_id}] Sequential upload: {len(successful_uploads)} successful, "
                        f"{len(failed_uploads)} failed"
                    )

                return result

            except Exception as e:
                result.success = False
                result.error_message = f"Image upload failed: {str(e)}"
                logger.error(f"[{correlation_id}] Image upload failed: {e}")
                raise

    def _get_presentation_info_sync(
        self, presentation_id: str, correlation_id: Optional[str] = None
    ) -> OperationResult:
        """
        Get presentation information synchronously.
        This method is needed by the chart resizer.
        """
        correlation_id = correlation_id or f"get_info_{int(time.time())}"

        try:
            if self._googleapi_available:
                # Try GoogleApiSupport first
                try:
                    from GoogleApiSupport import slides

                    presentation_info = slides.get_presentation_info(presentation_id)

                    return OperationResult(
                        success=True,
                        mode_used="clean",
                        execution_time=0,
                        api_calls_made=1,
                        objects_processed=1,
                        details={"slides": presentation_info.get("slides", [])},
                    )

                except Exception as e:
                    logger.warning(f"[{correlation_id}] GoogleApiSupport get_presentation_info failed: {e}")
                    if not self.feature_manager.flags.enable_fallback_on_error:
                        raise

            # Fallback to legacy method
            try:
                from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

                slides_service = connection_manager.get_service_sync()

                presentation = slides_service.presentations().get(presentationId=presentation_id).execute()

                return OperationResult(
                    success=True,
                    mode_used="legacy",
                    execution_time=0,
                    api_calls_made=1,
                    objects_processed=1,
                    details=presentation,
                    fallback_used=True,
                )

            except Exception as e:
                logger.error(f"[{correlation_id}] Legacy get_presentation_info failed: {e}")
                return OperationResult(
                    success=False,
                    mode_used="legacy_failed",
                    execution_time=0,
                    api_calls_made=0,
                    objects_processed=0,
                    error_message=str(e),
                )

        except Exception as e:
            return OperationResult(
                success=False,
                mode_used="failed",
                execution_time=0,
                api_calls_made=0,
                objects_processed=0,
                error_message=str(e),
            )

    def _execute_batch_update_sync(
        self, requests: List[Dict[str, Any]], presentation_id: str, correlation_id: Optional[str] = None
    ) -> OperationResult:
        """
        Execute batch update requests synchronously.
        This method is needed by the chart resizer.
        """
        correlation_id = correlation_id or f"batch_update_{int(time.time())}"

        try:
            if self._googleapi_available:
                # Try GoogleApiSupport first
                try:
                    from GoogleApiSupport import slides

                    response = slides.execute_batch_update(requests=requests, presentation_id=presentation_id)

                    return OperationResult(
                        success=True,
                        mode_used="clean",
                        execution_time=0,
                        api_calls_made=1,
                        objects_processed=len(requests),
                        details={"api_response": response},
                    )

                except Exception as e:
                    logger.warning(f"[{correlation_id}] GoogleApiSupport batch_update failed: {e}")
                    if not self.feature_manager.flags.enable_fallback_on_error:
                        raise

            # Fallback to legacy method
            try:
                from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

                slides_service = connection_manager.get_service_sync()

                body = {"requests": requests}
                response = (
                    slides_service.presentations().batchUpdate(presentationId=presentation_id, body=body).execute()
                )

                return OperationResult(
                    success=True,
                    mode_used="legacy",
                    execution_time=0,
                    api_calls_made=1,
                    objects_processed=len(requests),
                    details={"api_response": response},
                    fallback_used=True,
                )

            except Exception as e:
                logger.error(f"[{correlation_id}] Legacy batch_update failed: {e}")
                return OperationResult(
                    success=False,
                    mode_used="legacy_failed",
                    execution_time=0,
                    api_calls_made=0,
                    objects_processed=0,
                    error_message=str(e),
                )

        except Exception as e:
            return OperationResult(
                success=False,
                mode_used="failed",
                execution_time=0,
                api_calls_made=0,
                objects_processed=0,
                error_message=str(e),
            )


# Global wrapper instance
_api_wrapper = None


def get_api_wrapper() -> GoogleApiWrapper:
    """Get global API wrapper instance."""
    global _api_wrapper
    if _api_wrapper is None:
        _api_wrapper = GoogleApiWrapper()
    return _api_wrapper
