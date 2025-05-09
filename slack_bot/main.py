import logging
from typing import Any, Dict
import aiohttp
import asyncio
from datetime import datetime, timedelta

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


# Session management
class ConversationSession:
    def __init__(self, channel: str, user: str, thread_ts: str | None = None):
        self.channel = channel
        self.user = user
        self.thread_ts = thread_ts
        # Use thread_ts in the session_id if available for continuity
        thread_id = thread_ts if thread_ts else f"{datetime.now().timestamp()}"
        self.session_id = f"s_{channel}_{thread_id}"
        self.last_activity = datetime.now()
        self.user_id = f"u_{user}"  # Unique user ID for the API

    def update_activity(self):
        self.last_activity = datetime.now()

    def is_expired(
        self, timeout_minutes: int = 120
    ) -> bool:  # Increased timeout to 2 hours
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)


# Global session manager
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}
        self.cleanup_interval = 7200  # 2 hours (120 minutes)
        # New dictionary to map thread_ts to session_id for continuity
        self.thread_session_map: Dict[str, str] = {}

    def get_session(
        self, channel: str, user: str, thread_ts: str | None = None
    ) -> ConversationSession:
        # Clean up expired sessions
        self._cleanup_expired_sessions()

        # For thread continuity, first check if we already have a session for this thread
        thread_key = f"{channel}_{thread_ts}" if thread_ts else None

        # If this is a threaded conversation and we have a session for this thread
        if thread_ts and thread_key in self.thread_session_map:
            existing_session_key = self.thread_session_map[thread_key]

            # Check if the mapped session still exists and is not expired
            if (
                existing_session_key in self.sessions
                and not self.sessions[existing_session_key].is_expired()
            ):
                logger.info(
                    f"Reusing existing session for thread {thread_ts}: {existing_session_key}"
                )
                session = self.sessions[existing_session_key]
                session.update_activity()
                return session

        # Normal key format: channel + user + thread
        key = f"{channel}_{user}_{thread_ts if thread_ts else 'main'}"

        # Create new session if doesn't exist or is expired
        if key not in self.sessions or self.sessions[key].is_expired():
            self.sessions[key] = ConversationSession(channel, user, thread_ts)

            # If this is a threaded message, record the mapping from thread to session
            if thread_ts:
                self.thread_session_map[thread_key] = key
                logger.info(f"Created new session for thread {thread_ts}: {key}")
        else:
            self.sessions[key].update_activity()
            logger.info(f"Using existing session: {key}")

        return self.sessions[key]

    def _cleanup_expired_sessions(self):
        expired_keys = [k for k, v in self.sessions.items() if v.is_expired()]

        for k in expired_keys:
            # Also remove any thread mappings to this session
            expired_session = self.sessions[k]
            if expired_session.thread_ts:
                thread_key = f"{expired_session.channel}_{expired_session.thread_ts}"
                if thread_key in self.thread_session_map:
                    del self.thread_session_map[thread_key]

            # Remove the session
            del self.sessions[k]
            logger.info(f"Cleaned up expired session: {k}")


session_manager = SessionManager()


async def create_api_session(session: ConversationSession) -> bool:
    """Create a new session with the sre-bot-api, or handle case where session already exists"""
    async with aiohttp.ClientSession() as client:
        try:
            # Use the format from the README examples
            url = f"http://sre-bot-api:8000/apps/sre_agent/users/{session.user_id}/sessions/{session.session_id}"
            payload = {
                "state": {
                    "channel": session.channel,
                    "thread_ts": session.thread_ts,
                    "slack_user": session.user,
                }
            }
            logger.info(f"Creating API session at URL: {url}")
            logger.debug(f"Session payload: {payload}")

            # Add timeout to connection attempt
            logger.info("Attempting connection to sre-bot-api...")
            try:
                async with client.post(url, json=payload, timeout=10) as response:
                    response_text = await response.text()
                    logger.info(
                        f"API Response Status: {response.status}, Body: {response_text[:200]}"
                    )

                    # Consider both 200 OK and 400 with "Session already exists" as success
                    if response.status == 200:
                        logger.info(
                            f"Successfully created session {session.session_id}"
                        )
                        return True
                    elif response.status == 400 and "already exists" in response_text:
                        logger.info(
                            f"Session {session.session_id} already exists, proceeding anyway"
                        )
                        return True
                    else:
                        logger.error(
                            f"Failed to create session. Status: {response.status}, Response: {response_text}"
                        )
                        return False
            except asyncio.TimeoutError:
                logger.error("Connection timeout when trying to connect to sre-bot-api")
                return False
            except aiohttp.ClientConnectorError as conn_err:
                logger.error(f"Connection error to sre-bot-api: {conn_err}")
                return False

        except Exception as e:
            logger.error(f"Error creating API session: {e}", exc_info=True)
            return False


