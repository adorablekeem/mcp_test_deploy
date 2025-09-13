#!/usr/bin/env python3
"""
Pre-workflow setup script for enhanced chart folder management.
Run this before executing create_slides to ensure proper configuration.
"""

import os
import sys
from pathlib import Path


def setup_chart_folder_management():
    """Configure environment for enhanced chart folder management."""
    print("🚀 Pre-Workflow Setup: Enhanced Chart Folder Management")
    print("=" * 60)

    # Set optimal environment variables
    os.environ["SCALAPAY_ENABLE_EXECUTION_FOLDERS"] = "true"
    os.environ["SCALAPAY_CHART_BASE_FOLDER"] = "./plots"

    # Optional: Set a recognizable correlation ID
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    correlation_id = f"workflow_{timestamp}"
    os.environ["SCALAPAY_CHART_CORRELATION_ID"] = correlation_id

    print("✅ Environment variables configured:")
    print(f"   SCALAPAY_ENABLE_EXECUTION_FOLDERS = {os.getenv('SCALAPAY_ENABLE_EXECUTION_FOLDERS')}")
    print(f"   SCALAPAY_CHART_BASE_FOLDER = {os.getenv('SCALAPAY_CHART_BASE_FOLDER')}")
    print(f"   SCALAPAY_CHART_CORRELATION_ID = {correlation_id}")

    # Test the system
    try:
        sys.path.insert(0, "scalapay/scalapay_mcp_kam")
        from scalapay.scalapay_mcp_kam.utils.chart_folder_manager import ChartFolderManager

        manager = ChartFolderManager.from_environment()

        print(f"\n📁 Execution folder prepared:")
        print(f"   Execution ID: {manager.correlation_id}")
        print(f"   Charts folder: {manager.charts_folder}")
        print(f"   Metadata folder: {manager.metadata_folder}")
        print(f"   Folders created: {manager.charts_folder.exists()}")

        return True, manager.correlation_id, str(manager.charts_folder)

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False, None, None


def verify_integration():
    """Verify that enhanced chart persistence is integrated."""
    print(f"\n🔧 Verifying Enhanced Agent Integration:")
    print("-" * 40)

    try:
        sys.path.insert(0, "scalapay/scalapay_mcp_kam")
        from scalapay.scalapay_mcp_kam.agents.agent_matplot_enhanced import _persist_plot_ref_enhanced

        print("✅ Enhanced chart persistence available")

        # Check concurrent agent integration
        concurrent_agent_path = Path("scalapay/scalapay_mcp_kam/agents/agent_matplot_concurrent.py")
        if concurrent_agent_path.exists():
            with open(concurrent_agent_path, "r") as f:
                content = f.read()
                if "_persist_plot_ref_enhanced" in content:
                    print("✅ Concurrent agent integrated with enhanced persistence")
                else:
                    print("⚠️  Concurrent agent not using enhanced persistence")

        return True

    except Exception as e:
        print(f"❌ Integration check failed: {e}")
        return False


def show_next_steps(correlation_id, charts_folder):
    """Show next steps for running the workflow."""
    print(f"\n🎯 Ready to Run Workflow!")
    print("=" * 30)
    print(f"Your charts will be organized in:")
    print(f"   📁 {charts_folder}")
    print(f"   📋 Execution ID: {correlation_id}")
    print(f"\nNext steps:")
    print(f"1. Run your normal create_slides workflow")
    print(f"2. Charts will be automatically organized by execution")
    print(f"3. Check results: ls {charts_folder}")
    print(f"4. View manifest: cat {Path(charts_folder).parent}/metadata/execution_manifest.json")

    # Export instructions
    print(f"\n💡 For manual setup, use these commands:")
    print(f"export SCALAPAY_ENABLE_EXECUTION_FOLDERS=true")
    print(f"export SCALAPAY_CHART_BASE_FOLDER=./plots")
    print(f"export SCALAPAY_CHART_CORRELATION_ID={correlation_id}")


def main():
    """Main setup function."""
    success, correlation_id, charts_folder = setup_chart_folder_management()

    if success:
        integration_ok = verify_integration()

        if integration_ok:
            show_next_steps(correlation_id, charts_folder)
            print(f"\n🎉 Setup complete! Ready to run create_slides workflow.")
            return True
        else:
            print(f"\n⚠️  Setup completed but integration issues detected.")
            return False
    else:
        print(f"\n❌ Setup failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
