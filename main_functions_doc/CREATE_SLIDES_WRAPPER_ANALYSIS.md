# Technical Analysis: `create_slides_wrapper` Function

## Function Overview

The `create_slides_wrapper` function serves as the primary entry point for the Scalapay MCP KAM server's automated slide generation pipeline. Located in `mcp_server.py:22`, it's exposed as an MCP tool that orchestrates the complete workflow from merchant data elicitation to PDF slide delivery.

## Architecture & Data Flow

### 1. **Function Signature & Parameters**
```python
async def create_slides_wrapper(merchant_token: str, starting_date: str, end_date: str, ctx: Context | None = None) -> dict
```

- **Input Validation**: Accepts merchant identification, date range, and optional MCP context
- **Asynchronous Design**: Enables non-blocking execution for concurrent operations
- **Context Awareness**: Integrates with FastMCP's context system for real-time user feedback

### 2. **Execution Pipeline**

#### **Stage 1: Core Function Delegation**
The wrapper immediately delegates to `create_slides()` from `tools_agent_kam.py:25`, following a clean separation of concerns pattern where the MCP tool handles protocol concerns while the core logic resides in dedicated modules.

#### **Stage 2: Data Processing Chain**
```python
# Static data generation (current implementation)
data = {
    "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    "Sales": [4174, 4507, 1860, 2294, 2130, 3468],
    "Profit": [1244, 321, 666, 1438, 530, 892]
}
df = pd.DataFrame(data)
```

*Note: The commented Alfred MCP integration suggests future dynamic data retrieval capabilities*

#### **Stage 3: Visualization Generation**
- **Matplotlib Integration**: Creates publication-ready charts with 300 DPI resolution
- **File System Storage**: Persists charts to `/tmp/monthly_sales_profit_chart.png`
- **Dual-metric Plotting**: Generates line charts for sales and profit trends

#### **Stage 4: Google Slides Operations**
1. **Template Duplication**: Clones presentation `1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o`
2. **Text Replacement**: Substitutes `{{bot}}` placeholders with merchant token
3. **File Organization**: Moves presentations to designated folder `1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL`

#### **Stage 5: Asset Integration**
- **Chart Upload**: Transfers local chart to Google Drive
- **Image Insertion**: Replaces shape placeholders (`{{image1}}`, `{{image2}}`) with chart images
- **URL Generation**: Creates direct access links using `https://drive.google.com/uc?export=view&id={file_id}`

#### **Stage 6: Export & Delivery**
- **PDF Generation**: Converts slides to PDF format via Google Slides API
- **Local Storage**: Downloads PDF to `/tmp/{presentation_id}.pdf`
- **Resource URI**: Returns file URI for MCP resource serving

## Integration Points & Dependencies

### **External Service Dependencies**
1. **Google APIs**:
   - **Slides API**: Template operations, batch updates, PDF export
   - **Drive API**: File management, storage, sharing
   - **Authentication**: OAuth2 via `credentials.json`

2. **Planned Integrations**:
   - **Alfred MCP Server** (localhost:8000): Snowflake data warehouse connectivity
   - **Charts MCP Server**: Specialized matplotlib chart generation
   - **OpenAI GPT-4**: Dynamic content generation

### **Internal Architecture**
- **FastMCP Framework**: Protocol handling and tool exposure
- **GoogleApiSupport Library**: Abstracted Google API operations
- **Agent-Based System**: Modular processing via specialized agents

### **Data Flow Dependencies**
```
User Request → FastMCP → create_slides_wrapper → create_slides → 
[Data Generation] → [Chart Creation] → [Google Slides] → [PDF Export] → Response
```

## Error Handling & Resilience

### **Multi-Layer Exception Management**

1. **Top-Level Wrapper** (`mcp_server.py:39-44`):
   - Catches all exceptions from core pipeline
   - Provides MCP context error reporting
   - Returns structured error responses
   - Maintains service availability through graceful degradation

2. **Operation-Specific Handling** (`tools_agent_kam.py`):
   - **Chart Creation**: Lines 82-86 with matplotlib error recovery
   - **Slides Preparation**: Lines 97-101 with Google API error handling  
   - **File Upload**: Lines 115-119 with Drive API resilience
   - **Image Insertion**: Lines 130-133 with graceful failure (continues execution)
   - **PDF Export**: Lines 143-146 with warning-level logging (non-critical)

### **Fault Tolerance Patterns**
- **Continue on Non-Critical Failures**: Image insertion and PDF export failures don't halt execution
- **Structured Logging**: Debug, info, warning, and error levels provide operational visibility
- **Context-Aware Notifications**: Real-time user feedback through MCP context messages
- **Resource Cleanup**: Proper matplotlib figure closure prevents memory leaks

### **Service Integration Resilience**
- **Google API Rate Limits**: Implicit handling through google-api-python-client
- **File System Operations**: Temporary file storage with collision-resistant paths
- **Network Failures**: Graceful degradation with informative error messages

## Performance Characteristics

### **Execution Profile**
- **I/O Bound**: Dominated by Google API calls and file operations
- **Memory Efficient**: Minimal data structures, immediate resource cleanup
- **Scalable Design**: Stateless execution enables horizontal scaling

### **Resource Management**
- **Temporary Storage**: Uses `/tmp` directory for transient files
- **Memory Footprint**: Small DataFrames and immediate matplotlib cleanup
- **API Quotas**: Dependent on Google API limits (manageable for typical usage)

## Technical Debt & Future Enhancements

### **Current Limitations**
1. **Static Data**: Hardcoded sample data instead of dynamic retrieval
2. **Limited Error Recovery**: No retry mechanisms for transient failures
3. **Template Coupling**: Hardcoded presentation and folder IDs
4. **Single Chart Type**: Fixed matplotlib visualization pattern

### **Planned Improvements**
1. **Alfred MCP Integration**: Dynamic data retrieval from Snowflake
2. **Agent-Based Architecture**: Specialized processing agents for scalability  
3. **Dynamic Prompting**: Context-aware content generation
4. **Retry Mechanisms**: Resilience against transient API failures

## Conclusion

The `create_slides_wrapper` function represents a well-architected orchestration layer that successfully abstracts the complexity of multi-service integration while maintaining operational visibility and fault tolerance. Its design enables both current functionality and future extensibility through modular component integration.

---

*Generated by technical analysis of the Scalapay MCP KAM codebase*