async def send_message_to_api(session: ConversationSession, message: str) -> str:
    """Send a message to the sre-bot-api and get the response"""
    async with aiohttp.ClientSession() as client:
        try:
            # Use the /run endpoint which we know works from the logs
            url = f"http://sre-bot-api:8000/run"
            payload = {
                "app_name": "sre_agent",
                "user_id": session.user_id,
                "session_id": session.session_id,
                "new_message": {"role": "user", "parts": [{"text": message}]},
            }

            logger.info(f"Sending message to API at URL: {url}")
            logger.debug(f"Message payload: {payload}")
            # 60 seconds is the maximum timeout for the API to respond
            async with client.post(url, json=payload, timeout=120) as response:
                if response.status == 200:
                    # Try to parse as JSON
                    try:
                        data = await response.json()
                        logger.debug(
                            f"API response type: {type(data)}, content sample: {str(data)[:200]}..."
                        )
                    except Exception as json_err:
                        # If it's not valid JSON, get it as text
                        logger.error(f"Failed to parse JSON response: {json_err}")
                        data = await response.text()
                        logger.debug(f"Response as text: {data}")
                        return f"Got non-JSON response: {data[:200]}..."

                    # Handle different response formats
                    api_response = ""

                    # Handling for Event/Content/Parts structure (common in ADK responses)
                    if (
                        isinstance(data, list)
                        and len(data) > 0
                        and isinstance(data[-1], dict)
                    ):
                        # Check for ADK event structure
                        if "id" in data[-1] and "content" in data[-1]:
                            logger.debug("Found ADK event structure in list response")
                            event = data[-1]
                            if (
                                isinstance(event["content"], dict)
                                and "parts" in event["content"]
                            ):
                                parts = event["content"]["parts"]
                                if isinstance(parts, list) and len(parts) > 0:
                                    part = parts[0]
                                    if isinstance(part, dict) and "text" in part:
                                        api_response = part["text"]
                                        logger.debug(
                                            f"Extracted text from event/content/parts: {api_response[:50]}..."
                                        )
                                        return api_response

                    # Check for state_delta["kubernetes_agent_output"] - this appears in the logs
                    if (
                        isinstance(data, list)
                        and len(data) > 0
                        and isinstance(data[-1], dict)
                    ):
                        event = data[-1]
                        if "actions" in event and isinstance(event["actions"], dict):
                            actions = event["actions"]
                            if "state_delta" in actions and isinstance(
                                actions["state_delta"], dict
                            ):
                                state_delta = actions["state_delta"]
                                if "kubernetes_agent_output" in state_delta:
                                    api_response = state_delta[
                                        "kubernetes_agent_output"
                                    ]
                                    if isinstance(api_response, str):
                                        logger.debug(
                                            f"Extracted text from state_delta: {api_response[:50]}..."
                                        )
                                        return api_response

                    # Case 1: Response is a dictionary
                    if isinstance(data, dict):
                        logger.debug("Handling dictionary response")
                        # Try common key names used in API responses
                        for key in [
                            "response",
                            "text",
                            "content",
                            "message",
                            "answer",
                            "result",
                            "output",
                        ]:
                            if key in data and data[key]:
                                logger.debug(f"Found value in key: {key}")
                                if isinstance(data[key], str):
                                    api_response = data[key]
                                    break
                                elif (
                                    isinstance(data[key], dict) and "text" in data[key]
                                ):
                                    api_response = data[key]["text"]
                                    break
                                elif (
                                    isinstance(data[key], dict)
                                    and "content" in data[key]
                                ):
                                    api_response = data[key]["content"]
                                    break

                        # Check for candidate objects with text
                        if (
                            not api_response
                            and "candidates" in data
                            and isinstance(data["candidates"], list)
                            and data["candidates"]
                        ):
                            logger.debug("Looking in candidates list")
                            candidate = data["candidates"][0]
                            if isinstance(candidate, dict):
                                if (
                                    "content" in candidate
                                    and isinstance(candidate["content"], dict)
                                    and "parts" in candidate["content"]
                                ):
                                    parts = candidate["content"]["parts"]
                                    if (
                                        isinstance(parts, list)
                                        and parts
                                        and "text" in parts[0]
                                    ):
                                        api_response = parts[0]["text"]

                        # Direct return if we found a response
                        if api_response:
                            return api_response

                    # Case 2: Response is a list
                    elif isinstance(data, list):
                        logger.debug("Handling list response")
                        if data:
                            if isinstance(data[0], dict):
                                # Try to extract text from the first item
                                for key in ["text", "content", "message", "response"]:
                                    if key in data[0]:
                                        logger.debug(
                                            f"Found value in list item key: {key}"
                                        )
                                        api_response = data[0][key]
                                        break
                            elif isinstance(data[0], str):
                                api_response = data[0]

                    # Case 3: Response is a string
                    elif isinstance(data, str):
                        logger.debug("Handling string response")
                        api_response = data

                    # If we still don't have a response, use string representation
                    if not api_response:
                        logger.warning(
                            f"Could not extract structured response, using string representation: {str(data)[:200]}"
                        )
                        # Convert to string but don't call strip() on a dict
                        api_response = str(data)
                    elif isinstance(api_response, str):
                        # Only strip if it's a string to avoid the error
                        api_response = api_response.strip()
                    else:
                        # If api_response is not a string, convert it
                        api_response = str(api_response)

                    return api_response
                else:
                    error_text = await response.text()
                    logger.error(f"API returned status {response.status}: {error_text}")
                    return f"Error: API returned status {response.status}"
        except Exception as e:
            logger.error(f"Error sending message to API: {e}", exc_info=True)
            return f"Error communicating with API: {str(e)}"


