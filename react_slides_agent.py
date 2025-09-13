#!/usr/bin/env python3
"""
ReAct Slide Creation Agent - MCP Server

A simple ReAct (Reasoning and Acting) agent that orchestrates:
1. Alfred (data retrieval)  
2. MatplotAgent (chart generation)
3. Google Slides tools (slide creation)

This script runs as an MCP server tool that can be called by clients.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# FastMCP for creating MCP server
from fastmcp import Context, FastMCP
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

# Langchain for reasoning
from langchain_openai import ChatOpenAI

# Import the existing tools
from scalapay.scalapay_mcp_kam.agents.agent_alfred_concurrent import mcp_tool_run_with_fallback
from scalapay.scalapay_mcp_kam.agents.agent_matplot_concurrent import mcp_matplot_run_with_fallback
from scalapay.scalapay_mcp_kam.config import get_config
from scalapay.scalapay_mcp_kam.positioning import configure_positioning, fill_template_with_clean_positioning
from scalapay.scalapay_mcp_kam.positioning import health_check as positioning_health_check
from scalapay.scalapay_mcp_kam.prompts.charts_prompt import GENERAL_CHART_PROMPT
from scalapay.scalapay_mcp_kam.utils.concurrency_config import get_concurrency_config

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("react_slides_agent")


@dataclass
class SlideCreationPlan:
    """Plan for slide creation workflow."""

    data_requests: List[str]
    chart_types_needed: List[str]
    reasoning: str
    expected_outputs: List[str]


class ReActSlidesAgent:
    """
    A ReAct agent that reasons about slide creation tasks and acts using available tools.

    The agent follows this pattern:
    1. THOUGHT: Analyze the user request
    2. ACTION: Choose and execute appropriate tool
    3. OBSERVATION: Process tool results
    4. THOUGHT: Decide next steps
    5. Continue until task complete
    """

    def __init__(self, llm_model: str = "gpt-4o"):
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)
        self.config = get_config()
        self.concurrency_config = get_concurrency_config()

        # Initialize clean positioning
        configure_positioning(
            mode="hybrid",
            rollout_percentage=50.0,  # Use clean positioning more frequently
            enable_features={
                "template_discovery": True,
                "batch_operations": True,
                "concurrent_uploads": True,
                "fallback_on_error": True,
            },
            save_config=False,
        )

        # ReAct reasoning prompts
        self.planning_prompt = PromptTemplate(
            input_variables=["user_request", "merchant_token", "date_range"],
            template="""
You are a slide creation planning agent. Analyze the user request and create a plan.

User Request: {user_request}
Merchant Token: {merchant_token}  
Date Range: {date_range}

Based on this request, create a JSON plan with:
1. data_requests: List of specific data queries needed (e.g., "monthly sales year over year", "AOV", etc.)
2. chart_types_needed: Types of charts that would be most effective
3. reasoning: Your thinking about why these queries and charts are needed
4. expected_outputs: What the final slides should contain

Available data request types:
- "monthly sales year over year"
- "monthly sales by product type over time"  
- "monthly orders by user type"
- "AOV" (Average Order Value)
- "scalapay users demographic in percentages"
- "orders by product type (i.e. pay in 3, pay in 4)"
- "AOV by product type (i.e. pay in 3, pay in 4)"

Format your response as valid JSON.
""",
        )

        self.execution_prompt = PromptTemplate(
            input_variables=["plan", "current_step", "available_results", "context"],
            template="""
You are executing a slide creation plan. Decide the next action.

Plan: {plan}
Current Step: {current_step}
Available Results: {available_results}
Context: {context}

Choose your next action:
- "get_data": Use Alfred to retrieve data
- "create_charts": Use MatplotAgent to generate charts  
- "create_slides": Use Google Slides tools to create final presentation
- "complete": Task is finished

