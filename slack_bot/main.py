from typing import Any, Dict, Optional
import aiohttp
import asyncio
from datetime import datetime, timedelta
import os
import time

from fastapi import FastAPI
from fastapi import Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from modules.health import healthcheck

from utils import get_logger

# Configure logging using shared utility
logger = get_logger(__name__)

# Configuration from environment variables
API_BASE_URL = os.getenv("SRE_BOT_API_URL", "http://sre-bot-api:8000")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "300"))  # Default 300 seconds
SESSION_TIMEOUT_MINUTES = int(
    os.getenv("SESSION_TIMEOUT_MINUTES", "1200")
)  # Default 1200 minutes (20 hours)

# Whitelist configuration
WHITELIST_ENABLED = os.getenv("WHITELIST_ENABLED", "false").lower() == "true"
WHITELIST_USERS = set(
    user.strip() for user in os.getenv("WHITELIST_USERS", "").split(",") if user.strip()
)

logger.info(f"API timeout configured: {API_TIMEOUT} seconds")
logger.info(f"Session timeout configured: {SESSION_TIMEOUT_MINUTES} minutes")
logger.info(f"Whitelist enabled: {WHITELIST_ENABLED}")
if WHITELIST_ENABLED:
    logger.info(f"Whitelisted users: {len(WHITELIST_USERS)} users")
    logger.info(f"Whitelisted user IDs: {list(WHITELIST_USERS)}")
else:
    logger.info("Whitelist disabled - all users allowed")


def is_user_whitelisted(user_id: str) -> bool:
    """
    Check if a user is whitelisted to use the bot.

    Args:
        user_id: Slack user ID

    Returns:
        True if whitelisting is disabled OR user is in whitelist
        False if whitelisting is enabled AND user is not in whitelist
    """
    logger.debug(f"Checking whitelist for user: {user_id}")
    logger.debug(f"Whitelist enabled: {WHITELIST_ENABLED}")
    logger.debug(f"Whitelist users: {WHITELIST_USERS}")

    if not WHITELIST_ENABLED:
        logger.debug(f"Whitelist disabled, allowing user {user_id}")
        return True

    is_whitelisted = user_id in WHITELIST_USERS
    logger.debug(f"User {user_id} in whitelist: {is_whitelisted}")
    return is_whitelisted


# Initialize the Slack app
app = AsyncApp()
fast_api = FastAPI()
app_handler = AsyncSlackRequestHandler(app)

# Global variable to store bot user ID
bot_user_id = None


async def initialize_bot_user_id():
    """Initialize the bot's user ID at startup"""
    global bot_user_id
    try:
        client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))
        auth_response = await client.auth_test()
        if auth_response.get("ok"):
            bot_user_id = auth_response.get("user_id")
            logger.info(f"Bot initialized with user ID: {bot_user_id}")
        else:
            logger.error(f"Failed to get bot user ID at startup: {auth_response}")
    except Exception as e:
        logger.error(f"Error initializing bot user ID: {e}")


# Session management
class ConversationSession:
    def __init__(self, channel: str, user: str, thread_ts: str | None = None):
        self.channel = channel
        self.user = user  # Original user who started the session
        self.current_user = user  # Current user interacting (can change in threads)
        self.thread_ts = thread_ts
        # Use thread_ts in the session_id if available for continuity
        thread_id = thread_ts if thread_ts else f"{datetime.now().timestamp()}"
        self.session_id = f"s_{channel}_{thread_id}"
        self.last_activity = datetime.now()
        self.user_id = f"u_{user}"  # Unique user ID for the API

    def update_activity(self):
        self.last_activity = datetime.now()

    def is_expired(
        self, timeout_minutes: Optional[int] = None
    ) -> bool:  # Configurable session timeout
        if timeout_minutes is None:
            timeout_minutes = SESSION_TIMEOUT_MINUTES
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)


