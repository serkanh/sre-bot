"""
SRE Agent - Main agent for Site Reliability Engineering tasks.

Clean and simple agent definition with sub-agent delegation.
"""

import os
from google.adk.agents import Agent

# Import sub-agent packages (not internal tools)
from .sub_agents.aws_cost.agent import create_aws_cost_agent
from .utils import get_logger

# Configure logging
logger = get_logger(__name__)


def _get_model():
    """Get the configured model from environment variables."""
    return os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")


def _create_root_agent():
    """Create the main SRE agent with sub-agents."""
    # Create sub-agents
    aws_cost_agent = create_aws_cost_agent()

    # Create main SRE agent
    return Agent(
        name="sre_agent",
        model=_get_model(),
        instruction="""You are an expert Site Reliability Engineer (SRE) assistant specializing in operational tasks,
infrastructure management, and cost optimization.

Your primary responsibilities include:
- AWS cost analysis and optimization (delegate to aws_cost_agent)
- Infrastructure monitoring and troubleshooting
- Operational best practices and recommendations
- Performance optimization guidance

You can delegate AWS cost-related queries to your specialized aws_cost_agent sub-agent using transfer_to_agent(agent_name='aws_cost_agent').
For AWS cost questions, queries about spending, budget analysis, or cost optimization, always transfer to the aws_cost_agent.

Provide practical, actionable advice based on industry best practices for all SRE and DevOps tasks.""",
        description="A comprehensive SRE assistant for operational tasks, infrastructure management, and AWS cost optimization with specialized sub-agents.",
        sub_agents=[aws_cost_agent] if aws_cost_agent else [],
    )


# Main entrypoint for ADK
root_agent = _create_root_agent()
