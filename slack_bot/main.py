import logging
from typing import Any
import aiohttp
import asyncio

from fastapi import FastAPI
from fastapi import Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from modules.health import healthcheck

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize the Slack app
app = AsyncApp()
fast_api = FastAPI()
app_handler = AsyncSlackRequestHandler(app)


async def fetch_ip_address():
    """
    Fetch IP address from icanhazip.com
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://icanhazip.com') as response:
                if response.status == 200:
                    ip = await response.text()
                    return ip.strip()
                else:
                    return f"Error: HTTP {response.status}"
        except Exception as e:
            logger.error(f"Error fetching IP: {e}")
            return f"Error fetching IP: {str(e)}"


async def process_request_and_respond(client: AsyncWebClient, channel: str, thread_ts: str | None, user: str):
    """
    Process the request and send response when ready
    """
    try:
        # Fetch the IP address
        ip_address = await fetch_ip_address()
        
        # Prepare the response message
        response = f"Hey <@{user}>, here's the IP address: `{ip_address}`"
        
        # Send the response in thread if it was a threaded message, otherwise in channel
        await client.chat_postMessage(
            channel=channel,
            text=response,
            thread_ts=thread_ts if thread_ts else None
        )
        
    except Exception as e:
        error_msg = f"Sorry <@{user}>, I encountered an error: {str(e)}"
        try:
            await client.chat_postMessage(
                channel=channel,
                text=error_msg,
                thread_ts=thread_ts if thread_ts else None
            )
        except Exception as e2:
            logger.error(f"Error sending error message: {e2}")


@app.event("message")
async def handle_message_events(body, say, client, logger):
    """
    Handle all message events as suggested by Slack Bolt
    """
    logger.info(body)
    event = body.get("event", {})
    
    if event.get("type") == "message" and "text" in event:
        user = event.get("user")
        text = event.get("text")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))  # Get thread ts if it exists, otherwise message ts
        
        # Avoid responding to bot's own messages
        if not event.get("bot_id") and user:
            logger.info(f"Received message from user {user}: {text}")
            
            # Check if the message contains a bot mention
            if text and text.startswith("<@"):
                try:
                    # First, acknowledge quickly
                    await say({
                        "text": f"I'm fetching that information for you, <@{user}>! Give me a moment...",
                        "thread_ts": thread_ts
                    })
                    
                    # Start processing in background
                    asyncio.create_task(
                        process_request_and_respond(
                            client=client,
                            channel=channel,
                            thread_ts=thread_ts,
                            user=user
                        )
                    )
                    
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
                    await say({
                        "text": f"Sorry <@{user}>, something went wrong!",
                        "thread_ts": thread_ts
                    })


@fast_api.get("/health", status_code=200)
async def health() -> dict[str, Any]:
    """
    Health check endpoint
    """
    return healthcheck()


@fast_api.post("/slack/events")
async def slack_events(req: Request) -> Any:
    """
    Handle incoming Slack events
    """
    return await app_handler.handle(req)


# Error handler for debugging
@app.error
async def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")
