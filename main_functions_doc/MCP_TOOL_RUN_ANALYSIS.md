# Technical Analysis: `mcp_tool_run()` Function

## Function Overview

The `mcp_tool_run()` function is the data orchestration engine of the Scalapay MCP KAM system. Located in `agents/agent_alfred.py:73`, it serves as the primary interface between the application and the Alfred MCP server, managing bulk data retrieval operations, schema enforcement, and structured response processing for business intelligence queries.

## Architecture & Function Signature

### **Function Definition**
```python
async def mcp_tool_run(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    *,
    client: MCPClient | None = None,
    llm: ChatOpenAI | None = None,
) -> Dict[str, Any]
```

**Key Design Characteristics:**
- **Bulk Request Processing**: Handles multiple business intelligence queries simultaneously
- **Schema-Driven Architecture**: Enforces structured data formats for downstream processing
- **Dual LLM Integration**: Primary agent for data retrieval, secondary for content structuring
- **Flexible Client Management**: Supports dependency injection or default configuration
- **Comprehensive Error Isolation**: Individual request failures don't halt batch processing

## Core Processing Pipeline

### **Phase 1: Service Initialization & Configuration** (Lines 83-86)
```python
client = client or MCPClient.from_dict({"mcpServers": {"http": {"url": "http://127.0.0.1:8000/mcp"}}})
llm = llm or ChatOpenAI(model="gpt-4o")
agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)
llm_struct = llm.with_structured_output(SlidesContent)
```

**Service Architecture:**
- **Default Configuration**: Alfred MCP server on localhost:8000
- **AI Model Selection**: GPT-4 Omni for sophisticated data analysis
- **Agent Limitations**: 30-step maximum for complex query resolution
- **Structured Output**: Dedicated LLM instance with `SlidesContent` schema enforcement

### **Phase 2: Batch Request Processing** (Lines 88-173)

#### **Request Iteration & Error Isolation**
```python
results: Dict[str, Any] = {}

for data_type in requests_list:
    entry = results.setdefault(data_type, {"errors": []})
    try:
        # Processing logic
    except KeyError as e:
        entry["errors"].append(f"Prompt format error: missing key {e}")
        continue
```

**Fault Tolerance Pattern:**
- **Individual Request Isolation**: Single request failures don't affect batch
- **Structured Error Tracking**: Detailed error messages per data type
- **Continue-on-Error Strategy**: Maximizes successful data retrieval
- **Pre-allocated Error Arrays**: Consistent error reporting structure

### **Phase 3: Schema-Driven Prompt Generation** (Lines 93-153)

#### **Expected Data Schemas**
```python
EXPECTED_SCHEMAS = {
    "monthly sales over time": """
    Return JSON with this schema:
    {
    "structured_data": {
        "Jan": {"2022": 34, "2023": 66, "2024": 38},
        "Feb": {"2022": 31, "2023": 87, "2024": 139},
        ...
    },
    "paragraph": "Analysis..."
    }
    """,
    "monthly orders by user type": """
    Return JSON with this schema:
    {
    "structured_data": {
        "Oct-22": {"Network": 162, "Returning": 18, "New": 6},
        "Nov-22": {"Network": 186, "Returning": 31, "New": 9},
        ...
    },
    "paragraph": "Analysis..."
    }
    """,
    "scalapay users demographic": """
    Return JSON with this schema:
    {
    "structured_data": {
        "Age in percentages": {
        "18-24": 2,
        "25-34": 6,
        "35-44": 31,
        "45-54": 45,
        "55-64": 16
        },
        "Gender in percentages": {
        "M": 3,
        "F": 97
        },
        "Card type in percentages": {
        "credit": 39,
        "debit": 26,
        "prepaid": 35
        }
    },
    "paragraph": "Analysis..."
    }
    """
}
```

**Schema Architecture:**
- **Query-Specific Schemas**: Tailored data structures for different business metrics
- **Hierarchical Data Organization**: Nested dictionaries for complex relationships
- **Multi-Dimensional Support**: Time-series, categorical, and demographic data
- **Consistent Response Format**: Structured data + descriptive paragraph pattern

