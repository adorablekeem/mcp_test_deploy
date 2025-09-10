"""
Enhanced matplotlib agent with execution-specific folder management and workflow tracking.
Extends the original agent_matplot.py with advanced chart organization capabilities.
"""

import os
import logging
from typing import Dict, Any, Optional
from ..utils.chart_folder_manager import ChartFolderManager, enhanced_persist_plot_ref

logger = logging.getLogger(__name__)


def _persist_plot_ref_enhanced(
    data_type: str, 
    path: str | None, 
    correlation_id: str,
    out_dir: str = "./plots",
    chart_metadata: Optional[Dict[str, Any]] = None
) -> str | None:
    """
    Enhanced version of _persist_plot_ref with execution-specific folder management.
    
    Args:
        data_type: Type of chart data (e.g., "monthly sales year over year")
        path: Source path of the generated chart
        correlation_id: Correlation ID for workflow tracking
        out_dir: Base output directory (can be overridden by environment)
        chart_metadata: Additional metadata about the chart
        
    Returns:
        Path to persisted chart file or None if failed
        
    Environment Variables:
        SCALAPAY_CHART_BASE_FOLDER: Override base folder
        SCALAPAY_ENABLE_EXECUTION_FOLDERS: Enable execution-specific folders (default: true)
    """
    if not isinstance(path, str) or not path.lower().endswith(".png"):
        logger.warning(f"Invalid chart path for {data_type}: {path}")
        return None
    
    try:
        # Create folder manager with correlation ID
        folder_manager = ChartFolderManager.from_environment(correlation_id)
        
        # Use enhanced persist function
        target_path = enhanced_persist_plot_ref(
            data_type=data_type,
            source_path=path,
            folder_manager=folder_manager,
            chart_metadata=chart_metadata
        )
        
        if target_path:
            logger.info(f"Chart persisted with workflow tracking: {data_type} -> {os.path.basename(target_path)}")
            return target_path
        else:
            logger.error(f"Failed to persist chart for {data_type}")
            return None
            
    except Exception as e:
        logger.error(f"Enhanced persist failed for {data_type}: {e}")
        # Fallback to original logic
        return _persist_plot_ref_fallback(data_type, path, out_dir)


