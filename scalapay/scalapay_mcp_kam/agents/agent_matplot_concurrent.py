"""
Concurrent version of agent_matplot with parallel chart generation and resource pooling.
Optimizes chart generation performance through concurrent processing and improved resource management.
"""

import asyncio
import logging
import os
import json
import shutil
from typing import Dict, List, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from ..agents.agent_matplot import _safe_json_loads_maybe_single_quotes
from ..utils.concurrency_utils import (
    ConcurrencyManager, 
    ResourcePool, 
    log_concurrent_operation, 
    create_correlation_id
)

logger = logging.getLogger(__name__)

class MCPClientFactory:
    """Factory for creating MCP clients for chart generation."""
    
    def __init__(self, matplot_url: str, server_id: str, transport: str):
        self.matplot_url = matplot_url
        self.server_id = server_id
        self.transport = transport
    
    async def create_client(self) -> MCPClient:
        """Create a new MCP client instance."""
        client = MCPClient.from_dict({
            "mcpServers": {self.server_id: {"url": self.matplot_url, "type": self.transport}}
        })
        return client

async def generate_single_chart(
    data_type: str,
    entry: Dict[str, Any],
    client_factory: MCPClientFactory,
    llm: ChatOpenAI,
    operation: str,
    max_steps: int,
    correlation_id: str = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a single chart concurrently.
    
    Args:
        data_type: Type of chart/data being processed
        entry: Data entry containing slides_struct and other information
        client_factory: Factory for creating MCP clients
        llm: Language model instance
        operation: MCP operation name
        max_steps: Maximum steps for agent
        correlation_id: Correlation ID for tracking
    
    Returns:
        Tuple of (data_type, chart_result_dict)
    """
    corr_id = correlation_id or create_correlation_id()
    chart_result = {"errors": []}
    
    try:
        # Use the same data extraction logic as the original mcp_matplot_run
        from ..agents.agent_matplot import _extract_struct_and_paragraph
        
        try:
            structured_data, paragraph, total_variations = _extract_struct_and_paragraph(entry)
            if not isinstance(structured_data, dict):
                error_msg = f"No structured_data available or invalid for {data_type}"
                chart_result["errors"].append(error_msg)
                logger.warning(f"[{corr_id}] {error_msg}")
                return data_type, chart_result
        except Exception as extract_e:
            error_msg = f"Data extraction failed for {data_type}: {extract_e}"
            chart_result["errors"].append(error_msg)
            logger.warning(f"[{corr_id}] {error_msg}")
            return data_type, chart_result
        
        logger.debug(f"[{corr_id}] Starting chart generation for {data_type}")
        
        # Create dedicated client and agent for this chart
        client = await client_factory.create_client()
        agent = MCPAgent(llm=llm, client=client, max_steps=max_steps, verbose=False)
        await agent.initialize()
        
        # Find the chart generation tool
        chart_tool = None
        if hasattr(agent, "_tools") and agent._tools:
            for tool in agent._tools:
                if operation in tool.name:
                    chart_tool = tool
                    break
        
        if not chart_tool:
            error_msg = f"Chart tool '{operation}' not found"
            chart_result["errors"].append(error_msg)
            logger.error(f"[{corr_id}] {error_msg}")
            return data_type, chart_result
        
        # Build chart instruction
        chart_instruction = _build_chart_instruction(data_type, structured_data, paragraph)
        
        # Generate chart using the same args structure as the original
        logger.debug(f"[{corr_id}] Calling chart tool for {data_type}")
        
        # Use the same args structure as the original sequential version
        args = {
            "instruction": chart_instruction,
            "chart_type": "auto",
            "model_type": "gpt-4o",
            "workspace_name": "chart_generation",
        }
        
        # Try the same calling patterns as the original
        try:
            try:
                tool_result = await chart_tool.ainvoke(args)  # some wrappers expect a single dict
            except TypeError:
                tool_result = await chart_tool.ainvoke(**args)  # others expect kwargs
        except Exception as e:
            raise Exception(f"MatPlotAgent tool invocation failed: {e}")
        
        # Process tool result using the same logic as the original
        from ..agents.agent_matplot import _to_dict, _persist_plot_ref
        import re
        
        tool_result = _to_dict(tool_result)
        chart_result["matplot_raw"] = tool_result  # keep for debugging
        
        # Recover/ensure chart_path (same logic as original)
        returned_path = tool_result.get("chart_path")
        
        # If missing, scan workspace for any PNG (filename drift)
        if not returned_path:
            ws = tool_result.get("workspace_path")
            if isinstance(ws, str) and os.path.exists(ws) and os.path.isdir(ws):
                try:
                    pngs = [
                        os.path.join(ws, f)
                        for f in os.listdir(ws)
                        if f.lower().endswith(".png")
                    ]
                    if pngs:
                        latest_png = max(pngs, key=os.path.getmtime)
                        returned_path = latest_png
                        tool_result["chart_path"] = returned_path
                        logger.debug(f"[{corr_id}] Found PNG in workspace: {returned_path}")
                except Exception as e:
                    chart_result["errors"].append(f"Workspace scan failed: {e}")
        
        # As a last resort, extract a sandbox link from any raw text (debug-only)
        if not returned_path:
            raw = ""
            if isinstance(tool_result.get("raw"), str):
                raw = tool_result["raw"]
            if raw:
                m = re.search(r"(sandbox:/[^\s\)]*\.png)", raw)
                if m:
                    returned_path = m.group(1)  # not a local file; record only for traceability
                    tool_result["chart_path"] = returned_path
                    chart_result["errors"].append(
                        "Chart path points to a sandbox link (not a local file on this system)."
                    )
        
        # Persist/copy PNG into ./plots and set chart_path
        try:
            if returned_path:
                chart_path = _persist_plot_ref(data_type, returned_path)
                chart_result["chart_path"] = chart_path
                if chart_path:
                    logger.info(f"[{corr_id}] Chart saved for {data_type}: {chart_path}")
                else:
                    chart_result["errors"].append("Failed to persist chart file")
            else:
                chart_result["errors"].append("MatPlotAgent did not return a PNG path.")
        except Exception as e:
            chart_result["errors"].append(f"Chart persistence failed: {e}")
            logger.error(f"[{corr_id}] Chart persistence failed for {data_type}: {e}")
        
        return data_type, chart_result
        
    except Exception as e:
        error_msg = f"Chart generation failed for {data_type}: {e}"
        chart_result["errors"].append(error_msg)
        logger.error(f"[{corr_id}] {error_msg}")
        return data_type, chart_result

def _build_chart_instruction(data_type: str, structured_data: dict, paragraph: str) -> str:
    """Build chart instruction string for MatPlot tool."""
    data_json = json.dumps(structured_data, ensure_ascii=False)
    
    instruction = f"""Create a clean, publication-quality Matplotlib chart from the data below. 
Do NOT call plt.show(). Save the figure exactly as 'chart_output.png' at 300 DPI. 
Use readable axis labels; include a legend if multiple series exist.

Title: {data_type}
Data (JSON): {data_json}

Notes: {paragraph}"""
    
    return instruction

@log_concurrent_operation("concurrent_chart_generation")
async def mcp_matplot_run_concurrent(
    results_dict: Dict[str, Any] | str,
    *,
    max_concurrent_charts: int = 4,
    client: MCPClient | None = None,  # Kept for compatibility but will create dedicated ones
    llm: ChatOpenAI | None = None,
    matplot_url: str = "http://localhost:8010/mcp",
    server_id: str = "MatPlotAgent", 
    operation: str = "generate_chart_simple",
    model_type: str = "gpt-4o",
    max_steps: int = 15,
    verbose: bool = False,  # Forced to False for concurrent version
    transport: str = "http"
) -> Dict[str, Any]:
    """
    Concurrent version of mcp_matplot_run with parallel chart generation.
    
    Key improvements:
    - Processes charts concurrently instead of sequentially
    - Uses resource pooling for MCP clients
    - Implements safe file naming to avoid collisions
    - Provides better error isolation between chart generations
    
    Args:
        results_dict: Dictionary with data for chart generation
        max_concurrent_charts: Maximum concurrent chart generations (default: 4)
        Other args: Same as original mcp_matplot_run
    
    Returns:
        Dict with chart paths and metadata for each data type
    """
    correlation_id = create_correlation_id()
    
    # Normalize input
    if isinstance(results_dict, str):
        results_dict = _safe_json_loads_maybe_single_quotes(results_dict)
    if not isinstance(results_dict, dict):
        raise TypeError("mcp_matplot_run_concurrent expected dict or JSON string yielding a dict.")
    
    # Setup concurrency management
    concurrency_manager = ConcurrencyManager(
        max_concurrent_operations=max_concurrent_charts,
        retry_attempts=2
    )
    
    concurrency_manager.start_timing()
    logger.info(f"[{correlation_id}] Starting concurrent chart generation for {len(results_dict)} charts")
    
    # Setup shared resources
    llm = llm or ChatOpenAI(model=model_type)
    client_factory = MCPClientFactory(matplot_url, server_id, transport)
    
    # Filter entries that have processable data (ready for chart generation)
    chart_tasks = []
    processable_entries = {}
    
    def has_chart_data(entry, data_type=None):
        """Check if entry has data available for chart generation."""
        if not isinstance(entry, dict):
            return False
        
        # Check for slides_struct format
        if "slides_struct" in entry:
            slides_struct = entry["slides_struct"]
            if isinstance(slides_struct, dict) and slides_struct.get("structured_data"):
                return True
        
        # Check for direct format
        if entry.get("structured_data"):
            return True
            
        # Check for alfred_raw format
        if "alfred_raw" in entry:
            alfred_raw = entry["alfred_raw"]
            if isinstance(alfred_raw, dict) and alfred_raw.get("structured_data"):
                return True
            # Try parsing string format
            if isinstance(alfred_raw, str):
                try:
                    import json
                    import ast
                    try:
                        parsed = json.loads(alfred_raw)
                    except json.JSONDecodeError:
                        parsed = ast.literal_eval(alfred_raw)
                    if parsed.get("structured_data"):
                        return True
                except:
                    pass
        
        # Check tmp file as last resort
        if data_type:
            try:
                import os
                from ..agents.agent_alfred import _slug
                tmp_file = f"./tmp/alfred_result__{_slug(data_type)}.txt"
                if os.path.exists(tmp_file):
                    return True
            except:
                pass
        
        return False
    
    for data_type, entry in results_dict.items():
        if has_chart_data(entry, data_type):
            processable_entries[data_type] = entry
            
            # Create concurrent task for this chart
            task_corr_id = f"{correlation_id}_chart_{len(chart_tasks)}"
            task = concurrency_manager.execute_with_retry(
                generate_single_chart,
                data_type, entry, client_factory, llm, operation, max_steps, task_corr_id,
                operation_name=f"chart_{data_type}"
            )
            chart_tasks.append(task)
        else:
            logger.debug(f"[{correlation_id}] Skipping {data_type} - no chart data available. Entry keys: {list(entry.keys()) if isinstance(entry, dict) else 'Not a dict'}")
    
    if not chart_tasks:
        logger.warning(f"[{correlation_id}] No processable entries found for chart generation")
        return results_dict
    
    logger.info(f"[{correlation_id}] Processing {len(chart_tasks)} charts concurrently")
    
    # Execute all chart generation tasks concurrently
    chart_results = await asyncio.gather(*chart_tasks, return_exceptions=True)
    
    # Process results and update original dict
    successful_charts = 0
    for result in chart_results:
        if isinstance(result, Exception):
            logger.error(f"[{correlation_id}] Chart generation task failed: {result}")
            continue
        
        if isinstance(result, tuple) and len(result) == 2:
            data_type, chart_data = result
            if data_type in results_dict:
                # Update the original entry with chart information
                results_dict[data_type].update(chart_data)
                if "chart_path" in chart_data:
                    successful_charts += 1
        else:
            logger.error(f"[{correlation_id}] Unexpected result format: {result}")
    
    # Update metrics and log results
    concurrency_manager.metrics.concurrent_operations_count = len(chart_tasks)
    concurrency_manager.end_timing()
    concurrency_manager.log_metrics()
    
    logger.info(f"[{correlation_id}] Completed concurrent chart generation")
    logger.info(f"[{correlation_id}] Success rate: {successful_charts}/{len(chart_tasks)} charts")
    logger.info(f"[{correlation_id}] Total time: {concurrency_manager.metrics.total_processing_time:.2f}s")
    
    return results_dict

# Backward compatibility function
async def mcp_matplot_run_with_fallback(
    results_dict: Dict[str, Any] | str,
    *,
    use_concurrent: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Run MCP matplot with fallback to sequential processing if concurrent fails.
    
    Args:
        results_dict: Input data for chart generation
        use_concurrent: Whether to use concurrent processing (default: True)
        **kwargs: Additional arguments passed to the processing function
    
    Returns:
        Dict with chart generation results
    """
    if use_concurrent:
        try:
            return await mcp_matplot_run_concurrent(results_dict, **kwargs)
        except Exception as e:
            logger.warning(f"Concurrent chart generation failed, falling back to sequential: {e}")
            # Import the original function for fallback
            from .agent_matplot import mcp_matplot_run
            return await mcp_matplot_run(results_dict, **kwargs)
    else:
        # Use original sequential version
        from .agent_matplot import mcp_matplot_run
        return await mcp_matplot_run(results_dict, **kwargs)