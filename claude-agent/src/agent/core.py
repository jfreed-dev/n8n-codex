"""Core agent implementation using Claude API with tool use.

This module implements the UniFi Expert Agent using direct Claude API calls
with tool use capabilities, providing a simpler alternative to the full
Claude Agent SDK while maintaining the same functionality.
"""

import json
import logging

import httpx

from ..config import settings
from .prompts import AUDIT_ANALYSIS_PROMPT, HEALTH_ANALYSIS_PROMPT, UNIFI_EXPERT_SYSTEM_PROMPT
from .tools import TOOL_DEFINITIONS, ConfirmationRequired

logger = logging.getLogger(__name__)


class UniFiExpertAgent:
    """UniFi Network Expert Agent using Claude API with tool use."""

    def __init__(self, knowledge_base=None):
        """Initialize the agent.

        Args:
            knowledge_base: Optional KnowledgeBase instance for RAG
        """
        self.knowledge_base = knowledge_base
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = "claude-sonnet-4-20250514"
        self.api_url = "https://api.anthropic.com/v1/messages"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_tools(self) -> list[dict]:
        """Build tool definitions for Claude API."""
        tools = []
        for tool_def in TOOL_DEFINITIONS:
            # Convert our tool definition to Claude's format
            properties = {}
            required = []

            for param_name, param_info in tool_def.get("parameters", {}).items():
                properties[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
                if param_info.get("required", False):
                    required.append(param_name)

            tool = {
                "name": tool_def["name"],
                "description": tool_def["description"],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
            tools.append(tool)

        return tools

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str | ConfirmationRequired:
        """Execute a tool and return its result.

        Returns:
            String result, or ConfirmationRequired if the tool needs user confirmation.
        """
        for tool_def in TOOL_DEFINITIONS:
            if tool_def["name"] == tool_name:
                func = tool_def["function"]
                # Call the tool function with appropriate arguments
                if tool_input:
                    result = await func(**tool_input)
                else:
                    result = await func()
                return result

        return f"Unknown tool: {tool_name}"

    async def query(self, user_message: str, context: dict | None = None) -> str | ConfirmationRequired:
        """Query the agent with a user message.

        Args:
            user_message: The user's question or request
            context: Optional context dictionary

        Returns:
            The agent's response text, or ConfirmationRequired if an admin
            action needs user confirmation before execution.
        """
        client = await self._get_client()

        # Build the messages
        messages = [{"role": "user", "content": user_message}]

        # Add context if provided
        if context:
            context_str = f"\n\nContext:\n```json\n{json.dumps(context, indent=2)}\n```"
            messages[0]["content"] = user_message + context_str

        # Build request body
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "system": UNIFI_EXPERT_SYSTEM_PROMPT,
            "tools": self._build_tools(),
            "messages": messages,
        }

        # Agentic loop - keep processing until we get a final response
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Agent iteration {iteration}")

            response = await client.post(self.api_url, json=body)
            response.raise_for_status()
            result = response.json()

            stop_reason = result.get("stop_reason")
            content = result.get("content", [])

            # Check if we need to execute tools
            if stop_reason == "tool_use":
                # Find and execute tool calls
                tool_results = []
                assistant_content = []

                for block in content:
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name")
                        tool_input = block.get("input", {})
                        tool_use_id = block.get("id")

                        logger.info(f"Executing tool: {tool_name}")
                        result = await self._execute_tool(tool_name, tool_input)

                        # Check if this is a confirmation request
                        if isinstance(result, ConfirmationRequired):
                            logger.info(f"Tool {tool_name} requires confirmation")
                            return result

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result,
                        })
                        assistant_content.append(block)
                    else:
                        assistant_content.append(block)

                # Add assistant message with tool use and user message with results
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
                body["messages"] = messages

            elif stop_reason == "end_turn":
                # Extract final text response
                text_parts = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))

                return "\n".join(text_parts)

            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop reason: {stop_reason}")
                break

        return "I was unable to complete the request after multiple attempts."

    async def analyze_health(self, devices: list[dict], summary: str) -> str:
        """Analyze device health data and provide recommendations.

        Args:
            devices: List of device data from UniFi
            summary: Text summary of device status

        Returns:
            AI-generated analysis and recommendations
        """
        prompt = HEALTH_ANALYSIS_PROMPT.format(
            device_data=json.dumps(devices, indent=2),
            summary=summary,
        )
        return await self.query(prompt)

    async def analyze_audit(
        self,
        findings: list[dict],
        networks: list[dict],
        wlans: list[dict],
        firewall_rules: list[dict],
        devices: list[dict],
    ) -> str:
        """Analyze security audit findings and provide remediation steps.

        Args:
            findings: List of audit findings
            networks: Network configuration
            wlans: WLAN configuration
            firewall_rules: Firewall rules
            devices: Device information

        Returns:
            AI-generated remediation recommendations
        """
        prompt = AUDIT_ANALYSIS_PROMPT.format(
            findings=json.dumps(findings, indent=2),
            network_count=len(networks),
            wlan_count=len(wlans),
            firewall_count=len(firewall_rules),
            device_count=len(devices),
        )
        return await self.query(prompt)
