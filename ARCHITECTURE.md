# Architecture Logic - Scalapay MCP KAM

This document details the logical architecture and data flow of the Scalapay MCP KAM system, which orchestrates automated business intelligence slide generation through a sophisticated multi-agent pipeline.

## High-Level Architecture

```
User Input → MCP Server → Query Generation → Alfred MCP → Chart Generation → Slide Assembly → PDF Output
```

## Detailed Component Architecture

### 1. User Elicitation Layer (`mcp_server.py`)

**Purpose**: Collects required parameters from user interaction
- **Inputs**: User requests for merchant analysis
- **Elicitation Process**:
  - Merchant token validation
  - Start date specification
  - End date specification
- **Output**: Structured parameters for downstream processing

### 2. Query Orchestration Layer (`tools_agent_kam.py`)

**Purpose**: Coordinates the entire slide generation pipeline

#### 2.1 Query Planning
- Analyzes merchant context and date range
- Generates multiple specialized queries for different chart types
- Each query targets specific business metrics:
  - Monthly sales trends
  - Product type performance (Pay-in-3 vs Pay-in-4)
  - User demographics
  - Average Order Value (AOV) analysis
  - Order volume patterns

#### 2.2 Dynamic Query Structure
Each query includes:
```python
{
    "query_name": "descriptive_identifier",
    "business_question": "human_readable_question",
    "data_requirements": ["specific", "column", "names"],
    "chart_type": "visualization_type",
    "chart_config": {
        "title_template": "dynamic_title",
        "axis_labels": ["x_label", "y_label"],
        "color_scheme": "chart_colors",
        "formatting": "display_options"
    },
    "text_generation": {
        "prompt_template": "gpt4_analysis_prompt",
        "context_variables": ["merchant", "period", "metrics"]
    }
}
```

### 3. Data Retrieval Layer (`agents/agent_alfred.py`)

**Purpose**: Interface with Snowflake data warehouse via Alfred MCP

#### 3.1 Alfred MCP Integration
- Connects to `localhost:8000` (Alfred MCP server)
- Translates business queries to SQL via natural language
- Alfred MCP handles:
  - Snowflake connection management
  - SQL query generation and execution
  - Data validation and error handling
  - Result formatting and metadata

#### 3.2 Data Structure Validation
- Validates returned data against expected schemas
- Handles missing data gracefully with fallback strategies
- Enriches data with contextual information for chart generation

### 4. Chart Generation Layer (`agents/agent_matplot.py` + Charts MCP)

**Purpose**: Converts structured data into matplotlib visualizations

#### 4.1 Chart-Specific Processing
Each chart type has specialized logic:

**Monthly Sales Trends**
- Time series visualization
- Trend line calculation
- Seasonal pattern highlighting

**Product Performance Comparison**
- Grouped bar charts
- Percentage breakdown analysis
- Performance delta calculations

**Demographics Analysis**
- Pie charts with percentage labels
- Age/gender distribution visualization
- Geographic segmentation

**AOV Analysis**
- Multi-axis charts combining volume and value
- Correlation analysis visualization
- Trend comparison over time periods

#### 4.2 Dynamic Chart Configuration
- **Title Generation**: Context-aware titles using merchant name and period
- **Styling**: Consistent brand colors and formatting
- **Annotations**: Automatic highlighting of key insights
- **Export Settings**: High-resolution PNG with transparent backgrounds

### 5. Content Generation Layer (OpenAI Integration)

**Purpose**: Creates contextual text content for each slide

#### 5.1 Dynamic Prompt Engineering
Each chart generates unique prompts:
```python
prompt_template = f"""
Analyze the {chart_type} data for merchant {merchant_name} 
during {date_range}. Key metrics: {structured_data}.

Generate:
1. Executive summary (2-3 sentences)
2. Key insights (3-4 bullet points)
3. Actionable recommendations (2-3 specific actions)

Context: {business_context}
Focus: {analysis_focus}
"""
```

