from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, Tuple

from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
from scalapay.scalapay_mcp_kam.prompts.charts_prompt import MONTHLY_SALES_PROMPT, STRUCTURED_CHART_SCHEMA_PROMPT

# ---------- utils ----------


def _safe_json_loads_maybe_single_quotes(s: str) -> Dict[str, Any]:
    """Parse JSON that might use single quotes."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        s2 = re.sub(r"(?<!\\)'", '"', s)
        return json.loads(s2)


def _extract_struct_and_paragraph(entry: Dict[str, Any]) -> Tuple[dict | None, str | None, dict | None]:
    """Prefer slides_struct; fallback to alfred_raw string. Also extract total_variations."""
    structured = None
    paragraph = None
    total_variations = None

    slides_struct = entry.get("slides_struct")
    if isinstance(slides_struct, dict):
        structured = slides_struct.get("structured_data")
        paragraph = slides_struct.get("paragraph")
        total_variations = slides_struct.get("total_variations")
    elif (
        hasattr(slides_struct, "structured_data")
        or hasattr(slides_struct, "paragraph")
        or hasattr(slides_struct, "total_variations")
    ):
        structured = getattr(slides_struct, "structured_data", None)
        paragraph = getattr(slides_struct, "paragraph", None)
        total_variations = getattr(slides_struct, "total_variations", None)

    if (structured is None or paragraph is None or total_variations is None) and isinstance(
        entry.get("alfred_raw"), str
    ):
        try:
            parsed = _safe_json_loads_maybe_single_quotes(entry["alfred_raw"])
            structured = structured or parsed.get("structured_data")
            paragraph = paragraph or parsed.get("paragraph")
            total_variations = total_variations or parsed.get("total_variations")
        except Exception:
            pass

    return structured, paragraph, total_variations


def _persist_plot_ref(data_type: str, path: str | None, out_dir: str = "./plots") -> str | None:
    """Copy the generated PNG into ./plots with a stable-ish name."""
    if not isinstance(path, str) or not path.lower().endswith(".png"):
        return None

    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(path):
        safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "_", data_type) or "chart"
        target = os.path.join(out_dir, f"{safe_key}_{uuid.uuid4().hex[:8]}.png")
        try:
            with open(path, "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())
            return target
        except Exception:
            return path
    return path


# ---------- MCP call ----------
def _to_dict(x: Any) -> Dict[str, Any]:
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        # try plain JSON, then fenced JSON, then single-quote replacement
        try:
            return json.loads(x)
        except Exception:
            m = re.search(r"```json\s*(.*?)\s*```", x, flags=re.DOTALL | re.IGNORECASE) or re.search(
                r"```\s*(.*?)\s*```", x, flags=re.DOTALL
            )
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass
            try:
                return json.loads(re.sub(r"(?<!\\)'", '"', x))
            except Exception:
                return {"raw": x}
    return {"raw": x}


async def mcp_matplot_run(
    results_dict: Dict[str, Any] | str,
    *,
    agent: MCPAgent | None = None,
    client: MCPClient | None = None,
    llm: ChatOpenAI | None = None,
    matplot_url: str = "http://localhost:8010/mcp",
    server_id: str = "MatPlotAgent",
    operation: str = "generate_chart_simple",
    model_type: str = "gpt-4o",
    max_steps: int = 15,
    verbose: bool = False,
    transport: str = "http",  # set to "streamable-http" if your server runs with that
    ctx = None,  # Add context parameter
) -> Dict[str, Any]:
    """
    For each entry in results_dict:
      - Extract structured_data + paragraph
      - Build a single instruction string for generate_chart_simple
      - Call the MatPlot tool *directly* (no planner)
      - Copy PNG to ./plots and set entry['chart_path']
      - Keep full tool payload in entry['matplot_raw']
    """

    # --- normalize input ---
    if isinstance(results_dict, str):
        if ctx:
            await ctx.info("📥 Converting input string to dictionary...")
        results_dict = _safe_json_loads_maybe_single_quotes(results_dict)
    if not isinstance(results_dict, dict):
        raise TypeError("mcp_matplot_run expected dict or JSON string yielding a dict.")

    if ctx:
        chart_count = len([k for k, v in results_dict.items() if v.get("structured_data")])
        await ctx.info(f"📊 Starting chart generation for {chart_count} data sections")

    # --- client/agent setup (dedicated MatPlot server) ---
    if agent is None:
        # if a client was passed, we'll use it; otherwise create one
        if client is None:
            client = MCPClient.from_dict({"mcpServers": {server_id: {"url": matplot_url, "type": transport}}})
        
        if ctx:
            await ctx.info(f"🔌 Connected to MatPlot MCP server ({matplot_url})")
            
        llm = llm or ChatOpenAI(model=model_type)
        agent = MCPAgent(llm=llm, client=client, max_steps=max_steps, verbose=verbose)
        await agent.initialize()
        
        if ctx:
            await ctx.info(f"🤖 Initialized {model_type} agent for chart generation")
    elif ctx:
        await ctx.info("🔄 Reusing existing MatPlot agent session")

    # --- discover the tool once ---
    def _find_tool():
        if not getattr(agent, "_tools", None):
            return None
        # search by substring (names can be prefixed e.g. "MatPlotAgent:generate_chart_simple")
        for t in agent._tools:
            if operation in t.name:
                return t
        return None

    tool = _find_tool()
    if tool is None:
        available = ", ".join(t.name for t in (agent._tools or []))
        raise RuntimeError(
            f"Tool '{operation}' not found. Available tools: {available}. "
            f"Check server_id/transport and that MatPlot server is up at {matplot_url}."
        )

    # --- process each entry concurrently ---
    def has_valid_structured_data(entry):
        """Check if entry has structured data in slides_struct or at root level"""
        if not isinstance(entry, dict):
            return False
        # Check root level first
        if entry.get("structured_data"):
            return True
        # Check slides_struct
        slides_struct = entry.get("slides_struct")
        if isinstance(slides_struct, dict) and slides_struct.get("structured_data"):
            return True
        return False
    
    valid_entries = [k for k, v in results_dict.items() if has_valid_structured_data(v)]
    print(f"[DEBUG] Valid entries for chart generation: {valid_entries}")
    
    # Debug: Show what structured_data looks like for each valid entry
    for k in valid_entries:
        v = results_dict[k]
        sd = v.get("structured_data")
        print(f"[DEBUG] {k} structured_data: {type(sd)} - {sd}")
        if isinstance(sd, dict):
            print(f"[DEBUG] {k} structured_data length: {len(sd)}")
            if sd:
                print(f"[DEBUG] {k} first few items: {dict(list(sd.items())[:3])}")
        
    if not valid_entries:
        if ctx:
            await ctx.warning("⚠️ No valid entries found for chart generation")
        print("[DEBUG] No valid entries found - returning original results")
        return results_dict
    
    async def process_single_chart(data_type: str, entry: dict, index: int) -> tuple[str, dict]:
        """Process a single chart generation concurrently."""
        print(f"[DEBUG] Starting process_single_chart for: {data_type}")
        if not isinstance(entry, dict):
            print(f"[DEBUG] Invalid entry type for {data_type}: {type(entry).__name__}")
            return data_type, {"errors": [f"Invalid entry type: {type(entry).__name__}"], "chart_path": None}

        entry.setdefault("errors", [])
        entry.setdefault("chart_path", None)

        if ctx:
            await ctx.info(f"🎨 [{index}/{len(valid_entries)}] Generating chart: {data_type}")

        try:
            # 1) extract chartable info
            structured_data, paragraph, total_variations = _extract_struct_and_paragraph(entry)
            print(f"[DEBUG] {data_type} - structured_data: {structured_data}")
            print(f"[DEBUG] {data_type} - paragraph: {paragraph}")
            
            if not isinstance(structured_data, dict):
                print(f"[DEBUG] {data_type} - No valid structured data, skipping")
                if ctx:
                    await ctx.warning(f"  ⚠️ No valid structured data for {data_type}")
                entry["errors"].append("No structured_data available or invalid.")
                return data_type, entry
                
            if not structured_data:  # Empty dict
                print(f"[DEBUG] {data_type} - Empty structured data, skipping")
                if ctx:
                    await ctx.warning(f"  ⚠️ Empty structured data for {data_type}")
                entry["errors"].append("Structured data is empty.")
                return data_type, entry
                
            if ctx:
                await ctx.info(f"  📋 Data points: {len(structured_data)} entries")
                await ctx.info(f"  🤖 AI selecting optimal chart type...")
            chart_type = "bar"  # Default
            if "AOV" in data_type or "Average Order Value" in data_type:
                chart_type = "line"
            elif "user type" in data_type.lower() or "product type" in data_type.lower():
                chart_type = "stacked_bar"
            elif "demographic" in data_type.lower() or "percentage" in data_type.lower():
                chart_type = "pie"
            elif "user type" in data_type.lower():
                chart_type = "stacked_bar"

            # Chart-specific labeling instructions
            labeling_instructions = {
                "bar": (MONTHLY_SALES_PROMPT),
                "stacked_bar": (
                    "- Label each stack segment with its value\n"
                    "- Place labels inside segments if height > 5% of total\n"
                    "- Use white text on dark colors, black on light colors\n"
                    "- Show both absolute values and percentages if space permits"
                ),
                "line": (
                    "- Annotate key data points (first, last, min, max)\n"
                    "- Use markers on the line for each data point\n"
                    "- Add value labels with slight offset to avoid line overlap\n"
                    "- Include trend indicators (arrows) for significant changes"
                ),
                "pie": (
                    "- Show percentage and absolute value: '52% (€123K)'\n"
                    "- Use autopct='%1.1f%%' for percentages\n"
                    "- Add a legend with full category names if labels are truncated\n"
                    "- Explode small slices (<5%) for visibility"
                ),
            }

            # 2) build a concise instruction (no code; the tool handles codegen)
            # Keep it deterministic: require chart_output.png at 300 DPI.
            instruction = STRUCTURED_CHART_SCHEMA_PROMPT.format(
                alfred_data_description=paragraph, data=structured_data
            ) + (
                "Create a clean, publication-quality Matplotlib chart from the data below.\n"
                "Do NOT call plt.show(). Save the figure exactly as 'chart_output.png' at 300 DPI.\n"
                "Use readable axis labels; include a legend if multiple series exist.\n\n"
                f"CHART TYPE: {chart_type}\n"
                "DATA LABELING REQUIREMENTS:\n"
                f"{labeling_instructions.get(chart_type, labeling_instructions['bar'])}\n\n"
                "General formatting:\n"
                "- Ensure sufficient padding for labels\n§"
                "- Add gridlines for better readability (alpha=0.3)\n\n"
                f"Title: {data_type}\n"
                f"Data (JSON):\n{json.dumps(structured_data, ensure_ascii=False)}\n\n"
                f"Notes: {paragraph or ''}"
                f"{' Total variations: ' + json.dumps(total_variations) if total_variations else ''}"
            )
            print(f"\n[DEBUG] MatPlot instruction for '{data_type}':\n{instruction}\n")
            entry["matplot_instruction"] = instruction

            # 3) call the tool directly (no planner in the middle)
            if ctx:
                await ctx.info(f"  🎯 Executing MatPlot generation...")
                
            args = {
                "instruction": instruction,
                "chart_type": "auto",
                "model_type": model_type,
                "workspace_name": "chart_generation",
            }
            try:
                try:
                    tool_result = await tool.ainvoke(args)  # some wrappers expect a single dict
                    print("TOOL RESULT:", tool_result)
                except TypeError:
                    tool_result = await tool.ainvoke(**args)  # others expect kwargs
                    
                if ctx:
                    await ctx.info(f"  ✅ Chart generated successfully")
            except Exception as e:
                if ctx:
                    await ctx.error(f"  ❌ Chart generation failed for {data_type}: {str(e)}")
                entry["errors"].append(f"MatPlotAgent tool invocation failed: {e}")
                entry["chart_path"] = None
                return data_type, entry

            tool_result = _to_dict(tool_result)
            entry["matplot_raw"] = tool_result  # keep for debugging

            # 4) recover/ensure chart_path
            returned_path = tool_result.get("chart_path")

            print(f"[DEBUG] Initial chart_path from tool: {returned_path}")
            print(f"[DEBUG] Tool result keys: {list(tool_result.keys())}")

            # 4a) If missing, scan workspace for any PNG (filename drift)
            if not returned_path:
                ws = tool_result.get("workspace_path")
                print(f"[DEBUG] Workspace path: {ws}")

                if isinstance(ws, str) and os.path.isdir(ws):
                    try:
                        all_files = os.listdir(ws)
                        pngs = [os.path.join(ws, f) for f in all_files if f.lower().endswith(".png")]
                        print(f"[DEBUG] All files in workspace: {all_files}")
                        print(f"[DEBUG] PNG files found: {[os.path.basename(p) for p in pngs]}")

                        if pngs:
                            latest_png = max(pngs, key=os.path.getmtime)
                            returned_path = latest_png
                            tool_result["chart_path"] = returned_path
                            print(f"[DEBUG] Using latest PNG: {os.path.basename(latest_png)}")
                    except Exception as e:
                        print(f"[DEBUG] Workspace scan failed: {e}")
                        entry["errors"].append(f"Workspace scan failed: {e}")
                else:
                    print(f"[DEBUG] No valid workspace directory found")

            # 4b) As a last resort, extract a sandbox link from any raw text (debug-only)
            if not returned_path:
                raw = ""
                if isinstance(tool_result.get("raw"), str):
                    raw = tool_result["raw"]
                print(f"[DEBUG] Raw text available: {bool(raw)}")
                if raw:
                    m = re.search(r"(sandbox:/[^\s\)]*\.png)", raw)
                    if m:
                        returned_path = m.group(1)  # not a local file; record only for traceability
                        tool_result["chart_path"] = returned_path
                        entry["errors"].append("Chart path points to a sandbox link (not a local file on this system).")
                        print(f"[DEBUG] Found sandbox link: {returned_path}")

            print(f"[DEBUG] Final returned_path: {returned_path}")

            # 5) persist/copy PNG into ./plots and set entry['chart_path']
            try:
                chart_path = _persist_plot_ref(data_type, returned_path)
                entry["chart_path"] = chart_path
                if chart_path:
                    if ctx:
                        await ctx.info(f"  📁 Chart saved to {chart_path}")
                elif not (isinstance(returned_path, str) and returned_path.startswith("sandbox:")):
                    if ctx:
                        await ctx.warning(f"  ⚠️ No chart file found in MatPlot response")
                    entry["errors"].append("MatPlotAgent did not return a PNG path.")
            except Exception as e:
                if ctx:
                    await ctx.error(f"  ❌ Failed to save chart for {data_type}: {str(e)}")
                entry["chart_path"] = None
                entry["errors"].append(f"Persist plot failed: {e}")

        except Exception as e:
            if ctx:
                await ctx.error(f"  ❌ Chart pipeline failed for {data_type}: {str(e)}")
            entry["errors"].append(f"Matplotlib pipeline failed: {e}")
            
        return data_type, entry

    # Execute all chart generation concurrently
    import asyncio
    tasks = []
    for i, data_type in enumerate(valid_entries, 1):
        entry = results_dict[data_type]
        tasks.append(process_single_chart(data_type, entry, i))
    
    if tasks:
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update results with concurrent outputs
        for result in completed_results:
            if isinstance(result, Exception):
                # Log the exception but continue processing other results
                print(f"[ERROR] Chart generation task failed: {result}")
                if ctx:
                    await ctx.error(f"❌ Chart generation task failed: {str(result)}")
                continue
            data_type, updated_entry = result
            results_dict[data_type] = updated_entry

    if ctx:
        successful_charts = len([v for v in results_dict.values() if isinstance(v, dict) and v.get("chart_path") and not v.get("errors")])
        total_charts = len([k for k, v in results_dict.items() if isinstance(v, dict) and v.get("structured_data")])
        await ctx.info(f"🎯 Chart generation complete: {successful_charts}/{total_charts} successful")

    return results_dict
