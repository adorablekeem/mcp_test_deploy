# MatPlotLib Chart Generation Error Analysis

## Error Summary
**Error Type**: `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`
**Location**: Line 34 in generated code - `ax.bar(x + bar_width, data_2025, width=bar_width, label='2025', color='#FFA07A')`

## Root Cause Analysis

### The Problem
The generated matplotlib code is trying to create bar charts with incomplete data for 2025 (only 6 months), but handles it incorrectly:

```python
# PROBLEMATIC CODE:
data_2025 = [data[f"2025-{str(i).zfill(2)}"] for i in range(1, 7)]  # Only 6 months
data_2025.extend([None] * (12 - len(data_2025)))  # Pads with None values
# Result: [16000.9, 16500.35, 16800.5, 17200.6, 17650.75, 18000.8, None, None, None, None, None, None]

# FAILS HERE:
ax.bar(x + bar_width, data_2025, width=bar_width, label='2025', color='#FFA07A')
# matplotlib cannot add int + NoneType when positioning bars
```

### Why It Failed
1. **Incomplete Year Data**: 2025 only has 6 months of data (Jan-Jun)
2. **None Padding**: Code pads missing months with `None` values
3. **matplotlib Limitation**: `ax.bar()` cannot handle `None` values in the data array
4. **Math Operation Error**: When matplotlib tries to calculate bar positions, it performs `y0 + height` where `height` is `None`

## Immediate Fixes

### Fix 1: Filter Out None Values
```python
# Instead of padding with None, use separate arrays
def plot_partial_year_data():
    months_2023 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    months_2024 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] 
    months_2025 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']  # Only available months
    
    data_2023 = [data[f"2023-{str(i).zfill(2)}"] for i in range(1, 13)]
    data_2024 = [data[f"2024-{str(i).zfill(2)}"] for i in range(1, 13)]
    data_2025 = [data[f"2025-{str(i).zfill(2)}"] for i in range(1, 7)]
    
    x_2023 = np.arange(12)
    x_2024 = np.arange(12) 
    x_2025 = np.arange(6)  # Only 6 positions
    
    ax.bar(x_2023 - bar_width, data_2023, width=bar_width, label='2023')
    ax.bar(x_2024, data_2024, width=bar_width, label='2024')
    ax.bar(x_2025 + bar_width, data_2025, width=bar_width, label='2025')
```

### Fix 2: Use Zero Instead of None
```python
# Replace None with 0 for missing months
data_2025.extend([0] * (12 - len(data_2025)))
# Result: [16000.9, 16500.35, ..., 18000.8, 0, 0, 0, 0, 0, 0]
```

### Fix 3: Mask None Values
```python
import numpy as np

# Convert to numpy array and mask None values
data_2025_array = np.array(data_2025, dtype=float)
mask = ~np.isnan(data_2025_array)  # True where data exists
ax.bar(x[mask] + bar_width, data_2025_array[mask], width=bar_width, label='2025')
```

## Enhanced Chart Generation Logic

### Improved Data Validation
```python
def validate_and_clean_chart_data(data_dict):
    """Clean and validate chart data before plotting"""
    cleaned_data = {}
    
    for key, value in data_dict.items():
        if value is None:
            cleaned_data[key] = 0  # Replace None with 0
        elif isinstance(value, (int, float)) and not np.isnan(value):
            cleaned_data[key] = value
        else:
            cleaned_data[key] = 0  # Replace invalid values with 0
            
    return cleaned_data
```

### Smart Year Handling
```python
def handle_partial_years(data, years):
    """Handle cases where some years have incomplete data"""
    year_data = {}
    max_months = 0
    
    for year in years:
        year_values = []
        for month in range(1, 13):
            key = f"{year}-{str(month).zfill(2)}"
            if key in data:
                year_values.append(data[key])
            else:
                break  # Stop when we reach missing data
        
        year_data[year] = year_values
        max_months = max(max_months, len(year_values))
    
    return year_data, max_months
```

