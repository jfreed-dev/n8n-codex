"""Slack Socket Mode handler for the UniFi Expert Agent."""

import asyncio
import logging
import re
from typing import Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from ..config import settings

logger = logging.getLogger(__name__)


def create_slack_app(agent) -> AsyncSocketModeHandler:
    """Create and configure the Slack app with Socket Mode.

    Args:
        agent: UniFiExpertAgent instance

    Returns:
        AsyncSocketModeHandler ready to start
    """
    app = AsyncApp(token=settings.SLACK_BOT_TOKEN)

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
                text="Hi! I'm the UniFi Network Expert. Ask me anything about your network, WiFi, security, or UniFi devices.",
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

            # Update with the response (or send new message if update fails)
            try:
                await client.chat_update(
                    channel=channel,
                    ts=initial_msg["ts"],
                    text=response,
                )
            except Exception:
                await say(text=response, thread_ts=thread_ts)

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

            # Update with response
            try:
                await client.chat_update(
                    channel=channel,
                    ts=initial_msg["ts"],
                    text=response,
                )
            except Exception:
                await say(text=response)

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
                            "Get recommendations for optimal network configuration"
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
                            "- _Is WPA3 enabled on my WiFi networks?_\n"
                            "- _How do I set up VLANs for IoT devices?_\n"
                            "- _What's the recommended channel for 5GHz?_"
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