async def process_message_with_api(
    client: AsyncWebClient, channel: str, thread_ts: str | None, user: str, message: str
):
    """Process the message using the API and send response"""
    try:
        # Get or create session
        session = session_manager.get_session(channel, user, thread_ts)

        # Create API session if needed - consider session exists case as success
        session_created = False
        try:
            # Skip the broken health check endpoint
            session_created = await create_api_session(session)
        except Exception as create_error:
            logger.error(f"Failed to create session: {create_error}", exc_info=True)

        if not session_created:
            error_message = (
                "I couldn't establish a connection with the sre-bot-api service. This could be because:\n"
                "1. The API service is not running\n"
                "2. There's a network issue between services\n"
                "3. The API endpoint is incorrect\n\n"
                "Please check the logs for more details."
            )

            await client.chat_postMessage(
                channel=channel,
                text=f"Sorry <@{user}>, {error_message}",
                thread_ts=thread_ts,
            )
            return

        # Send message to API and get response
        response = await send_message_to_api(session, message)

        # Send response back to Slack
        await client.chat_postMessage(
            channel=channel, text=response, thread_ts=thread_ts
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await client.chat_postMessage(
            channel=channel,
            text=f"Sorry <@{user}>, something went wrong while processing your request.",
            thread_ts=thread_ts,
        )


@app.event("message")
async def handle_message_events(body, say, client, logger):
    """Handle all message events"""
    logger.info(body)
    event = body.get("event", {})

    if event.get("type") == "message" and "text" in event:
        user = event.get("user")
        text = event.get("text")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))

        # Avoid responding to bot's own messages
        if not event.get("bot_id") and user:
            logger.info(f"Received message from user {user}: {text}")

            # Check if the message contains a bot mention
            if text and text.startswith("<@"):
                try:
                    # First, acknowledge quickly
                    await say(
                        {
                            "text": f"I'm processing your request, <@{user}>! One moment please...",
                            "thread_ts": thread_ts,
                        }
                    )

                    # Process in background
                    asyncio.create_task(
                        process_message_with_api(
                            client=client,
                            channel=channel,
                            thread_ts=thread_ts,
                            user=user,
                            message=text,
                        )
                    )

                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
                    await say(
                        {
                            "text": f"Sorry <@{user}>, something went wrong!",
                            "thread_ts": thread_ts,
                        }
                    )


@fast_api.get("/health", status_code=200)
async def health() -> dict[str, Any]:
    """Health check endpoint"""
    return healthcheck()


@fast_api.post("/slack/events")
async def slack_events(req: Request) -> Any:
    """Handle incoming Slack events"""
    return await app_handler.handle(req)


# Error handler for debugging
@app.error
async def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")
