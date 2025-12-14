"""MCP tools for UniFi Network operations.

These tools are registered with the Claude Agent SDK and can be invoked
by the agent to query live UniFi controller data.
"""

import json
import logging
from typing import Any

from ..config import settings
from ..unifi.integration_api import UniFiIntegrationAPI
from ..unifi.controller_api import UniFiControllerAPI

logger = logging.getLogger(__name__)

# Lazy-initialized API clients
_integration_api: UniFiIntegrationAPI | None = None
_controller_api: UniFiControllerAPI | None = None


def get_integration_api() -> UniFiIntegrationAPI:
    """Get or create the Integration API client."""
    global _integration_api
    if _integration_api is None:
        _integration_api = UniFiIntegrationAPI(
            base_url=settings.UNIFI_BASE_URL,
            api_token=settings.UNIFI_API_TOKEN,
        )
    return _integration_api


def get_controller_api() -> UniFiControllerAPI:
    """Get or create the Controller API client."""
    global _controller_api
    if _controller_api is None:
        _controller_api = UniFiControllerAPI(
            base_url=settings.UNIFI_BASE_URL,
            username=settings.UNIFI_USERNAME,
            password=settings.UNIFI_PASSWORD,
            site=settings.UNIFI_SITE,
        )
    return _controller_api


# Tool definitions for Claude Agent SDK
# These are functions that will be wrapped as MCP tools

async def get_unifi_sites() -> str:
    """Get list of all UniFi sites available.

    Returns:
        Formatted string with site information
    """
    api = get_integration_api()
    try:
        sites = await api.get_sites()
        if not sites:
            return "No sites found."

        lines = [f"Found {len(sites)} site(s):"]
        for site in sites:
            ref = site.get("internalReference", "unknown")
            name = site.get("name", "unnamed")
            site_id = site.get("id", "?")
            lines.append(f"- **{ref}** ({name}): ID={site_id}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting sites: {e}")
        return f"Error fetching sites: {str(e)}"