# Global session manager
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}
        self.cleanup_interval = (
            SESSION_TIMEOUT_MINUTES * 60
        )  # Convert minutes to seconds
        # Map thread_ts to session_id for continuity
        self.thread_session_map: Dict[str, str] = {}

    def update_session_thread(self, session: ConversationSession, new_thread_ts: str):
        """Update an existing session with a new thread_ts (for thread creation)"""
        old_key = f"{session.channel}_{session.user}_{session.thread_ts if session.thread_ts else 'main'}"

        # Update the session object
        session.thread_ts = new_thread_ts

        # Create new session ID with thread
        thread_id = new_thread_ts
        session.session_id = f"s_{session.channel}_{thread_id}"
        session.update_activity()

        # Create new key with thread
        new_key = f"{session.channel}_{session.user}_{new_thread_ts}"

        # Move session to new key
        if old_key in self.sessions:
            self.sessions[new_key] = self.sessions[old_key]
            del self.sessions[old_key]
            logger.info(f"Migrated session from {old_key} to {new_key}")

        # Update thread mapping
        thread_key = f"{session.channel}_{new_thread_ts}"
        self.thread_session_map[thread_key] = new_key

        return session

    def get_session(
        self, channel: str, user: str, thread_ts: str | None = None
    ) -> ConversationSession:
        # Clean up expired sessions
        self._cleanup_expired_sessions()

        # For threaded conversations, prioritize thread-based sessions
        if thread_ts:
            thread_key = f"{channel}_{thread_ts}"

            # Check if we already have a session for this thread
            if thread_key in self.thread_session_map:
                existing_session_key = self.thread_session_map[thread_key]

                # Check if the mapped session still exists and is not expired
                if (
                    existing_session_key in self.sessions
                    and not self.sessions[existing_session_key].is_expired()
                ):
                    logger.info(
                        f"Reusing existing thread session {existing_session_key} for thread {thread_ts} (current user: {user})"
                    )
                    session = self.sessions[existing_session_key]
                    session.update_activity()
                    # Update current user for this interaction
                    session.current_user = user
                    return session

        # For non-threaded or new threads, use user-based session key
        key = f"{channel}_{user}_{thread_ts if thread_ts else 'main'}"

        # Create new session if doesn't exist or is expired
        if key not in self.sessions or self.sessions[key].is_expired():
            self.sessions[key] = ConversationSession(channel, user, thread_ts)

            # If this is a threaded message, record the mapping from thread to session
            if thread_ts:
                thread_key = f"{channel}_{thread_ts}"
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


