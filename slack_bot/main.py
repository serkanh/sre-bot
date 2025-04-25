import logging
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from modules.health import healthcheck

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Slack app
app = AsyncApp()# Initialize the Slack app


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

@app.event("message")
async def handle_message_events(body, say, logger):
    """
    Handle all message events as suggested by Slack Bolt
    """
    logger.info(body)
    # Extract the event from the body
    event = body.get("event", {})
    
    # If this is a message mentioning the bot
    if event.get("type") == "message" and "text" in event:
        user = event.get("user")
        text = event.get("text")
        channel = event.get("channel")
        
        # Avoid responding to bot's own messages
        if not event.get("bot_id") and user:
            logger.info(f"Received message from user {user}: {text}")
            
            # Check if the message contains a bot mention (starts with <@BOT_ID>)
            if text and text.startswith("<@"):
                try:
                    # Reply with a greeting using the user's mention format
                    await say(f"Hello <@{user}>! How can I help you today? 👋")
                    logger.info(f"Sent greeting to user {user}")
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
