"""
Concurrent version of agent_alfred with batching and improved context management.
Addresses context length exceeded errors through batched processing and resource optimization.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from ..agents.agent_alfred import (
    SlidesContent, 
    format_chart_prompt,
    build_slides_struct,
    persist_raw_result,
    derive_normalized_months
)
from ..utils.concurrency_utils import ConcurrencyManager, log_concurrent_operation, create_correlation_id

logger = logging.getLogger(__name__)

# Simplified schema definitions to reduce context size
SIMPLIFIED_SCHEMAS = {
    "monthly sales over time": """
    Return JSON: {"structured_data": {"Jan": {"2023": 66, "2024": 38}, ...}, "paragraph": "Analysis..."}
    """,
    "monthly orders by user type": """
    Return JSON: {"structured_data": {"Oct-22": {"Network": 162, "Returning": 18}, ...}, "paragraph": "Analysis..."}
    """,
    "scalapay users demographic": """
    Return JSON: {"structured_data": {"Age %": {"18-24": 2, "25-34": 6}, "Gender %": {"M": 3, "F": 97}}, "paragraph": "Analysis..."}
    """
}

async def process_single_request(
    agent: MCPAgent,
    llm_struct: ChatOpenAI,
    data_type: str,
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Process a single data request with error handling."""
    corr_id = correlation_id or create_correlation_id()
    entry = {"errors": []}
    
    try:
        # Format prompt with simplified schema
        prompt = format_chart_prompt(
            chart_prompt_template,
            data_type=data_type,
            merchant_token=merchant_token,
            starting_date=starting_date,
            end_date=end_date,
        )
        
        # Add simplified schema if available
        if data_type in SIMPLIFIED_SCHEMAS:
            prompt += "\n\n" + SIMPLIFIED_SCHEMAS[data_type]
        
        logger.debug(f"[{corr_id}] Processing request: {data_type}")
        
        # Run Alfred request
        alfred_result = await agent.run(prompt, max_steps=15)
        entry["alfred_raw"] = alfred_result
        
        # Persist result
        persist_raw_result(data_type, alfred_result)
        
        # Build slides structure
        try:
            slides_struct = await build_slides_struct(llm_struct, alfred_result)
            entry["slides_struct"] = slides_struct
        except Exception as e:
            entry["errors"].append(f"LLM slides struct failed: {e}")
            slides_struct = None
        
        logger.info(f"[{corr_id}] Successfully processed: {data_type}")
        return entry
        
    except Exception as e:
        error_msg = f"Request failed for {data_type}: {e}"
        entry["errors"].append(error_msg)
        logger.error(f"[{corr_id}] {error_msg}")
        return entry

