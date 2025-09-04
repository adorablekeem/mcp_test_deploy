from prompts.charts_prompt import SLIDES_GENERATION_PROMPT
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
import logging
from dataclasses import dataclass
from tools.chart_utils import _extract_months_map, _normalize_months_map
import os
import re
import json
from typing import List, Dict, Any

@dataclass
class SlidesContent:
    paragraph: str = ""
    structured_data: dict = None
    total_variations: dict = None

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "chart"

# 1) Pure prompt formatter
def format_chart_prompt(tpl: str, *, data_type: str, merchant_token: str, starting_date: str, end_date: str) -> str:
    return tpl.format(
        data_type=data_type,
        merchant_token=merchant_token,
        starting_date=starting_date,
        end_date=end_date,
    )

# 2) Alfred runner for one request
async def run_alfred_for_request(agent, chart_prompt: str) -> Any:
    return await agent.run(chart_prompt, max_steps=30)

# 3) Persist raw artifact (optional)
def persist_raw_result(data_type: str, alfred_result: Any, outdir: str = "./tmp") -> None:
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"alfred_result__{_slug(data_type)}.txt")
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(alfred_result, (dict, list)):
            json.dump(alfred_result, f, ensure_ascii=False, indent=2)
        else:
            f.write(str(alfred_result))

# 4) Slides struct builder (separate LLM)
async def build_slides_struct(llm_struct, alfred_result: Any) -> dict | None:
    resp = await llm_struct.ainvoke(SLIDES_GENERATION_PROMPT.format(alfred_result=alfred_result))
    if hasattr(resp, "dict"): return resp.dict()
    if isinstance(resp, dict): return resp
    return json.loads(json.dumps(resp, default=str))

# 5) Months extraction + normalization (pure function)
def derive_normalized_months(slides_struct: dict | None, alfred_result: Any) -> tuple[dict, dict]:
    resp_months = {}
    if isinstance(slides_struct, dict):
        sd = slides_struct.get("structured_data") or {}
        if isinstance(sd, dict) and ("months" in sd):
            resp_months = sd.get("months") or {}
        elif isinstance(sd, dict):
            if any(k[:3].lower() in ("jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec") for k in sd.keys()):
                resp_months = sd
    raw_months = _extract_months_map(alfred_result)
    months_map = resp_months if resp_months else raw_months
    normalized = _normalize_months_map(months_map)
    return months_map, normalized

# 6) Orchestrator (now very thin)
async def mcp_tool_run(
    requests_list: List[str],
    merchant_token: str,
    starting_date: str,
    end_date: str,
    chart_prompt_template: str,
    *,
    client: MCPClient | None = None,
    llm: ChatOpenAI | None = None,
) -> Dict[str, Any]:
    client = client or MCPClient.from_dict({"mcpServers": {"http": {"url": "http://127.0.0.1:8000/mcp"}}})
    llm = llm or ChatOpenAI(model="gpt-4o")
    agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)
    llm_struct = llm.with_structured_output(SlidesContent)

    results: Dict[str, Any] = {}

    for data_type in requests_list:
        entry = results.setdefault(data_type, {"errors": []})
        try:
            EXPECTED_SCHEMAS = {
                    "monthly sales over time": """
                Return JSON with this schema:
                {
                "structured_data": {
                    "Jan": {"2022": 34, "2023": 66, "2024": 38},
                    "Feb": {"2022": 31, "2023": 87, "2024": 139},
                    ...
                },
                "paragraph": "Analysis..."
                }
                """,
                    "monthly orders by user type": """
                Return JSON with this schema:
                {
                "structured_data": {
                    "Oct-22": {"Network": 162, "Returning": 18, "New": 6},
                    "Nov-22": {"Network": 186, "Returning": 31, "New": 9},
                    ...
                },
                "paragraph": "Analysis..."
                }
                """,
                    "scalapay users demographic": """
                Return JSON with this schema:
                {
                "structured_data": {
                    "Age in percentages": {
                    "18-24": 2,
                    "25-34": 6,
                    "35-44": 31,
                    "45-54": 45,
                    "55-64": 16
                    },
                    "Gender in percentages": {
                    "M": 3,
                    "F": 97
                    },
                    "Card type in percentages": {
                    "credit": 39,
                    "debit": 26,
                    "prepaid": 35
                    }
                },
                "paragraph": "Analysis..."
                }
                """
            }

            prompt = format_chart_prompt(
                chart_prompt_template,
                data_type=data_type,
                merchant_token=merchant_token,
                starting_date=starting_date,
                end_date=end_date,
            )

            # enforce schema instructions
            if data_type in EXPECTED_SCHEMAS:
                prompt += "\n\n" + EXPECTED_SCHEMAS[data_type]
                
        except KeyError as e:
            entry["errors"].append(f"Prompt format error: missing key {e}")
            continue

        try:
            alfred_result = await run_alfred_for_request(agent, prompt)
            entry["alfred_raw"] = alfred_result
            persist_raw_result(data_type, alfred_result)
        except Exception as e:
            entry["errors"].append(f"Agent run failed: {e}")
            continue

        try:
            slides_struct = await build_slides_struct(llm_struct, alfred_result)
            entry["slides_struct"] = slides_struct
        except Exception as e:
            entry["errors"].append(f"LLM invocation for slides failed: {e}")
            slides_struct = None

    return results
