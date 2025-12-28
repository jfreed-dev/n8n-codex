"""Slack Socket Mode handler for the UniFi Expert Agent."""

import logging
import re

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from ..agent.confirmations import ConfirmationStore, DuoAuthClient, PendingAction
from ..agent.tools import TOOL_DEFINITIONS, ConfirmationRequired, set_confirmation_store
from ..config import settings

logger = logging.getLogger(__name__)

# Global confirmation store
_confirmation_store: ConfirmationStore | None = None


def get_confirmation_store() -> ConfirmationStore:
    """Get the global confirmation store, creating it if needed."""
    global _confirmation_store
    if _confirmation_store is None:
        # Check if Duo is configured
        duo_client = None
        if all([
            settings.DUO_INTEGRATION_KEY,
            settings.DUO_SECRET_KEY,
            settings.DUO_API_HOST,
            settings.DUO_MFA_USER,
        ]):
            duo_client = DuoAuthClient(
                integration_key=settings.DUO_INTEGRATION_KEY,
                secret_key=settings.DUO_SECRET_KEY,
                api_host=settings.DUO_API_HOST,
                mfa_user=settings.DUO_MFA_USER,
            )
            logger.info(f"Duo MFA enabled for user {settings.DUO_MFA_USER}")
        else:
            logger.info("Duo MFA not configured - dangerous actions will use Slack-only confirmation")

        _confirmation_store = ConfirmationStore(
            ttl_minutes=5,
            duo_client=duo_client,
        )

        # Set the store in tools module so tools can validate tokens
        set_confirmation_store(_confirmation_store)

    return _confirmation_store


def build_confirmation_message(pending: PendingAction) -> list[dict]:
    """Build Slack Block Kit message for confirmation.

    Args:
        pending: The pending action

    Returns:
        List of Slack blocks
    """
    # Risk level styling
    risk_emoji = {
        "moderate": ":warning:",
        "dangerous": ":rotating_light:",
        "critical": ":skull:",
    }
    emoji = risk_emoji.get(pending.risk_level, ":question:")

    # Check if Duo is required
    store = get_confirmation_store()
    duo_required = store.requires_duo(pending.risk_level)
    duo_note = "\n\n:iphone: *Duo MFA verification required*" if duo_required else ""

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *Confirmation Required*\n\n"
                    f"*Action:* {pending.description}\n"
                    f"*Risk Level:* {pending.risk_level.upper()}\n\n"
                    f"*Impact:* {pending.impact}"
                    f"{duo_note}"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"confirm_{pending.action_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "danger",
                    "action_id": f"approve_{pending.action_id}",
                    "value": pending.action_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "action_id": f"deny_{pending.action_id}",
                    "value": pending.action_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_Expires in 5 minutes_",
                }
            ],
        },
    ]

    return blocks


async def execute_tool_by_name(tool_name: str, tool_args: dict) -> str:
    """Execute a tool by name with the given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool

    Returns:
        Tool result string
    """
    for tool_def in TOOL_DEFINITIONS:
        if tool_def["name"] == tool_name:
            func = tool_def["function"]
            return await func(**tool_args)
    return f"Unknown tool: {tool_name}"


