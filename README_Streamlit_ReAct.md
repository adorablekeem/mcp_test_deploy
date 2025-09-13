# Streamlit ReAct Agent ⚡📊

**Super fast ReAct agent that creates interactive Streamlit reports instead of Google Slides.**

## Why Streamlit > Google Slides?

| Feature | Streamlit ReAct | Google Slides |
|---------|----------------|---------------|
| **Speed** | 🟢 25-30 seconds | 🔴 45-70 seconds |
| **Setup** | 🟢 No APIs needed | 🔴 Google APIs required |
| **Interactivity** | 🟢 Full interactive web app | 🔴 Static images |
| **Updates** | 🟢 Real-time refresh | 🔴 Manual regeneration |
| **Customization** | 🟢 Full Python control | 🔴 Template limited |
| **Sharing** | 🟢 Web URL | 🟢 Google Drive link |

## Quick Start

### 1. Start the Agent
```bash
python streamlit_react_agent.py
```
Server: `http://localhost:8022/mcp`

### 2. Test Generation
```bash
python test_streamlit_generation.py
```

### 3. Use via MCP Client
```python
from mcp_use import MCPClient

client = MCPClient.from_dict({
    "mcpServers": {"streamlit_react": {"url": "http://localhost:8022/mcp"}}
})

result = await client.call_tool("create_streamlit_report", {
    "user_request": "Business performance dashboard",
    "merchant_token": "your_token",
    "starting_date": "2024-06-01", 
    "end_date": "2024-09-01"
})

# Get the report path
print(f"Report: {result['report_path']}")
print(f"Run: {result['run_command']}")
```

## ReAct Workflow

```
🤔 THINK: Quick keyword-based planning (0.1s)
   ↓
📊 ACT: Get data via Alfred (~12s) 
   ↓
📈 ACT: Create charts via MatplotAgent (~10s)
   ↓  
📄 ACT: Generate Streamlit app (~0.001s)
   ↓
✅ RESULT: Interactive web report (instant viewing)
```

## Generated Report Features

The Streamlit app includes:

### 📊 **Dashboard Layout**
- Header with request details and date range
- Performance metrics overview (charts, data sources, timing)
- Side-by-side chart + description layout
- Interactive sidebar with controls

### 📈 **Charts & Analysis** 
- All charts from MatplotAgent displayed
- Data descriptions from Alfred shown alongside
- Key insights and recommendations
- Responsive layout for different screen sizes

### 🔄 **Interactivity**
- Real-time refresh button
- Responsive design
- Error handling for missing charts
- Performance metrics display

## Example Generated Code Structure

```python
import streamlit as st
import matplotlib.image as mpimg

st.set_page_config(page_title="Business Report", layout="wide")
st.title("📊 Business Performance Report")

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📈 Charts Generated", 3)

# Charts with descriptions
st.subheader("Monthly Sales YoY")
col1, col2 = st.columns([2, 1])
with col1:
    st.image("chart.png")
with col2:
    st.write("Sales increased 15% YoY...")
```

## Performance Comparison

### Streamlit ReAct Agent:
- **Planning**: 0.1s (keyword-based)
- **Data retrieval**: ~12s (concurrent)
- **Chart creation**: ~10s (concurrent) 
- **Report generation**: ~0.001s (file creation)
- **Total**: **~22 seconds** + instant web viewing

### Google Slides (legacy):
- Planning: 2-5s (LLM reasoning)
- Data retrieval: ~15s
- Chart creation: ~15s  
- Template discovery: ~5s
- Slide positioning: ~10s
- API uploads: ~8s
- **Total**: **50-60 seconds**

## Tools Available

### `create_streamlit_report`
Main tool that orchestrates the full workflow.

**Returns:**
```json
{
  "success": true,
  "report_path": "/tmp/report_123.py",
  "run_command": "streamlit run /tmp/report_123.py",
  "report_url": "http://localhost:8501",
  "total_time": 22.5,
  "charts_included": 3
}
```

### `list_reports`
Lists all generated Streamlit reports in temp directory.

## Prerequisites

1. **MCP Servers Running:**
   - Alfred (data): `http://localhost:8000/mcp`
   - MatplotAgent (charts): `http://localhost:8010/mcp`

2. **Python Packages:**
   ```bash
   pip install streamlit fastmcp mcp-use langchain-openai
   ```

3. **Environment:**
   ```bash
   export OPENAI_API_KEY="your_key"
   ```

## Usage Examples

### Quick Business Dashboard
```python
result = await client.call_tool("create_streamlit_report", {
    "user_request": "comprehensive business dashboard",
    "merchant_token": "merchant_123",
    "starting_date": "2024-01-01",
    "end_date": "2024-09-01"
})
# Creates 4 charts: sales, AOV, user types, demographics
```

### Sales Focus Report  
```python
result = await client.call_tool("create_streamlit_report", {
    "user_request": "sales performance analysis",
    "merchant_token": "merchant_123", 
    "starting_date": "2024-06-01",
    "end_date": "2024-09-01"
})
# Creates 2 charts: sales trends, AOV
```

## Key Advantages

1. **⚡ Speed**: 2x faster than Google Slides
2. **🔧 No Setup**: No Google API configuration needed
3. **📊 Interactive**: Live web dashboard vs static images
4. **🔄 Real-time**: Instant updates and refresh
5. **🎨 Flexible**: Full Python/Streamlit customization
6. **📱 Responsive**: Works on mobile and desktop
7. **🔗 Easy Sharing**: Simple web URL

## Architecture

The agent demonstrates clean separation:
- **ReAct Logic**: Simple keyword-based reasoning 
- **Data Layer**: Alfred for business data
- **Visualization**: MatplotAgent for charts
- **Presentation**: Streamlit for interactive reports
- **Speed**: Optimized for minimal latency

Perfect for rapid business reporting and interactive data exploration! 🚀