### Error-Resistant Bar Chart Generation
```python
def create_robust_bar_chart(data, title):
    """Create bar chart that handles missing/partial data gracefully"""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Handle different data lengths for different years
    years = list(set(key.split('-')[0] for key in data.keys()))
    year_data, max_months = handle_partial_years(data, years)
    
    colors = {'2023': '#FF1493', '2024': '#9370DB', '2025': '#FFA07A'}
    bar_width = 0.25
    
    for i, year in enumerate(years):
        values = year_data[year]
        positions = np.arange(len(values)) + i * bar_width - bar_width
        
        ax.bar(positions, values, width=bar_width, 
               label=year, color=colors.get(year, '#888888'))
    
    # Set labels only for months that have data
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][:max_months]
    ax.set_xticks(np.arange(max_months))
    ax.set_xticklabels(month_labels)
    
    ax.set_title(title)
    ax.legend()
    plt.savefig('chart_output.png', dpi=300, bbox_inches='tight')
```

## Prevention Strategies for MatPlot Agent

### 1. Pre-Generation Data Validation
```python
def pre_chart_validation(data_dict):
    """Validate data before sending to matplotlib"""
    issues = []
    
    # Check for None values
    none_values = [k for k, v in data_dict.items() if v is None]
    if none_values:
        issues.append(f"None values found in keys: {none_values}")
    
    # Check for non-numeric values
    non_numeric = [k for k, v in data_dict.items() if not isinstance(v, (int, float))]
    if non_numeric:
        issues.append(f"Non-numeric values found in keys: {non_numeric}")
    
    # Check for NaN values
    nan_values = [k for k, v in data_dict.items() if isinstance(v, float) and np.isnan(v)]
    if nan_values:
        issues.append(f"NaN values found in keys: {nan_values}")
    
    return len(issues) == 0, issues
```

### 2. Smart Chart Type Selection
```python
def select_appropriate_chart_type(data_dict):
    """Choose chart type based on data characteristics"""
    
    # Check data completeness
    total_entries = len(data_dict)
    valid_entries = sum(1 for v in data_dict.values() if v is not None and not np.isnan(v))
    completeness = valid_entries / total_entries
    
    # Check for time series pattern
    has_time_keys = any('-' in str(k) for k in data_dict.keys())
    
    # Check for partial years
    if has_time_keys:
        years = list(set(str(k).split('-')[0] for k in data_dict.keys()))
        if len(years) > 1:
            year_completeness = {}
            for year in years:
                year_keys = [k for k in data_dict.keys() if str(k).startswith(year)]
                year_completeness[year] = len(year_keys)
            
            # If years have different data counts, use line chart instead of grouped bars
            if len(set(year_completeness.values())) > 1:
                return "line_chart_partial_years"
    
    if completeness < 0.7:
        return "sparse_data_chart"  # Special handling for incomplete data
    
    return "standard_bar_chart"
```

## Recommendations for MatPlot Agent

### Short-term Fixes
1. **Replace None with Zero**: Always convert `None` values to `0` before plotting
2. **Add Data Type Validation**: Check all values are numeric before chart generation
3. **Use Try-Catch**: Wrap matplotlib calls in exception handlers

### Medium-term Improvements
1. **Smart Padding**: Instead of `None`, use appropriate defaults (0, last known value, interpolation)
2. **Partial Year Handling**: Detect incomplete years and adjust chart layout accordingly
3. **Chart Type Adaptation**: Switch from grouped bars to line charts when dealing with partial data

### Long-term Enhancements
1. **Data Quality Scoring**: Rate data quality and choose chart types accordingly
2. **Intelligent Defaults**: Use domain knowledge to fill missing values appropriately
3. **Multi-Chart Generation**: Generate multiple chart variants for different data completeness scenarios

## Error Prevention Checklist

Before generating any matplotlib chart:
- [ ] Check for None values in data
- [ ] Validate all values are numeric
- [ ] Handle partial time series appropriately
- [ ] Choose chart type based on data completeness
- [ ] Test chart generation with edge cases
- [ ] Provide fallback chart options