from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from contextlib import AsyncExitStack
from .tools.aws_cost_tools import *
import os
from .utils import load_instruction_from_file


async def get_aws_cost_agent():
    exit_stack = AsyncExitStack()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    agent = Agent(
        name="aws_cost_agent",
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        ),
        instruction=load_instruction_from_file(
            os.path.join(current_dir, "prompts", "aws_cost_agent_system_prompt.md")
        ),
        description="An assistant agent to identify cost anomalies and inefficiencies in the AWS environment.",
        tools=[
            get_cost_for_period,
            get_monthly_cost,
            get_cost_excluding_services,
            get_cost_trend,
            get_current_month_cost_excluding_days,
            get_average_daily_cost,
            get_weekend_daily_cost,
            get_weekday_daily_cost,
            get_most_expensive_account,
            get_cost_by_service,
            get_cost_by_tag,
            get_digital_cost_for_month,
            get_current_date_info,
            get_current_month_cost,
            get_previous_month_cost,
            get_last_n_months_trend,
        ],
        output_key="aws_cost_agent_output",
    )
    return agent, exit_stack
