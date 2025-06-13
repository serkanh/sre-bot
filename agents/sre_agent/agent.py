from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .kube_agent import kubernetes_agent
# from .aws_mcps import get_aws_core_mcp, get_aws_cost_analysis_mcp
from .aws_cost_agent import get_aws_cost_agent
from google.adk.sessions import DatabaseSessionService
from .settings import DB_URL
import logging
import os
import asyncio
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

# Initialize session service
session_service = DatabaseSessionService(db_url=DB_URL)
logger.info(f"Connected to database at {DB_URL}")

async def create_root_agent():
    """Create the root agent with its sub-agents."""
    logger.info("Creating root agent and its sub-agents...")
    
    # Initialize sub-agents
    k8s_agent, _ = await kubernetes_agent()
    # aws_core_mcp_agent, _ = await get_aws_core_mcp()
    # aws_cost_analysis_mcp_agent, _ = await get_aws_cost_analysis_mcp()
    aws_cost_agent, _ = await get_aws_cost_agent()

    # Create root agent
    agent = Agent(
        name="root_agent",
        model=LiteLlm(
            model="bedrock/arn:aws:bedrock:us-west-2:812201244513:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
        ),
        description="An assistant that can help you with your Kubernetes cluster and AWS Cost Analysis",
        instruction="""
        You are an helpful assistant who tries to understand the user's request and delegates it to the most appropriate sub agent.
        Here are the sub agents available:
        - kubernetes_agent: for Kubernetes related queries
        - aws_core_mcp_agent: Core mcp server for AWS related queries
        - aws_cost_analysis_mcp_agent: Cost analysis mcp server for AWS Cost Analysis
        - aws_cost_agent: for AWS Cost Analysis
        """,
        sub_agents=[
            k8s_agent,
            # aws_core_mcp_agent,
            # aws_cost_analysis_mcp_agent,
            aws_cost_agent,
        ],
    )
    logger.info("Root agent created successfully")
    return agent

# Create root agent synchronously
loop = asyncio.get_event_loop()
root_agent = loop.run_until_complete(create_root_agent())

# Initialize runner for the CLI
async def get_runner():
    """Get the runner instance for the CLI."""
    from google.adk.runners import Runner
    return Runner(
        agent=root_agent,
        app_name="sre_agent",
        session_service=session_service
    )

# Expose runner for ADK
runner = get_runner
