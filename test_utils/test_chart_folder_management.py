#!/usr/bin/env python3
"""
Test script for enhanced chart folder management with execution-specific organization.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the project to path
sys.path.insert(0, "scalapay/scalapay_mcp_kam")


def test_basic_folder_management():
    """Test basic folder management functionality."""
    print("🗂️  Testing Basic Chart Folder Management")
    print("=" * 60)

    try:
        from scalapay.scalapay_mcp_kam.utils.chart_folder_manager import ChartFolderManager

        # Create a temporary base folder for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            test_base = Path(temp_dir) / "test_plots"

            # Test 1: Create manager with execution folders
            print("\n📁 Test 1: Creating manager with execution folders")
            manager1 = ChartFolderManager(
                base_folder=str(test_base), enable_execution_folders=True, correlation_id="test_exec_001"
            )

            print(f"   Execution ID: {manager1.correlation_id}")
            print(f"   Charts folder: {manager1.charts_folder}")
            print(f"   Folders exist: {manager1.charts_folder.exists()}")

            # Test 2: Register some charts
            print("\n📊 Test 2: Registering test charts")
            test_data_types = [
                "monthly sales year over year",
                "AOV by product type",
                "user demographics in percentages",
            ]

            for data_type in test_data_types:
                chart_path = manager1.get_chart_path(data_type)

                # Create a dummy chart file
                Path(chart_path).parent.mkdir(parents=True, exist_ok=True)
                with open(chart_path, "w") as f:
                    f.write(f"dummy chart content for {data_type}")

                # Register the chart
                manager1.register_chart(
                    data_type, chart_path, {"chart_type": "bar" if "sales" in data_type else "line", "test_mode": True}
                )

                print(f"   ✅ {data_type} -> {Path(chart_path).name}")

            # Test 3: Get execution summary
            print("\n📋 Test 3: Execution summary")
            summary = manager1.get_execution_summary()
            print(f"   Total charts: {summary['total_charts']}")
            print(f"   Chart files: {summary['chart_files']}")
            print(f"   Data types: {summary['data_types']}")

            # Test 4: Test finalization
            print("\n✅ Test 4: Finalizing execution")
            manager1.finalize_execution()

            # Test 5: Environment-based manager
            print("\n🌍 Test 5: Environment-based configuration")
            os.environ["SCALAPAY_CHART_BASE_FOLDER"] = str(test_base)
            os.environ["SCALAPAY_ENABLE_EXECUTION_FOLDERS"] = "true"

            manager2 = ChartFolderManager.from_environment("test_exec_002")
            print(f"   Environment manager ID: {manager2.correlation_id}")
            print(f"   Base folder: {manager2.base_folder}")

            return True

    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_integration_with_enhanced_agent():
    """Test integration with enhanced matplotlib agent."""
    print("\n🚀 Testing Integration with Enhanced Agent")
    print("=" * 60)

    try:
        from scalapay.scalapay_mcp_kam.agents.agent_matplot_enhanced import (
            configure_chart_folders_for_execution,
            finalize_chart_execution,
            get_execution_folder_summary,
        )

        # Test 1: Configure for new execution
        print("\n📁 Test 1: Configure folders for execution")
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = configure_chart_folders_for_execution(
                correlation_id="integration_test_001", base_folder=temp_dir, enable_execution_folders=True
            )

            print(f"   Configured manager ID: {manager.correlation_id}")
            print(f"   Charts folder: {manager.charts_folder}")

            # Test 2: Simulate chart registration
            print("\n📊 Test 2: Simulate chart persistence")
            test_charts = [("monthly sales", "line"), ("user demographics", "pie"), ("product analysis", "bar")]

            for data_type, chart_type in test_charts:
                # Create a dummy source file
                source_path = Path(temp_dir) / f"temp_{data_type.replace(' ', '_')}.png"
                with open(source_path, "w") as f:
                    f.write(f"dummy {chart_type} chart for {data_type}")

                # Get target path and register
                target_path = manager.get_chart_path(data_type)
                manager.register_chart(data_type, target_path, {"chart_type": chart_type})

                print(f"   ✅ {data_type} ({chart_type}) -> {Path(target_path).name}")

            # Test 3: Get summary
            print("\n📋 Test 3: Get execution summary")
            summary = get_execution_folder_summary("integration_test_001")
            print(f"   Total charts: {summary.get('total_charts', 0)}")
            if "chart_files" in summary:
                print(f"   Files: {', '.join(summary['chart_files'][:3])}")

            # Test 4: Finalize
            print("\n✅ Test 4: Finalize execution")
            success = finalize_chart_execution("integration_test_001")
            print(f"   Finalization successful: {success}")

        return True

    except Exception as e:
        print(f"💥 Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_environment_variable_usage():
    """Test different environment variable configurations."""
    print("\n🌍 Testing Environment Variable Configurations")
    print("=" * 60)

    test_cases = [
        {"name": "Default configuration", "env": {}},
        {"name": "Custom base folder", "env": {"SCALAPAY_CHART_BASE_FOLDER": "./custom_plots"}},
        {"name": "Execution folders disabled", "env": {"SCALAPAY_ENABLE_EXECUTION_FOLDERS": "false"}},
        {"name": "Custom correlation ID", "env": {"SCALAPAY_CHART_CORRELATION_ID": "custom_corr_123"}},
    ]

    try:
        from scalapay.scalapay_mcp_kam.utils.chart_folder_manager import ChartFolderManager

        # Save original environment
        original_env = {}
        env_vars = ["SCALAPAY_CHART_BASE_FOLDER", "SCALAPAY_ENABLE_EXECUTION_FOLDERS", "SCALAPAY_CHART_CORRELATION_ID"]
        for var in env_vars:
            if var in os.environ:
                original_env[var] = os.environ[var]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 Test {i}: {test_case['name']}")

            # Clear environment
            for var in env_vars:
                if var in os.environ:
                    del os.environ[var]

            # Set test environment
            for key, value in test_case["env"].items():
                os.environ[key] = value

            # Create manager
            manager = ChartFolderManager.from_environment()

            print(f"   Correlation ID: {manager.correlation_id}")
            print(f"   Base folder: {manager.base_folder}")
            print(f"   Execution folders: {manager.enable_execution_folders}")
            print(f"   Charts folder: {manager.charts_folder}")

        # Restore original environment
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
        for var, value in original_env.items():
            os.environ[var] = value

        return True

    except Exception as e:
        print(f"💥 Environment test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Chart Folder Management Test Suite")
    print("=" * 60)

    test_results = []

    # Run tests
    tests = [
        ("Basic Folder Management", test_basic_folder_management),
        ("Enhanced Agent Integration", test_integration_with_enhanced_agent),
        ("Environment Variables", test_environment_variable_usage),
    ]

    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            success = test_func()
            test_results.append((test_name, success))
        except Exception as e:
            print(f"💥 {test_name} crashed: {e}")
            test_results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)

    passed = 0
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} {test_name}")
        if success:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{len(test_results)} tests passed")

    if passed == len(test_results):
        print("🎉 All tests successful! Chart folder management is working correctly.")
        print("\n💡 Usage Examples:")
        print("   export SCALAPAY_CHART_BASE_FOLDER='./my_charts'")
        print("   export SCALAPAY_ENABLE_EXECUTION_FOLDERS='true'")
        print("   # Charts will be organized in execution-specific folders with tracking")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