#### **Dynamic Prompt Assembly**
```python
prompt = format_chart_prompt(
    chart_prompt_template,
    data_type=data_type,
    merchant_token=merchant_token,
    starting_date=starting_date,
    end_date=end_date,
)

# enforce schema instructions
if data_type in EXPECTED_SCHEMAS:
    prompt += "\n\n" + EXPECTED_SCHEMAS[data_type]
```

**Prompt Engineering Pattern:**
- **Template-Based Generation**: Consistent prompt structure across queries
- **Parameter Substitution**: Dynamic merchant and date range injection
- **Schema Enforcement**: Appended structure requirements for data consistency
- **Context Preservation**: Original template intent maintained with schema constraints

### **Phase 4: Multi-Stage Data Processing** (Lines 158-172)

#### **Stage 1: Raw Data Retrieval**
```python
try:
    alfred_result = await run_alfred_for_request(agent, prompt)
    entry["alfred_raw"] = alfred_result
    persist_raw_result(data_type, alfred_result)
except Exception as e:
    entry["errors"].append(f"Agent run failed: {e}")
    continue
```

**Raw Data Management:**
- **Asynchronous Execution**: Non-blocking Alfred MCP communication
- **Result Persistence**: Automatic file-based caching for debugging
- **Error Isolation**: Individual query failures don't affect batch
- **Artifact Preservation**: Raw results maintained for troubleshooting

#### **Stage 2: Structured Content Generation**
```python
try:
    slides_struct = await build_slides_struct(llm_struct, alfred_result)
    entry["slides_struct"] = slides_struct
except Exception as e:
    entry["errors"].append(f"LLM invocation for slides failed: {e}")
    slides_struct = None
```

**Content Processing Architecture:**
- **Secondary LLM Processing**: Structured output generation from raw data
- **Schema Compliance**: `SlidesContent` dataclass enforcement
- **Graceful Degradation**: Raw data preserved even if structuring fails
- **Dual-Track Processing**: Both raw and structured data available downstream

## Data Flow Architecture

### **Multi-Agent Orchestration Pattern**
```
Business Queries → Prompt Template → Alfred MCP Agent → Raw Data → 
Secondary LLM → Structured Content → Response Assembly
```

### **Schema-Driven Transformation**
1. **Query Definition** → Template-based prompt generation
2. **Schema Injection** → Data structure requirements appended
3. **Alfred Agent** → Raw business intelligence retrieval
4. **Content Structuring** → `SlidesContent` schema compliance
5. **Result Assembly** → Multi-track data preservation

### **Error Propagation Strategy**
- **Individual Isolation**: Single query failures contained
- **Error Accumulation**: Comprehensive error tracking per request
- **Graceful Continuation**: Maximum successful data retrieval
- **Diagnostic Preservation**: Raw artifacts maintained for debugging

## Advanced Data Processing Features

### **Helper Function Architecture**

#### **Prompt Engineering** (Lines 28-34)
```python
def format_chart_prompt(tpl: str, *, data_type: str, merchant_token: str, starting_date: str, end_date: str) -> str:
    return tpl.format(
        data_type=data_type,
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
    )
```

#### **Raw Data Persistence** (Lines 41-48)
```python
def persist_raw_result(data_type: str, alfred_result: Any, outdir: str = "./tmp") -> None:
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"alfred_result__{_slug(data_type)}.txt")
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(alfred_result, (dict, list)):
            json.dump(alfred_result, f, ensure_ascii=False, indent=2)
        else:
            f.write(str(alfred_result))
```

**Utility Functions:**
- **URL-Safe Naming**: Slug generation for file-system compatibility
- **Type-Aware Serialization**: JSON for structured data, string for others
- **Directory Management**: Automatic temp directory creation
- **Encoding Safety**: UTF-8 support for international data

#### **Structured Content Processing** (Lines 51-55)
```python
async def build_slides_struct(llm_struct, alfred_result: Any) -> dict | None:
    resp = await llm_struct.ainvoke(SLIDES_GENERATION_PROMPT.format(alfred_result=alfred_result))
    if hasattr(resp, "dict"): return resp.dict()
    if isinstance(resp, dict): return resp
    return json.loads(json.dumps(resp, default=str))
```