def _persist_plot_ref_fallback(data_type: str, path: str | None, out_dir: str = "./plots") -> str | None:
    """
    Fallback version of _persist_plot_ref (original logic) when enhanced version fails.
    """
    import uuid
    import re
    
    if not isinstance(path, str) or not path.lower().endswith(".png"):
        return None

    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(path):
        safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "_", data_type) or "chart"
        target = os.path.join(out_dir, f"{safe_key}_{uuid.uuid4().hex[:8]}.png")
        try:
            with open(path, "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())
            logger.info(f"Fallback persist: {data_type} -> {os.path.basename(target)}")
            return target
        except Exception:
            return path
    return path


def get_execution_folder_summary(correlation_id: str) -> Dict[str, Any]:
    """
    Get summary of charts generated for a specific execution.
    
    Args:
        correlation_id: The correlation ID for the execution
        
    Returns:
        Dictionary with execution summary and chart information
    """
    try:
        folder_manager = ChartFolderManager.from_environment(correlation_id)
        return folder_manager.get_execution_summary()
    except Exception as e:
        logger.error(f"Failed to get execution summary for {correlation_id}: {e}")
        return {"error": str(e), "execution_id": correlation_id}


def finalize_chart_execution(correlation_id: str) -> bool:
    """
    Finalize chart execution and update manifest.
    
    Args:
        correlation_id: The correlation ID for the execution
        
    Returns:
        True if successful, False otherwise
    """
    try:
        folder_manager = ChartFolderManager.from_environment(correlation_id)
        folder_manager.finalize_execution()
        logger.info(f"Finalized chart execution: {correlation_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to finalize execution {correlation_id}: {e}")
        return False


# Configuration helpers
def configure_chart_folders_for_execution(
    correlation_id: Optional[str] = None,
    base_folder: Optional[str] = None,
    enable_execution_folders: bool = True
) -> ChartFolderManager:
    """
    Configure chart folder management for a new execution.
    
    Args:
        correlation_id: Optional correlation ID (auto-generated if None)
        base_folder: Base folder for charts (uses env var if None)
        enable_execution_folders: Whether to create execution-specific folders
        
    Returns:
        Configured ChartFolderManager instance
    """
    if base_folder:
        os.environ["SCALAPAY_CHART_BASE_FOLDER"] = base_folder
    
    os.environ["SCALAPAY_ENABLE_EXECUTION_FOLDERS"] = str(enable_execution_folders).lower()
    
    if correlation_id:
        os.environ["SCALAPAY_CHART_CORRELATION_ID"] = correlation_id
    
    return ChartFolderManager.from_environment()


def get_charts_by_execution(base_folder: str = "./plots") -> Dict[str, Dict[str, Any]]:
    """
    Get all charts organized by execution ID.
    
    Args:
        base_folder: Base plots folder to scan
        
    Returns:
        Dictionary mapping execution IDs to their chart information
    """
    executions = {}
    
    try:
        import json
        from pathlib import Path
        
        plots_path = Path(base_folder)
        if not plots_path.exists():
            return executions
        
        # Find all execution folders
        for item in plots_path.iterdir():
            if item.is_dir() and item.name.startswith("execution_"):
                execution_id = item.name.replace("execution_", "")
                manifest_path = item / "metadata" / "execution_manifest.json"
                
                if manifest_path.exists():
                    try:
                        with open(manifest_path, 'r') as f:
                            manifest_data = json.load(f)
                            executions[execution_id] = {
                                "execution_folder": str(item),
                                "manifest": manifest_data,
                                "chart_count": len(manifest_data.get("charts", [])),
                                "status": manifest_data.get("status", "unknown"),
                                "created_at": manifest_data.get("created_at"),
                                "completed_at": manifest_data.get("completed_at")
                            }
                    except Exception as e:
                        logger.warning(f"Failed to load manifest for {execution_id}: {e}")
                        executions[execution_id] = {
                            "execution_folder": str(item),
                            "error": str(e)
                        }
        
    except Exception as e:
        logger.error(f"Failed to scan executions: {e}")
    
    return executions


# Example usage functions for debugging/testing
def demo_folder_manager_usage():
    """Demonstrate folder manager usage."""
    print("🗂️  Chart Folder Manager Demo")
    print("=" * 50)
    
    # Create manager for new execution
    manager = ChartFolderManager.from_environment()
    print(f"📁 Execution ID: {manager.correlation_id}")
    print(f"📁 Charts folder: {manager.charts_folder}")
    
    # Simulate chart registration
    test_charts = [
        ("monthly sales year over year", "/tmp/monthly_sales.png"),
        ("AOV by product type", "/tmp/aov_chart.png"),
        ("user demographics", "/tmp/demographics.png")
    ]
    
    for data_type, fake_path in test_charts:
        # Get target path
        target_path = manager.get_chart_path(data_type)
        print(f"📊 {data_type} -> {os.path.basename(target_path)}")
        
        # Register (without actual file)
        manager.register_chart(data_type, target_path, {
            "chart_type": "bar" if "sales" in data_type else "line",
            "demo": True
        })
    
    # Show summary
    summary = manager.get_execution_summary()
    print(f"\n📋 Execution Summary:")
    print(f"   Total charts: {summary['total_charts']}")
    print(f"   Chart files: {', '.join(summary['chart_files'])}")
    print(f"   Manifest: {summary['manifest_path']}")
    
    # Finalize
    manager.finalize_execution()
    print(f"\n✅ Execution finalized!")


if __name__ == "__main__":
    # Run demo when script is executed directly
    demo_folder_manager_usage()