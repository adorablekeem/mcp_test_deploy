GENERAL_CHART_PROMPT = """
Output a JSON following the format of this example: "{{
    'structured_data': {{

    }},
    'paragraph': ''  
}}" — this should contain {data_type} for the merchant "{merchant_token}" from {starting_date} to {end_date} and a comprehensive analysis of the trends. you lose points if you don't output the data in the format above. you cant't do anything but trying to find the specific data about the merchant. your accepted output is only a json with the structure above, nothing else. Do not output any other text or explanation. Execute multiple steps to make sure the resulting dataframe is always the same everytime. This output:

```json
{{

}}
```

would be wrong because you used ```json``` block, you should only output the json text without any formatting.
"""

SLIDES_GENERATION_PROMPT = """
Given the following data:
{alfred_result}

Extract and transform it into this format (according to the data type and year availability):
{{
    "structured_data": {{
    }},
    "variations": {{
        "2020": "percentage change from previous year",
        "2021": "percentage change from previous year",
        "2022": "percentage change from previous year",
        "2023": "percentage change from previous year",
        "2024": "percentage change from previous year",
        "2025": "percentage change from previous year"
    }},
    "paragraph": "analytical summary of the data"
}}

Note: If data for a year doesn't exist, use "N/A" for that year's variation.
"""

STRUCTURED_CHART_SCHEMA_PROMPT = """
You are a chart planning assistant. 
Given a user request and some data preview, decide the best chart configuration.
**CRITICAL REQUIREMENTS:**
1. Use ONLY valid matplotlib styles - DO NOT use deprecated seaborn styles
2. Prioritize raw data over percentage-converted data for accurate visualization
3. Create clean, professional charts suitable for business presentations

**VALID MATPLOTLIB STYLES TO USE:**
- 'default' (recommended for professional look)
- 'classic'
- 'bmh'
- 'ggplot'
- 'seaborn-v0_8' (if seaborn styling needed)

**FORBIDDEN STYLES:**
- 'seaborn-whitegrid' (deprecated and will cause errors)
- 'seaborn-white' (deprecated)
- Any other 'seaborn-*' styles without version suffix

**Data Source Priority:**
1. First check for 'alfred_raw' data (contains original raw values)
2. If unavailable, use 'slides_struct' but verify data format
3. Ensure numerical values are not in percentage string format

Mapping rules:
- "monthly sales over time" → bar
- "monthly sales by product type" → stacked_bar
- "monthly orders by user type" → stacked_bar (and optionally pie for share)
- "AOV over time" or "Average Order Value over time" → line
- "age distribution" → pie
- "gender distribution" → pie
- "card type distribution" → pie

If none of these match, fall back to:
- If values are continuous over time → line
- If values compare multiple years side-by-side → bar
- If values are percentages or distributions → pie
- If categories contribute to a total over time → stacked_bar

data description:
{alfred_data_description}

Data preview (only first few entries):
{data}

"""

