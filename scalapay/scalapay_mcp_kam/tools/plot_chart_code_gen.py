import os
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the client
client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def generate_chart_with_claude(data_description, color_palette=None, return_image=True):
    """
    Generate a chart using Claude's code execution based on natural language description
    
    Args:
        data_description: Natural language description of the data and chart requirements
        color_palette: Optional list of hex colors to use for the chart
        return_image: If True, return the image data directly
    """
    
    # Default color palette if none provided
    if color_palette is None:
        color_palette = [
            "#87CEEB", 
            "#DA70D6", 
            "#FFA500", 
            "#FF1493", 
            "#9370DB", 
            "#FFA07A", 
            "#FFB6C1", 
            "#FF69B4", 
            "#98FB98", 
            "#DDA0DD" 
        ]
    
    # Create the prompt for Claude - with image return mechanism
    if return_image:
        prompt = f"""
        Please create a professional matplotlib chart with the following requirements:
        
        {data_description}
        
        Use this color palette for the visualization: {color_palette}
        
        Requirements:
        - Use matplotlib with the 'Agg' backend
        - Set figure size to 12x4 inches with 150 DPI
        - Add value labels on top of bars if it's a bar chart
        - Include proper labels, title, and legend
        - Use tight_layout() for optimal spacing
        
        IMPORTANT: After creating the chart, save it and return the image data:
        ```python
        import io
        import base64
        
        # Save to bytes buffer instead of file
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        
        # Read the image data
        image_bytes = buffer.read()
        print(f"Chart created successfully! Size: {{len(image_bytes)}} bytes")
        
        # Save to file for verification
        with open('/tmp/chart.png', 'wb') as f:
            f.write(image_bytes)
        print("Chart saved to /tmp/chart.png")
        ```
        """
    else:
        prompt = f"""
        Please create a professional matplotlib chart with the following requirements:
        
        {data_description}
        
        Use this color palette for the visualization: {color_palette}
        
        Requirements:
        - Use matplotlib with the 'Agg' backend
        - Set figure size to 12x4 inches with 150 DPI
        - Add value labels on top of bars if it's a bar chart
        - Include proper labels, title, and legend
        - Save the chart to '/tmp/chart.png' using plt.savefig('/tmp/chart.png', dpi=150, bbox_inches='tight')
        - Use tight_layout() for optimal spacing
        - Print the file size after saving
        """
    
    # Execute the request
    response = client.beta.messages.create(
        model="claude-opus-4-1-20250805",  
        betas=["code-execution-2025-05-22"],
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": prompt
        }],
        tools=[{
            "type": "code_execution_20250522",
            "name": "code_execution"
        }]
    )
    
    return response

def download_generated_files(response):
    """
    Download any files generated during code execution
    """
    downloaded_files = []
    
    for item in response.content:
        if hasattr(item, 'type') and item.type == 'code_execution_tool_result':
            # Print execution output
            if hasattr(item.content, 'stdout') and item.content.stdout:
                print("Execution output:")
                print(item.content.stdout)
            
            # Check for generated files
            if hasattr(item.content, 'content'):
                for file_info in item.content.content:
                    if 'file_id' in file_info:
                        try:
                            file_metadata = client.beta.files.retrieve_metadata(file_info['file_id'])
                            file_content = client.beta.files.download(file_info['file_id'])
                            
                            local_filename = file_metadata.filename or "chart.png"
                            file_content.write_to_file(local_filename)
                            downloaded_files.append(local_filename)
                            print(f"✓ Chart downloaded: {local_filename}")
                        except Exception as e:
                            print(f"Error downloading file: {e}")
    
    return downloaded_files

