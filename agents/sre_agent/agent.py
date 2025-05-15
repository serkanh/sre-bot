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
from typing import Dict, Any

# Import our custom JSON encoder patch
from .json_utils import *

# This will print DEBUG, INFO, WARNING, ERROR, and CRITICAL logs
# DEBUG is the lowest level, so all higher levels will be printed as well
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants for session management
APP_NAME = "sre_agent"
USER_ID = "test_user"  # Match the existing session in the database


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


def initialize_state() -> Dict[str, Any]:
    """Initialize the default state for new sessions."""
    return {"conversations": [], "context": {}, "preferences": {}}


try:
    session_service = DatabaseSessionService(db_url=DB_URL)
    logger.info(f"Successfully connected to database at {DB_URL}")
except Exception as e:
    logger.error(f"Could not connect to database: {e}", exc_info=True)
    logger.warning("Falling back to in-memory session service.")
    session_service = InMemorySessionService()


async def get_or_create_session():
    """
    Get an existing session or create a new one if none exists.

    Returns:
        str: Session ID for the current session
    """
    try:
        logger.critical(f"DEBUG: get_or_create_session called")
        logger.critical(
            f"Checking for existing sessions for app_name={APP_NAME}, user_id={USER_ID}"
        )
        # Check for existing sessions for this user
        existing_sessions = session_service.list_sessions(
            app_name=APP_NAME,
            user_id=USER_ID,
        )

        logger.info(
            f"Found {len(existing_sessions.sessions) if existing_sessions else 0} existing sessions"
        )

        # If there's an existing session, use it, otherwise create a new one
        if existing_sessions and len(existing_sessions.sessions) > 0:
            # Use the most recent session
            session_id = existing_sessions.sessions[0].id
            logger.info(f"Continuing existing session: {session_id}")

            # Log all sessions for debugging
            for i, session in enumerate(existing_sessions.sessions):
                logger.info(
                    f"Session {i}: id={session.id}, create_time={session.create_time}"
                )

            return session_id
        else:
            # Create a new session with initial state
            initial_state = initialize_state()
            logger.info(f"Creating new session with initial state: {initial_state}")

            new_session = session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                state=initial_state,
            )
            logger.info(f"Created new session: {new_session.id}")
            return new_session.id
    except Exception as e:
        logger.error(f"Error getting or creating session: {e}", exc_info=True)
        raise


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

    # Get or create a session
    session_id = await get_or_create_session()
    logger.info(f"Using session: {session_id}")

    # Return runner with the session service
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    logger.info(
        f"Runner created with app_name: {APP_NAME}, user_id: {USER_ID}, session_id: {session_id}"
    )
    return runner


# Don't call async function directly, just expose it for ADK to await properly
runner = get_runner  # Note: without parentheses, just the function reference
