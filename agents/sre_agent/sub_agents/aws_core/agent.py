"""
AWS Core Agent - General AWS operations sub-agent.

Provides general AWS infrastructure management and monitoring capabilities
using role-based authentication for cross-account access.
"""

import os
from google.adk.agents import Agent
from contextlib import AsyncExitStack
from ...utils import load_instruction_from_file, get_logger, get_configured_model

# Configure logging
logger = get_logger(__name__)


def create_aws_core_agent():
    """
    Create AWS Core Operations agent (sync version for ADK).

    Returns:
        Agent: Configured AWS core agent or None if creation fails
    """
    try:
        from .tools.aws_core_tools import (
            get_caller_identity,
            list_s3_buckets,
            list_ec2_instances,
            list_rds_instances,
            get_aws_regions,
            get_account_summary,
            test_aws_connectivity,
        )

        current_dir = os.path.dirname(os.path.abspath(__file__))

        return Agent(
            name="aws_core_agent",
            model=get_configured_model(),
            description="Specialized agent for general AWS infrastructure operations and cross-account management. Handles EC2, S3, RDS discovery, account summaries, and connectivity testing.",
            instruction=load_instruction_from_file(
                os.path.join(current_dir, "prompts", "aws_core_agent_system_prompt.md")
            ),
            tools=[
                get_caller_identity,
                list_s3_buckets,
                list_ec2_instances,
                list_rds_instances,
                get_aws_regions,
                get_account_summary,
                test_aws_connectivity,
            ],
        )
    except Exception as e:
        logger.warning(f"Failed to create AWS core agent: {e}")
        return None


async def get_aws_core_agent():
    """
    Create AWS Core Operations agent (async version for backward compatibility).

    Returns:
        Agent: Configured AWS core agent
        AsyncExitStack: Exit stack for cleanup
    """
    exit_stack = AsyncExitStack()

    try:
        agent = create_aws_core_agent()
        if agent is None:
            raise Exception("Failed to create AWS core agent")

        return agent, exit_stack

    except Exception as e:
        await exit_stack.aclose()
        raise Exception(f"Failed to create AWS core agent: {e}")
