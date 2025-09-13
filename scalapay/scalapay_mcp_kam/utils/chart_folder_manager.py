"""
Chart folder management with execution-specific organization and tracking.
Provides workflow-aware chart storage with correlation IDs and metadata.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChartFolderManager:
    """
    Manages execution-specific chart storage with workflow tracking.

    Features:
    - Creates unique folders per workflow execution
    - Tracks charts with correlation IDs
    - Maintains execution metadata and manifest
    - Supports custom folder hierarchies
    """

    def __init__(
        self, base_folder: str = "./plots", enable_execution_folders: bool = True, correlation_id: Optional[str] = None
    ):
        self.base_folder = Path(base_folder)
        self.enable_execution_folders = enable_execution_folders
        self.correlation_id = correlation_id or self._generate_correlation_id()

        # Execution-specific folder structure
        if enable_execution_folders:
            self.execution_folder = self.base_folder / f"execution_{self.correlation_id}"
            self.charts_folder = self.execution_folder / "charts"
            self.metadata_folder = self.execution_folder / "metadata"
        else:
            self.execution_folder = self.base_folder
            self.charts_folder = self.base_folder
            self.metadata_folder = self.base_folder / "metadata"

        self.manifest_path = self.metadata_folder / "execution_manifest.json"
        self.chart_registry = []

        # Create directories
        self._setup_directories()

        # Initialize manifest
        self._initialize_manifest()

    @staticmethod
    def _generate_correlation_id() -> str:
        """Generate a unique correlation ID for this execution."""
        timestamp = int(time.time())
        return f"{timestamp}_{os.urandom(4).hex()}"

    def _setup_directories(self):
        """Create all necessary directories."""
        try:
            self.charts_folder.mkdir(parents=True, exist_ok=True)
            self.metadata_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Chart folders initialized: {self.charts_folder}")
        except Exception as e:
            logger.error(f"Failed to create chart directories: {e}")
            raise

    def _initialize_manifest(self):
        """Initialize or load execution manifest."""
        manifest_data = {
            "execution_id": self.correlation_id,
            "created_at": datetime.now().isoformat(),
            "base_folder": str(self.base_folder),
            "charts_folder": str(self.charts_folder),
            "enable_execution_folders": self.enable_execution_folders,
            "charts": [],
            "total_charts": 0,
            "status": "active",
        }

        # Load existing manifest if it exists
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r") as f:
                    existing_manifest = json.load(f)
                    self.chart_registry = existing_manifest.get("charts", [])
                    manifest_data["charts"] = self.chart_registry
                    manifest_data["total_charts"] = len(self.chart_registry)
                    logger.info(f"Loaded existing manifest with {len(self.chart_registry)} charts")
            except Exception as e:
                logger.warning(f"Failed to load existing manifest: {e}")

        # Save/update manifest
        self._save_manifest(manifest_data)

    def _save_manifest(self, manifest_data: Dict[str, Any]):
        """Save execution manifest to disk."""
        try:
            with open(self.manifest_path, "w") as f:
                json.dump(manifest_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")

    def get_chart_path(self, data_type: str, chart_extension: str = "png") -> str:
        """
        Generate a unique chart path for the given data type.

        Args:
            data_type: The type of chart (e.g., "monthly sales year over year")
            chart_extension: File extension (default: png)

        Returns:
            Full path for the chart file
        """
        # Clean data type for filename
        safe_name = self._sanitize_filename(data_type)

        # Generate unique filename with timestamp and correlation ID
        timestamp = int(time.time())
        filename = f"{safe_name}_{timestamp}_{self.correlation_id[:8]}.{chart_extension}"

        return str(self.charts_folder / filename)

    def register_chart(
        self, data_type: str, chart_path: str, chart_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a chart in the execution manifest.

        Args:
            data_type: Type of chart data
            chart_path: Path to the saved chart file
            chart_metadata: Additional metadata about the chart

        Returns:
            Chart registry entry
        """
        chart_entry = {
            "data_type": data_type,
            "chart_path": chart_path,
            "filename": Path(chart_path).name,
            "registered_at": datetime.now().isoformat(),
            "correlation_id": self.correlation_id,
            "file_size": None,
            "metadata": chart_metadata or {},
        }

        # Get file size if file exists
        if os.path.exists(chart_path):
            try:
                chart_entry["file_size"] = os.path.getsize(chart_path)
            except OSError:
                pass

        # Add to registry
        self.chart_registry.append(chart_entry)

        # Update manifest
        self._update_manifest_with_new_chart(chart_entry)

        logger.info(f"Registered chart: {data_type} -> {Path(chart_path).name}")
        return chart_entry

    def _update_manifest_with_new_chart(self, chart_entry: Dict[str, Any]):
        """Update manifest file with new chart entry."""
        try:
            # Load current manifest
            manifest_data = {}
            if self.manifest_path.exists():
                with open(self.manifest_path, "r") as f:
                    manifest_data = json.load(f)

            # Update with new chart
            manifest_data["charts"] = self.chart_registry
            manifest_data["total_charts"] = len(self.chart_registry)
            manifest_data["last_updated"] = datetime.now().isoformat()

            # Save updated manifest
            self._save_manifest(manifest_data)

        except Exception as e:
            logger.error(f"Failed to update manifest with new chart: {e}")

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Convert data type to safe filename."""
        import re

        # Replace problematic characters with underscores
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\s]", "", filename)
        # Replace spaces with underscores
        safe_name = re.sub(r"\s+", "_", safe_name)
        # Remove multiple underscores
        safe_name = re.sub(r"_+", "_", safe_name)
        # Limit length
        return safe_name[:50] or "chart"

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of current execution."""
        return {
            "execution_id": self.correlation_id,
            "execution_folder": str(self.execution_folder),
            "charts_folder": str(self.charts_folder),
            "total_charts": len(self.chart_registry),
            "chart_files": [entry["filename"] for entry in self.chart_registry],
            "data_types": [entry["data_type"] for entry in self.chart_registry],
            "manifest_path": str(self.manifest_path),
        }

    def finalize_execution(self):
        """Mark execution as complete and finalize manifest."""
        try:
            # Load current manifest
            manifest_data = {}
            if self.manifest_path.exists():
                with open(self.manifest_path, "r") as f:
                    manifest_data = json.load(f)

            # Mark as completed
            manifest_data["status"] = "completed"
            manifest_data["completed_at"] = datetime.now().isoformat()
            manifest_data["final_chart_count"] = len(self.chart_registry)

            # Save final manifest
            self._save_manifest(manifest_data)

            logger.info(f"Execution {self.correlation_id} finalized with {len(self.chart_registry)} charts")

        except Exception as e:
            logger.error(f"Failed to finalize execution: {e}")

    @classmethod
    def from_environment(cls, correlation_id: Optional[str] = None) -> "ChartFolderManager":
        """
        Create ChartFolderManager from environment variables.

        Environment variables:
        - SCALAPAY_CHART_BASE_FOLDER: Base folder for charts (default: ./plots)
        - SCALAPAY_ENABLE_EXECUTION_FOLDERS: Enable execution-specific folders (default: true)
        - SCALAPAY_CHART_CORRELATION_ID: Use specific correlation ID
        """
        base_folder = os.getenv("SCALAPAY_CHART_BASE_FOLDER", "./plots")
        enable_execution_folders = os.getenv("SCALAPAY_ENABLE_EXECUTION_FOLDERS", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        env_correlation_id = os.getenv("SCALAPAY_CHART_CORRELATION_ID")

        final_correlation_id = env_correlation_id or correlation_id

        return cls(
            base_folder=base_folder,
            enable_execution_folders=enable_execution_folders,
            correlation_id=final_correlation_id,
        )


# Helper function for backward compatibility
def get_execution_chart_folder(correlation_id: Optional[str] = None) -> str:
    """
    Get the chart folder for current execution.

    Returns:
        Path to charts folder for this execution
    """
    manager = ChartFolderManager.from_environment(correlation_id)
    return str(manager.charts_folder)


# Integration with existing _persist_plot_ref function
def enhanced_persist_plot_ref(
    data_type: str,
    source_path: str,
    folder_manager: ChartFolderManager,
    chart_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Enhanced version of _persist_plot_ref with folder management.

    Args:
        data_type: Type of chart data
        source_path: Source path of generated chart
        folder_manager: ChartFolderManager instance
        chart_metadata: Additional chart metadata

    Returns:
        Path to persisted chart file or None if failed
    """
    if not isinstance(source_path, str) or not source_path.lower().endswith(".png"):
        return None

    if not os.path.exists(source_path):
        return None

    try:
        # Get target path from folder manager
        target_path = folder_manager.get_chart_path(data_type, "png")

        # Copy file
        with open(source_path, "rb") as src, open(target_path, "wb") as dst:
            dst.write(src.read())

        # Register chart
        folder_manager.register_chart(data_type, target_path, chart_metadata)

        logger.info(f"Enhanced persist: {data_type} -> {Path(target_path).name}")
        return target_path

    except Exception as e:
        logger.error(f"Enhanced persist failed for {data_type}: {e}")
        return None
