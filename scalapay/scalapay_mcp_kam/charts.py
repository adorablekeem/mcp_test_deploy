import os
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Set matplotlib backend for headless operation
matplotlib.use('Agg')

class ChartGenerator:
    """Local chart generator using matplotlib"""
    
    def __init__(self, color_palette=None):
        self.color_palette = color_palette or [
            "#8ad3f4", "#d896f6", "#f7a463", "#f15375", "#b7b8f5", 
            "#f6b8ea", "#469acf", "#ffd700", "#b0e0e6", "#ffa07a"
        ]
        
        # Set default style
        plt.style.use('default')
        
    def create_grouped_bar_chart(self, data, title, xlabel="Month", ylabel="Units", 
                                output_path="chart.png", figsize=(12, 4), dpi=150):
        """
        Create a grouped bar chart
        
        Args:
            data: Dictionary with structure {category: {year: value}}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            output_path: Path to save the chart
            figsize: Figure size in inches
            dpi: Dots per inch for image quality
        """
        
        # Extract categories and years
        categories = list(data.keys())
        years = sorted(set().union(*[d.keys() for d in data.values()]))
        
        # Prepare data arrays
        x = np.arange(len(categories))
        width = 0.8 / len(years)  # Width of bars
        
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Create bars for each year
        bars_list = []
        for i, year in enumerate(years):
            values = [data[cat].get(year, 0) for cat in categories]
            color = self.color_palette[i % len(self.color_palette)]
            bars = ax.bar(x + i * width - width * (len(years) - 1) / 2, 
                         values, width, label=str(year), color=color)
            bars_list.append(bars)
            
            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:  # Only label non-zero bars
                    ax.annotate(f'{int(height)}',
                              xy=(bar.get_x() + bar.get_width() / 2, height),
                              xytext=(0, 3),
                              textcoords="offset points",
                              ha='center', va='bottom',
                              fontsize=8)
        
        # Customize the chart
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        # Improve layout
        plt.tight_layout()
        
        # Save the chart
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        
        # Get file info
        file_size = os.path.getsize(output_path)
        print(f"✓ Chart saved to: {output_path}")
        print(f"  File size: {file_size:,} bytes")
        print(f"  Dimensions: {figsize[0]}x{figsize[1]} inches")
        print(f"  DPI: {dpi}")
        
        plt.close()
        return output_path
    
    def create_line_chart(self, data, title, xlabel="Period", ylabel="Value", 
                         output_path="line_chart.png", figsize=(12, 4), dpi=150):
        """
        Create a line chart
        
        Args:
            data: Dictionary with structure {series_name: {x_value: y_value}}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            output_path: Path to save the chart
            figsize: Figure size in inches
            dpi: Dots per inch for image quality
        """
        
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Plot each series
        for i, (series_name, series_data) in enumerate(data.items()):
            x_values = list(series_data.keys())
            y_values = list(series_data.values())
            color = self.color_palette[i % len(self.color_palette)]
            
            ax.plot(x_values, y_values, marker='o', linewidth=2, 
                   markersize=6, label=series_name, color=color)
        
        # Customize the chart
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Improve layout
        plt.tight_layout()
        
        # Save the chart
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        
        # Get file info
        file_size = os.path.getsize(output_path)
        print(f"✓ Chart saved to: {output_path}")
        print(f"  File size: {file_size:,} bytes")
        print(f"  Dimensions: {figsize[0]}x{figsize[1]} inches")
        print(f"  DPI: {dpi}")
        
        plt.close()
        return output_path

def create_monthly_sales_chart(output_path="monthly_sales_chart.png"):
    """Create the monthly sales comparison chart"""
    
    # Sample data structure
    sales_data = {
        'Jan': {2023: 15, 2024: 41, 2025: 46},
        'Feb': {2023: 11, 2024: 31, 2025: 52},
        'Mar': {2023: 10, 2024: 44, 2025: 52},
        'Apr': {2023: 42, 2024: 31, 2025: 47},
        'May': {2023: 59, 2024: 43, 2025: 44},
        'Jun': {2023: 61, 2024: 41, 2025: 29}
    }
    
    generator = ChartGenerator()
    return generator.create_grouped_bar_chart(
        data=sales_data,
        title="Monthly Sales Comparison 2023-2025",
        xlabel="Month",
        ylabel="Units Sold",
        output_path=output_path
    )