async def send_acknowledgment_message(
    client: AsyncWebClient, channel: str, user: str, thread_ts: str = None
) -> bool:
    """
    Send acknowledgment message to user when processing request.

    Args:
        client: Slack AsyncWebClient instance
        channel: Channel ID
        user: User ID
        thread_ts: Thread timestamp (optional)

    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        location = f"thread {thread_ts}" if thread_ts else "channel"
        logger.info(f"Sending acknowledgment message to {location} for user {user}")

        response = await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"I'm processing your request, <@{user}>! One moment please...",
        )

        if response.get("ok"):
            logger.info(f"✅ Successfully sent acknowledgment message to {location}")
            return True
        else:
            logger.error(f"❌ Failed to send acknowledgment message: {response}")
            return False

    except Exception as ack_error:
        logger.error(
            f"❌ Exception sending acknowledgment message: {ack_error}", exc_info=True
        )
        return False


async def fetch_parent_message_content(
    client: AsyncWebClient, channel: str, thread_ts: str
) -> Dict[str, Any]:
    """
    Fetch the parent message content and recent thread history for context.

    Args:
        client: Slack AsyncWebClient instance
        channel: Channel ID
        thread_ts: Thread timestamp (which is also the parent message timestamp)

    Returns:
        Dict containing parent message and thread context
    """
    try:
        logger.info(
            f"Fetching parent message content for thread {thread_ts} in channel {channel}"
        )

        # Fetch conversation replies to get the thread content
        # The first message in replies is always the parent message
        response = await client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=10,  # Get parent + last 9 messages for context
        )

        if not response.get("ok"):
            error = response.get("error", "Unknown error")
            logger.warning(f"Failed to fetch thread messages: {error}")
            return {"error": f"Slack API error: {error}"}

        messages = response.get("messages", [])
        if not messages:
            logger.warning("No messages found in thread response")
            return {"error": "No messages found in thread"}

        parent_message = messages[0]  # First message is always the parent

        # Validate parent message has required fields
        if not parent_message.get("ts") == thread_ts:
            logger.warning(
                f"Parent message timestamp {parent_message.get('ts')} doesn't match thread_ts {thread_ts}"
            )
            return {"error": "Parent message timestamp mismatch"}

        # Extract parent message content
        parent_content = {
            "text": parent_message.get("text", ""),
            "user": parent_message.get("user"),
            "timestamp": parent_message.get("ts"),
            "user_profile": {},
        }

        # Get user info for the parent message author
        try:
            user_info = await client.users_info(user=parent_message.get("user"))
            if user_info.get("ok"):
                user_profile = user_info.get("user", {}).get("profile", {})
                parent_content["user_profile"] = {
                    "display_name": user_profile.get("display_name", ""),
                    "real_name": user_profile.get("real_name", ""),
                }
        except Exception as e:
            logger.warning(f"Could not fetch user info: {e}")

        # Collect recent thread context (excluding the parent message)
        thread_context = []
        for msg in messages[1:]:  # Skip parent message
            if not msg.get("bot_id"):  # Exclude bot messages for cleaner context
                thread_context.append(
                    {
                        "text": msg.get("text", ""),
                        "user": msg.get("user"),
                        "timestamp": msg.get("ts"),
                    }
                )

        result = {
            "parent_message": parent_content,
            "thread_context": thread_context,
            "thread_length": len(messages),
            "channel": channel,
        }

        logger.debug(f"Successfully fetched thread content: {len(messages)} messages")
        return result

    except Exception as e:
        logger.error(f"Error fetching parent message content: {e}", exc_info=True)
        return {"error": f"Failed to fetch thread content: {str(e)}"}


async def create_api_session(
    session: ConversationSession, parent_thread_data: Dict[str, Any] = None
) -> bool:
    """Create a new session with the sre-bot-api, or handle case where session already exists"""
    async with aiohttp.ClientSession() as client:
        try:
            # Use the format from the README examples
            url = f"{API_BASE_URL}/apps/sre_agent/users/{session.user_id}/sessions/{session.session_id}"
            # Enhanced payload with thread context and parent message data
            payload = {
                "state": {
                    "channel": session.channel,
                    "thread_ts": session.thread_ts,
                    "slack_user": session.current_user,  # Use current user, not original
                    "original_user": session.user,  # Keep track of who started the thread
                    # Add parent thread context if available
                    "thread_context": parent_thread_data if parent_thread_data else {},
                    "has_thread_context": bool(parent_thread_data),
                    # Add timestamp for context freshness
                    "session_created_at": datetime.now().isoformat(),
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
            url = f"{API_BASE_URL}/run"
            payload = {
                "app_name": "sre_agent",
                "user_id": session.user_id,
                "session_id": session.session_id,
                "new_message": {"role": "user", "parts": [{"text": message}]},
            }

            logger.info(f"Sending message to API at URL: {url}")
            logger.debug(f"Message payload: {payload}")

            # Track API call timing
            start_time = time.time()
            # Configurable timeout for the API to respond
            async with client.post(url, json=payload, timeout=API_TIMEOUT) as response:
                response_time_ms = (time.time() - start_time) * 1000
                if response.status == 200:
                    logger.info(
                        f"API call successful - Status: {response.status}, Response time: {response_time_ms:.2f}ms"
                    )
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
                    logger.error(
                        f"API returned status {response.status}: {error_text[:200]}, Response time: {response_time_ms:.2f}ms"
                    )
                    return f"Error: API returned status {response.status}"
        except Exception as e:
            logger.error(f"Error sending message to API: {e}", exc_info=True)
            return f"Error communicating with API: {str(e)}"


async def process_message_with_api(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str | None,
    user: str,
    message: str,
    original_message_ts: str | None = None,
):
    """Process the message using the API and send response"""
    try:
        # Send acknowledgment message immediately for ANY threaded message
        if thread_ts:
            logger.info(
                "🔄 Detected threaded message - sending immediate acknowledgment"
            )
            ack_sent = await send_acknowledgment_message(
                client, channel, user, thread_ts
            )
            logger.info(f"🔄 Immediate acknowledgment sent: {ack_sent}")

        # Handle thread creation for direct mentions
        if not thread_ts and original_message_ts:
            logger.info(
                f"Processing direct mention from user {user} in channel {channel} - will create thread under original message"
            )

            # Create thread by replying to the original message
            thread_ts = original_message_ts
            ack_sent = await send_acknowledgment_message(
                client, channel, user, thread_ts
            )

            if ack_sent:
                logger.info(
                    f"Created thread under message {thread_ts} for user {user} in channel {channel}"
                )

                # Get session and update it with the new thread
                session = session_manager.get_session(channel, user, None)
                session = session_manager.update_session_thread(session, thread_ts)

                logger.info(
                    f"Thread created and session migrated: {session.session_id}"
                )
            else:
                logger.error("Failed to send acknowledgment message for new thread")
                # Fall back to no thread but still create session
                session = session_manager.get_session(channel, user, None)
        elif not thread_ts and not original_message_ts:
            logger.warning(
                f"Cannot create thread - no original message timestamp provided for user {user} in channel {channel}"
            )
            # Fall back to no thread
            session = session_manager.get_session(channel, user, None)

            # Send acknowledgment message for non-threaded responses
            await send_acknowledgment_message(client, channel, user)
        else:
            logger.info(
                f"Processing threaded message from user {user} in thread {thread_ts}"
            )

            # Get or create session for existing thread
            # This will reuse existing session if thread already has one, or create new one
            session = session_manager.get_session(channel, user, thread_ts)

        # Fetch parent thread content if this is an existing thread message (not one we just created)
        parent_thread_data = None
        # thread_just_created is True when we created a new thread in this request
        # This happens when we had no thread_ts initially and original_message_ts was provided
        thread_just_created = (
            session.thread_ts == original_message_ts and original_message_ts is not None
        )

        if session.thread_ts and not thread_just_created:
            logger.info(
                f"Bot mentioned in existing thread {session.thread_ts}, fetching parent message content"
            )
            try:
                parent_thread_data = await fetch_parent_message_content(
                    client, channel, session.thread_ts
                )

                if parent_thread_data.get("error"):
                    logger.warning(
                        f"Could not fetch parent thread data: {parent_thread_data['error']}"
                    )
                    parent_thread_data = None
                else:
                    logger.info(
                        f"Successfully fetched parent thread data with {parent_thread_data.get('thread_length', 0)} messages"
                    )
            except Exception as thread_fetch_error:
                logger.error(
                    f"Exception while fetching thread content: {thread_fetch_error}",
                    exc_info=True,
                )
                parent_thread_data = None
        elif thread_just_created:
            logger.debug(
                "Thread was just created by bot, skipping parent message fetch"
            )
        else:
            logger.debug("Non-threaded message, skipping parent message fetch")

        # Create API session if needed - consider session exists case as success
        session_created = False
        try:
            # Skip the broken health check endpoint
            session_created = await create_api_session(session, parent_thread_data)
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
        # Include parent thread context in the message if available
        enhanced_message = message
        if parent_thread_data and not parent_thread_data.get("error"):
            parent_msg = parent_thread_data.get("parent_message", {})
            parent_text = parent_msg.get("text", "").strip()

            if parent_text:
                # Get author name with fallback options
                author_name = "Unknown"
                user_profile = parent_msg.get("user_profile", {})
                if user_profile.get("display_name"):
                    author_name = user_profile["display_name"]
                elif user_profile.get("real_name"):
                    author_name = user_profile["real_name"]
                elif parent_msg.get("user"):
                    author_name = f"User {parent_msg['user']}"

                thread_length = parent_thread_data.get("thread_length", 1)

                enhanced_message = f"""User message: {message}

