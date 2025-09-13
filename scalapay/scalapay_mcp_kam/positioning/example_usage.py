"""
Example usage and integration guide for the clean positioning system.
Shows how to migrate from legacy implementation to the new system.
"""

import asyncio
import logging
from typing import Any, Dict, List

# Import the new positioning system
from scalapay.scalapay_mcp_kam.positioning import (  # Drop-in replacements; Direct API for new code; Configuration and monitoring; Feature flags
    CleanChartPositioner,
    apply_chart_specific_positioning_correctly,
    configure_positioning,
    emergency_rollback,
    fill_template_with_clean_positioning,
    get_positioning_status,
    health_check,
    should_use_clean_positioning,
)

logger = logging.getLogger(__name__)


async def example_drop_in_replacement():
    """
    Example 1: Drop-in replacement for existing code

    This shows how to replace the legacy function with zero code changes.
    The function signature is identical, but the implementation is much cleaner.
    """

    # Existing parameters (unchanged)
    presentation_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
    image_map = {
        "{{monthly_sales_chart}}": "https://drive.google.com/uc?id=chart1_file_id",
        "{{aov_chart}}": "https://drive.google.com/uc?id=chart2_file_id",
        "{{demographics_chart}}": "https://drive.google.com/uc?id=chart3_file_id",
    }
    slide_metadata = {
        "monthly_sales": {"title": "Monthly Sales", "chart_type": "bar"},
        "aov": {"title": "Average Order Value", "chart_type": "line"},
        "demographics": {"title": "User Demographics", "chart_type": "pie"},
    }

    # This is the EXACT same function call as before
    # But now it uses the clean implementation with fallback
    result = await apply_chart_specific_positioning_correctly(
        slides_service=None,  # Will be handled internally
        presentation_id=presentation_id,
        image_map=image_map,
        slide_metadata=slide_metadata,
    )

    print(f"Positioning result: {result}")
    return result


async def example_new_clean_api():
    """
    Example 2: Using the new clean API directly

    This shows the cleaner, more explicit API for new code.
    Provides better error handling and more control.
    """

    presentation_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"

    # Initialize the clean positioner
    positioner = CleanChartPositioner(presentation_id, correlation_id="example_new_api")

    # Initialize (discovers placeholders)
    success = await positioner.initialize()
    if not success:
        print("Failed to initialize positioner")
        return

    # Chart mappings (cleaner format)
    chart_mappings = {
        "monthly_sales": "https://drive.google.com/uc?id=chart1_file_id",
        "aov": "https://drive.google.com/uc?id=chart2_file_id",
        "demographics": "https://drive.google.com/uc?id=chart3_file_id",
    }

    # Convert to legacy format for positioning (temporary during migration)
    image_map = {f"{{{{{k}_chart}}}}": v for k, v in chart_mappings.items()}
    slide_metadata = {k: {"title": k.replace("_", " ").title()} for k in chart_mappings.keys()}

    # Position charts
    result = await positioner.position_charts_batch(image_map, slide_metadata)

    print(f"Clean positioning result: {result}")
    return result


def example_configuration_management():
    """
    Example 3: Configuration and feature flag management

    Shows how to configure the system for different environments
    and use cases.
    """

    # Check current status
    status = get_positioning_status()
    print(f"Current positioning status: {status}")

    # Configure for gradual rollout (25% of requests use clean mode)
    configure_positioning(
        mode="hybrid",
        rollout_percentage=25.0,
        enable_features={
            "template_discovery": True,
            "batch_operations": True,
            "concurrent_uploads": True,
            "fallback_on_error": True,
        },
    )

    # Check if specific template should use clean positioning
    template_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
    use_clean = should_use_clean_positioning(template_id)
    print(f"Should use clean positioning for {template_id}: {use_clean}")

    # Health check
    health = health_check()
    print(f"System health: {health}")


async def example_template_processing_integration():
    """
    Example 4: Complete template processing with clean positioning

    Shows how the new system integrates with the full template processing pipeline.
    """

    # Mock data from mcp_matplot_run (this would come from your chart generation)
    charts_data = {
        "monthly sales year over year": {
            "title": "Monthly Sales YoY",
            "paragraph": "Sales performance comparison across years...",
            "chart_path": "/tmp/monthly_sales_chart.png",
            "structured_data": "...",
            "chart_type": "bar",
        },
        "AOV": {
            "title": "Average Order Value",
            "paragraph": "Trends in customer spending patterns...",
            "chart_path": "/tmp/aov_chart.png",
            "structured_data": "...",
            "chart_type": "line",
        },
        "scalapay users demographic in percentages": {
            "title": "User Demographics",
            "paragraph": "Breakdown of user base by demographics...",
            "chart_path": "/tmp/demographics_chart.png",
            "structured_data": "...",
            "chart_type": "pie",
        },
    }

    # Template processing with clean positioning
    result = await fill_template_with_clean_positioning(
        drive=None,  # Service instances handled internally
        slides=None,
        results=charts_data,
        template_id="1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o",
        folder_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        verbose=True,
    )

    print(f"Template processing result: {result}")
    return result