@log_concurrent_operation("batch_processing")
async def process_batch(
    batch: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    correlation_id: str = None
) -> Dict[str, Any]:
    """Process a batch of requests concurrently."""
    corr_id = correlation_id or create_correlation_id()
    
    # Create dedicated client and agent for this batch
    client = MCPClient.from_dict({"mcpServers": {"http": {"url": "http://127.0.0.1:8000/mcp"}}})
    llm = ChatOpenAI(model="gpt-4o")
    agent = MCPAgent(llm=llm, client=client, max_steps=15, verbose=False)
    llm_struct = llm.with_structured_output(SlidesContent)
    
    logger.info(f"[{corr_id}] Processing batch of {len(batch)} requests: {batch}")
    
    # Process all requests in the batch concurrently
    tasks = [
        process_single_request(
            agent, llm_struct, request, merchant_token, starting_date, end_date, 
            chart_prompt_template, f"{corr_id}_{i}"
        )
        for i, request in enumerate(batch)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build batch results
    batch_results = {}
    for request, result in zip(batch, results):
        if isinstance(result, Exception):
            batch_results[request] = {"errors": [str(result)]}
            logger.error(f"[{corr_id}] Batch item failed: {request} - {result}")
        else:
            batch_results[request] = result
    
    logger.info(f"[{corr_id}] Completed batch processing")
    return batch_results

async def mcp_tool_run_concurrent(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    *,
    batch_size: int = 3,
    max_concurrent_batches: int = 3,
    client: MCPClient = None,  # Kept for compatibility but will create dedicated ones
    llm: ChatOpenAI = None     # Kept for compatibility but will create dedicated ones
) -> Dict[str, Any]:
    """
    Concurrent version of mcp_tool_run with batching to prevent context overflow.
    
    Key improvements:
    - Processes requests in batches to stay within context limits
    - Uses dedicated MCP agents per batch to avoid context accumulation
    - Implements concurrent batch processing with rate limiting
    - Uses simplified schemas to reduce token usage
    
    Args:
        requests_list: List of data types to process
        merchant_token: Merchant identifier
        starting_date: Start date for data query
        end_date: End date for data query
        chart_prompt_template: Template for chart generation prompts
        batch_size: Number of requests per batch (default: 3)
        max_concurrent_batches: Maximum concurrent batches (default: 3)
    
    Returns:
        Dict with results for each request type
    """
    correlation_id = create_correlation_id()
    concurrency_manager = ConcurrencyManager(
        max_concurrent_operations=max_concurrent_batches,
        batch_size=batch_size
    )
    
    concurrency_manager.start_timing()
    logger.info(f"[{correlation_id}] Starting concurrent MCP tool run for {len(requests_list)} requests")
    
    # Create batches to prevent context overflow
    batches = concurrency_manager.create_batches(requests_list)
    logger.info(f"[{correlation_id}] Created {len(batches)} batches with max size {batch_size}")
    
    # Process all batches concurrently
    batch_tasks = []
    for i, batch in enumerate(batches):
        batch_corr_id = f"{correlation_id}_batch_{i}"
        task = concurrency_manager.execute_with_retry(
            process_batch,
            batch, merchant_token, starting_date, end_date, chart_prompt_template, batch_corr_id,
            operation_name=f"batch_{i}"
        )
        batch_tasks.append(task)
    
    # Wait for all batches to complete
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    
    # Merge results from all batches
    final_results = {}
    successful_batches = 0
    
    for i, batch_result in enumerate(batch_results):
        if isinstance(batch_result, Exception):
            logger.error(f"[{correlation_id}] Batch {i} failed entirely: {batch_result}")
            # Add error entries for all requests in this batch
            for request in batches[i]:
                final_results[request] = {"errors": [f"Batch processing failed: {batch_result}"]}
        else:
            final_results.update(batch_result)
            successful_batches += 1
    
    # Update metrics
    concurrency_manager.metrics.concurrent_operations_count = len(requests_list)
    concurrency_manager.end_timing()
    concurrency_manager.log_metrics()
    
    logger.info(f"[{correlation_id}] Completed concurrent processing: {successful_batches}/{len(batches)} batches successful")
    logger.info(f"[{correlation_id}] Total time: {concurrency_manager.metrics.total_processing_time:.2f}s")
    
    return final_results

# Backward compatibility function
async def mcp_tool_run_with_fallback(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    *,
    use_concurrent: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Run MCP tool with fallback to sequential processing if concurrent fails.
    
    Args:
        use_concurrent: Whether to use concurrent processing (default: True)
        **kwargs: Additional arguments passed to the processing function
    
    Returns:
        Dict with results from either concurrent or sequential processing
    """
    if use_concurrent:
        try:
            return await mcp_tool_run_concurrent(
                requests_list, merchant_token, starting_date, end_date, 
                chart_prompt_template, **kwargs
            )
        except Exception as e:
            logger.warning(f"Concurrent processing failed, falling back to sequential: {e}")
            # Import the original function for fallback
            from .agent_alfred import mcp_tool_run
            return await mcp_tool_run(
                requests_list, merchant_token, starting_date, end_date, chart_prompt_template
            )
    else:
        # Use original sequential version
        from .agent_alfred import mcp_tool_run
        return await mcp_tool_run(
            requests_list, merchant_token, starting_date, end_date, chart_prompt_template
        )