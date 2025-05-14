from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .kube_agent import kubernetes_agent
from .aws_mcps import get_aws_core_mcp, get_aws_cost_analysis_mcp
from .aws_cost_agent import get_aws_cost_agent
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from .settings import DB_URL
import logging
from google.adk.runners import Runner
import functools
import traceback

# Import our custom JSON encoder patch
from .json_utils import *


# Error handling decorator for telemetry errors
def handle_telemetry_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TypeError as e:
            if "not JSON serializable" in str(e):
                logging.warning(f"Telemetry serialization error: {e}")
                # Continue execution without telemetry
                return None
            raise
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}")
            logging.error(traceback.format_exc())
            raise

    return wrapper


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    session_service = DatabaseSessionService(db_url=DB_URL)
    logger.info(f"Successfully connected to database at {DB_URL}")
except Exception as e:
    logger.error(f"Could not connect to database: {e}", exc_info=True)
    logger.warning("Falling back to in-memory session service.")
    session_service = InMemorySessionService()


async def create_root_agent():
    k8s_agent, exit_stack = await kubernetes_agent()
    aws_core_mcp_agent, exit_stack = await get_aws_core_mcp()
    aws_cost_analysis_mcp_agent, exit_stack = await get_aws_cost_analysis_mcp()
    aws_cost_agent, exit_stack = await get_aws_cost_agent()
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
        - aws_cost_agent: for AWS Cost Analysis
        """,
        sub_agents=[
            k8s_agent,
            aws_core_mcp_agent,
            aws_cost_analysis_mcp_agent,
            aws_cost_agent,
        ],
    )

    return agent, exit_stack


async def get_root_agent():
    return await create_root_agent()


# This is what the CLI looks for
root_agent = get_root_agent()


# Initialize runner for the CLI
@handle_telemetry_errors
async def get_runner():
    agent, exit_stack = await get_root_agent()
    logger.info("Creating runner with session service")
    return Runner(agent=agent, app_name="sre_agent", session_service=session_service)


# Don't call async function directly, just expose it for ADK to await properly
runner = get_runner  # Note: without parentheses, just the function reference
