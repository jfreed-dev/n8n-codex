"""Confirmation store for administrative actions with Duo MFA support.

This module manages pending confirmation requests for dangerous operations,
with optional Duo push notification approval for high-risk actions.
"""

import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """A pending action awaiting user confirmation."""
    action_id: str
    tool_name: str
    tool_args: dict
    user_id: str
    channel_id: str
    thread_ts: str
    message_ts: str
    risk_level: Literal["moderate", "dangerous", "critical"]
    description: str
    impact: str
    created_at: datetime
    expires_at: datetime
    confirm_token: str | None = None
    duo_approved: bool = False
    duo_txid: str | None = None


class DuoAuthClient:
    """Duo Auth API client for push notifications."""

    def __init__(
        self,
        integration_key: str,
        secret_key: str,
        api_host: str,
        mfa_user: str,
    ):
        """Initialize Duo client.

        Args:
            integration_key: Duo Auth API integration key (ikey)
            secret_key: Duo Auth API secret key (skey)
            api_host: Duo API hostname (e.g., api-XXXXXXXX.duosecurity.com)
            mfa_user: User identifier for push notifications (e.g., jon@freed.dev)
        """
        self.integration_key = integration_key
        self.secret_key = secret_key
        self.api_host = api_host
        self.mfa_user = mfa_user
        self._client = None

    async def _get_client(self):
        """Get or create the Duo Admin client."""
        if self._client is None:
            try:
                import duo_client
                self._client = duo_client.Auth(
                    ikey=self.integration_key,
                    skey=self.secret_key,
                    host=self.api_host,
                )
            except ImportError:
                logger.error("duo_client package not installed")
                raise RuntimeError("Duo client not available - install duo_client package")
        return self._client

    async def send_push(self, description: str, action_id: str) -> tuple[bool, str | None]:
        """Send a Duo push notification and wait for response.

        Args:
            description: Description of the action to show in push
            action_id: Unique action ID for tracking

        Returns:
            Tuple of (approved: bool, txid: str | None)
        """
        try:
            client = await self._get_client()

            # Run Duo API call in thread pool since it's blocking
            loop = asyncio.get_event_loop()

            # First, initiate the push
            def auth_push():
                return client.auth(
                    factor="push",
                    username=self.mfa_user,
                    device="auto",
                    type="UniFi Admin Action",
                    display_username=self.mfa_user,
                    pushinfo=f"Action={description}&ID={action_id}",
                    async_txn=False,  # Wait for response
                )

            logger.info(f"Sending Duo push to {self.mfa_user} for: {description}")
            result = await loop.run_in_executor(None, auth_push)

            if result.get("result") == "allow":
                logger.info(f"Duo push approved for action {action_id}")
                return True, result.get("txid")
            else:
                reason = result.get("status_msg", "Unknown reason")
                logger.info(f"Duo push denied for action {action_id}: {reason}")
                return False, None

        except Exception as e:
            logger.error(f"Duo push error: {e}")
            return False, None

    async def check_status(self, txid: str) -> bool:
        """Check status of an async transaction (not used in sync mode).

        Args:
            txid: Transaction ID from auth call

        Returns:
            True if approved, False otherwise
        """
        try:
            client = await self._get_client()
            loop = asyncio.get_event_loop()

            def check():
                return client.auth_status(txid)

            result = await loop.run_in_executor(None, check)
            return result.get("result") == "allow"
        except Exception as e:
            logger.error(f"Duo status check error: {e}")
            return False


