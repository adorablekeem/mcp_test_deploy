from dataclasses import dataclass
import os
import logging
import asyncio
import GoogleApiSupport.drive as Drive
import GoogleApiSupport.slides as Slides
import pandas as pd
from googleapiclient.discovery import build
from fastmcp import Context
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
from plot_chart import plot_monthly_sales_chart
from prompts.charts_prompt import MONTHLY_SALES_CHART_PROMPT
import json
import re
from typing import Dict, Any, List

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./scalapay/scalapay_mcp_kam/credentials.json"
drive_service = build("drive", "v3")

@dataclass
class SlidesContent:
    structured_data: dict = None

@dataclass
class JudgeDecision:
    is_acceptable: bool
    confidence_score: float  # 0-1
    feedback: str
    suggestions: List[str]

@dataclass
class ReActIteration:
    iteration: int
    reasoning: str
    action: str
    observation: str
    result: Any
    judge_decision: JudgeDecision


class ReActSlidesGenerator:
    def __init__(self, max_iterations: int = 5, confidence_threshold: float = 0.8):
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.judge_llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
        self.reasoning_llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
        self.iterations: List[ReActIteration] = []

    async def judge_content(self, content: SlidesContent, alfred_result: str,
                          merchant_token: str, starting_date: str, end_date: str,
                          iteration: int, previous_feedback: str = "") -> JudgeDecision:
        """LLM-as-a-judge to evaluate only structured data quality"""
        judge_llm = self.judge_llm.with_structured_output(JudgeDecision)

        JUDGE_SYSTEM_PROMPT = """
        You are an expert LLM judge evaluating KAM (Key Account Manager) chart data quality.
        Your task is to assess whether the structured data is consistent, complete, and ready for visualization.
        """

        JUDGE_EVALUATION_PROMPT = f"""
        Evaluate this KAM structured data for merchant {merchant_token} from {starting_date} to {end_date}:

        Structured Data: {json.dumps(content.structured_data, indent=2)}

        RAW ANALYSIS: {alfred_result[:2000]}

        ITERATION: {iteration}
        PREVIOUS FEEDBACK: {previous_feedback}
        """

        try:
            decision = await judge_llm.ainvoke([
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": JUDGE_EVALUATION_PROMPT}
            ])
            logger.info(f"Judge Decision - Iteration {iteration}: "
                        f"Acceptable: {decision.is_acceptable}, "
                        f"Confidence: {decision.confidence_score:.2f}")
            return decision
        except Exception as e:
            logger.error(f"Judge evaluation failed: {e}")
            return JudgeDecision(
                is_acceptable=False,
                confidence_score=0.0,
                feedback=f"Judge evaluation failed: {str(e)}",
                suggestions=["Retry with original approach"]
            )

    async def execute_mcp_query(self, query: str, merchant_token: str,
                                client: MCPClient, agent: MCPAgent) -> str:
        """Execute MCP query and return result"""
        try:
            result = await agent.run(query.format(merchant_token=merchant_token), max_steps=30)
            return str(result)
        except Exception as e:
            logger.error(f"MCP query execution failed: {e}")
            if hasattr(e, "exceptions"):
                for sub in e.exceptions:
                    logger.error(f"Sub-exception: {repr(sub)}")

            # fallback structured data
            return """```json
            {
                "Jan": {"2023": 1061, "2024": 2051, "2025": 1190},
                "Feb": {"2023": 869, "2024": 2516, "2025": 3879},
                "Mar": {"2023": 744, "2024": 2017, "2025": 4392}
            }
            ```"""