#### 5.2 Content Adaptation
- Adjusts tone based on performance trends (positive/negative)
- Incorporates industry benchmarks when available
- Customizes recommendations based on merchant segment

### 6. Slide Assembly Layer (`agents/agent_google_slides.py`)

**Purpose**: Combines charts and content into formatted presentation

#### 6.1 Template Management
- Loads predefined Google Slides templates
- Maps content types to specific slide layouts
- Maintains consistent formatting across all slides

#### 6.2 Content Placement Logic
```python
slide_structure = {
    "slide_1": {
        "title": "dynamic_title",
        "chart_position": {"x": 50, "y": 100, "width": 400, "height": 300},
        "text_position": {"x": 500, "y": 100, "width": 300, "height": 400},
        "placeholders": ["{{MERCHANT_NAME}}", "{{PERIOD}}", "{{CHART_IMAGE}}"]
    }
}
```

#### 6.3 Asset Management
- Uploads charts to Google Drive
- Manages sharing permissions
- Tracks asset references for cleanup

### 7. Export and Delivery Layer

**Purpose**: Generates final deliverables

#### 7.1 PDF Generation
- Exports Google Slides to high-quality PDF
- Maintains formatting and image quality
- Generates unique filenames with timestamps

#### 7.2 Resource Serving
- Serves PDFs via MCP resource endpoints
- Provides direct download links
- Maintains temporary file cleanup

## Data Flow Architecture

### Phase 1: Initialization
```
User Request → Parameter Validation → Context Setup
```

### Phase 2: Query Orchestration
```
Business Requirements → Query Generation → Multiple Parallel Queries
```

### Phase 3: Data Acquisition
```
Structured Queries → Alfred MCP → Snowflake → Validated Data Sets
```

### Phase 4: Visualization Pipeline
```
Data + Chart Specs → Chart Generation → Google Drive Upload → URLs
```

### Phase 5: Content Pipeline
```
Data + Context → GPT-4 Analysis → Structured Text Content
```

### Phase 6: Assembly Pipeline
```
Charts + Content + Template → Google Slides API → Formatted Presentation
```

### Phase 7: Export Pipeline
```
Presentation → PDF Export → Resource Serving → User Delivery
```

## Error Handling and Resilience

### Retry Mechanisms
- API call failures: Exponential backoff with maximum retry limits
- Data validation errors: Fallback to default templates
- Chart generation failures: Alternative visualization methods

### Graceful Degradation
- Missing data points: Use available data with appropriate disclaimers
- API unavailability: Generate text-only reports
- Template issues: Fall back to basic layouts

### Logging and Monitoring
- Comprehensive logging at each pipeline stage
- Performance metrics tracking
- Error rate monitoring and alerting

## Performance Optimizations

### Parallel Processing
- Concurrent query execution to Alfred MCP
- Parallel chart generation for multiple visualizations
- Asynchronous API calls to Google services

### Caching Strategies
- Template caching for repeated merchant requests
- Chart configuration caching
- Credential and session management

### Resource Management
- Automatic cleanup of temporary files
- Google Drive quota management
- Memory optimization for large datasets

## Security Considerations

### Authentication
- Google OAuth2 with appropriate scopes
- MCP server authentication for Alfred integration
- Secure credential storage and rotation

### Data Privacy
- Merchant data isolation
- Temporary file encryption
- Access logging and audit trails

### Network Security
- HTTPS for all external API communications
- Local MCP server communication security
- Input validation and sanitization

## Extensibility Points

### New Chart Types
- Add new chart specifications to tools system
- Extend prompt templates for new visualizations
- Update slide template mappings

### Additional Data Sources
- Create new MCP server integrations
- Extend query orchestration layer
- Add data validation schemas

### Custom Templates
- Template versioning system
- Dynamic layout generation
- Brand customization options

This architecture provides a robust, scalable foundation for automated business intelligence report generation while maintaining flexibility for future enhancements and integrations.