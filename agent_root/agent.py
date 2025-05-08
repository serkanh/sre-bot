from google.adk.agents import Agent, LlmAgent
from .tools.kube_tools import *
from google.adk.models.lite_llm import LiteLlm
from .kube_agent import kubernetes_agent
from .aws_mcps import get_aws_core_mcp, get_aws_cost_analysis_mcp


async def create_root_agent():
    k8s_agent, exit_stack = await kubernetes_agent()
    aws_core_mcp_agent, exit_stack = await get_aws_core_mcp()
    aws_cost_analysis_mcp_agent, exit_stack = await get_aws_cost_analysis_mcp()
    agent = Agent(
        name="root_agent",
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        ),
        description="An assistant that can help you with your Kubernetes cluster and AWS Cost Analysis",
        instruction="""
        You are an helpful assistant who tries to understand the user's request and delegates it to the most appropriate sub agent.
        Here are the sub agents available:
        - kubernetes_agent: for Kubernetes related queries
        - aws_core_mcp_agent: Core mcp server for AWS related queries
        - aws_cost_analysis_mcp_agent: Cost analysis mcp server for AWS Cost Analysis
        """,
        sub_agents=[k8s_agent, aws_core_mcp_agent, aws_cost_analysis_mcp_agent],
    )

    return agent, exit_stack


async def get_root_agent():
    return await create_root_agent()


# Don't call create_root_agent directly
root_agent = get_root_agent()