# Example usage
if __name__ == "__main__":
    
    # Define your custom color palette
    my_colors = [
        "#8ad3f4", "#d896f6", "#f7a463", "#f15375", "#b7b8f5", 
        "#f6b8ea", "#469acf", "#ffd700", "#b0e0e6", "#ffa07a"
    ]
    
    # Example 1: Monthly sales data
    sales_description = """
    Create a grouped bar chart showing monthly sales data:
    - January 2023: 15 units, 2024: 41 units, 2025: 46 units
    - February 2023: 11 units, 2024: 31 units, 2025: 52 units
    - March 2023: 10 units, 2024: 44 units, 2025: 52 units
    - April 2023: 42 units, 2024: 31 units, 2025: 47 units
    - May 2023: 59 units, 2024: 43 units, 2025: 44 units
    - June 2023: 61 units, 2024: 41 units, 2025: 29 units
    
    Group bars by month, with different colors for each year.
    Add value labels on top of each bar.
    Title: "Monthly Sales Comparison 2023-2025"
    """
    
    print("Generating sales chart...")
    response = generate_chart_with_claude(sales_description, my_colors)
    files = download_generated_files(response)
    
    print("-" * 50)
    
    # Example 2: Different type of chart with same color palette
    revenue_description = """
    Create a line chart showing quarterly revenue trends:
    - Q1 2023: $1.2M, Q2 2023: $1.5M, Q3 2023: $1.8M, Q4 2023: $2.1M
    - Q1 2024: $2.3M, Q2 2024: $2.7M, Q3 2024: $3.1M, Q4 2024: $3.5M
    
    Use markers on the line points and add a grid for better readability.
    Title: "Quarterly Revenue Growth"
    Y-axis should show values in millions with $ prefix.
    """
    
    print("\nGenerating revenue chart...")
    response2 = generate_chart_with_claude(revenue_description, my_colors)
    files2 = download_generated_files(response2)
    
    print("\nAll charts generated successfully!")
    print(f"Files created: {files + files2}")

# Alternative: Simple one-liner function for quick charts
def quick_chart(description, colors=None):
    """
    Quick function to generate a chart with minimal code
    
    Example:
        quick_chart("Bar chart of product sales: A=100, B=150, C=200")
    """
    response = generate_chart_with_claude(description, colors)
    return download_generated_files(response)

# Simpler approach: Just ask Claude to create the chart without file handling
def create_chart_simple(data_description, save_locally=True):
    """
    Simpler approach - just ask Claude to create and show the chart
    """
    
    prompt = f"""
    Create a matplotlib chart based on this description: {data_description}
    
    Use professional styling with a nice color palette.
    Save the final chart to 'chart.png' in the current directory if possible.
    Show me the chart data and confirm it was created.
    """
    
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    print(response.content[0].text)
    return response

# Most direct approach: Use matplotlib locally with Claude generating the code
def generate_chart_code_only(data_description, color_palette=None):
    """
    Have Claude generate the matplotlib code, then run it locally
    """
    if color_palette is None:
        color_palette = [
            "#8ad3f4", "#d896f6", "#f7a463", "#f15375", "#b7b8f5", 
            "#f6b8ea", "#469acf", "#ffd700", "#b0e0e6", "#ffa07a"
        ]
    
    prompt = f"""
    Generate Python matplotlib code to create this chart: {data_description}
    
    Use this color palette: {color_palette}
    
    Requirements:
    - Return ONLY the Python code, no explanations
    - Use figure size 12x4 inches, 150 DPI
    - Include all necessary imports
    - Save to 'generated_chart.png'
    - The code should be ready to run as-is
    """
    
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    # Extract the code from the response
    code_text = response.content[0].text
    
    # Find code block if it exists
    if "```python" in code_text:
        start = code_text.index("```python") + 9
        end = code_text.index("```", start)
        code = code_text[start:end].strip()
    else:
        code = code_text.strip()
    
    # Save the code
    with open('generated_chart_code.py', 'w') as f:
        f.write(code)
    
    print("Chart code saved to 'generated_chart_code.py'")
    print("Running the code locally...")
    
    # Execute the code locally
    try:
        exec(code)
        print("✓ Chart generated successfully as 'generated_chart.png'")
        return 'generated_chart.png'
    except Exception as e:
        print(f"Error running code: {e}")
        print("You can manually run 'generated_chart_code.py' to create the chart")
        return None