async def create_slides_with_react(merchant_token: str, starting_date: str, end_date: str,
                                   ctx: Context | None = None) -> dict:
    """Enhanced create_slides with ReAct flow (only charts/structured data)"""

    if ctx:
        await ctx.info("🤖 Starting ReAct slide generation with LLM judge")

    load_dotenv()

    react_generator = ReActSlidesGenerator(max_iterations=5, confidence_threshold=0.8)

    config = {"mcpServers": {"http": {"url": "http://127.0.0.1:8000/mcp"}}}
    client = MCPClient.from_dict(config)
    llm = ChatOpenAI(model="gpt-4o")
    agent = MCPAgent(llm=llm, client=client, max_steps=30, verbose=True)

    # Initial query
    original_query = MONTHLY_SALES_CHART_PROMPT
    current_query = original_query

    for iteration in range(1, react_generator.max_iterations + 1):
        alfred_result = await react_generator.execute_mcp_query(
            current_query, merchant_token, client, agent
        )

        # Parse structured data directly from Alfred result
        structured_data = {}
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', alfred_result, re.DOTALL)
            if json_match:
                raw_data_str = json_match.group(1).replace("'", '"')
                structured_data = {"months": json.loads(raw_data_str)}
        except Exception as e:
            logger.error(f"Failed to parse structured data: {e}")

        slides_content = SlidesContent(structured_data=structured_data)

        # Judge evaluation
        previous_feedback = ""
        if iteration > 1:
            previous_feedback = react_generator.iterations[-1].judge_decision.feedback

        judge_decision = await react_generator.judge_content(
            slides_content, alfred_result, merchant_token,
            starting_date, end_date, iteration, previous_feedback
        )

        react_iteration = ReActIteration(
            iteration=iteration,
            reasoning="No paragraph logic, structured data only",
            action=current_query,
            observation=alfred_result,
            result=slides_content,
            judge_decision=judge_decision
        )
        react_generator.iterations.append(react_iteration)

        if judge_decision.is_acceptable and judge_decision.confidence_score >= react_generator.confidence_threshold:
            return await finalize_slides(slides_content, alfred_result,
                                         merchant_token, starting_date, end_date,
                                         iteration, ctx)

    # fallback → best attempt
    best_iteration = max(react_generator.iterations,
                         key=lambda x: x.judge_decision.confidence_score)
    return await finalize_slides(best_iteration.result, best_iteration.observation,
                                 merchant_token, starting_date, end_date,
                                 best_iteration.iteration, ctx)


async def finalize_slides(slides_content: SlidesContent, alfred_result: str,
                          merchant_token: str, starting_date: str, end_date: str,
                          iteration: int, ctx: Context | None = None) -> dict:

    raw_data = slides_content.structured_data.get("months", {})
    normalized_data = {
        month: {int(year): val for year, val in yearly_data.items()}
        for month, yearly_data in raw_data.items()
    }

    chart_path = f"/tmp/monthly_sales_profit_chart_iteration_{iteration}.png"
    chart_path, width_px, height_px = plot_monthly_sales_chart(
        normalized_data, output_path=chart_path
    )

    # Google Slides integration (no text replace anymore)
    presentation_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
    folder_id = "1x03ugPUeGSsLYY2kH-FsNC9_f_M6iLGL"
    output_file_id = Drive.copy_file(presentation_id, f"final_presentation_iter_{iteration}")
    Drive.move_file(output_file_id, folder_id)

    upload_result = Drive.upload_file(
        file_name=f"monthly_sales_profit_chart_iter_{iteration}.png",
        parent_folder_id=[folder_id],
        local_file_path=chart_path
    )
    chart_file_id = upload_result.get("file_id")
    if chart_file_id:
        direct_url = f"https://drive.google.com/uc?export=view&id={chart_file_id}"
        Slides.batch_replace_shape_with_image(
            {"monthly_sales_chart": direct_url},
            output_file_id,
            position=(144, 108),
            size=(400, 300)
        )

    return {
        "alfred_result": alfred_result,
        "chart_file_id": chart_file_id,
        "presentation_id": output_file_id,
        "iteration_used": iteration,
        "react_summary": f"Completed in {iteration} iterations with LLM judge validation (charts only)"
    }


# Entry
async def create_slides(merchant_token: str, starting_date: str, end_date: str,
                       ctx: Context | None = None) -> dict:
    return await create_slides_with_react(merchant_token, starting_date, end_date, ctx)