MONTHLY_SALES_PROMPT = """# Detailed Prompt for Creating Multi-Year Monthly Comparison Bar Chart

## Chart Overview
Create a grouped bar chart that displays monthly data across multiple years (2020-2024), with each month showing 5 different colored bars representing different years.

## Chart Specifications

### Chart Type
- **Type**: Grouped/Clustered Bar Chart
- **Orientation**: Vertical bars
- **Layout**: Monthly groupings with year-based clustering
```

### Visual Design Elements

#### Color Scheme
- **2020**: Light blue/cyan (#87CEEB or similar)
- **2021**: Purple/magenta (#DA70D6 or similar)
- **2022**: Orange (#FFA500 or similar)
- **2023**: Hot pink/magenta (#FF1493 or similar)
- **2024**: Light purple/lavender (#9370DB or similar)

#### Bar Configuration
- **Bar Width**: Medium thickness with small gaps between bars within each month
- **Group Spacing**: Larger gaps between monthly groups
- **Bar Arrangement**: Left to right: 2020, 2021, 2022, 2023, 2024

#### Data Labels
- Display the exact numeric value on top of each bar
- Font: Small, dark color for readability
- Position: Centered above each bar with slight padding

### Axis Configuration

#### X-Axis (Horizontal)
- **Labels**: Month abbreviations (Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)
- **Position**: Bottom of chart
- **Spacing**: Equal spacing between month groups
- **Grid Lines**: None or very subtle

#### Y-Axis (Vertical)
- **Scale**: Start at 0, extend to accommodate highest value (around 70-75)
- **Grid Lines**: Horizontal lines for easier reading
- **Labels**: Numeric values at regular intervals
- **Position**: Left side of chart

### Legend
- **Position**: Top of chart, horizontal layout
- **Format**: Colored squares followed by year labels
- **Order**: 2020, 2021, 2022, 2023, 2024
- **Style**: Clean, minimal design

### Chart Dimensions
- **Aspect Ratio**: Wide format (approximately 3:1 or 4:1 ratio)
- **Size**: Large enough to clearly display all data labels
- **Margins**: Adequate space around all edges for labels and legend

## Implementation Guidelines

### For Excel/Google Sheets:
1. Structure data with months as rows and years as columns
2. Select data range including headers
3. Insert clustered column chart
4. Customize colors to match specified palette
5. Add data labels to all series
6. Format axes and add legend as specified

### For Programming Languages (Python/R/JavaScript):
1. Prepare data in appropriate format (array of objects or matrix)
3. Set up grouped bar chart with specified colors
4. Configure axis labels, data labels, and legend
5. Apply styling for professional appearance

### For Data Visualization Tools (Tableau/Power BI):
1. Import data with proper date/numeric formatting
2. Drag months to columns and years to color/legend
3. Set measure to rows for bar height
4. Customize color palette to match specifications
5. Enable data labels and format layout

## Key Design Principles
- **Clarity**: Each bar should be easily distinguishable
- **Consistency**: Uniform spacing and styling throughout
- **Readability**: Clear labels and appropriate font sizes
- **Professional**: Clean, business-ready appearance
- **Accessibility**: Color choices that work for colorblind users

## Year-over-Year Analysis Components


### Additional Analytical Elements

#### Summary Statistics Table
Include a companion table or text box showing:
- **Highest performing year**: 2022 (321 total)
- **Lowest performing year**: 2024 (213 total)
- **Biggest YoY increase**: 2022 (+7, +2.2%)
- **Biggest YoY decrease**: 2023 (-74, -23.1%)
- **Overall trend**: Declining since 2022 peak

#### Visual Enhancement Options
1. **Secondary Y-Axis**: Add annual total line graph overlaying the monthly bars
2. **Trend Arrows**: Small arrows showing YoY direction for each year
3. **Performance Indicators**: Color-coded backgrounds (green for growth, red for decline)
4. **Callout Boxes**: Highlight significant changes or patterns

### Implementation for YoY Analysis

```python
# Example calculation structure
annual_totals = data.groupby('Year').sum()
yoy_change = annual_totals.diff()
yoy_percent = (yoy_change / annual_totals.shift(1)) * 100

# Add to visualization
ax2 = ax.twinx()  # Secondary axis
ax2.plot(years, annual_totals, 'ko-', linewidth=2, markersize=8)
ax2.set_ylabel('Annual Total')
```

#### Dashboard Integration:
- **KPI Cards**: Show current vs previous year totals
- **Gauge Charts**: YoY performance indicators
- **Heat Map**: Month-over-month, year-over-year performance matrix
- **Trend Analysis**: Moving averages and seasonality indicators

### Key Insights Template
Include text analysis highlighting:
- **Seasonal Patterns**: "November consistently shows peak performance across all years"
- **Concerning Trends**: "Significant decline starting in 2023 (-23.1% YoY)"
- **Recovery Indicators**: "August 2024 shows strong recovery (+111% vs 2023)"
- **Stability Metrics**: "May remains most consistent high-performer"

## Common Variations
- Can be adapted for different time periods
- Colors can be customized to match brand guidelines
- Can include trend lines or additional statistical overlays
- Suitable for quarterly, weekly, or other temporal groupings
- Enhanced with YoY analysis components for comprehensive business intelligence
"""

SLIDE_CONTENT_OPTIMIZATION_PROMPT = """
You are a presentation expert optimizing analytical content for slide display.

TASK: Transform the detailed analytical paragraph into slide-appropriate content that:
1. Highlights 2-3 key insights maximum
2. Uses clear, concise language (40-80 words ideal)
3. Focuses on actionable insights rather than raw data
4. Maintains professional tone suitable for business presentations

CONTEXT:
- Slide Title: {title}
- Chart Type: {chart_type}  
- Position in Presentation: {slide_index} of {total_slides}
- Audience Level: Executive/Management

ORIGINAL ANALYTICAL CONTENT:
{full_paragraph}

CHART DATA SUMMARY:
{structured_data_summary}

OUTPUT REQUIREMENTS:
- slide_paragraph: Optimized text for slide display (40-80 words)
- key_insights: List of 2-3 main takeaways
- presenter_notes_addition: Additional context for speaker notes (if needed)

Return as JSON format:
{{
    "slide_paragraph": "...",
    "key_insights": ["...", "...", "..."],
    "presenter_notes_addition": "..."
}}
"""