Thread Context:
- Original message: "{parent_text}"
- Original author: {author_name}
- Thread length: {thread_length} messages
- Context: This message is part of an ongoing thread discussion

Please consider this thread context when responding to provide relevant and coherent assistance."""

                logger.debug(f"Enhanced message with thread context from {author_name}")
            else:
                logger.debug(
                    "Parent message has no text content, using original message only"
                )
        else:
            logger.debug("No thread context available, using original message only")

        response = await send_message_to_api(session, enhanced_message)

        # Send response back to Slack (use the session's thread_ts which may have been updated)
        await client.chat_postMessage(
            channel=channel, text=response, thread_ts=session.thread_ts
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await client.chat_postMessage(
            channel=channel,
            text=f"Sorry <@{user}>, something went wrong while processing your request.",
            thread_ts=session.thread_ts if "session" in locals() else thread_ts,
        )


@app.event("app_mention")
async def handle_app_mention_events(body, say, client, logger):
    """Handle app mentions (when someone @mentions the bot)"""
    logger.info("App mention received")
    logger.info(body)
    event = body.get("event", {})

    if event.get("type") == "app_mention" and "text" in event:
        user = event.get("user")
        text = event.get("text")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))

        if user:
            logger.info(f"Received app mention from user {user}: {text}")

            # Check if user is whitelisted
            if not is_user_whitelisted(user):
                logger.info(f"User {user} not in whitelist, sending GA message")
                try:
                    await say(
                        text=f"Hi <@{user}>! 👋 Thanks for your interest in the SRE bot. "
                        "This bot is currently in limited preview and will be available "
                        "to all users when it reaches general availability (GA). "
                        "Stay tuned for updates! 🚀",
                        thread_ts=thread_ts,
                    )
                except Exception as e:
                    logger.error(f"Error sending whitelist message: {e}")
                return

            try:
                # Process the app mention
                original_message_ts = event.get("ts") if not thread_ts else None

                logger.info(
                    f"Processing app mention - User: {user}, Channel: {channel}, "
                    f"Thread: {thread_ts}, Original: {original_message_ts}"
                )

                asyncio.create_task(
                    process_message_with_api(
                        client=client,
                        channel=channel,
                        thread_ts=thread_ts,
                        user=user,
                        message=text,
                        original_message_ts=original_message_ts,
                    )
                )

            except Exception as e:
                logger.error(f"Error handling app mention: {str(e)}")
                await say(
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
        # Only set thread_ts if this is actually a thread reply, not for regular messages
        thread_ts = event.get("thread_ts")

        # Avoid responding to bot's own messages
        if not event.get("bot_id") and user:
            logger.info(f"Received message from user {user}: {text}")

            # Use the global bot_user_id (initialized at startup)
            global bot_user_id
            if bot_user_id is None:
                logger.warning(
                    "Bot user ID not initialized, attempting to initialize now"
                )
                await initialize_bot_user_id()

            # Check if user is whitelisted before any processing
            if not is_user_whitelisted(user):
                # Only respond to direct mentions of the bot for non-whitelisted users
                is_bot_mentioned = bot_user_id and text and f"<@{bot_user_id}>" in text
                if is_bot_mentioned:
                    logger.info(f"User {user} not in whitelist, sending GA message")
                    try:
                        await say(
                            {
                                "text": f"Hi <@{user}>! 👋 Thanks for your interest in the SRE bot. "
                                "This bot is currently in limited preview and will be available "
                                "to all users when it reaches general availability (GA). "
                                "Stay tuned for updates! 🚀",
                                "thread_ts": thread_ts,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error sending whitelist message: {e}")
                return

            # Only respond to direct mentions of the bot (either in channel or thread)
            is_direct_mention = bot_user_id and text and f"<@{bot_user_id}>" in text

            if is_direct_mention:
                if thread_ts:
                    logger.info(
                        f"Will respond - bot mentioned in thread {thread_ts} from user {user}"
                    )
                else:
                    logger.info(
                        f"Will respond - bot mentioned in channel from user {user}"
                    )
            else:
                logger.debug(
                    f"Ignoring message - bot not mentioned (bot_user_id: {bot_user_id})"
                )

            if is_direct_mention:
                try:
                    # Process in background
                    # Get the original message timestamp for thread creation
                    original_message_ts = event.get("ts") if not thread_ts else None

                    logger.info(
                        f"Processing message - User: {user}, Channel: {channel}, "
                        f"Thread: {thread_ts}, Original: {original_message_ts}"
                    )

                    asyncio.create_task(
                        process_message_with_api(
                            client=client,
                            channel=channel,
                            thread_ts=thread_ts,
                            user=user,
                            message=text,
                            original_message_ts=original_message_ts,
                        )
                    )

                except Exception as e:
                    logger.error(f"Error in message handler: {e}", exc_info=True)
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


@fast_api.on_event("startup")
async def startup_event():
    """Initialize bot when FastAPI starts"""
    await initialize_bot_user_id()


@fast_api.post("/slack/events")
async def slack_events(req: Request) -> Any:
    """Handle incoming Slack events"""
    return await app_handler.handle(req)


# Error handler for debugging
@app.error
async def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")
