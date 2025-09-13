#!/usr/bin/env python3
"""
Example client for the ReAct Slides Agent MCP Server

This demonstrates how to use the ReAct agent to create slides.
"""

import asyncio
import json

from mcp_use import MCPClient


async def example_usage():
    """Example of using the ReAct Slides Agent."""

    print("🤖 ReAct Slides Agent - Example Usage")
    print("=" * 50)

    # Connect to the ReAct agent MCP server
    client = MCPClient.from_dict({"mcpServers": {"react_slides_agent": {"url": "http://localhost:8020/mcp"}}})

    try:
        print("1️⃣ Connecting to ReAct Slides Agent server...")

        # List available tools
        tools = await client.list_tools()
        print(f"   Available tools: {[tool.name for tool in tools]}")

        print("\n2️⃣ Creating slides with ReAct agent...")

        # Call the ReAct agent to create slides
        result = await client.call_tool(
            "create_slides_with_react",
            {
                "user_request": "Create a comprehensive business dashboard showing monthly sales performance, customer behavior analysis, and product insights for our Q3 review",
                "merchant_token": "your_merchant_token_here",
                "starting_date": "2024-06-01",
                "end_date": "2024-09-01",
            },
        )

        print(f"   Result: {json.dumps(result, indent=2)}")

        if result.get("success"):
            print(f"\n✅ Slides created successfully!")
            print(f"   Presentation ID: {result.get('presentation_id', 'Unknown')}")
            print(f"   Total duration: {result.get('total_duration', 0):.2f} seconds")

            # Show workflow steps
            steps = result.get("steps", [])
            print(f"\n📋 Workflow Steps:")
            for i, step in enumerate(steps, 1):
                print(
                    f"   {i}. {step['step']}: {step['duration']:.2f}s ({'✅ SUCCESS' if step['success'] else '❌ FAILED'})"
                )
        else:
            print(f"\n❌ Slide creation failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"\n❌ Client error: {e}")
        print("\n💡 Make sure the ReAct agent server is running:")
        print("   python react_slides_agent.py")


if __name__ == "__main__":
    print("🚀 Starting ReAct Slides Agent Example")
    print("\n⚠️  Prerequisites:")
    print("   1. Start the ReAct agent server: python react_slides_agent.py")
    print("   2. Start Alfred MCP server: (usually on port 8000)")
    print("   3. Start MatplotAgent server: (usually on port 8010)")
    print("   4. Configure Google API credentials")
    print("\n" + "=" * 60)

    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        print("\n⏹️  Example interrupted")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
