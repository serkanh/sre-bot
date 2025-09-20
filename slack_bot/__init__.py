import sys
import os
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from app.modules.health import healthcheck

# Add the parent directory to sys.path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agents.sre_agent.utils import get_logger

# Configure logging using shared utility
logger = get_logger(__name__)

# Initialize the Slack app
app = AsyncApp()

fast_api = FastAPI()
app_handler = AsyncSlackRequestHandler(app)


@fast_api.get("/health", status_code=200)
async def health() -> dict[str, Any]:
    """
    This function is used to perform a health check.

    Returns:
        Dict[str, Any]: The result of the health check.
    """
    return healthcheck()


@fast_api.post("/slack/events")
async def slack_events(req: Request) -> Any:
    """
    This function is used to validate and "enable events" in the Slack app.

    Args:
        req (Request): The request object.

    Returns:
        Any: The response to the Slack event.
    """
    return await app_handler.handle(req)
