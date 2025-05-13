import logging
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from app.modules.health import healthcheck

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