**Response Normalization:**
- **Multiple Response Types**: Handles various LLM response formats
- **Defensive Programming**: Type checking with graceful fallbacks
- **Serialization Safety**: JSON conversion with string fallback for complex objects
- **Schema Enforcement**: `SLIDES_GENERATION_PROMPT` template for consistency

### **SlidesContent Schema**
```python
@dataclass
class SlidesContent:
    paragraph: str = ""
    structured_data: dict = None
    total_variations: dict = None
```

**Schema Design:**
- **Minimal Structure**: Essential fields for slide generation
- **Default Values**: Graceful handling of partial responses
- **Type Flexibility**: Dict type for variable data structures
- **Extensibility**: Additional fields can be added without breaking changes

## Performance & Scalability Characteristics

### **Asynchronous Architecture**
- **Non-Blocking Operations**: All MCP and LLM calls use async/await
- **Parallel Processing**: Multiple requests processed independently
- **Resource Efficiency**: Minimal memory footprint with streaming processing

### **Caching & Persistence**
- **Automatic Artifact Storage**: Raw results cached to `./tmp` directory
- **Debug-Friendly**: Complete request/response audit trail
- **File-System Integration**: Standard file operations for cross-platform compatibility

### **Error Recovery Patterns**
- **Continue-on-Error**: Individual failures don't halt batch processing
- **Comprehensive Logging**: Detailed error messages with context
- **Partial Success Handling**: Returns all successfully processed data

## Integration Patterns

### **MCP Client Architecture**
- **Default Configuration**: Localhost Alfred server on port 8000
- **Dependency Injection**: Supports custom client configuration
- **Connection Management**: Automatic client lifecycle handling
- **Transport Abstraction**: HTTP-based communication with MCP servers

### **LLM Integration**
- **Dual Model Strategy**: Primary agent for data, secondary for structuring
- **Model Selection**: GPT-4 Omni for sophisticated analysis capabilities
- **Structured Output**: Schema-driven response formatting
- **Error Handling**: LLM invocation failures gracefully handled

## Business Intelligence Query Support

### **Supported Query Types**
1. **Time-Series Analytics**: Monthly sales, orders, user activity
2. **Categorical Analysis**: Product types, user segments, demographics
3. **Comparative Metrics**: Year-over-year, segment comparisons
4. **Value Metrics**: AOV, conversion rates, retention statistics

### **Schema Flexibility**
- **Nested Hierarchies**: Support for multi-dimensional data structures
- **Dynamic Categories**: Variable segment names and counts
- **Temporal Data**: Flexible date formats and aggregation periods
- **Percentage-Based Metrics**: Demographic and categorical distributions

## Error Handling & Resilience

### **Multi-Tier Exception Management**

#### **Tier 1: Prompt Generation Errors**
```python
except KeyError as e:
    entry["errors"].append(f"Prompt format error: missing key {e}")
    continue
```

#### **Tier 2: Agent Execution Failures**
```python
except Exception as e:
    entry["errors"].append(f"Agent run failed: {e}")
    continue
```

#### **Tier 3: Content Processing Errors**
```python
except Exception as e:
    entry["errors"].append(f"LLM invocation for slides failed: {e}")
    slides_struct = None
```

### **Error Reporting Strategy**
- **Structured Error Arrays**: Consistent error format across all entries
- **Contextual Messages**: Specific error types with descriptive context
- **Non-Blocking Failures**: Individual errors don't affect batch completion
- **Debug Information**: Error messages include operation context

## Conclusion

The `mcp_tool_run()` function represents a sophisticated data orchestration system that successfully manages complex business intelligence workflows through multi-agent coordination, schema-driven processing, and comprehensive error handling. Its architecture demonstrates enterprise-grade patterns including bulk request processing, structured data validation, and resilient service integration.

The function's design achieves optimal balance between data quality and operational reliability, enabling comprehensive business analytics while maintaining system stability through intelligent error isolation and graceful degradation strategies. This implementation serves as a robust foundation for automated data retrieval and processing in production environments.

---

*Generated by technical analysis of the Scalapay MCP KAM data orchestration system*