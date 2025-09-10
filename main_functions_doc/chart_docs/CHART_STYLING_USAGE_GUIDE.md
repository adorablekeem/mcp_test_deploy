# Chart-Specific Styling System - Usage Guide

## Overview

The chart-specific styling system automatically applies different positioning, sizing, and formatting to your slides based on the chart type and content. Each chart gets optimized layout and styling appropriate for its data visualization needs.

## 🎨 **Key Features**

### **Automatic Chart Type Detection**
- **Bar Charts**: Monthly sales, yearly comparisons → Wider aspect ratio
- **Stacked Bar Charts**: User types, product analysis → Extra space for legends
- **Line Charts**: AOV trends, time series → Optimized for trend visualization
- **Pie Charts**: Demographics, distributions → Square aspect ratio with label space

### **Content-Based Style Selection**
The system analyzes both the data type and paragraph content to select the best styling:
```python
# Examples of automatic detection:
"monthly sales year over year" → Bar chart with yearly comparison styling
"orders by user type" → Stacked bar chart with user type styling  
"AOV over time" → Line chart with trend visualization styling
"scalapay users demographic in percentages" → Pie chart with demographic styling
```

### **Chart-Specific Positioning & Sizing**
Each chart type gets optimized dimensions:
- **Bar charts**: `scaleX=140, scaleY=100` (wider for categories)
- **Line charts**: `scaleX=145, scaleY=95` (wider for time series)
- **Pie charts**: `scaleX=110, scaleY=110` (square for circular data)
- **Stacked bars**: `scaleX=135, scaleY=105` (space for legends)

## 📁 **File Structure**

```
scalapay/scalapay_mcp_kam/
├── config/
│   └── chart_styling_config.py          # Style definitions and detection logic
├── batch_operations_with_styling.py     # Core styled batch operations  
├── batch_operations_styled_wrapper.py   # Integration wrapper with fallbacks
└── tools_agent_kam_concurrent.py        # Updated to use styled operations
```

## ⚙️ **Configuration Options**

### **Environment Variables**
```bash
# Disable chart styling (fallback to standard operations)
export SCALAPAY_DISABLE_CHART_STYLING=true

# Emergency mode (disables all advanced features)
export SCALAPAY_EMERGENCY_MODE=true

# Force sequential processing (for troubleshooting)
export SCALAPAY_FORCE_SEQUENTIAL_BATCH=true
```

### **Code-Level Configuration**
```python
from scalapay.scalapay_mcp_kam.batch_operations_styled_wrapper import configure_chart_styling

# Configure styling behavior
config = configure_chart_styling(
    enable_styling=True,              # Enable/disable chart-specific styling
    enable_concurrent_with_styling=True,  # Allow concurrency with styling
    styling_fallback_mode="standard"      # What to do when styling fails
)
```

## 🔧 **Usage Examples**

### **1. Basic Usage (Automatic)**
The system automatically applies styling when you use the enhanced template processing:

```python
# In your slide generation code, styling is applied automatically
result = await fill_template_for_all_sections_new_enhanced_concurrent(
    drive, slides, results,  # results contains Alfred data for styling context
    template_id=template_id,
    folder_id=folder_id,
    llm_processor=llm_processor
)

# Check styling results
print(f"Chart styling enabled: {result['chart_styling_enabled']}")
print(f"Total styles applied: {result['total_styles_applied']}")
```

### **2. Manual Styling Control**
```python
from scalapay.scalapay_mcp_kam.batch_operations_styled_wrapper import enhanced_batch_text_replace_with_styling

# Control styling behavior explicitly
text_result = await enhanced_batch_text_replace_with_styling(
    slides_service, presentation_id, text_map,
    results=alfred_results,        # Pass Alfred results for context
    enable_styling=True,           # Enable chart-specific styling
    enable_concurrent=False,       # Disable concurrency if needed
    correlation_id="my_operation"
)
```

### **3. Direct Style Configuration Access**
```python
from scalapay.scalapay_mcp_kam.config.chart_styling_config import (
    get_image_style_for_slide, select_style_config
)

# Get styling for a specific chart
image_style = get_image_style_for_slide(
    data_type="monthly sales year over year",
    paragraph="Sales show strong growth with seasonal peaks",
    chart_type=ChartType.BAR
)

print(f"Recommended size: {image_style['resize']['scaleX']} x {image_style['resize']['scaleY']}")
print(f"Position: ({image_style['resize']['translateX']}, {image_style['resize']['translateY']})")
```

## 📊 **Chart Type Specific Styles**