async def example_error_handling_and_monitoring():
    """
    Example 5: Error handling and performance monitoring

    Shows how to handle errors gracefully and monitor system performance.
    """

    from scalapay.scalapay_mcp_kam.positioning.monitoring import get_monitor, get_positioning_health, monitor_operation

    # Get performance monitor
    monitor = get_monitor()

    # Example operation with automatic monitoring
    async with monitor_operation("template_processing", "clean", "example_monitor"):
        # Simulate some work
        await asyncio.sleep(0.1)

        # This could raise an exception, which would be automatically recorded
        # raise Exception("Simulated error")

    # Get metrics summary
    metrics = monitor.get_metrics_summary(window_seconds=3600)  # Last hour
    print(f"Performance metrics: {metrics}")

    # Get health status
    health = get_positioning_health()
    print(f"System health: {health}")

    # Export metrics for external monitoring (e.g., Prometheus, DataDog)
    json_metrics = monitor.export_metrics(format="json")
    csv_metrics = monitor.export_metrics(format="csv")

    print(f"Exported {len(json_metrics)} bytes of JSON metrics")
    print(f"Exported {len(csv_metrics)} bytes of CSV metrics")


def example_emergency_procedures():
    """
    Example 6: Emergency rollback and troubleshooting

    Shows emergency procedures when issues are detected.
    """

    # Check if system is healthy
    health = health_check()

    if health["status"] != "healthy":
        print(f"System not healthy: {health}")

        # Emergency rollback to legacy system
        emergency_rollback("System health check failed")
        print("Emergency rollback completed")

    # Manual configuration for specific issues
    configure_positioning(
        mode="legacy",  # Force legacy mode
        rollout_percentage=0.0,  # Stop all clean mode usage
        enable_features={"fallback_on_error": True},  # Ensure fallback is enabled
    )

    # Verify rollback
    status = get_positioning_status()
    print(f"Post-rollback status: {status}")


async def example_migration_strategy():
    """
    Example 7: Migration strategy from legacy to clean implementation

    Shows recommended approach for migrating existing code.
    """

    # Phase 1: Enable clean mode for specific templates only
    configure_positioning(
        mode="hybrid",
        rollout_percentage=0.0,  # Start with 0%
        enable_features={"template_discovery": True, "fallback_on_error": True},
    )

    # Test with specific template
    test_template_id = "test_template_123"

    # Phase 2: Gradual rollout
    for rollout_percentage in [10, 25, 50, 75, 100]:
        print(f"Rolling out to {rollout_percentage}% of requests")

        configure_positioning(rollout_percentage=rollout_percentage)

        # Monitor for issues
        await asyncio.sleep(5)  # Wait for metrics

        health = health_check()
        if health["status"] != "healthy":
            print(f"Issues detected at {rollout_percentage}% rollout: {health}")
            # Rollback
            configure_positioning(rollout_percentage=rollout_percentage - 10)
            break

        print(f"{rollout_percentage}% rollout successful")

    # Phase 3: Full deployment
    configure_positioning(mode="clean", rollout_percentage=100.0)  # Force clean mode for all requests

    print("Migration to clean positioning complete!")


async def main():
    """Run all examples."""

    print("=== Clean Positioning System Examples ===\n")

    # Example 1: Drop-in replacement
    print("1. Drop-in Replacement Example:")
    try:
        await example_drop_in_replacement()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    print()

    # Example 2: New clean API
    print("2. New Clean API Example:")
    try:
        await example_new_clean_api()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    print()

    # Example 3: Configuration
    print("3. Configuration Management Example:")
    try:
        example_configuration_management()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    print()

    # Example 4: Template processing
    print("4. Template Processing Integration Example:")
    try:
        await example_template_processing_integration()
    except Exception as e:
        print(f"Example 4 failed: {e}")
    print()

    # Example 5: Monitoring
    print("5. Error Handling and Monitoring Example:")
    try:
        await example_error_handling_and_monitoring()
    except Exception as e:
        print(f"Example 5 failed: {e}")
    print()

    # Example 6: Emergency procedures
    print("6. Emergency Procedures Example:")
    try:
        example_emergency_procedures()
    except Exception as e:
        print(f"Example 6 failed: {e}")
    print()

    # Example 7: Migration strategy
    print("7. Migration Strategy Example:")
    try:
        await example_migration_strategy()
    except Exception as e:
        print(f"Example 7 failed: {e}")
    print()

    print("=== All Examples Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
