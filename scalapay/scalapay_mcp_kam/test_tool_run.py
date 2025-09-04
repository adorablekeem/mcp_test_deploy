import asyncio
from tools.alfred_automation import mcp_tool_run
from prompts.charts_prompt import GENERAL_CHART_PROMPT

async def test_mcp_tool_run():
    results = await mcp_tool_run(
        requests_list=[
            "monthly sales over time",
            "monthly orders by user type",
            "scalapay users demographic"
        ],
        merchant_token="2L8082NCG",           # Replace with a valid merchant token if needed
        starting_date="2023-01-01",
        end_date="2025-06-30",
        chart_prompt_template=GENERAL_CHART_PROMPT,
    )
    print("MCP Tool Run Results:")
    print(results)

if __name__ == "__main__":
    asyncio.run(test_mcp_tool_run())