async def get_unifi_devices(site_id: str | None = None) -> str:
    """Get all devices for a site with status, model, firmware info.

    Args:
        site_id: Optional site ID. If not provided, uses default site.

    Returns:
        Formatted string with device information
    """
    api = get_integration_api()
    try:
        # Get site ID if not provided
        if not site_id:
            site = await api.get_site_by_reference(settings.UNIFI_SITE)
            if not site:
                return "No sites found."
            site_id = site.get("id")

        devices = await api.get_devices(site_id)
        if not devices:
            return "No devices found."

        # Categorize devices by state
        online = []
        offline = []
        other = []
        upgradable = []

        for d in devices:
            name = d.get("name") or d.get("mac", "Unknown")
            model = d.get("model", "")
            state = (d.get("state") or "").upper()
            version = d.get("version") or d.get("displayableVersion", "?")

            info = f"- **{name}** ({model}): v{version}"

            if d.get("upgradable") or d.get("upgradeable"):
                upgradable.append(name)
                info += " [UPGRADE AVAILABLE]"

            if state in ("ONLINE", "CONNECTED"):
                online.append(info)
            elif state in ("OFFLINE", "DISCONNECTED"):
                offline.append(info + f" - **{state}**")
            else:
                other.append(info + f" - {state}")

        lines = [f"**Device Status** ({len(devices)} total)"]

        if offline:
            lines.append(f"\n:x: **Offline ({len(offline)}):**")
            lines.extend(offline)

        if other:
            lines.append(f"\n:warning: **Other States ({len(other)}):**")
            lines.extend(other)

        lines.append(f"\n:white_check_mark: **Online ({len(online)}):**")
        lines.extend(online[:10])  # Limit to first 10
        if len(online) > 10:
            lines.append(f"  ... and {len(online) - 10} more")

        if upgradable:
            lines.append(f"\n:arrow_up: **Firmware Updates Available:** {', '.join(upgradable)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return f"Error fetching devices: {str(e)}"


async def get_device_details(mac_address: str) -> str:
    """Get detailed information about a specific device by MAC address.

    Args:
        mac_address: Device MAC address (e.g., "00:11:22:33:44:55")

    Returns:
        Formatted string with detailed device information
    """
    api = get_controller_api()
    try:
        device = await api.get_device_by_mac(mac_address)
        if not device:
            return f"Device with MAC {mac_address} not found."

        name = device.get("name") or device.get("mac", "Unknown")
        model = device.get("model", "Unknown")
        state = device.get("state", "unknown")
        version = device.get("version", "?")
        ip = device.get("ip", "N/A")
        uptime = device.get("uptime", 0)

        # Format uptime
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"

        # System stats
        sys_stats = device.get("system-stats", {})
        cpu = sys_stats.get("cpu", "N/A")
        mem = sys_stats.get("mem", "N/A")

        lines = [
            f"**Device Details: {name}**",
            f"- Model: {model}",
            f"- State: {state}",
            f"- Firmware: {version}",
            f"- IP Address: {ip}",
            f"- Uptime: {uptime_str}",
            f"- CPU: {cpu}%",
            f"- Memory: {mem}%",
        ]

        # Check for upgrades
        if device.get("upgradable") or device.get("upgrade_to_firmware"):
            new_ver = device.get("upgrade_to_firmware", "available")
            lines.append(f"- :arrow_up: **Upgrade Available**: {new_ver}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting device details: {e}")
        return f"Error fetching device details: {str(e)}"


async def get_network_config() -> str:
    """Get network/VLAN configuration for the site.

    Returns:
        Formatted string with network configuration
    """
    api = get_controller_api()
    try:
        networks = await api.get_networks()
        if not networks:
            return "No networks configured."

        lines = [f"**Network Configuration** ({len(networks)} networks):"]

        for net in networks:
            name = net.get("name", "unnamed")
            purpose = net.get("purpose", "unknown")
            vlan = net.get("vlan", "untagged")
            subnet = net.get("ip_subnet", "N/A")
            dhcp = "enabled" if net.get("dhcpd_enabled") else "disabled"

            lines.append(f"\n**{name}** (VLAN {vlan})")
            lines.append(f"  - Purpose: {purpose}")
            lines.append(f"  - Subnet: {subnet}")
            lines.append(f"  - DHCP: {dhcp}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting network config: {e}")
        return f"Error fetching network config: {str(e)}"


async def get_wlan_config() -> str:
    """Get wireless network (SSID) configuration.

    Returns:
        Formatted string with WLAN configuration
    """
    api = get_controller_api()
    try:
        wlans = await api.get_wlans()
        if not wlans:
            return "No wireless networks configured."

        lines = [f"**Wireless Networks** ({len(wlans)} SSIDs):"]

        for wlan in wlans:
            name = wlan.get("name", "unnamed")
            enabled = wlan.get("enabled", True)
            security = wlan.get("security", "unknown")
            wpa_mode = wlan.get("wpa_mode", "")
            wpa3 = wlan.get("wpa3_support", False)
            pmf = wlan.get("pmf_mode", "unknown")
            is_guest = wlan.get("is_guest", False)
            hidden = wlan.get("hide_ssid", False)

            status = ":white_check_mark:" if enabled else ":x:"

            lines.append(f"\n{status} **{name}**")
            lines.append(f"  - Security: {security} ({wpa_mode})")

            if wpa3:
                lines.append("  - WPA3: :white_check_mark: Enabled")
            else:
                lines.append("  - WPA3: :x: Disabled")

            if pmf == "required":
                lines.append("  - PMF: :white_check_mark: Required")
            elif pmf == "optional":
                lines.append("  - PMF: :warning: Optional")
            else:
                lines.append("  - PMF: :x: Disabled")

            if is_guest:
                lines.append("  - Type: Guest Network")
            if hidden:
                lines.append("  - Hidden: Yes")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting WLAN config: {e}")
        return f"Error fetching WLAN config: {str(e)}"


async def get_firewall_rules() -> str:
    """Get firewall rules for the site.

    Returns:
        Formatted string with firewall rules
    """
    api = get_controller_api()
    try:
        rules = await api.get_firewall_rules()
        if not rules:
            return "No custom firewall rules configured."

        lines = [f"**Firewall Rules** ({len(rules)} rules):"]

        for rule in rules:
            name = rule.get("name", "unnamed")
            enabled = rule.get("enabled", True)
            action = rule.get("action", "?")
            ruleset = rule.get("ruleset", "?")

            status = ":white_check_mark:" if enabled else ":x:"
            action_icon = ":no_entry:" if action == "drop" else ":arrow_right:"

            lines.append(f"- {status} {action_icon} **{name}**: {action} ({ruleset})")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting firewall rules: {e}")
        return f"Error fetching firewall rules: {str(e)}"


async def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for WiFi, networking, and UniFi documentation.

    Args:
        query: Search query string

    Returns:
        Relevant documentation excerpts
    """
    from ..knowledge.embeddings import get_knowledge_base

    kb = get_knowledge_base()
    if kb is None:
        return "Knowledge base not initialized."

    try:
        results = await kb.search(query, n_results=3)
        if not results:
            return f"No results found for: {query}"

        lines = ["**Relevant Documentation:**\n"]
        for i, result in enumerate(results, 1):
            source = result.get("metadata", {}).get("source", "unknown")
            doc = result.get("document", "")
            # Truncate long documents
            if len(doc) > 500:
                doc = doc[:500] + "..."
            lines.append(f"**{i}. From {source}:**\n{doc}\n")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return f"Error searching knowledge base: {str(e)}"


# Tool metadata for registration
TOOL_DEFINITIONS = [
    {
        "name": "get_unifi_sites",
        "description": "Get list of all UniFi sites available",
        "parameters": {},
        "function": get_unifi_sites,
    },
    {
        "name": "get_unifi_devices",
        "description": "Get all devices for a site with status, model, firmware info",
        "parameters": {
            "site_id": {
                "type": "string",
                "description": "Optional site ID. If not provided, uses default site.",
                "required": False,
            }
        },
        "function": get_unifi_devices,
    },
    {
        "name": "get_device_details",
        "description": "Get detailed information about a specific device by MAC address",
        "parameters": {
            "mac_address": {
                "type": "string",
                "description": "Device MAC address (e.g., '00:11:22:33:44:55')",
                "required": True,
            }
        },
        "function": get_device_details,
    },
    {
        "name": "get_network_config",
        "description": "Get network/VLAN configuration for the site",
        "parameters": {},
        "function": get_network_config,
    },
    {
        "name": "get_wlan_config",
        "description": "Get wireless network (SSID) configuration including security settings",
        "parameters": {},
        "function": get_wlan_config,
    },
    {
        "name": "get_firewall_rules",
        "description": "Get firewall rules for the site",
        "parameters": {},
        "function": get_firewall_rules,
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the knowledge base for WiFi, networking, and UniFi documentation",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search query string",
                "required": True,
            }
        },
        "function": search_knowledge_base,
    },
]