def create_slack_app(agent) -> AsyncSocketModeHandler:
    """Create and configure the Slack app with Socket Mode.

    Args:
        agent: UniFiExpertAgent instance

    Returns:
        AsyncSocketModeHandler ready to start
    """
    app = AsyncApp(token=settings.SLACK_BOT_TOKEN)

    # Initialize confirmation store
    store = get_confirmation_store()

    async def process_agent_response(
        response: str | ConfirmationRequired,
        say,
        client,
        channel: str,
        thread_ts: str,
        user: str,
        initial_ts: str | None = None,
    ) -> None:
        """Process agent response, handling confirmation requests.

        Args:
            response: Agent response (string or ConfirmationRequired)
            say: Slack say function
            client: Slack client
            channel: Channel ID
            thread_ts: Thread timestamp
            user: User ID who made the request
            initial_ts: Optional initial message timestamp to update
        """
        if isinstance(response, ConfirmationRequired):
            # Create pending action
            pending = store.create(
                tool_name=response.tool_name,
                tool_args=response.tool_args,
                user_id=user,
                channel_id=channel,
                thread_ts=thread_ts,
                message_ts=initial_ts or "",  # Will be updated
                risk_level=response.risk_level,
                description=response.description,
                impact=response.impact,
            )

            # Build confirmation message
            blocks = build_confirmation_message(pending)

            # Send or update message with confirmation buttons
            if initial_ts:
                await client.chat_update(
                    channel=channel,
                    ts=initial_ts,
                    text=f"Confirmation required: {response.description}",
                    blocks=blocks,
                )
                # Update message_ts in pending action
                pending.message_ts = initial_ts
            else:
                msg = await say(
                    text=f"Confirmation required: {response.description}",
                    blocks=blocks,
                    thread_ts=thread_ts,
                )
                # Update message_ts in pending action
                pending.message_ts = msg.get("ts", "")

        else:
            # Regular text response
            if initial_ts:
                try:
                    await client.chat_update(
                        channel=channel,
                        ts=initial_ts,
                        text=response,
                    )
                except Exception:
                    await say(text=response, thread_ts=thread_ts)
            else:
                await say(text=response, thread_ts=thread_ts)

    @app.event("app_mention")
    async def handle_mention(event: dict, say, client) -> None:
        """Handle @mentions of the bot in channels."""
        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Remove bot mention from the message
        # Pattern: <@BOTID> or <@BOTID|botname>
        query = re.sub(r"<@[A-Z0-9]+(\|[^>]+)?>", "", text).strip()

        if not query:
            await say(
                text="Hi! I'm the UniFi Network Expert. Ask me anything about your network, WiFi, security, or UniFi devices. I can also perform administrative actions like restarting devices or blocking clients.",
                thread_ts=thread_ts,
            )
            return

        logger.info(f"Mention from {user} in {channel}: {query}")

        # Send initial response to show we're working
        initial_msg = await say(
            text=f":thinking_face: Analyzing: _{query}_",
            thread_ts=thread_ts,
        )

        try:
            # Query the agent
            response = await agent.query(query)

            # Process response (may be text or ConfirmationRequired)
            await process_agent_response(
                response=response,
                say=say,
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                user=user,
                initial_ts=initial_msg["ts"],
            )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_msg = f":x: Sorry, I encountered an error: {str(e)}"
            try:
                await client.chat_update(
                    channel=channel,
                    ts=initial_msg["ts"],
                    text=error_msg,
                )
            except Exception:
                await say(text=error_msg, thread_ts=thread_ts)

    @app.event("message")
    async def handle_message(event: dict, say, client) -> None:
        """Handle direct messages to the bot."""
        # Only respond to DMs
        channel_type = event.get("channel_type")
        if channel_type != "im":
            return

        # Ignore bot messages and message_changed events
        if event.get("bot_id") or event.get("subtype"):
            return

        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")

        if not text.strip():
            return

        logger.info(f"DM from {user}: {text}")

        # Send typing indicator
        initial_msg = await say(text=":thinking_face: Let me check on that...")

        try:
            response = await agent.query(text)

            # Process response (may be text or ConfirmationRequired)
            await process_agent_response(
                response=response,
                say=say,
                client=client,
                channel=channel,
                thread_ts=event.get("ts", ""),
                user=user,
                initial_ts=initial_msg["ts"],
            )

        except Exception as e:
            logger.error(f"Agent error in DM: {e}")
            error_msg = f":x: Sorry, I encountered an error: {str(e)}"
            try:
                await client.chat_update(
                    channel=channel,
                    ts=initial_msg["ts"],
                    text=error_msg,
                )
            except Exception:
                await say(text=error_msg)

    # =========================================================================
    # Interactive Button Handlers
    # =========================================================================

    @app.action(re.compile(r"approve_.*"))
    async def handle_approve(ack, body, client) -> None:
        """Handle approval button clicks."""
        await ack()

        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        thread_ts = body["message"].get("thread_ts") or message_ts

        logger.info(f"Approve action {action_id} by user {user_id}")

        # Get the pending action
        pending = store.get(action_id)
        if not pending:
            await client.chat_update(
                channel=channel,
                ts=message_ts,
                text=":x: This action has expired. Please request it again.",
                blocks=[],
            )
            return

        # Show processing message
        await client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f":hourglass: Confirming: {pending.description}...",
            blocks=[],
        )

        # Confirm and get token (this may trigger Duo MFA)
        token, error = await store.confirm(action_id, user_id)

        if error:
            await client.chat_update(
                channel=channel,
                ts=message_ts,
                text=f":x: {error}",
                blocks=[],
            )
            return

        # Execute the tool with the confirmation token
        try:
            result = await execute_tool_by_name(
                pending.tool_name,
                {**pending.tool_args, "confirm_token": token},
            )

            # Show success result
            await client.chat_update(
                channel=channel,
                ts=message_ts,
                text=f":white_check_mark: *Completed:* {pending.description}\n\n{result}",
                blocks=[],
            )

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            await client.chat_update(
                channel=channel,
                ts=message_ts,
                text=f":x: Error executing action: {str(e)}",
                blocks=[],
            )

    @app.action(re.compile(r"deny_.*"))
    async def handle_deny(ack, body, client) -> None:
        """Handle denial button clicks."""
        await ack()

        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        message_ts = body["message"]["ts"]

        logger.info(f"Deny action {action_id} by user {user_id}")

        # Get action details before denying
        pending = store.get(action_id)
        description = pending.description if pending else "Unknown action"

        # Deny the action
        store.deny(action_id)

        await client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f":no_entry_sign: *Cancelled:* {description}",
            blocks=[],
        )

    @app.event("app_home_opened")
    async def handle_app_home(event: dict, client) -> None:
        """Update App Home when user opens it."""
        user = event.get("user")

        # Build home view
        view = {
            "type": "home",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":satellite: UniFi Network Expert",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "I'm your AI-powered UniFi network assistant. I can help you with:",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Network Status*\n"
                            "Check device health, connectivity, and performance\n\n"
                            "*Security Audits*\n"
                            "Review WiFi security, VLANs, and firewall rules\n\n"
                            "*Troubleshooting*\n"
                            "Diagnose connectivity issues and get remediation steps\n\n"
                            "*Best Practices*\n"
                            "Get recommendations for optimal network configuration\n\n"
                            "*Administrative Actions* :new:\n"
                            "Restart devices, block clients, manage guest access"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*How to Use*\n"
                            "- Send me a direct message\n"
                            "- @mention me in a channel\n"
                            "- Ask natural language questions about your network"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Example Questions*\n"
                            "- _What's the status of my network?_\n"
                            "- _Are there any devices offline?_\n"
                            "- _Show me connected clients_\n"
                            "- _Who are the top bandwidth users?_\n"
                            "- _What's the recommended channel for 5GHz?_\n\n"
                            "*Admin Commands*\n"
                            "- _Restart the living room AP_\n"
                            "- _Block the device with MAC xx:xx:xx_\n"
                            "- _Disable the Guest WiFi network_"
                        ),
                    },
                },
            ],
        }

        try:
            await client.views_publish(user_id=user, view=view)
        except Exception as e:
            logger.error(f"Failed to publish home view: {e}")

    # Error handler
    @app.error
    async def handle_error(error, body, logger) -> None:
        """Handle errors in Slack event processing."""
        logger.error(f"Slack error: {error}")
        logger.debug(f"Error body: {body}")

    # Create Socket Mode handler
    handler = AsyncSocketModeHandler(app, settings.SLACK_APP_TOKEN)
    return handler


async def start_slack_handler(agent) -> None:
    """Start the Slack Socket Mode handler.

    Args:
        agent: UniFiExpertAgent instance
    """
    if not settings.SLACK_APP_TOKEN:
        logger.warning("SLACK_APP_TOKEN not set, Slack handler disabled")
        return

    if not settings.SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not set, Slack handler disabled")
        return

    handler = create_slack_app(agent)
    logger.info("Starting Slack Socket Mode handler...")
    await handler.start_async()
