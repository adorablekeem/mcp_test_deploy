import asyncio
import json
import os
from pathlib import Path
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

@dataclass 
class ChartResult:
    success: bool = False
    chart_path: str = None
    workspace_path: str = None
    generated_code: str = None
    execution_log: str = None
    error: str = None

async def test_matplot_mcp_server():
    """Test the MatPlotAgent MCP server using the same pattern as your working code"""
    
    # Initialize client and agent following your pattern
    client = MCPClient.from_dict({
        "mcpServers": {
            "matplot": {
                "url": "http://localhost:8010/mcp"  # Your MCP server URL
            }
        }
    })
    
    llm = ChatOpenAI(model="gpt-4o-mini")  # Use a lighter model for testing
    agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)
    
    # Test 1: Simple chart generation
    print("=== Test 1: Simple Chart Generation ===")
    
    chart_instruction = """
    Use the generate_chart_simple tool to create a grouped bar chart showing monthly sales comparison.
    
    Parameters:
    - instruction: "Create a professional grouped bar chart showing monthly sales data. Use this data: Jan 2024: 11234, Jan 2025: 10456, Feb 2024: 15098, Feb 2025: 14300, Mar 2024: 9800 (no 2025 data), Apr 2024: 14050 (no 2025 data). X-axis should show months, Y-axis should show sales values, with separate bars for 2024 and 2025. Add a title 'Monthly Sales Comparison 2024 vs 2025' and a legend. Save as 'chart_output.png'"
    - chart_type: "bar"
    - model_type: "gpt-3.5-turbo"
    
    Call the tool and return the result.
    """
    
    try:
        result = await agent.run(chart_instruction, max_steps=10)
        print("Simple chart result:")
        print(json.dumps(result, indent=2, default=str))
        
    except Exception as e:
        print(f"❌ Simple chart test failed: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: Custom chart with data
    print("=== Test 2: Custom Chart With Data ===")
    
    custom_chart_instruction = """
    Use the create_custom_chart_with_data tool to create a chart with structured data.
    
    Parameters:
    - data: {
        "monthly_sales": {
            "Jan": {"2024": 11234, "2025": 10456},
            "Feb": {"2024": 15098, "2025": 14300}, 
            "Mar": {"2024": 9800, "2025": null},
            "Apr": {"2024": 14050, "2025": null}
        }
    }
    - chart_instruction: "Load the data from the JSON file and create a professional grouped bar chart. X-axis: months, Y-axis: sales values, two series for 2024 and 2025 (skip null values). Add title 'Monthly Sales 2024 vs 2025', legend, and save as 'custom_chart.png'"
    - data_filename: "sales_data.json"
    - model_type: "gpt-3.5-turbo"
    
    Call the tool and return the result.
    """
    
    try:
        result2 = await agent.run(custom_chart_instruction, max_steps=10)
        print("Custom chart result:")
        print(json.dumps(result2, indent=2, default=str))
        
    except Exception as e:
        print(f"❌ Custom chart test failed: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 3: Scalapay demographics (predefined)
    print("=== Test 3: Scalapay Demographics ===")
    
    demographics_instruction = """
    Use the generate_scalapay_demographics tool to create the predefined Scalapay customer demographics pie charts.
    
    This tool requires no parameters and will generate three pie charts for age, country, and gender distribution.
    
    Call the tool and return the result.
    """
    
    try:
        result3 = await agent.run(demographics_instruction, max_steps=10)
        print("Demographics result:")
        print(json.dumps(result3, indent=2, default=str))
        
    except Exception as e:
        print(f"❌ Demographics test failed: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 4: List available tools
    print("=== Test 4: List Available Tools ===")
    
    list_tools_instruction = """
    List all available tools from the MatPlotAgent MCP server.
    Show me what chart generation capabilities are available.
    """
    
    try:
        result4 = await agent.run(list_tools_instruction, max_steps=5)
        print("Available tools:")
        print(json.dumps(result4, indent=2, default=str))
        
    except Exception as e:
        print(f"❌ List tools test failed: {e}")

async def test_simple_direct_call():
    """Test a simple direct instruction without specific tool calls"""
    
    client = MCPClient.from_dict({
        "mcpServers": {
            "matplot": {
                "url": "http://localhost:8010/mcp"
            }
        }
    })
    
    llm = ChatOpenAI(model="gpt-4o-mini") 
    agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)
    
    simple_instruction = """
    I need to create a bar chart showing monthly sales data. The data is:
    - January 2024: 11,234 sales, January 2025: 10,456 sales
    - February 2024: 15,098 sales, February 2025: 14,300 sales  
    - March 2024: 9,800 sales (no 2025 data available)
    - April 2024: 14,050 sales (no 2025 data available)
    
    Please create a professional grouped bar chart comparing 2024 vs 2025 monthly sales. 
    Use appropriate colors, add a title, legend, and axis labels.
    """
    
    try:
        result = await agent.run(simple_instruction, max_steps=15)
        print("=== Simple Direct Call Result ===")
        print(json.dumps(result, indent=2, default=str))
        
    except Exception as e:
        print(f"❌ Simple direct call failed: {e}")

async def main():
    """Run all tests"""
    
    print("Testing MatPlotAgent MCP Server using MCPAgent pattern")
    print("=" * 70)
    
    # Test if server is accessible
    try:
        client = MCPClient.from_dict({
            "mcpServers": {
                "matplot": {
                    "url": "http://localhost:8010/mcp"
                }
            }
        })
        print("✅ MCP Client initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize MCP Client: {e}")
        print("Make sure your MCP server is running on http://localhost:8010/mcp")
        return
    
    # Run the comprehensive tests
    await test_matplot_mcp_server()
    
    print("\n" + "="*70 + "\n")
    
    # Also try the simple approach
    await test_simple_direct_call()

if __name__ == "__main__":
    asyncio.run(main())