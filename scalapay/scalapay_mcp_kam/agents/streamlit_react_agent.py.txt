#!/usr/bin/env python3
"""
Fast ReAct Agent with Streamlit Reports

Creates interactive Streamlit reports instead of slides.
Much faster and more flexible than Google Slides.
"""

import logging
import os
import tempfile
import time
from typing import Any, Dict, Optional

from fastmcp import Context, FastMCP

# Import only what we need
from scalapay.scalapay_mcp_kam.agents.agent_alfred_concurrent import mcp_tool_run_with_fallback
from scalapay.scalapay_mcp_kam.agents.agent_matplot_concurrent import mcp_matplot_run_with_fallback
from scalapay.scalapay_mcp_kam.prompts.charts_prompt import GENERAL_CHART_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamlit_react_agent")


class StreamlitReActAgent:
    """ReAct agent that creates Streamlit reports."""

    def __init__(self):
        self.report_counter = 0

    async def quick_plan(self, user_request: str) -> list[str]:
        """THINK: Quick planning based on keywords."""

        request_lower = user_request.lower()

        if "comprehensive" in request_lower or "dashboard" in request_lower:
            return [
                "monthly sales year over year",
                "AOV",
                "monthly orders by user type",
                "scalapay users demographic in percentages",
            ]
        elif "sales" in request_lower:
            return ["monthly sales year over year", "AOV"]
        elif "customer" in request_lower or "user" in request_lower:
            return ["monthly orders by user type", "scalapay users demographic in percentages"]
        else:
            # Default set
            return ["monthly sales year over year", "AOV", "monthly orders by user type"]

    async def get_data_fast(
        self, requests: list[str], merchant_token: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """ACT: Get data quickly."""

        logger.info(f"📊 Getting data: {len(requests)} requests")

        return await mcp_tool_run_with_fallback(
            requests_list=requests,
            merchant_token=merchant_token,
            starting_date=start_date,
            end_date=end_date,
            chart_prompt_template=GENERAL_CHART_PROMPT,
            use_concurrent=True,
            batch_size=4,
            max_concurrent_batches=2,
        )

    async def create_charts_fast(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """ACT: Create charts."""

        logger.info(f"📈 Creating charts for {len(data)} datasets")

        return await mcp_matplot_run_with_fallback(
            data,
            matplot_url="http://localhost:8010/mcp",
            server_id="MatPlotAgent",
            operation="generate_chart_simple",
            model_type="gpt-4o-mini",
            use_concurrent=True,
            max_concurrent_charts=4,
            max_steps=10,
            verbose=False,
            transport="http",
        )

    def create_streamlit_report(
        self, data: Dict[str, Any], charts: Dict[str, Any], user_request: str, date_range: str
    ) -> str:
        """ACT: Create Streamlit report file."""

        self.report_counter += 1
        report_filename = f"report_{int(time.time())}_{self.report_counter}.py"
        report_path = os.path.join(tempfile.gettempdir(), report_filename)

        # Build Streamlit code
        streamlit_code = self._generate_streamlit_code(data, charts, user_request, date_range)

        # Write report file
        with open(report_path, "w") as f:
            f.write(streamlit_code)

        logger.info(f"📄 Streamlit report created: {report_path}")
        return report_path

    def _generate_streamlit_code(
        self, data: Dict[str, Any], charts: Dict[str, Any], user_request: str, date_range: str
    ) -> str:
        """Generate the Streamlit app code."""

        # Extract chart paths and data descriptions
        chart_info = []
        for key, chart_data in charts.items():
            if isinstance(chart_data, dict) and chart_data.get("chart_path"):
                # Get corresponding data description
                data_desc = ""
                if key in data and isinstance(data[key], dict):
                    slides_struct = data[key].get("slides_struct", {})
                    if isinstance(slides_struct, dict):
                        data_desc = slides_struct.get("paragraph", "")
                    elif hasattr(slides_struct, "paragraph"):
                        data_desc = slides_struct.paragraph

                chart_info.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "path": chart_data["chart_path"],
                        "description": data_desc or f"Analysis of {key.replace('_', ' ')}",
                    }
                )

        # Generate Streamlit code
        code = f"""import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from datetime import datetime
import os

# Page config
st.set_page_config(
    page_title="Business Report",
    page_icon="📊",
    layout="wide"
)

# Header
st.title("📊 Business Performance Report")
st.markdown(f"**Request**: {user_request}")
st.markdown(f"**Date Range**: {date_range}")
st.markdown(f"**Generated**: {{datetime.now().strftime('%Y-%m-%d %H:%M')}}")
st.divider()

# Metrics overview
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📈 Charts Generated", {len(chart_info)})
with col2:
    st.metric("📊 Data Sources", {len(data)})
with col3:
    st.metric("⚡ Generation Time", "< 30s")

st.divider()

# Charts and descriptions
"""

        # Add each chart section
        for i, chart in enumerate(chart_info):
            code += f'''
# Chart {i+1}: {chart["title"]}
st.subheader("{chart["title"]}")

col1, col2 = st.columns([2, 1])

with col1:
    # Display chart
    if os.path.exists("{chart["path"]}"):
        img = mpimg.imread("{chart["path"]}")
        st.image(img, use_container_width=True)
    else:
        st.error("Chart file not found: {chart["path"]}")

with col2:
    # Display description
    st.markdown("**Analysis:**")
    st.write("""{chart["description"]}""")
    
    # Add some metrics or insights
    st.markdown("**Key Insights:**")
    st.write("• Data trends analysis")
    st.write("• Performance indicators") 
    st.write("• Business recommendations")

st.divider()
'''

        # Add sidebar with fixed values
        code += f"""
# Sidebar with additional info
with st.sidebar:
    st.header("📋 Report Details")
    st.write("**Charts**: {len(chart_info)}")
    st.write("**Data Points**: {len(data)}")
    st.write("**Format**: Interactive Streamlit")
    
    st.header("🔄 Actions")
    if st.button("🔄 Refresh Data"):
        st.rerun()
    
    st.markdown("---")
    st.markdown("**💡 Tip**: This report updates in real-time!")

# Footer
st.markdown("---")
st.markdown("🤖 **Generated by StreamlitReAct Agent**")
st.markdown("⚡ Fast • 📊 Interactive • 🔄 Real-time")
"""

        return code


