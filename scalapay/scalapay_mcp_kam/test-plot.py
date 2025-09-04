#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# ---------- small helpers ----------
def parse_json_from_text(text: str):
    """
    Robustly extract JSON from LLM text:
    - Prefer a ```json ... ``` fenced block
    - Else any ``` ... ``` fenced block
    - Else the largest {...} substring
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty response")

    # 1) fenced ```json ... ```
    m = re.search(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        # 2) any fenced block
        m = re.search(r"```\s*(.*?)\s*```", text, flags=re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        return json.loads(candidate)

    # 3) largest {...} substring heuristic
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1].strip()
        return json.loads(candidate)

    # 4) last resort: replace single quotes and try whole string
    try:
        s2 = re.sub(r"(?<!\\)'", '"', text)
        return json.loads(s2)
    except Exception:
        raise ValueError("Could not find valid JSON in response")

def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", s.strip().lower())
    return re.sub(r"-+", "-", s).strip("-") or "item"

def _persist_plot(path: str | None, key: str, out_dir: str = "./plots") -> Optional[str]:
    if not isinstance(path, str) or not path.lower().endswith(".png"):
        return None
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(path):
        target = os.path.join(out_dir, f"{_slug(key)}_{uuid.uuid4().hex[:8]}.png")
        with open(path, "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
        return target
    return None

async def _discover_tool(agent: MCPAgent, server_id: str, tool_name: str):
    """
    Find the LangChain tool that maps to a given MCP tool on a given server.
    We search by substring to handle name prefixes like "MatPlotAgent:generate_chart_simple".
    """
    if not getattr(agent, "_tools", None):
        await agent.initialize()
    candidates = [t for t in agent._tools if tool_name in t.name and server_id.split(":")[0] in t.name]
    if not candidates:
        # fallback: any tool containing the op name
        candidates = [t for t in agent._tools if tool_name in t.name]
    if not candidates:
        names = ", ".join(t.name for t in agent._tools)
        raise RuntimeError(f"Tool '{tool_name}' not found on server '{server_id}'. Available: {names}")
    return candidates[0]

def _find_latest_png_in_workspace(workspace: str | None) -> Optional[str]:
    if not workspace or not os.path.isdir(workspace):
        return None
    pngs = [os.path.join(workspace, f) for f in os.listdir(workspace) if f.lower().endswith(".png")]
    if not pngs:
        return None
    return max(pngs, key=os.path.getmtime)

# ---------- core tests ----------

async def test_alfred(agent: MCPAgent) -> Dict[str, Any]:
    """
    Ask Alfred for JSON (structured_data + paragraph). We force a simple schema
    to keep output predictable.
    """
    schema = """
Return JSON with this schema ONLY:
{
  "structured_data": {
    "Jan": {"2024": 120, "2025": 140},
    "Feb": {"2024": 150, "2025": 160},
    "Mar": {"2024": 130, "2025": 170}
  },
  "paragraph": "One-paragraph analysis of the data."
}
"""
    prompt = f"""
You are Alfred. Produce monthly sales over time for 2024-2025.
IMPORTANT: Output must be valid JSON. No prose outside JSON.

{schema}
"""
    print("▶️  Running Alfred...")
    res = await agent.run(prompt, max_steps=5)
    # Parse result (often a string)
    try:
        data = parse_json_from_text(res)
    except Exception as e:
        raise RuntimeError(f"Alfred did not return valid JSON: {e}\nRaw: {res[:400]}")

    if not isinstance(data, dict) or "structured_data" not in data:
        raise RuntimeError(f"Alfred JSON missing 'structured_data'. Got keys: {list(data.keys())}")
    if "paragraph" not in data:
        data["paragraph"] = ""
    print("✅ Alfred returned structured_data with keys:", list(data["structured_data"].keys()))
    return data

async def test_matplot_direct(agent: MCPAgent, instruction: str) -> Dict[str, Any]:
    """
    Call MatPlotAgent.generate_chart_simple directly (no planner).
    Returns the dict from the tool: {success, chart_path, workspace_path, ...}
    """
    tool = await _discover_tool(agent, server_id="MatPlotAgent", tool_name="generate_chart_simple")

    args = {
        "instruction": instruction,
        "chart_type": "auto",
        "model_type": "gpt-4o",
        "workspace_name": "chart_generation",
    }
    print("▶️  Invoking MatPlot tool directly...")
    # Some versions use .ainvoke(**kwargs); some expect a dict
    try:
        result = await tool.ainvoke(args)
    except TypeError:
        result = await tool.ainvoke(**args)

    # Normalize to dict
    if isinstance(result, str):
        try:
            result = parse_json_from_text(result)
        except Exception:
            result = {"raw": result}
    elif not isinstance(result, dict):
        result = {"raw": result}

    # Recover chart if tool forgot to set chart_path but saved a PNG
    if not result.get("chart_path"):
        lp = _find_latest_png_in_workspace(result.get("workspace_path"))
        if lp:
            result["chart_path"] = lp

    return result

# ---------- scenario orchestration ----------

async def main():
    parser = argparse.ArgumentParser(description="End-to-end MCP test (Alfred + MatPlot).")
    parser.add_argument("--alfred", default="http://127.0.0.1:8000/mcp", help="Alfred MCP URL")
    parser.add_argument("--matplot", default="http://127.0.0.1:8010/mcp", help="MatPlot MCP URL")
    parser.add_argument("--transport", default="streamable-http", choices=["http", "streamable-http"], help="MCP transport type (match server)")
    args = parser.parse_args()

    # Build a single client with BOTH servers
    client = MCPClient.from_dict({
        "mcpServers": {
            "Alfred":      {"url": args.alfred,  "type": args.transport},
            "MatPlotAgent":{"url": args.matplot, "type": args.transport},
        }
    })

    llm = ChatOpenAI(model="gpt-4o")
    agent = MCPAgent(llm=llm, client=client, max_steps=8, verbose=True)
    await agent.initialize()

    # 1) Test Alfred
    alfred_json = await test_alfred(agent)
    structured = alfred_json.get("structured_data", {})
    paragraph = alfred_json.get("paragraph", "")

    # 2) Build a MatPlot instruction from Alfred output
    instruction = (
        "Create a professional Matplotlib chart from the JSON data below. "
        "Do NOT call plt.show(). Save as 'chart_output.png' at 300 DPI. "
        "Use readable axis labels and a legend when multiple series exist.\n\n"
        f"Title: Monthly Sales Over Time (Test)\n"
        f"Data (JSON):\n{json.dumps(structured, ensure_ascii=False)}\n\n"
        f"Notes: {paragraph}"
    )

    # 3) Call MatPlot tool directly
    result = await test_matplot_direct(agent, instruction)

    print("\n================= MatPlot Result =================")
    print(json.dumps({k: v for k, v in result.items() if k != "generated_code"}, indent=2))
    if "generated_code" in result:
        print("\n--- generated_code (first 400 chars) ---")
        print(str(result["generated_code"])[:400])
        print("----------------------------------------")

    # 4) Persist PNG to ./plots
    chart_path = result.get("chart_path")
    copied = _persist_plot(chart_path, key="monthly-sales-test")
    print("\n🎯 chart_path:", chart_path)
    print("📦 copied_to :", copied or "(not copied)")

    success = bool(result.get("success") and (chart_path or copied))
    if not success:
        print("\n❌ Chart generation reported failure. Check:")
        print("  - execution_log (if present)")
        print("  - log_file path")
        print("  - workspace_path for any *.png")
        sys.exit(2)

    print("\n✅ End-to-end test succeeded.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