ORDERS_BY_USER_TYPE_PROMPT = """Performance Dashboard with Stacked Bar Chart and Pie Chart - Complete Guide
Dashboard Overview
Create a comprehensive performance dashboard featuring stacked bar charts showing user type orders over time periods, combined with a pie chart breakdown and key performance insights.
Main Components
1. Stacked Bar Chart - "Orders by User Type"
Chart Type

Type: Stacked Column/Bar Chart
Orientation: Vertical bars
Layout: Time periods on X-axis with segmented user type data

New Users: Orange/Peach (#FFA07A or similar)
Returning Users: Light Pink/Rose (#FFB6C1 or similar)
Scalapay Network+: Hot Pink/Magenta (#FF69B4 or similar)

Visual Design Elements

Bar Spacing: Medium gaps between time periods
Data Labels: Total values displayed above each stacked bar
Individual Segment Values: Optional - can show within each segment if space allows
Legend: Positioned below chart, horizontal layout with color squares

2. Pie Chart - "Orders per User Type"
Chart Configuration

Type: Donut/Pie Chart
Position: Bottom left of dashboard
Size: Medium, complementary to bar chart

Use same colors as stacked bar chart
Scalapay Network+: Hot Pink/Magenta (largest segment)
Returning: Light Pink/Rose (medium segment)
New: Orange/Peach (smallest segment)

Labels and Formatting

Percentage labels: Display on or near each segment
Legend: Optional if segments are clearly labeled
Brand logo: Small Scalapay logo positioned below chart

3. Performance Insights Text Box
Key Metrics Summary
📊 Performance Insights:

- 52% Scalapay Network+: des utilisateurs fidèles à Scalapay qui ont déjà 
  utilisé la solution dans le passé sur d'autres sites marchands

- 26% Returning: des utilisateurs qui ont déjà acheté avec Scalapay dans le 
  passé sur votre eShop

- 22% New: des utilisateurs qui ont utilisé Scalapay pour la première 
  fois et qui ont acheté sur votre eShop
Text Formatting

Typography: Clean, professional font
Hierarchy: Bold percentages and user types
Color coding: Optional colored bullets matching chart colors
Language: French (as shown in example)

Year-over-Year Analysis Components
Annual Performance Tracking
Year    | New Users | Returning | Network+ | Total | YoY Change | YoY %
--------|-----------|-----------|----------|-------|------------|-------
2022    |   1,456   |   1,623   |  2,234   | 5,313 |     -      |   -
2023    |   1,607   |   1,868   |  2,946   | 6,421 |  +1,108    | +20.9%
2024    |   1,823   |   2,145   |  3,287   | 7,255 |   +834     | +13.0%
User Type Growth Analysis
User Segment      | 2022→2023 | Growth% | 2023→2024 | Growth% | 2-Yr CAGR
------------------|-----------|---------|-----------|---------|------------
New Users         |   +151    | +10.4%  |   +216    | +13.4%  |   +11.9%
Returning         |   +245    | +15.1%  |   +277    | +14.8%  |   +14.9%
Scalapay Network+ |   +712    | +31.9%  |   +341    | +11.6%  |   +21.2%
Monthly Trend Analysis
Month    | Peak Year | Peak Value | Trend Direction | Seasonality
---------|-----------|------------|----------------|-------------
Jan      |   2024    |    967     |   Increasing   |   Post-holiday dip
Feb      |   2024    |   1,056    |   Strong growth|   Recovery month
Mar      |   2023    |   1,132    |   Declining    |   Peak season
Apr      |   2024    |   1,203    |   Increasing   |   Spring growth
May      |   2023    |   1,145    |   Variable     |   Stable high
Jun      |   2023    |   1,119    |   Declining    |   Summer start
Performance Insights with YoY Context
Advanced KPIs

Customer Acquisition Rate: New users as % of total
Retention Rate: Returning users growth YoY
Network Effect: Scalapay Network+ penetration
Customer Lifetime Value: Evolution by user segment

Comparative Analysis
Metric                    | Current | Previous | Change | Industry Benchmark
--------------------------|---------|----------|--------|--------------------
New Customer %            |   22%   |   27%    |  -5pp  |       25-30%
Returning Customer %      |   26%   |   31%    |  -5pp  |       20-25%
Network+ Penetration      |   52%   |   42%    | +10pp  |       N/A (Unique)
Overall Conversion Growth |  +13%   |  +21%    |  -8pp  |       10-15%
Implementation Guidelines
For Google Slides/PowerPoint:

Layout Setup: Use 16:9 slide ratio for dashboard format
Chart Creation:

Insert stacked column chart for time series data
Create separate pie chart with matching colors
Position text box for insights on right side


Color Consistency: Apply same color palette across all elements
Data Labels: Enable for totals and percentages
Branding: Include company logo and consistent fonts

For Data Visualization Tools (Tableau/Power BI):
Stacked Bar Chart Setup:
Columns: Time Period (Month/Year)
Rows: SUM(Orders)
Color: User Type
Marks: Stacked Bar
Labels: Show totals on top
Pie Chart Configuration:
Angle: SUM(Orders) 
Color: User Type
Labels: Percentage + Count
Filter: Latest period or overall totals
Dashboard Layout:

Grid System: 3-column layout
Left: Stacked bar chart (60% width)
Bottom Left: Pie chart (20% width)
Right: KPIs and insights text (20% width)

For Programming Languages:
Python (Matplotlib/Plotly):
python# Stacked bar chart
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))

# Stacked bars
bottom1 = new_users
bottom2 = bottom1 + returning_users
ax1.bar(months, new_users, color='#FFA07A', label='New')
ax1.bar(months, returning_users, bottom=bottom1, color='#FFB6C1', label='Returning')
ax1.bar(months, network_plus, bottom=bottom2, color='#FF69B4', label='Network+')

# Add total labels
for i, total in enumerate(totals):
    ax1.text(i, total + 20, str(total), ha='center', va='bottom')

# Pie chart
ax2.pie(user_totals, labels=user_types, colors=colors, autopct='%1.0f%%')
JavaScript (Chart.js):
javascript// Stacked bar configuration
{
    type: 'bar',
    data: {
        labels: months,
        datasets: [
            {
                label: 'New',
                data: newUsers,
                backgroundColor: '#FFA07A'
            },
            {
                label: 'Returning', 
                data: returningUsers,
                backgroundColor: '#FFB6C1'
            },
            {
                label: 'Scalapay Network+',
                data: networkPlus,
                backgroundColor: '#FF69B4'
            }
        ]
    },
    options: {
        scales: {
            x: { stacked: true },
            y: { stacked: true }
        }
    }
}
For Excel Integration:

Data Preparation: Structure data with months as rows, user types as columns
Chart Creation: Insert stacked column chart, then add pie chart
Formatting: Apply consistent colors and add data labels
Dashboard Assembly: Use Excel's camera tool to create dashboard layout
Dynamic Updates: Use pivot tables for automatic data refresh

Advanced Analytics Features
Cohort Analysis Integration

Track user progression from New → Returning → Network+
Show conversion rates between segments
Identify retention patterns by acquisition period

Predictive Elements

Trend Lines: Add polynomial trend lines to forecast growth
Seasonality Indicators: Highlight recurring patterns
Goal Tracking: Show targets vs actual performance
Alert Systems: Color-coded indicators for KPI thresholds

Interactive Features

Drill-down Capability: Click on segments to see detailed breakdowns
Time Range Filters: Dynamic period selection
User Segment Filters: Toggle user types on/off
Comparative Views: Side-by-side period comparisons

Key Performance Indicators Dashboard
Primary KPIs

Total Orders Growth: Monthly and YoY tracking
User Mix Evolution: Percentage composition changes
Customer Acquisition Cost: By user segment
Revenue per User Type: Average order values
Retention Metrics: Return purchase rates

Secondary Metrics

Scalapay Network+ Effectiveness: Cross-merchant loyalty impact
Seasonal Performance: Peak period identification
Growth Sustainability: Trend analysis and projections
Market Penetration: New vs returning customer balance

Customization Options

Adaptable to different time periods (weekly, quarterly, yearly)
Scalable for additional user segments or product categories
Multiple language support for international markets
Brand customization with company colors and fonts
Mobile-responsive layouts for various screen sizes
Export capabilities for presentations and reports
"""
