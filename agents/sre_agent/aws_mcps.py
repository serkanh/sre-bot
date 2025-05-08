from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import LlmAgent
import os


async def get_aws_core_mcp():
    """Gets tools from MCP Server."""
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command="uvx",
            args=["awslabs.core-mcp-server@latest"],
            env={
                "AWS_PROFILE": os.getenv("AWS_PROFILE"),
            },
            autoApprove=[],
            disabled=False,
        )
    )

    agent = LlmAgent(
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.deepseek.r1-v1:0"
        ),
        name="aws_core_mcp_agent",
        instruction="AWS Related queries.",
        tools=tools,
    )
    return agent, exit_stack


async def get_aws_cost_analysis_mcp():
    """AWS Cost analysis MCP server to"""
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command="uvx",
            args=["awslabs.cost-analysis-mcp-server@latest"],
            env={
                "AWS_PROFILE": os.getenv("AWS_PROFILE"),
            },
            autoApprove=[],
            disabled=False,
        )
    )

    agent = LlmAgent(
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-east-1:827541288795:inference-profile/us.deepseek.r1-v1:0"
        ),
        name="aws_cost_analysis_mcp_agent",
        instruction="AWS Cost Analysis related queries.",
        tools=tools,
    )
    return agent, exit_stack
