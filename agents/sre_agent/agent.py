"""
SRE Agent - Main agent for Site Reliability Engineering tasks.

Clean and simple agent definition with sub-agent delegation.
"""

from google.adk.agents import Agent

# Import sub-agent packages (not internal tools)
from .sub_agents.aws_cost.agent import create_aws_cost_agent
from .sub_agents.aws_core.agent import create_aws_core_agent
from .utils import get_logger, get_configured_model

# Configure logging
logger = get_logger(__name__)


def _create_root_agent():
    """Create the main SRE agent with sub-agents."""
    # Create sub-agents
    aws_cost_agent = create_aws_cost_agent()
    aws_core_agent = create_aws_core_agent()

    # Create main SRE agent
    return Agent(
        name="sre_agent",
        model=get_configured_model(),
        instruction="""You are an expert Site Reliability Engineer (SRE) assistant specializing in operational tasks,
infrastructure management, and cost optimization.

Your primary responsibilities include:
- AWS cost analysis and optimization (delegate to aws_cost_agent)
- AWS infrastructure management and operations (delegate to aws_core_agent)
- Infrastructure monitoring and troubleshooting
- Operational best practices and recommendations
- Performance optimization guidance

You have two specialized AWS sub-agents:

1. **aws_cost_agent**: For AWS cost analysis, spending queries, budget analysis, and cost optimization
   - Use transfer_to_agent(agent_name='aws_cost_agent') for cost-related questions

2. **aws_core_agent**: For general AWS infrastructure operations, account management, and resource discovery
   - Use transfer_to_agent(agent_name='aws_core_agent') for infrastructure queries, account summaries, resource listings (EC2, S3, RDS), connectivity testing, and cross-account operations

For AWS cost questions, always delegate to aws_cost_agent.
For AWS infrastructure operations, resource discovery, or account management, always delegate to aws_core_agent.

Provide practical, actionable advice based on industry best practices for all SRE and DevOps tasks.""",
        description="A comprehensive SRE assistant for operational tasks, infrastructure management, and AWS cost optimization with specialized sub-agents.",
        sub_agents=[
            agent for agent in [aws_cost_agent, aws_core_agent] if agent is not None
        ],
    )


# Main entrypoint for ADK
root_agent = _create_root_agent()