Format response as JSON: {{"action": "...", "reasoning": "...", "parameters": {{...}}}}
""",
        )

    async def think_and_plan(self, user_request: str, merchant_token: str, date_range: str) -> SlideCreationPlan:
        """THOUGHT: Analyze request and create execution plan."""

        logger.info(f"🤔 THINKING: Planning slide creation for request: {user_request}")

        try:
            # Use LLM to create a plan
            planning_chain = self.planning_prompt | self.llm | JsonOutputParser()

            plan_result = await planning_chain.ainvoke(
                {"user_request": user_request, "merchant_token": merchant_token, "date_range": date_range}
            )

            plan = SlideCreationPlan(
                data_requests=plan_result.get("data_requests", []),
                chart_types_needed=plan_result.get("chart_types_needed", []),
                reasoning=plan_result.get("reasoning", ""),
                expected_outputs=plan_result.get("expected_outputs", []),
            )

            logger.info(f"📋 PLAN CREATED:")
            logger.info(f"   Data requests: {plan.data_requests}")
            logger.info(f"   Chart types: {plan.chart_types_needed}")
            logger.info(f"   Reasoning: {plan.reasoning}")

            return plan

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Fallback to default plan
            return SlideCreationPlan(
                data_requests=["monthly sales year over year", "AOV", "monthly orders by user type"],
                chart_types_needed=["line", "bar"],
                reasoning="Using default comprehensive business metrics plan",
                expected_outputs=["Sales trends", "Customer insights", "Performance metrics"],
            )

    async def act_get_data(
        self, plan: SlideCreationPlan, merchant_token: str, starting_date: str, end_date: str
    ) -> Dict[str, Any]:
        """ACTION: Execute data retrieval using Alfred."""

        logger.info(f"📊 ACTING: Retrieving data using Alfred")
        logger.info(f"   Requests: {plan.data_requests}")

        try:
            results = await mcp_tool_run_with_fallback(
                requests_list=plan.data_requests,
                merchant_token=merchant_token,
                starting_date=starting_date,
                end_date=end_date,
                chart_prompt_template=GENERAL_CHART_PROMPT,
                use_concurrent=self.concurrency_config.enable_concurrent_data_retrieval,
                batch_size=self.concurrency_config.batch_size,
                max_concurrent_batches=self.concurrency_config.max_concurrent_batches,
            )

            logger.info(f"✅ OBSERVATION: Data retrieved successfully")
            logger.info(f"   Retrieved {len(results)} data sets")

            return results

        except Exception as e:
            logger.error(f"❌ OBSERVATION: Data retrieval failed: {e}")
            raise

    async def act_create_charts(self, data_results: Dict[str, Any]) -> Dict[str, Any]:
        """ACTION: Generate charts using MatplotAgent."""

        logger.info(f"📈 ACTING: Creating charts using MatplotAgent")

        try:
            charts_results = await mcp_matplot_run_with_fallback(
                data_results,
                matplot_url="http://localhost:8010/mcp",
                server_id="MatPlotAgent",
                operation="generate_chart_simple",
                model_type="gpt-4o",
                use_concurrent=self.concurrency_config.enable_concurrent_chart_generation,
                max_concurrent_charts=self.concurrency_config.max_concurrent_charts,
                max_steps=self.concurrency_config.chart_generation_max_steps,
                verbose=True,
                transport="http",
            )

            # Count successful charts
            successful_charts = sum(1 for v in charts_results.values() if isinstance(v, dict) and v.get("chart_path"))

            logger.info(f"✅ OBSERVATION: Charts created successfully")
            logger.info(f"   Generated {successful_charts} charts")

            return charts_results

        except Exception as e:
            logger.error(f"❌ OBSERVATION: Chart creation failed: {e}")
            raise

    async def act_create_slides(self, charts_results: Dict[str, Any]) -> Dict[str, Any]:
        """ACTION: Create slides using Google Slides tools."""

        logger.info(f"🎨 ACTING: Creating slides using Google Slides tools")

        try:
            # Check positioning system health
            positioning_health = positioning_health_check()
            use_clean_positioning = positioning_health["status"] == "healthy"

            if use_clean_positioning:
                logger.info("🎯 Using CLEAN POSITIONING for slide creation")

                # Import required services
                import os

                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager

                # Get services
                slides_service = connection_manager.get_service_sync()

                # Create drive service
                credentials_path = os.getenv(
                    "GOOGLE_APPLICATION_CREDENTIALS", "./scalapay/scalapay_mcp_kam/credentials.json"
                )
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                drive_service = build("drive", "v3", credentials=credentials)

                final_result = await fill_template_with_clean_positioning(
                    drive_service,
                    slides_service,
                    charts_results,
                    template_id=self.config.default_template_id,
                    folder_id=self.config.default_folder_id,
                    verbose=self.config.debug_mode,
                    correlation_id=f"react_agent_{int(time.time())}",
                )

                logger.info(f"✅ OBSERVATION: Slides created with clean positioning")
                logger.info(f"   Presentation ID: {final_result.get('presentation_id', 'Unknown')}")

                return final_result

            else:
                logger.warning("⚠️  Clean positioning not available, using legacy method")
                # Could implement legacy fallback here
                raise Exception("Legacy slide creation not implemented in ReAct agent")

        except Exception as e:
            logger.error(f"❌ OBSERVATION: Slide creation failed: {e}")
            raise

    async def execute_plan(
        self,
        plan: SlideCreationPlan,
        merchant_token: str,
        starting_date: str,
        end_date: str,
        ctx: Optional[Context] = None,
    ) -> Dict[str, Any]:
        """Execute the complete slide creation workflow."""

        logger.info("🚀 EXECUTING: Starting slide creation workflow")

        workflow_start_time = time.time()
        results = {
            "plan": {
                "data_requests": plan.data_requests,
                "chart_types_needed": plan.chart_types_needed,
                "reasoning": plan.reasoning,
            },
            "steps": [],
            "success": False,
        }

        try:
            # Step 1: Get Data
            if ctx:
                await ctx.info("📊 Step 1: Retrieving business data...")

            step_start = time.time()
            data_results = await self.act_get_data(plan, merchant_token, starting_date, end_date)
            step_time = time.time() - step_start

            results["steps"].append(
                {"step": "data_retrieval", "duration": step_time, "success": True, "data_sets": len(data_results)}
            )

            # Step 2: Create Charts
            if ctx:
                await ctx.info("📈 Step 2: Generating charts...")

            step_start = time.time()
            charts_results = await self.act_create_charts(data_results)
            step_time = time.time() - step_start

            successful_charts = sum(1 for v in charts_results.values() if isinstance(v, dict) and v.get("chart_path"))

            results["steps"].append(
                {
                    "step": "chart_generation",
                    "duration": step_time,
                    "success": True,
                    "charts_created": successful_charts,
                }
            )

            # Step 3: Create Slides
            if ctx:
                await ctx.info("🎨 Step 3: Creating presentation...")

            step_start = time.time()
            slides_result = await self.act_create_slides(charts_results)
            step_time = time.time() - step_start

            results["steps"].append(
                {
                    "step": "slide_creation",
                    "duration": step_time,
                    "success": True,
                    "presentation_id": slides_result.get("presentation_id"),
                }
            )

            # Final results
            total_time = time.time() - workflow_start_time
            results.update(
                {
                    "success": True,
                    "total_duration": total_time,
                    "presentation_id": slides_result.get("presentation_id"),
                    "final_result": slides_result,
                }
            )

            logger.info(f"🎉 COMPLETE: Slide creation successful in {total_time:.2f}s")
            if ctx:
                await ctx.info(
                    f"✅ Presentation created successfully! ID: {slides_result.get('presentation_id', 'Unknown')}"
                )

            return results

        except Exception as e:
            error_time = time.time() - workflow_start_time
            results.update({"success": False, "error": str(e), "total_duration": error_time})

            logger.error(f"❌ FAILED: Slide creation failed after {error_time:.2f}s: {e}")
            if ctx:
                await ctx.error(f"❌ Slide creation failed: {str(e)}")

            raise


# Create FastMCP server
mcp = FastMCP("ReAct Slides Agent")


@mcp.tool()
async def create_slides_with_react(
    user_request: str, merchant_token: str, starting_date: str, end_date: str, ctx: Context
) -> dict:
    """
    Create slides using ReAct agent that orchestrates Alfred, MatplotAgent, and Google Slides tools.

    This tool uses a reasoning-and-acting approach to:
    1. Analyze the user request and plan the workflow
    2. Retrieve data using Alfred (MCP tool)
    3. Generate charts using MatplotAgent (MCP tool)
    4. Create slides using Google Slides positioning system

    Args:
        user_request: Description of what slides to create (e.g., "Create a business performance report")
        merchant_token: Scalapay merchant identifier
        starting_date: Start date for data analysis (YYYY-MM-DD)
        end_date: End date for data analysis (YYYY-MM-DD)
        ctx: MCP context for progress updates

    Returns:
        dict: Results including presentation_id, performance metrics, and workflow details
    """

    agent = ReActSlidesAgent()

    try:
        await ctx.info(f"🤖 ReAct Agent starting slide creation")
        await ctx.info(f"📝 Request: {user_request}")
        await ctx.info(f"📅 Date range: {starting_date} to {end_date}")

        # THINK: Create plan
        plan = await agent.think_and_plan(user_request, merchant_token, f"{starting_date} to {end_date}")

        await ctx.info(f"📋 Plan created with {len(plan.data_requests)} data requests")

        # ACT: Execute plan
        results = await agent.execute_plan(plan, merchant_token, starting_date, end_date, ctx)

        return results

    except Exception as e:
        error_msg = f"ReAct agent failed: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg, "agent_type": "react_slides_agent"}


@mcp.tool()
async def get_positioning_system_status(ctx: Context) -> dict:
    """Get the current status of the clean positioning system."""

    try:
        from scalapay.scalapay_mcp_kam.positioning import get_positioning_status, health_check

        status = get_positioning_status()
        health = health_check()

        await ctx.info(f"Positioning system status: {health['status']}")

        return {"positioning_status": status, "health_check": health, "success": True}

    except Exception as e:
        error_msg = f"Failed to get positioning status: {str(e)}"
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}


if __name__ == "__main__":
    # Run the MCP server
    print("🚀 Starting ReAct Slides Agent MCP Server")
    print("📡 Available tools:")
    print("   • create_slides_with_react - Main slide creation tool")
    print("   • get_positioning_system_status - Check system health")
    print()
    print("🌐 Server will be available at: http://localhost:8020/mcp")

    # Use FastMCP's built-in run method with HTTP transport
    mcp.run(transport="http", port=8020)