def create_revenue_chart(output_path="revenue_chart.png"):
    """Create the quarterly revenue growth chart"""
    
    # Revenue data in millions
    revenue_data = {
        '2023': {
            'Q1': 1.2, 'Q2': 1.5, 'Q3': 1.8, 'Q4': 2.1
        },
        '2024': {
            'Q1': 2.3, 'Q2': 2.7, 'Q3': 3.1, 'Q4': 3.5
        }
    }
    
    generator = ChartGenerator()
    
    # Create line chart
    fig, ax = plt.subplots(figsize=(12, 4), dpi=150)
    
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    colors = generator.color_palette
    
    for i, (year, data) in enumerate(revenue_data.items()):
        values = [data[q] for q in quarters]
        color = colors[i % len(colors)]
        ax.plot(quarters, values, marker='o', linewidth=3, 
               markersize=8, label=year, color=color)
        
        # Add value labels
        for j, value in enumerate(values):
            ax.annotate(f'${value}M',
                       xy=(j, value),
                       xytext=(0, 10),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=10, fontweight='bold')
    
    # Customize
    ax.set_xlabel('Quarter', fontsize=12)
    ax.set_ylabel('Revenue (Millions USD)', fontsize=12)
    ax.set_title('Quarterly Revenue Growth', fontsize=16, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x}M'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', 
               facecolor='white', edgecolor='none')
    
    file_size = os.path.getsize(output_path)
    print(f"✓ Revenue chart saved to: {output_path}")
    print(f"  File size: {file_size:,} bytes")
    
    plt.close()
    return output_path

def create_custom_chart(data_dict, chart_type="bar", title="Custom Chart", 
                       output_path="custom_chart.png"):
    """
    Create a custom chart from dictionary data
    
    Args:
        data_dict: Data in various formats
        chart_type: 'bar', 'line', 'pie'
        title: Chart title
        output_path: Output file path
    """
    
    generator = ChartGenerator()
    
    if chart_type == "bar":
        return generator.create_grouped_bar_chart(
            data=data_dict,
            title=title,
            output_path=output_path
        )
    elif chart_type == "line":
        return generator.create_line_chart(
            data=data_dict,
            title=title,
            output_path=output_path
        )
    else:
        print(f"Chart type '{chart_type}' not implemented yet")
        return None

def parse_data_from_text(text_description):
    """
    Parse data from natural language description
    This is a simple parser - you could extend it with NLP
    """
    
    # Example parsing for monthly sales data
    if "monthly sales" in text_description.lower():
        # Extract data patterns like "January 2023: 15 units"
        import re
        pattern = r'(\w+)\s+(\d{4}):\s*(\d+)\s*units?'
        matches = re.findall(pattern, text_description)
        
        data = {}
        for month, year, value in matches:
            if month not in data:
                data[month] = {}
            data[month][int(year)] = int(value)
        
        return data
    
    return None

def create_pie_chart(self, data, title, output_path="pie_chart.png",
                        figsize=(6, 6), dpi=150, autopct='%1.1f%%'):
        """
        Create a pie chart.

        Args:
            data: Dict {label: value}
            title: Chart title
            output_path: File to save
        """
        labels = list(data.keys())
        values = list(data.values())
        colors = self.color_palette[:len(labels)]

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        wedges, texts, autotexts = ax.pie(values, labels=labels, colors=colors,
                                          autopct=autopct, startangle=90,
                                          textprops={'fontsize': 10})
        ax.set_title(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close()
        print(f"✓ Pie chart saved to {output_path}")
        return output_path

def create_stacked_bar_chart(self, data, title, xlabel="Period", ylabel="Value",
                            output_path="stacked_bar.png", figsize=(12, 4), dpi=150):
    """
    Create stacked bar chart.

    Args:
        data: Dict {period: {category: value}}
    """
    periods = list(data.keys())
    categories = set()
    for v in data.values():
        categories.update(v.keys())
    categories = sorted(categories)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    bottom = np.zeros(len(periods))

    for i, cat in enumerate(categories):
        values = [data[p].get(cat, 0) for p in periods]
        color = self.color_palette[i % len(self.color_palette)]
        ax.bar(periods, values, bottom=bottom, label=cat, color=color)
        bottom += np.array(values)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"✓ Stacked bar chart saved to {output_path}")
    return output_path

