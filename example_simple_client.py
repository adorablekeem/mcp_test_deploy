#!/usr/bin/env python3
"""Simple client for the Fast ReAct Agent"""

import asyncio

from mcp_use import MCPClient


async def test_fast_agent():
    """Test the fast ReAct agent."""

    print("⚡ Testing Fast ReAct Agent")
    print("=" * 40)

    client = MCPClient.from_dict({"mcpServers": {"simple_react": {"url": "http://localhost:8021/mcp"}}})

    try:
        # Test ping first
        print("📡 Testing connection...")
        ping_result = await client.call_tool("ping_simple_agent", {})
        print(f"   Status: {ping_result.get('status')}")

        # Test fast slide creation
        print("\n🚀 Creating slides (fast mode)...")

        import time

        start_time = time.time()

        result = await client.call_tool(
            "create_slides_simple_react",
            {
                "user_request": "Quick sales dashboard",
                "merchant_token": "test_merchant_123",
                "starting_date": "2024-06-01",
                "end_date": "2024-09-01",
            },
        )

        total_time = time.time() - start_time

        if result.get("success"):
            print(f"✅ Slides created in {total_time:.1f}s!")
            print(f"   Presentation ID: {result.get('presentation_id')}")
            print(f"   Charts added: {result.get('charts_added', 0)}")

            breakdown = result.get("breakdown", {})
            print(f"\n⚡ Performance breakdown:")
            print(f"   Planning: {breakdown.get('planning', 0):.3f}s")
            print(f"   Data: {breakdown.get('data_retrieval', 0):.1f}s")
            print(f"   Charts: {breakdown.get('chart_creation', 0):.1f}s")
            print(f"   Slides: {breakdown.get('slide_creation', 0):.1f}s")

        else:
            print(f"❌ Failed: {result.get('error')}")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Make sure server is running: python simple_react_agent.py")


if __name__ == "__main__":
    asyncio.run(test_fast_agent())
