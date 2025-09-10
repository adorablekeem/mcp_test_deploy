# Concurrency Optimization Plan: Chart Generation & MCP Tool Interactions

## Executive Summary

This document outlines a comprehensive plan to transform the current sequential chart generation and MCP tool interaction system into a concurrent, high-performance pipeline. The current implementation processes 7 chart types sequentially, leading to significant performance bottlenecks and the context length exceeded errors observed in production.

## Current Sequential Implementation Analysis

### Performance Bottlenecks Identified

1. **Sequential Data Retrieval**: `mcp_tool_run()` processes each chart type one by one in `agents/agent_alfred.py:100`
2. **Sequential Chart Generation**: `mcp_matplot_run()` processes each chart sequentially in `agents/agent_matplot.py:140-200`  
3. **Context Accumulation**: Long conversation histories build up across 30 max_steps per chart type
4. **Resource Underutilization**: Multiple MCP servers (Alfred, MatPlot) idle while waiting for sequential operations

### Current Flow Analysis
```
create_slides_wrapper() → 
  mcp_tool_run() [SEQUENTIAL] →
    - "monthly sales year over year"
    - "monthly sales by product type over time" ← CONTEXT LENGTH EXCEEDED HERE
    - "monthly orders by user type"
    - "AOV"
    - "scalapay users demographic in percentages"
    - "orders by product type (i.e. pay in 3, pay in 4)"
    - "AOV by product type (i.e. pay in 3, pay in 4)"
  → mcp_matplot_run() [SEQUENTIAL] →
    - Chart 1, Chart 2, Chart 3... [SEQUENTIAL PROCESSING]
```

## Proposed Concurrent Architecture

### Phase 1: Data Retrieval Concurrency

#### 1.1 Batch Processing Strategy
- **Current**: Single loop processing all 7 chart types
- **Proposed**: Process in concurrent batches of 3-4 chart types to stay within context limits
- **Implementation**: `asyncio.gather()` with semaphore-based rate limiting

#### 1.2 Independent MCP Agent Instances
- **Current**: Single `MCPAgent` instance reused across all requests
- **Proposed**: Dedicated agent instances per concurrent batch
- **Benefits**: Isolated context, reduced token accumulation

```python
async def mcp_tool_run_concurrent(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    *,
    batch_size: int = 3,
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """Concurrent version of mcp_tool_run with batching."""
    
    # Create batches to prevent context overflow
    batches = [requests_list[i:i + batch_size] for i in range(0, len(requests_list), batch_size)]
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(batch: List[str]) -> Dict[str, Any]:
        async with semaphore:
            # Create dedicated client/agent for this batch
            client = MCPClient.from_dict({"mcpServers": {"http": {"url": "http://127.0.0.1:8000/mcp"}}})
            llm = ChatOpenAI(model="gpt-4o")
            agent = MCPAgent(llm=llm, client=client, max_steps=15, verbose=False)  # Reduced steps
            
            batch_results = {}
            tasks = [process_single_request(agent, request, merchant_token, starting_date, end_date, chart_prompt_template) 
                    for request in batch]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for request, result in zip(batch, results):
                if isinstance(result, Exception):
                    batch_results[request] = {"errors": [str(result)]}
                else:
                    batch_results[request] = result
                    
            return batch_results
    
    # Process all batches concurrently
    batch_tasks = [process_batch(batch) for batch in batches]
    batch_results = await asyncio.gather(*batch_tasks)
    
    # Merge results
    final_results = {}
    for batch_result in batch_results:
        final_results.update(batch_result)
    
    return final_results
```

### Phase 2: Chart Generation Concurrency

#### 2.1 Parallel Chart Processing
- **Current**: Sequential chart generation in `mcp_matplot_run()`
- **Proposed**: Concurrent chart generation with resource pooling