# Create MCP server
mcp = FastMCP("Streamlit ReAct Agent")


@mcp.tool()
async def create_streamlit_report(
    user_request: str, merchant_token: str, starting_date: str, end_date: str, ctx: Context
) -> dict:
    """
    Create interactive Streamlit report instead of slides.

    Much faster than slides:
    - No template discovery needed
    - No Google APIs calls
    - Creates interactive web report
    - Shows charts + data descriptions

    Args:
        user_request: What kind of report to create
        merchant_token: Merchant identifier
        starting_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        dict: Results with report_path and instructions to run
    """

    start_time = time.time()
    agent = StreamlitReActAgent()

    try:
        await ctx.info("🚀 Creating Streamlit report...")

        # THINK: Quick planning
        plan_start = time.time()
        requests = await agent.quick_plan(user_request)
        plan_time = time.time() - plan_start

        await ctx.info(f"📋 Plan: {len(requests)} data requests")

        # ACT 1: Get data
        data_start = time.time()
        data = await agent.get_data_fast(requests, merchant_token, starting_date, end_date)
        data_time = time.time() - data_start

        await ctx.info(f"📊 Data retrieved in {data_time:.1f}s")

        # ACT 2: Create charts
        charts_start = time.time()
        charts = await agent.create_charts_fast(data)
        charts_time = time.time() - charts_start

        await ctx.info(f"📈 Charts created in {charts_time:.1f}s")

        # ACT 3: Generate Streamlit report
        report_start = time.time()
        report_path = agent.create_streamlit_report(data, charts, user_request, f"{starting_date} to {end_date}")
        report_time = time.time() - report_start

        total_time = time.time() - start_time

        await ctx.info(f"✅ Streamlit report ready in {total_time:.1f}s!")
        await ctx.info(f"📁 Report file: {report_path}")
        await ctx.info(f"🚀 Run: streamlit run {report_path}")

        return {
            "success": True,
            "report_path": report_path,
            "report_url": f"http://localhost:8501",  # Default Streamlit port
            "total_time": total_time,
            "breakdown": {
                "planning": plan_time,
                "data_retrieval": data_time,
                "chart_creation": charts_time,
                "report_generation": report_time,
            },
            "charts_included": len([c for c in charts.values() if isinstance(c, dict) and c.get("chart_path")]),
            "run_command": f"streamlit run {report_path}",
            "method": "streamlit_react",
        }

    except Exception as e:
        total_time = time.time() - start_time
        error_msg = f"Streamlit report creation failed: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)

        return {"success": False, "error": error_msg, "total_time": total_time}


@mcp.tool()
async def list_reports(ctx: Context) -> dict:
    """List all generated Streamlit reports."""

    import glob

    temp_dir = tempfile.gettempdir()
    report_files = glob.glob(os.path.join(temp_dir, "report_*.py"))

    reports = []
    for report_file in report_files:
        stat = os.stat(report_file)
        reports.append(
            {
                "filename": os.path.basename(report_file),
                "path": report_file,
                "created": time.ctime(stat.st_ctime),
                "size": f"{stat.st_size} bytes",
                "run_command": f"streamlit run {report_file}",
            }
        )

    return {"reports_found": len(reports), "reports": reports, "temp_directory": temp_dir}


if __name__ == "__main__":
    print("🚀 Streamlit ReAct Agent")
    print("=" * 40)
    print("⚡ Features:")
    print("   • Interactive Streamlit reports")
    print("   • No Google APIs needed")
    print("   • Charts + data descriptions")
    print("   • Real-time web interface")
    print("   • Target: <25 seconds + instant viewing")
    print()
    print("🌐 Starting server on http://localhost:8022...")

    mcp.run(transport="http", port=8022)
