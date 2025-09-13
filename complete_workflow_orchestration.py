#!/usr/bin/env python3
"""
Complete End-to-End Workflow with Full Context Logging
Orchestrates Alfred data retrieval, MatPlot chart generation, and Google Slides creation
with comprehensive real-time progress updates via MCP context logging.
"""
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context

# Import the enhanced functions with context logging
from scalapay.scalapay_mcp_kam.agents.agent_alfred import mcp_tool_run
from scalapay.scalapay_mcp_kam.agents.agent_matplot import mcp_matplot_run
from scalapay.scalapay_mcp_kam.tools_agent_kam import create_slides
from scalapay.scalapay_mcp_kam.prompts.charts_prompt import GENERAL_CHART_PROMPT

logger = logging.getLogger(__name__)


async def create_complete_slides_workflow(
    merchant_token: str,
    starting_date: str, 
    end_date: str,
    data_requests: List[str],
    ctx: Context | None = None
) -> Dict[str, Any]:
    """
    Complete end-to-end slide generation workflow with full context logging
    
    Args:
        merchant_token: Merchant identifier (e.g., "Zalando")
        starting_date: Start date for data retrieval (e.g., "2024-01-01")
        end_date: End date for data retrieval (e.g., "2024-12-31")
        data_requests: List of data types to retrieve (e.g., ["monthly sales over time", "orders by user type"])
        ctx: MCP context for real-time progress updates
        
    Returns:
        Complete workflow results including data, charts, and slides
    """
    if ctx:
        await ctx.info("🚀 Starting complete slide generation workflow")
        await ctx.info(f"📊 Target merchant: {merchant_token}")
        await ctx.info(f"📅 Date range: {starting_date} to {end_date}")
        await ctx.info(f"📋 Data requests: {len(data_requests)} types")
        
    workflow_results = {
        "alfred_results": None,
        "chart_results": None,
        "slide_results": None,
        "success": False,
        "errors": []
    }
    
    try:
        # PHASE 1: Alfred Data Retrieval
        if ctx:
            await ctx.info("🔍 PHASE 1: Data Retrieval")
            
        alfred_results = await mcp_tool_run(
            requests_list=data_requests,
            merchant_token=merchant_token,
            starting_date=starting_date,
            end_date=end_date,
            chart_prompt_template=GENERAL_CHART_PROMPT,
            ctx=ctx  # Pass context through for detailed logging
        )
        
        workflow_results["alfred_results"] = alfred_results
        
        # Validate Alfred results
        successful_data = len([k for k, v in alfred_results.items() if not v.get("errors")])
        if successful_data == 0:
            if ctx:
                await ctx.error("❌ No data retrieved successfully from Alfred")
            workflow_results["errors"].append("No data retrieved from Alfred")
            return workflow_results
            
        if ctx:
            await ctx.info(f"✅ Phase 1 complete: {successful_data}/{len(data_requests)} data types retrieved")
        
        # PHASE 2: Chart Generation
        if ctx:
            await ctx.info("📊 PHASE 2: Chart Generation")
            
        chart_results = await mcp_matplot_run(
            results_dict=alfred_results,
            ctx=ctx  # Pass context through for detailed logging
        )
        
        workflow_results["chart_results"] = chart_results
        
        # Validate chart results
        successful_charts = len([v for v in chart_results.values() if isinstance(v, dict) and v.get("chart_path") and not v.get("errors")])
        if successful_charts == 0:
            if ctx:
                await ctx.warning("⚠️ No charts generated successfully - proceeding with slides anyway")
        else:
            if ctx:
                await ctx.info(f"✅ Phase 2 complete: {successful_charts} charts generated")
        
        # PHASE 3: Slide Creation  
        if ctx:
            await ctx.info("📄 PHASE 3: Slide Creation")
            
        slide_results = await create_slides(
            merchant_token=merchant_token,
            starting_date=starting_date,
            end_date=end_date,
            ctx=ctx  # Pass context through for detailed logging
        )
        
        workflow_results["slide_results"] = slide_results
        
        if slide_results.get("error"):
            if ctx:
                await ctx.error(f"❌ Slide creation failed: {slide_results['error']}")
            workflow_results["errors"].append(f"Slide creation failed: {slide_results['error']}")
        else:
            workflow_results["success"] = True
            if ctx:
                await ctx.info("✅ Phase 3 complete: Slides generated successfully")
        
        if ctx:
            await ctx.info("🎉 Complete workflow finished!")
            
    except Exception as e:
        error_msg = f"Workflow failed: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}")
        workflow_results["errors"].append(error_msg)
        logger.exception("Complete workflow failed")
        
    return workflow_results


async def create_slides_with_charts_workflow(
    merchant_token: str,
    starting_date: str,
    end_date: str,
    ctx: Context | None = None
) -> Dict[str, Any]:
    """
    Predefined workflow with common data requests for merchant slide generation
    
    Args:
        merchant_token: Merchant identifier
        starting_date: Start date for data
        end_date: End date for data  
        ctx: MCP context for progress updates
        
    Returns:
        Complete workflow results
    """
    # Predefined common data requests
    common_data_requests = [
        "monthly sales over time",
        "orders by user type", 
        "scalapay users demographic",
        "AOV by product type",
        "monthly orders by user type",
        "monthly sales by product type over time"
    ]
    
    return await create_complete_slides_workflow(
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
        data_requests=common_data_requests,
        ctx=ctx
    )


# Progress tracking for complex workflows
class WorkflowProgressTracker:
    """Track workflow progress with percentage completion"""
    
    def __init__(self, total_phases: int = 3, ctx: Context | None = None):
        self.total_phases = total_phases
        self.current_phase = 0
        self.ctx = ctx
        
    async def start_phase(self, phase_name: str):
        """Start a new phase and update progress"""
        self.current_phase += 1
        if self.ctx:
            percentage = int((self.current_phase / self.total_phases) * 100)
            await self.ctx.info(f"[{percentage}%] {phase_name}")
            
    async def update_phase_progress(self, message: str, current: int = None, total: int = None):
        """Update progress within current phase"""
        if self.ctx:
            if current is not None and total is not None:
                phase_percentage = int((current / total) * 100)
                await self.ctx.info(f"  📊 {message} ({current}/{total} - {phase_percentage}%)")
            else:
                await self.ctx.info(f"  📊 {message}")


async def example_enhanced_workflow():
    """Example demonstrating the enhanced workflow with progress tracking"""
    
    # Example usage with progress tracking
    progress = WorkflowProgressTracker(total_phases=3, ctx=None)  # ctx would be passed from MCP
    
    # This would show:
    # [33%] Data Retrieval Phase
    #   📊 Processing request 1/6 (17%)  
    #   📊 Processing request 2/6 (33%)
    # [67%] Chart Generation Phase  
    #   📊 Generating chart 1/4 (25%)
    #   📊 Generating chart 2/4 (50%)
    # [100%] Slide Creation Phase
    #   📊 Text replacements complete
    #   📊 Image positioning applied
    
    result = await create_slides_with_charts_workflow(
        merchant_token="Zalando",
        starting_date="2024-01-01", 
        end_date="2024-12-31",
        ctx=None  # Would be actual context in real usage
    )
    
    return result


if __name__ == "__main__":
    import asyncio
    
    # Example execution
    async def main():
        result = await example_enhanced_workflow()
        print(f"Workflow completed: {result['success']}")
        if result["errors"]:
            print(f"Errors: {result['errors']}")
            
    asyncio.run(main())