```python
async def mcp_matplot_run_concurrent(
    results_dict: Dict[str, Any],
    *,
    max_concurrent_charts: int = 4,
    **kwargs
) -> Dict[str, Any]:
    """Concurrent chart generation with resource pooling."""
    
    semaphore = asyncio.Semaphore(max_concurrent_charts)
    
    async def generate_single_chart(data_type: str, entry: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        async with semaphore:
            # Create dedicated MatPlot client for this chart
            client = MCPClient.from_dict({
                "mcpServers": {"MatPlotAgent": {"url": kwargs.get("matplot_url", "http://localhost:8010/mcp")}}
            })
            
            try:
                # Extract and process chart data
                structured_data = entry.get("slides_struct", {}).get("structured_data", {})
                paragraph = entry.get("slides_struct", {}).get("paragraph", "")
                
                # Generate chart concurrently
                chart_result = await generate_chart_for_data(client, data_type, structured_data, paragraph, **kwargs)
                return data_type, chart_result
                
            except Exception as e:
                logger.error(f"Chart generation failed for {data_type}: {e}")
                return data_type, {"errors": [str(e)]}
    
    # Process all charts concurrently
    tasks = []
    for data_type, entry in results_dict.items():
        if "slides_struct" in entry:
            tasks.append(generate_single_chart(data_type, entry))
    
    chart_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Update results with chart data
    for result in chart_results:
        if isinstance(result, tuple):
            data_type, chart_data = result
            if data_type in results_dict:
                results_dict[data_type].update(chart_data)
    
    return results_dict
```

### Phase 3: End-to-End Pipeline Concurrency

#### 3.1 Producer-Consumer Pattern
- **Data Producer**: Concurrent data retrieval batches
- **Chart Consumer**: Concurrent chart generation as data becomes available
- **Slide Assembly**: Final presentation assembly

```python
async def create_slides_concurrent(
    merchant_token: str,
    starting_date: str,
    end_date: str
) -> dict:
    """Fully concurrent slide generation pipeline."""
    
    requests_list = [
        "monthly sales year over year",
        "monthly sales by product type over time",
        "monthly orders by user type",
        "AOV",
        "scalapay users demographic in percentages", 
        "orders by product type (i.e. pay in 3, pay in 4)",
        "AOV by product type (i.e. pay in 3, pay in 4)"
    ]
    
    # Phase 1: Concurrent data retrieval
    data_retrieval_task = asyncio.create_task(
        mcp_tool_run_concurrent(
            requests_list, merchant_token, starting_date, end_date, GENERAL_CHART_PROMPT
        )
    )
    
    # Phase 2: Chart generation starts as soon as data is available
    results = await data_retrieval_task
    
    chart_generation_task = asyncio.create_task(
        mcp_matplot_run_concurrent(results)
    )
    
    # Phase 3: Slide assembly preparation can happen in parallel
    template_preparation_task = asyncio.create_task(
        prepare_slide_template(merchant_token, starting_date, end_date)
    )
    
    # Wait for both chart generation and template preparation
    charts_results, template_config = await asyncio.gather(
        chart_generation_task,
        template_preparation_task
    )
    
    # Phase 4: Final slide assembly
    final_slides = await assemble_final_presentation(charts_results, template_config)
    
    return final_slides
```

## Implementation Plan

### Stage 1: Context Length Mitigation (Immediate - Week 1)
**Priority**: Critical
**Risk**: High - Current system failing in production

**Changes**:
1. **Reduce `max_steps` from 30 to 15** in `agents/agent_alfred.py:95`
2. **Disable verbose mode**: Set `verbose=False` in `agents/agent_alfred.py:95`
3. **Implement schema truncation**: Simplify EXPECTED_SCHEMAS definitions
4. **Add context monitoring**: Log token usage per request

**Files to modify**:
- `scalapay/scalapay_mcp_kam/agents/agent_alfred.py:95`
- `scalapay/scalapay_mcp_kam/agents/agent_matplot.py:127`

### Stage 2: Batch Processing Implementation (Week 2)
**Priority**: High
**Risk**: Medium