class ConfirmationStore:
    """In-memory store for pending action confirmations."""

    def __init__(
        self,
        ttl_minutes: int = 5,
        duo_client: DuoAuthClient | None = None,
    ):
        """Initialize the confirmation store.

        Args:
            ttl_minutes: Time-to-live for pending actions in minutes
            duo_client: Optional Duo client for MFA on dangerous+ actions
        """
        self._actions: dict[str, PendingAction] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        self.duo_client = duo_client

    def requires_duo(self, risk_level: str) -> bool:
        """Check if an action requires Duo MFA.

        Args:
            risk_level: The risk level of the action

        Returns:
            True if Duo MFA is required
        """
        # Duo required for dangerous and critical actions
        return self.duo_client is not None and risk_level in ("dangerous", "critical")

    def create(
        self,
        tool_name: str,
        tool_args: dict,
        user_id: str,
        channel_id: str,
        thread_ts: str,
        message_ts: str,
        risk_level: Literal["moderate", "dangerous", "critical"],
        description: str,
        impact: str,
    ) -> PendingAction:
        """Create a new pending action.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            user_id: Slack user ID who requested the action
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            message_ts: Message timestamp for the confirmation message
            risk_level: Risk level of the action
            description: Human-readable description
            impact: Description of the impact

        Returns:
            The created PendingAction
        """
        # Cleanup expired actions first
        self.cleanup_expired()

        action_id = secrets.token_urlsafe(16)
        now = datetime.utcnow()

        action = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            tool_args=tool_args,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_ts=message_ts,
            risk_level=risk_level,
            description=description,
            impact=impact,
            created_at=now,
            expires_at=now + self.ttl,
        )

        self._actions[action_id] = action
        logger.info(f"Created pending action {action_id}: {description}")

        return action

    def get(self, action_id: str) -> PendingAction | None:
        """Get a pending action by ID.

        Args:
            action_id: The action ID

        Returns:
            The PendingAction or None if not found/expired
        """
        action = self._actions.get(action_id)
        if action and datetime.utcnow() > action.expires_at:
            del self._actions[action_id]
            return None
        return action

    async def confirm(
        self,
        action_id: str,
        user_id: str,
    ) -> tuple[str | None, str | None]:
        """Confirm an action and get the confirmation token.

        For dangerous+ actions with Duo enabled, this will send a push notification.

        Args:
            action_id: The action ID to confirm
            user_id: The user ID confirming (must match requester)

        Returns:
            Tuple of (confirm_token, error_message)
            - On success: (token, None)
            - On failure: (None, error_message)
        """
        action = self.get(action_id)

        if not action:
            return None, "Action expired or not found."

        if action.user_id != user_id:
            return None, "Only the original requester can confirm this action."

        if action.confirm_token:
            return None, "Action already confirmed."

        # Check if Duo MFA is required
        if self.requires_duo(action.risk_level):
            logger.info(f"Action {action_id} requires Duo MFA")

            approved, txid = await self.duo_client.send_push(
                description=action.description,
                action_id=action_id,
            )

            if not approved:
                return None, "Duo MFA verification failed or was denied."

            action.duo_approved = True
            action.duo_txid = txid

        # Generate confirmation token
        action.confirm_token = secrets.token_urlsafe(32)
        logger.info(f"Action {action_id} confirmed, token generated")

        return action.confirm_token, None

    def validate_token(self, tool_name: str, token: str) -> dict | None:
        """Validate a confirmation token and consume it.

        Args:
            tool_name: The tool name the token should be for
            token: The confirmation token

        Returns:
            The tool_args dict if valid, None otherwise
        """
        for action_id, action in list(self._actions.items()):
            if action.confirm_token == token and action.tool_name == tool_name:
                # Consume the token by removing the action
                tool_args = action.tool_args.copy()
                del self._actions[action_id]
                logger.info(f"Token validated and consumed for action {action_id}")
                return tool_args

        logger.warning(f"Invalid token for tool {tool_name}")
        return None

    def deny(self, action_id: str) -> bool:
        """Deny/cancel a pending action.

        Args:
            action_id: The action ID to deny

        Returns:
            True if action was found and removed
        """
        if action_id in self._actions:
            del self._actions[action_id]
            logger.info(f"Action {action_id} denied/cancelled")
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired actions.

        Returns:
            Number of actions removed
        """
        now = datetime.utcnow()
        expired = [
            action_id
            for action_id, action in self._actions.items()
            if action.expires_at < now
        ]

        for action_id in expired:
            del self._actions[action_id]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired actions")

        return len(expired)

    def list_pending(self, user_id: str | None = None) -> list[PendingAction]:
        """List pending actions, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of pending actions
        """
        self.cleanup_expired()

        actions = list(self._actions.values())
        if user_id:
            actions = [a for a in actions if a.user_id == user_id]

        return actions