def create_line_chart_with_growth(self, series_data, title, growth_pct=None,
                                    output_path="line_growth.png", figsize=(12, 4), dpi=150):
    """
    Line chart with optional growth annotation.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    for i, (series_name, data) in enumerate(series_data.items()):
        x = list(data.keys())
        y = list(data.values())
        ax.plot(x, y, marker='o', linewidth=2,
                color=self.color_palette[i % len(self.color_palette)],
                label=series_name)
    if growth_pct is not None:
        ax.annotate(f"{growth_pct:.2f}% ↑",
                    xy=(x[-1], y[-1]), xytext=(0, -30),
                    textcoords="offset points",
                    ha='center', color="green",
                    fontsize=12, fontweight='bold',
                    arrowprops=dict(arrowstyle="->", color="green"))
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"✓ Line chart with growth saved to {output_path}")
    return output_path

# Example usage and testing
if __name__ == "__main__":
    
    print("🎨 Local Chart Generator")
    print("=" * 50)
    
    # Create monthly sales chart
    print("\n📊 Creating monthly sales chart...")
    sales_chart = create_monthly_sales_chart("monthly_sales_2023_2025.png")
    
    # Create revenue chart
    print("\n📈 Creating revenue growth chart...")
    revenue_chart = create_revenue_chart("quarterly_revenue_growth.png")
    
    # Custom chart example
    print("\n🎯 Creating custom product performance chart...")
    product_data = {
        'Product A': {2023: 120, 2024: 150, 2025: 180},
        'Product B': {2023: 80, 2024: 95, 2025: 110},
        'Product C': {2023: 60, 2024: 85, 2025: 95}
    }
    
    custom_chart = create_custom_chart(
        data_dict=product_data,
        chart_type="bar",
        title="Product Performance Comparison",
        output_path="product_performance.png"
    )
    
    # Summary
    print("\n" + "=" * 50)
    print("✅ All charts generated successfully!")
    
    # List all generated files
    generated_files = [
        "monthly_sales_2023_2025.png",
        "quarterly_revenue_growth.png", 
        "product_performance.png"
    ]
    
    print("\n📁 Generated files:")
    for file in generated_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"  • {file} ({size:,} bytes)")
        else:
            print(f"  ⚠️  {file} (not found)")
    
    print(f"\n🕒 Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Utility functions for integration with your MCP server
def generate_kam_chart(merchant_data, output_path="kam_chart.png"):
    """
    Generate KAM chart from merchant data (for MCP integration)
    
    Args:
        merchant_data: Dictionary with merchant sales data
        output_path: Where to save the chart
    """
    
    if not merchant_data:
        print("⚠️  No merchant data provided")
        return None
    
    generator = ChartGenerator()
    return generator.create_grouped_bar_chart(
        data=merchant_data,
        title="Merchant Performance Analysis",
        xlabel="Period",
        ylabel="Sales",
        output_path=output_path
    )

def quick_chart(chart_type, data, title="Quick Chart", output_path="quick_chart.png"):
    """
    Quick chart generation function
    
    Example:
        quick_chart("bar", {"A": {2024: 100}, "B": {2024: 150}}, "Sales Data")
    """
    
    return create_custom_chart(
        data_dict=data,
        chart_type=chart_type,
        title=title,
        output_path=output_path
    )

if __name__ == "__main__":
    # Example usage of quick chart
    print("\n🔍 Quick chart example:")
    quick_chart_data = {
        'Category 1': {2023: 50, 2024: 70},
        'Category 2': {2023: 60, 2024: 80}
    }
    
    quick_chart("bar", quick_chart_data, "Quick Sales Chart", "quick_sales_chart.png")
    
    print("✅ Quick chart generated successfully!") 