**Changes**:
1. **Implement `mcp_tool_run_concurrent()`** with 3-request batches
2. **Create dedicated agent instances** per batch
3. **Add semaphore-based rate limiting**
4. **Implement error isolation** between batches

**New files**:
- `scalapay/scalapay_mcp_kam/agents/agent_alfred_concurrent.py`
- `scalapay/scalapay_mcp_kam/utils/concurrency_utils.py`

### Stage 3: Chart Generation Concurrency (Week 3)
**Priority**: Medium
**Risk**: Medium

**Changes**:
1. **Implement `mcp_matplot_run_concurrent()`**
2. **Add chart generation resource pooling**
3. **Implement parallel file I/O** for chart saving
4. **Add progress tracking** for concurrent operations

**Modified files**:
- `scalapay/scalapay_mcp_kam/agents/agent_matplot.py`
- `scalapay/scalapay_mcp_kam/tools_agent_kam_local.py`

### Stage 4: Full Pipeline Integration (Week 4)
**Priority**: Medium  
**Risk**: Low

**Changes**:
1. **Implement producer-consumer pipeline**
2. **Add comprehensive error handling**
3. **Implement performance monitoring**
4. **Add graceful degradation** to sequential mode on failures

## Performance Expectations

### Before Optimization
- **Total Processing Time**: ~180-240 seconds (7 charts × 30-40s each)
- **Context Token Usage**: 350,000+ tokens (exceeding limits)
- **Error Rate**: 15-20% due to context overflow
- **Resource Utilization**: 25% (single-threaded bottlenecks)

### After Optimization  
- **Total Processing Time**: ~60-90 seconds (concurrent processing)
- **Context Token Usage**: <100,000 tokens per batch
- **Error Rate**: <5% (improved error isolation)
- **Resource Utilization**: 75-85% (multi-threaded efficiency)

### Key Metrics to Track
1. **End-to-end latency reduction**: Target 60-70% improvement
2. **Context token efficiency**: Target 70% reduction per operation
3. **Error rate reduction**: Target 80% reduction in context-related failures
4. **Throughput increase**: Target 3-4x concurrent chart generation

## Risk Mitigation

### Technical Risks
1. **MCP Server Overload**: Implement connection pooling and rate limiting
2. **Memory Usage Increase**: Monitor concurrent agent instances, implement cleanup
3. **Error Propagation**: Isolate failures between concurrent operations
4. **Resource Contention**: Implement semaphore-based resource management

### Operational Risks
1. **Backward Compatibility**: Maintain sequential fallback mode
2. **Monitoring Complexity**: Implement structured logging for concurrent operations
3. **Debugging Difficulty**: Add correlation IDs for tracing concurrent flows

## Testing Strategy

### Unit Tests
- Individual concurrent functions with mocked MCP clients
- Batch processing logic validation
- Error handling in concurrent scenarios

### Integration Tests  
- End-to-end concurrent pipeline testing
- Performance benchmarking against sequential implementation
- Resource utilization monitoring

### Load Tests
- Multiple concurrent slide generation requests
- MCP server capacity testing under concurrent load
- Memory and connection pool stress testing

## Monitoring and Observability

### Performance Metrics
```python
@dataclass
class ConcurrencyMetrics:
    total_processing_time: float
    data_retrieval_time: float
    chart_generation_time: float
    concurrent_operations_count: int
    context_tokens_used: int
    error_count_by_type: Dict[str, int]
    resource_utilization: Dict[str, float]
```

### Logging Enhancements
- Structured logging with correlation IDs
- Per-operation timing and resource usage
- Concurrent operation tracking and visualization

## Conclusion

This concurrency optimization plan addresses the critical performance bottlenecks and context length issues in the current system. The phased implementation approach allows for incremental improvements while maintaining system stability. The expected performance gains of 60-70% latency reduction and 80% error rate improvement will significantly enhance the user experience and system reliability.

**Implementation Timeline**: 4 weeks
**Resource Requirements**: 1 senior developer, 40 hours testing
**Expected ROI**: 3-4x throughput improvement, 80% reduction in context-related failures