### **Bar Charts** (`ChartType.BAR`)
```python
# Monthly Sales Style
{
    "scale": (140, 100),           # Wider for category labels
    "position": (100, 200),        # Standard positioning
    "max_size": (600, 350),        # Constrained dimensions
    "title": "28px, bold, #1f4e79" # Professional blue
}

# Yearly Comparison Style  
{
    "scale": (150, 110),           # Extra wide for year comparisons
    "position": (80, 180),         # Shifted left for more space
    "max_size": (650, 380)         # Larger maximum size
}
```

### **Stacked Bar Charts** (`ChartType.STACKED_BAR`)
```python
# User Type Orders Style
{
    "scale": (135, 105),           # Slightly more space for legends
    "position": (90, 190),         # Positioned for legend visibility
    "max_size": (620, 360),        # Accommodates legend space
    "title": "26px, bold, #8b4513" # Warm brown color
}
```

### **Line Charts** (`ChartType.LINE`)
```python
# AOV Trends Style
{
    "scale": (145, 95),            # Wide for time series
    "position": (75, 210),         # Optimized for trend lines
    "max_size": (650, 340),        # Wide format
    "title": "26px, bold, #d2691e" # Orange for trends
}
```

### **Pie Charts** (`ChartType.PIE`)
```python
# Demographics Style
{
    "scale": (110, 110),           # Square aspect ratio
    "position": (120, 200),        # Centered positioning
    "max_size": (400, 400),        # Square constraints
    "title": "24px, bold, #4682b4" # Steel blue
}
```

## 🔄 **Fallback Behavior**

The styling system has multiple fallback levels:

1. **Styled Operations**: Use chart-specific positioning and formatting
2. **Standard Concurrent**: Fall back to regular concurrent batch operations  
3. **Emergency Sequential**: Fall back to proven sequential operations
4. **Error Recovery**: Automatic detection and retry with different modes

### **Fallback Triggers**
- Missing Alfred results data → Standard operations
- Styling configuration errors → Standard operations  
- API conflicts → Emergency sequential
- SSL/connection errors → Emergency sequential

## 📈 **Performance Impact**

### **With Styling (Expected)**
- **Processing Time**: ~10-15% slower (due to style calculations)
- **Memory Usage**: Minimal increase (style configs are lightweight)
- **Visual Quality**: Significantly improved chart positioning and sizing
- **User Experience**: Much better layout and readability

### **Styling vs Standard Comparison**
```
Chart Type          | Standard Position | Styled Position    | Improvement
--------------------|-------------------|--------------------|--------------
Monthly Sales       | (130, 250)       | (100, 200) 140x100| Better fit
User Type Orders    | (130, 250)       | (90, 190) 135x105 | Legend space
AOV Trends          | (130, 250)       | (75, 210) 145x95  | Trend clarity
Demographics        | (130, 250)       | (120, 200) 110x110| Square layout
```

## 🐛 **Troubleshooting**

### **Styling Not Applied**
```python
# Check if styling is enabled
result = await your_batch_operation(...)
print(f"Processing mode: {result.get('processing_mode')}")
print(f"Styles applied: {result.get('styles_applied', 0)}")

# If processing_mode doesn't start with 'styled', styling was not applied
```

### **Common Issues**
1. **No Alfred results provided** → Pass `results` parameter with Alfred data
2. **Empty paragraph data** → Ensure Alfred results contain paragraph text
3. **Environment override** → Check `SCALAPAY_DISABLE_CHART_STYLING` setting
4. **Emergency mode active** → Check `SCALAPAY_EMERGENCY_MODE` setting

### **Debug Logging**
```python
import logging
logging.getLogger("scalapay.scalapay_mcp_kam.batch_operations_with_styling").setLevel(logging.DEBUG)
logging.getLogger("scalapay.scalapay_mcp_kam.config.chart_styling_config").setLevel(logging.DEBUG)
```

## 🔮 **Advanced Customization**

### **Adding New Chart Styles**
```python
# In chart_styling_config.py, add to CHART_STYLE_CONFIGS
ChartType.BAR: {
    "my_custom_style": SlideStyleConfig(
        title_style=TextStyling(font_size=30, color="#ff0000"),
        image_style=ImageStyling(
            scale_x=160, scale_y=90,
            translate_x=50, translate_y=150,
            max_width=700, max_height=400
        )
    )
}
```

### **Adding Content Pattern Matching**
```python
# In chart_styling_config.py, add to CONTENT_STYLE_PATTERNS
{
    "pattern": r"revenue.*quarterly",
    "chart_type": ChartType.BAR,
    "style_key": "quarterly_revenue"
}
```

---

**The chart styling system provides automatic, intelligent layout optimization for your presentations, ensuring each chart type gets the best possible positioning and formatting for maximum visual impact.**