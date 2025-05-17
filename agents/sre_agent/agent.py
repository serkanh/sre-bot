from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .kube_agent import kubernetes_agent
from .aws_mcps import get_aws_core_mcp, get_aws_cost_analysis_mcp
from .aws_cost_agent import get_aws_cost_agent
from google.adk.sessions import DatabaseSessionService, InMemorySessionService
from .settings import DB_URL
import logging
import os
from google.adk.runners import Runner
import functools
import traceback
from typing import Dict, Any

# Import our custom JSON encoder patch
from .json_utils import *

# Determine log level from environment variable or default to INFO
log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
numeric_log_level = getattr(logging, log_level_name, logging.INFO)

# Configure logging
logging.basicConfig(
    level=numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

# Explicitly set levels to be certain
logging.getLogger().setLevel(numeric_log_level)  # Set root logger level
logger.setLevel(numeric_log_level)  # Set sre_agent.agent logger level

logger.info(
    f"Logging initialized. Effective level: {logging.getLevelName(logger.getEffectiveLevel())}"
)

# Constants for session management
APP_NAME = "sre_agent"
USER_ID = "test_user"  # Default for agent.py contexts (e.g., __main__ or runner init log). API requests will use user_id from their payload.
logger.info(
    f"Default USER_ID for agent.py contexts: '{USER_ID}'. API requests will use user_id from their payload if provided."
)


# Error handling decorator for telemetry errors
def handle_telemetry_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TypeError as e:
            if "not JSON serializable" in str(e):
                logging.warning(
                    f"Telemetry serialization error: {e} in {func.__name__}"
                )
                # Continue execution without telemetry
                return (
                    None  # Or some default error value if the function expects a return
                )
            # Reraise other TypeErrors or handle them as needed
            logging.error(f"TypeError in {func.__name__}: {e}", exc_info=True)
            raise
        except Exception as e:
            # Log the specific function name where the error occurred
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            # traceback.format_exc() is automatically included by exc_info=True
            raise  # Reraise the exception after logging

    return wrapper


def initialize_state() -> Dict[str, Any]:
    """Initialize the default state for new sessions."""
    return {"conversations": [], "context": {}, "preferences": {}}


try:
    # Attempt to connect to the database
    session_service = DatabaseSessionService(db_url=DB_URL)
    logger.info(f"Successfully connected to database at {DB_URL}")
except Exception as e:
    # Log the error and fall back to in-memory session service
    logger.error(f"Could not connect to database: {e}", exc_info=True)
    logger.warning("Falling back to in-memory session service.")
    session_service = InMemorySessionService()


async def get_or_create_session():
    """
    Get an existing session or create a new one if none exists.

    Returns:
        str: Session ID for the current session
    """
    logger.debug(
        f"Attempting to get or create session for app_name='{APP_NAME}', user_id='{USER_ID}'"
    )
    try:
        existing_sessions = session_service.list_sessions(
            app_name=APP_NAME,
            user_id=USER_ID,
        )

        found_sessions_count = (
            len(existing_sessions.sessions)
            if existing_sessions and existing_sessions.sessions
            else 0
        )
        logger.info(f"Found {found_sessions_count} existing sessions.")

        if found_sessions_count > 0:
            session_id = existing_sessions.sessions[0].id
            logger.info(f"Continuing existing session: {session_id}")
            for i, session in enumerate(existing_sessions.sessions):
                logger.debug(
                    f"Existing Session {i}: id={session.id}, create_time={session.create_time}"
                )
            return session_id
        else:
            logger.info("No existing session found. Creating a new session.")
            initial_state = initialize_state()
            logger.debug(f"Initial state for new session: {initial_state}")

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
    logger.debug("Creating root agent and its sub-agents...")
    k8s_agent, k8s_exit_stack = await kubernetes_agent()
    aws_core_mcp_agent, aws_core_exit_stack = await get_aws_core_mcp()
    aws_cost_analysis_mcp_agent, aws_cost_exit_stack = await get_aws_cost_analysis_mcp()
    aws_cost_agent, aws_cost_exit_stack = await get_aws_cost_agent()
    # TODO: Properly handle multiple exit_stacks if they need individual management.
    # For now, assuming the last one assigned is what might be used or they are managed internally by ADK.
    # If specific cleanup is needed for each, they should be collected and returned.
    exit_stack = (
        aws_cost_exit_stack  # Placeholder for combined exit_stack logic if needed
    )

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
    logger.info("Root agent created successfully.")
    return agent, exit_stack


async def get_root_agent():
    logger.debug("Getting root agent...")
    return await create_root_agent()


# This is what the CLI looks for
root_agent = get_root_agent()


# Initialize runner for the CLI
@handle_telemetry_errors
async def get_runner():
    logger.info("Initializing SRE Bot Runner...")
    agent, exit_stack = await get_root_agent()
    logger.debug("Root agent obtained for runner.")

    session_id = await get_or_create_session()
    logger.debug(f"Session ID for runner: {session_id}")

    runner_instance = Runner(
        agent=agent, app_name=APP_NAME, session_service=session_service
    )
    logger.info(
        f"Runner created: app_name='{APP_NAME}', user_id='{USER_ID}', session_id='{session_id}'"
    )
    # Note: exit_stack from create_root_agent is not currently returned or used by this get_runner.
    # If cleanup is needed, ensure exit_stack is propagated and handled.
    return runner_instance


# Don't call async function directly, just expose it for ADK to await properly
runner = get_runner  # Note: without parentheses, just the function reference
logger.debug("SRE Agent module initialized.")
