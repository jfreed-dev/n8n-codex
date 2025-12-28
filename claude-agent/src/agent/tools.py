"""MCP tools for UniFi Network operations.

These tools are registered with the Claude Agent SDK and can be invoked
by the agent to query live UniFi controller data.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from ..config import settings
from ..unifi.controller_api import UniFiControllerAPI
from ..unifi.integration_api import UniFiIntegrationAPI

logger = logging.getLogger(__name__)


# ============================================================================
# Confirmation Required Response
# ============================================================================

@dataclass
class ConfirmationRequired:
    """Returned by tools that require user confirmation before execution."""
    tool_name: str
    tool_args: dict
    risk_level: Literal["moderate", "dangerous", "critical"]
    description: str
    impact: str

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


# ============================================================================
# Additional Read Tools (Phase 1)
# ============================================================================

async def get_connected_clients(network: str | None = None, search: str | None = None) -> str:
    """Get connected clients with optional filtering.

    Args:
        network: Filter by network/SSID name (optional)
        search: Search term to filter by hostname, MAC, or IP (optional)

    Returns:
        Formatted string with client information
    """
    api = get_controller_api()
    try:
        clients = await api.get_clients()
        if not clients:
            return "No clients currently connected."

        # Apply filters
        filtered = clients
        if network:
            network_lower = network.lower()
            filtered = [c for c in filtered if network_lower in c.get("essid", "").lower()
                       or network_lower in c.get("network", "").lower()]
        if search:
            search_lower = search.lower()
            filtered = [c for c in filtered if
                       search_lower in c.get("hostname", "").lower() or
                       search_lower in c.get("mac", "").lower() or
                       search_lower in c.get("ip", "").lower()]

        if not filtered:
            return "No clients found matching the criteria."

        lines = [f"**Connected Clients** ({len(filtered)} of {len(clients)} total):"]

        for client in filtered[:20]:  # Limit to 20
            hostname = client.get("hostname") or client.get("name") or "Unknown"
            mac = client.get("mac", "?")
            ip = client.get("ip", "N/A")
            ssid = client.get("essid", "Wired")
            signal = client.get("signal", None)
            rx_bytes = client.get("rx_bytes", 0)
            tx_bytes = client.get("tx_bytes", 0)

            # Format traffic
            rx_mb = rx_bytes / (1024 * 1024)
            tx_mb = tx_bytes / (1024 * 1024)

            line = f"- **{hostname}** ({mac})"
            line += f"\n  IP: {ip} | Network: {ssid}"
            if signal:
                line += f" | Signal: {signal}dBm"
            line += f"\n  Traffic: {rx_mb:.1f}MB down / {tx_mb:.1f}MB up"
            lines.append(line)

        if len(filtered) > 20:
            lines.append(f"\n... and {len(filtered) - 20} more clients")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return f"Error fetching clients: {str(e)}"


async def get_client_details(mac_address: str) -> str:
    """Get detailed information about a specific client.

    Args:
        mac_address: Client MAC address

    Returns:
        Formatted string with client details
    """
    api = get_controller_api()
    try:
        client = await api.get_client_by_mac(mac_address)
        if not client:
            return f"Client with MAC {mac_address} not found or not currently connected."

        hostname = client.get("hostname") or client.get("name") or "Unknown"
        mac = client.get("mac", "?")
        ip = client.get("ip", "N/A")
        ssid = client.get("essid", "Wired")
        is_wired = client.get("is_wired", False)
        signal = client.get("signal")
        uptime = client.get("uptime", 0)
        rx_bytes = client.get("rx_bytes", 0)
        tx_bytes = client.get("tx_bytes", 0)
        is_guest = client.get("is_guest", False)
        blocked = client.get("blocked", False)

        # Format uptime
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"

        # Format traffic
        rx_mb = rx_bytes / (1024 * 1024)
        tx_mb = tx_bytes / (1024 * 1024)

        lines = [
            f"**Client Details: {hostname}**",
            f"- MAC: `{mac}`",
            f"- IP Address: {ip}",
            f"- Connection: {'Wired' if is_wired else f'Wireless ({ssid})'}",
        ]

        if not is_wired and signal:
            lines.append(f"- Signal Strength: {signal}dBm")

        lines.extend([
            f"- Connected For: {uptime_str}",
            f"- Traffic: {rx_mb:.1f}MB down / {tx_mb:.1f}MB up",
        ])

        if is_guest:
            lines.append("- :bust_in_silhouette: Guest Client")
        if blocked:
            lines.append("- :no_entry: **BLOCKED**")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting client details: {e}")
        return f"Error fetching client details: {str(e)}"


async def get_traffic_stats(hours: int = 24) -> str:
    """Get traffic statistics for the site.

    Args:
        hours: Number of hours of stats to retrieve (default: 24)

    Returns:
        Formatted string with traffic statistics
    """
    api = get_controller_api()
    try:
        stats = await api.get_hourly_site_stats(hours)
        if not stats:
            return "No traffic statistics available."

        # Aggregate stats
        total_rx = sum(s.get("wan-rx_bytes", 0) for s in stats)
        total_tx = sum(s.get("wan-tx_bytes", 0) for s in stats)
        total_bytes = sum(s.get("bytes", 0) for s in stats)
        avg_clients = sum(s.get("num_sta", 0) for s in stats) / len(stats) if stats else 0

        # Convert to human-readable
        def format_bytes(b):
            if b > 1024**3:
                return f"{b / 1024**3:.2f} GB"
            elif b > 1024**2:
                return f"{b / 1024**2:.2f} MB"
            else:
                return f"{b / 1024:.2f} KB"

        lines = [
            f"**Traffic Statistics** (Last {hours} hours)",
            f"- WAN Download: {format_bytes(total_rx)}",
            f"- WAN Upload: {format_bytes(total_tx)}",
            f"- Total LAN Traffic: {format_bytes(total_bytes)}",
            f"- Average Connected Clients: {avg_clients:.1f}",
        ]

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting traffic stats: {e}")
        return f"Error fetching traffic stats: {str(e)}"


async def get_dpi_stats() -> str:
    """Get Deep Packet Inspection (DPI) statistics showing traffic by application.

    Returns:
        Formatted string with DPI statistics
    """
    api = get_controller_api()
    try:
        dpi = await api.get_dpi()
        if not dpi:
            return "No DPI statistics available. DPI may be disabled."

        # Sort by total traffic
        sorted_dpi = sorted(dpi, key=lambda x: x.get("rx_bytes", 0) + x.get("tx_bytes", 0), reverse=True)

        lines = ["**Application Traffic (DPI)**"]

        for entry in sorted_dpi[:15]:  # Top 15
            app = entry.get("app", "Unknown")
            cat = entry.get("cat", "Unknown")
            rx = entry.get("rx_bytes", 0) / (1024 * 1024)
            tx = entry.get("tx_bytes", 0) / (1024 * 1024)

            lines.append(f"- **{app}** ({cat}): {rx:.1f}MB down / {tx:.1f}MB up")

        if len(sorted_dpi) > 15:
            lines.append(f"\n... and {len(sorted_dpi) - 15} more categories")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting DPI stats: {e}")
        return f"Error fetching DPI stats: {str(e)}"


async def get_top_clients(limit: int = 10, metric: str = "rx_bytes") -> str:
    """Get top clients by traffic usage.

    Args:
        limit: Number of top clients to return (default: 10)
        metric: Metric to sort by - "rx_bytes" (download) or "tx_bytes" (upload)

    Returns:
        Formatted string with top clients
    """
    api = get_controller_api()
    try:
        clients = await api.get_clients()
        if not clients:
            return "No clients currently connected."

        # Sort by metric
        sorted_clients = sorted(clients, key=lambda x: x.get(metric, 0), reverse=True)

        metric_label = "Download" if metric == "rx_bytes" else "Upload"
        lines = [f"**Top {min(limit, len(sorted_clients))} Clients by {metric_label}**"]

        for i, client in enumerate(sorted_clients[:limit], 1):
            hostname = client.get("hostname") or client.get("name") or "Unknown"
            mac = client.get("mac", "?")
            rx = client.get("rx_bytes", 0) / (1024 * 1024)
            tx = client.get("tx_bytes", 0) / (1024 * 1024)

            lines.append(f"{i}. **{hostname}** ({mac}): {rx:.1f}MB down / {tx:.1f}MB up")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting top clients: {e}")
        return f"Error fetching top clients: {str(e)}"


async def get_recent_events(hours: int = 24, event_type: str | None = None) -> str:
    """Get recent network events.

    Args:
        hours: Number of hours of events to retrieve (default: 24)
        event_type: Filter by event type (optional)

    Returns:
        Formatted string with recent events
    """
    api = get_controller_api()
    try:
        events = await api.get_events(hours)
        if not events:
            return f"No events in the last {hours} hours."

        # Filter by type if specified
        if event_type:
            type_lower = event_type.lower()
            events = [e for e in events if type_lower in e.get("key", "").lower()]

        if not events:
            return f"No events matching '{event_type}' in the last {hours} hours."

        lines = [f"**Recent Events** (Last {hours} hours, showing up to 20)"]

        for event in events[:20]:
            key = event.get("key", "unknown")
            msg = event.get("msg", "No message")
            time_str = event.get("datetime", "?")

            # Determine icon based on event type
            if "connected" in key.lower() or "up" in key.lower():
                icon = ":white_check_mark:"
            elif "disconnected" in key.lower() or "down" in key.lower():
                icon = ":x:"
            elif "upgrade" in key.lower():
                icon = ":arrow_up:"
            elif "error" in key.lower() or "fail" in key.lower():
                icon = ":warning:"
            else:
                icon = ":information_source:"

            lines.append(f"- {icon} `{key}`: {msg}")

        if len(events) > 20:
            lines.append(f"\n... and {len(events) - 20} more events")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return f"Error fetching events: {str(e)}"


async def get_alarms(include_archived: bool = False) -> str:
    """Get active network alarms.

    Args:
        include_archived: Whether to include archived/resolved alarms

    Returns:
        Formatted string with alarms
    """
    api = get_controller_api()
    try:
        alarms = await api.get_alarms()
        if not alarms:
            return ":white_check_mark: No active alarms."

        # Filter by archived status
        if not include_archived:
            alarms = [a for a in alarms if not a.get("archived", False)]

        if not alarms:
            return ":white_check_mark: No active alarms (some archived alarms exist)."

        lines = [f"**Active Alarms** ({len(alarms)} total)"]

        for alarm in alarms[:20]:
            key = alarm.get("key", "unknown")
            msg = alarm.get("msg", "No message")
            time_str = alarm.get("datetime", "?")
            archived = alarm.get("archived", False)

            status = ":white_check_mark: Resolved" if archived else ":rotating_light: Active"
            lines.append(f"- {status} **{key}**")
            lines.append(f"  {msg}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error getting alarms: {e}")
        return f"Error fetching alarms: {str(e)}"


# ============================================================================
# Administrative Tools (Phase 3 - Require Confirmation)
# ============================================================================

# Global reference to confirmation store (set by handler.py)
_confirmation_store = None


def set_confirmation_store(store):
    """Set the confirmation store for admin tools to use."""
    global _confirmation_store
    _confirmation_store = store


def get_confirmation_store():
    """Get the confirmation store."""
    return _confirmation_store


async def device_admin_command(
    mac_address: str,
    command: str,
    confirm_token: str | None = None
) -> str | ConfirmationRequired:
    """Execute an administrative command on a device.

    Args:
        mac_address: Device MAC address
        command: Command to execute (restart, locate, upgrade, adopt, forget)
        confirm_token: Confirmation token (provided after user approval)

    Returns:
        Result string or ConfirmationRequired if confirmation needed
    """
    api = get_controller_api()

    # Define risk levels for each command
    risk_map = {
        "locate": None,  # Safe - no confirmation needed
        "restart": "moderate",
        "adopt": "moderate",
        "upgrade": "dangerous",
        "forget": "critical",
        "delete": "critical",
    }

    impact_map = {
        "locate": None,
        "restart": "Device will reboot. Connected clients will be disconnected for ~1-2 minutes.",
        "adopt": "Device will be adopted and added to your controller.",
        "upgrade": "Firmware upgrade will begin. Device will be unavailable for several minutes during the upgrade.",
        "forget": "Device will be removed from the controller. You will need to re-adopt it to manage it again.",
        "delete": "Device will be removed from the controller. You will need to re-adopt it to manage it again.",
    }

    cmd = command.lower()
    risk_level = risk_map.get(cmd)

    # Validate command
    if cmd not in risk_map:
        return f"Unknown command: {command}. Valid commands: locate, restart, adopt, upgrade, forget"

    # Safe commands execute immediately
    if risk_level is None:
        try:
            await api.device_command(mac_address, cmd)
            return f":flashlight: LED on device {mac_address} is now blinking for identification."
        except Exception as e:
            return f"Error executing command: {str(e)}"

    # Commands requiring confirmation
    if confirm_token is None:
        # Return confirmation required
        return ConfirmationRequired(
            tool_name="device_admin_command",
            tool_args={"mac_address": mac_address, "command": command},
            risk_level=risk_level,
            description=f"{command.title()} device {mac_address}",
            impact=impact_map.get(cmd, "This action may affect network connectivity."),
        )

    # Verify token and execute
    store = get_confirmation_store()
    if store is None:
        return "Error: Confirmation system not initialized."

    valid_args = store.validate_token("device_admin_command", confirm_token)
    if not valid_args:
        return "Error: Invalid or expired confirmation token. Please request the action again."

    try:
        # Map 'forget' to 'delete' for the API
        api_cmd = "delete" if cmd == "forget" else cmd
        await api.device_command(mac_address, api_cmd)

        result_messages = {
            "restart": f":arrows_counterclockwise: Device {mac_address} is restarting.",
            "adopt": f":heavy_plus_sign: Device {mac_address} is being adopted.",
            "upgrade": f":arrow_up: Firmware upgrade started on {mac_address}.",
            "forget": f":wastebasket: Device {mac_address} has been removed from the controller.",
            "delete": f":wastebasket: Device {mac_address} has been removed from the controller.",
        }
        return result_messages.get(cmd, f"Command {command} executed on {mac_address}.")
    except Exception as e:
        return f"Error executing {command}: {str(e)}"


async def client_admin_command(
    mac_address: str,
    command: str,
    confirm_token: str | None = None
) -> str | ConfirmationRequired:
    """Execute an administrative command on a client.

    Args:
        mac_address: Client MAC address
        command: Command to execute (kick, block, unblock)
        confirm_token: Confirmation token (provided after user approval)

    Returns:
        Result string or ConfirmationRequired if confirmation needed
    """
    api = get_controller_api()

    risk_map = {
        "unblock": None,  # Safe - no confirmation needed
        "kick": "moderate",
        "block": "dangerous",
    }

    impact_map = {
        "unblock": None,
        "kick": "Client will be disconnected but can reconnect immediately.",
        "block": "Client will be permanently blocked from the network until manually unblocked.",
    }

    cmd = command.lower()
    risk_level = risk_map.get(cmd)

    if cmd not in risk_map:
        return f"Unknown command: {command}. Valid commands: kick, block, unblock"

    # Safe commands execute immediately
    if risk_level is None:
        try:
            await api.client_command(mac_address, cmd)
            return f":white_check_mark: Client {mac_address} has been unblocked."
        except Exception as e:
            return f"Error executing command: {str(e)}"

    # Commands requiring confirmation
    if confirm_token is None:
        return ConfirmationRequired(
            tool_name="client_admin_command",
            tool_args={"mac_address": mac_address, "command": command},
            risk_level=risk_level,
            description=f"{command.title()} client {mac_address}",
            impact=impact_map.get(cmd, "This action will affect the client's network access."),
        )

    # Verify token and execute
    store = get_confirmation_store()
    if store is None:
        return "Error: Confirmation system not initialized."

    valid_args = store.validate_token("client_admin_command", confirm_token)
    if not valid_args:
        return "Error: Invalid or expired confirmation token. Please request the action again."

    try:
        await api.client_command(mac_address, cmd)

        result_messages = {
            "kick": f":boot: Client {mac_address} has been disconnected.",
            "block": f":no_entry: Client {mac_address} has been blocked.",
        }
        return result_messages.get(cmd, f"Command {command} executed on {mac_address}.")
    except Exception as e:
        return f"Error executing {command}: {str(e)}"


async def create_guest_access(
    mac_address: str,
    minutes: int = 60,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
) -> str:
    """Create guest access for a client (no confirmation required).

    Args:
        mac_address: Client MAC address to authorize
        minutes: Access duration in minutes (default: 60)
        upload_limit_kbps: Upload speed limit in Kbps (optional)
        download_limit_kbps: Download speed limit in Kbps (optional)

    Returns:
        Result string
    """
    api = get_controller_api()
    try:
        await api.authorize_guest(
            mac=mac_address,
            minutes=minutes,
            up_kbps=upload_limit_kbps,
            down_kbps=download_limit_kbps,
        )

        duration = f"{minutes} minutes" if minutes < 60 else f"{minutes // 60} hours"
        limits = []
        if download_limit_kbps:
            limits.append(f"{download_limit_kbps} Kbps down")
        if upload_limit_kbps:
            limits.append(f"{upload_limit_kbps} Kbps up")

        msg = f":ticket: Guest access granted to {mac_address} for {duration}"
        if limits:
            msg += f" (limits: {', '.join(limits)})"

        return msg
    except Exception as e:
        return f"Error creating guest access: {str(e)}"


async def update_wlan_settings(
    wlan_name: str,
    enabled: bool | None = None,
    password: str | None = None,
    confirm_token: str | None = None
) -> str | ConfirmationRequired:
    """Update WLAN settings.

    Args:
        wlan_name: Name of the WLAN (SSID) to modify
        enabled: Set to True/False to enable/disable the WLAN
        password: New password for the WLAN
        confirm_token: Confirmation token (provided after user approval)

    Returns:
        Result string or ConfirmationRequired if confirmation needed
    """
    api = get_controller_api()

    # Determine risk level based on changes
    if password is not None:
        risk_level = "dangerous"
        description = f"Change password for WLAN '{wlan_name}'"
        impact = "All clients will be disconnected and must reconnect with the new password."
    elif enabled is False:
        risk_level = "moderate"
        description = f"Disable WLAN '{wlan_name}'"
        impact = "All clients connected to this SSID will be disconnected."
    elif enabled is True:
        risk_level = None  # Safe
        description = f"Enable WLAN '{wlan_name}'"
        impact = None
    else:
        return "No changes specified. Provide 'enabled' or 'password' parameter."

    # Safe operations execute immediately
    if risk_level is None:
        try:
            wlan = await api.get_wlan_by_name(wlan_name)
            if not wlan:
                return f"WLAN '{wlan_name}' not found."
            await api.update_wlan(wlan["_id"], enabled=True)
            return f":white_check_mark: WLAN '{wlan_name}' has been enabled."
        except Exception as e:
            return f"Error updating WLAN: {str(e)}"

    # Operations requiring confirmation
    if confirm_token is None:
        return ConfirmationRequired(
            tool_name="update_wlan_settings",
            tool_args={
                "wlan_name": wlan_name,
                "enabled": enabled,
                "password": password,
            },
            risk_level=risk_level,
            description=description,
            impact=impact,
        )

    # Verify token and execute
    store = get_confirmation_store()
    if store is None:
        return "Error: Confirmation system not initialized."

    valid_args = store.validate_token("update_wlan_settings", confirm_token)
    if not valid_args:
        return "Error: Invalid or expired confirmation token. Please request the action again."

    try:
        wlan = await api.get_wlan_by_name(wlan_name)
        if not wlan:
            return f"WLAN '{wlan_name}' not found."

        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if password is not None:
            updates["x_passphrase"] = password

        await api.update_wlan(wlan["_id"], **updates)

        if password is not None:
            return f":key: Password changed for WLAN '{wlan_name}'."
        elif enabled is False:
            return f":no_entry: WLAN '{wlan_name}' has been disabled."
        else:
            return f"WLAN '{wlan_name}' updated successfully."
    except Exception as e:
        return f"Error updating WLAN: {str(e)}"


async def update_firewall_rule_settings(
    rule_name: str,
    enabled: bool | None = None,
    confirm_token: str | None = None
) -> str | ConfirmationRequired:
    """Enable or disable a firewall rule.

    Args:
        rule_name: Name of the firewall rule to modify
        enabled: Set to True/False to enable/disable the rule
        confirm_token: Confirmation token (provided after user approval)

    Returns:
        Result string or ConfirmationRequired if confirmation needed
    """
    api = get_controller_api()

    if enabled is None:
        return "No changes specified. Provide 'enabled' parameter."

    risk_level = "dangerous"
    action = "Enable" if enabled else "Disable"
    description = f"{action} firewall rule '{rule_name}'"
    impact = "Changing firewall rules may affect network security and traffic flow."

    if confirm_token is None:
        return ConfirmationRequired(
            tool_name="update_firewall_rule_settings",
            tool_args={"rule_name": rule_name, "enabled": enabled},
            risk_level=risk_level,
            description=description,
            impact=impact,
        )

    # Verify token and execute
    store = get_confirmation_store()
    if store is None:
        return "Error: Confirmation system not initialized."

    valid_args = store.validate_token("update_firewall_rule_settings", confirm_token)
    if not valid_args:
        return "Error: Invalid or expired confirmation token. Please request the action again."

    try:
        rule = await api.get_firewall_rule_by_name(rule_name)
        if not rule:
            return f"Firewall rule '{rule_name}' not found."

        await api.update_firewall_rule(rule["_id"], enabled=enabled)

        icon = ":white_check_mark:" if enabled else ":no_entry:"
        status = "enabled" if enabled else "disabled"
        return f"{icon} Firewall rule '{rule_name}' has been {status}."
    except Exception as e:
        return f"Error updating firewall rule: {str(e)}"


# Tool metadata for registration
TOOL_DEFINITIONS = [
    # ========== Existing Read Tools ==========
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
    # ========== New Read Tools (Phase 1) ==========
    {
        "name": "get_connected_clients",
        "description": "Get connected clients with optional filtering by network or search term",
        "parameters": {
            "network": {
                "type": "string",
                "description": "Filter by network/SSID name",
                "required": False,
            },
            "search": {
                "type": "string",
                "description": "Search term to filter by hostname, MAC, or IP",
                "required": False,
            },
        },
        "function": get_connected_clients,
    },
    {
        "name": "get_client_details",
        "description": "Get detailed information about a specific client by MAC address",
        "parameters": {
            "mac_address": {
                "type": "string",
                "description": "Client MAC address (e.g., '00:11:22:33:44:55')",
                "required": True,
            }
        },
        "function": get_client_details,
    },
    {
        "name": "get_traffic_stats",
        "description": "Get traffic statistics (bandwidth usage, client counts) for the site",
        "parameters": {
            "hours": {
                "type": "integer",
                "description": "Number of hours of stats to retrieve (default: 24)",
                "required": False,
            }
        },
        "function": get_traffic_stats,
    },
    {
        "name": "get_dpi_stats",
        "description": "Get Deep Packet Inspection statistics showing traffic by application category",
        "parameters": {},
        "function": get_dpi_stats,
    },
    {
        "name": "get_top_clients",
        "description": "Get top clients by traffic usage",
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Number of top clients to return (default: 10)",
                "required": False,
            },
            "metric": {
                "type": "string",
                "description": "Metric to sort by: 'rx_bytes' (download) or 'tx_bytes' (upload)",
                "required": False,
            },
        },
        "function": get_top_clients,
    },
    {
        "name": "get_recent_events",
        "description": "Get recent network events (device connections, disconnections, alerts)",
        "parameters": {
            "hours": {
                "type": "integer",
                "description": "Number of hours of events to retrieve (default: 24)",
                "required": False,
            },
            "event_type": {
                "type": "string",
                "description": "Filter by event type keyword",
                "required": False,
            },
        },
        "function": get_recent_events,
    },
    {
        "name": "get_alarms",
        "description": "Get active network alarms",
        "parameters": {
            "include_archived": {
                "type": "boolean",
                "description": "Whether to include archived/resolved alarms (default: false)",
                "required": False,
            }
        },
        "function": get_alarms,
    },
    # ========== Administrative Tools (Phase 3) ==========
    {
        "name": "device_admin_command",
        "description": "Execute administrative commands on a device: restart, locate (blink LED), upgrade firmware, adopt, or forget. Dangerous operations require confirmation.",
        "parameters": {
            "mac_address": {
                "type": "string",
                "description": "Device MAC address",
                "required": True,
            },
            "command": {
                "type": "string",
                "description": "Command: 'locate' (safe), 'restart' (moderate), 'adopt' (moderate), 'upgrade' (dangerous), 'forget' (critical)",
                "required": True,
            },
            "confirm_token": {
                "type": "string",
                "description": "Confirmation token (system-provided after user approval)",
                "required": False,
            },
        },
        "function": device_admin_command,
    },
    {
        "name": "client_admin_command",
        "description": "Execute administrative commands on a client: kick (disconnect), block (permanent), or unblock. Dangerous operations require confirmation.",
        "parameters": {
            "mac_address": {
                "type": "string",
                "description": "Client MAC address",
                "required": True,
            },
            "command": {
                "type": "string",
                "description": "Command: 'unblock' (safe), 'kick' (moderate), 'block' (dangerous)",
                "required": True,
            },
            "confirm_token": {
                "type": "string",
                "description": "Confirmation token (system-provided after user approval)",
                "required": False,
            },
        },
        "function": client_admin_command,
    },
    {
        "name": "create_guest_access",
        "description": "Create temporary guest access for a client (safe, no confirmation needed)",
        "parameters": {
            "mac_address": {
                "type": "string",
                "description": "Client MAC address to authorize",
                "required": True,
            },
            "minutes": {
                "type": "integer",
                "description": "Access duration in minutes (default: 60)",
                "required": False,
            },
            "upload_limit_kbps": {
                "type": "integer",
                "description": "Upload speed limit in Kbps",
                "required": False,
            },
            "download_limit_kbps": {
                "type": "integer",
                "description": "Download speed limit in Kbps",
                "required": False,
            },
        },
        "function": create_guest_access,
    },
    {
        "name": "update_wlan_settings",
        "description": "Update WLAN settings: enable/disable SSID or change password. Disabling or changing password requires confirmation.",
        "parameters": {
            "wlan_name": {
                "type": "string",
                "description": "Name of the WLAN (SSID) to modify",
                "required": True,
            },
            "enabled": {
                "type": "boolean",
                "description": "Set to true/false to enable/disable the WLAN",
                "required": False,
            },
            "password": {
                "type": "string",
                "description": "New password for the WLAN",
                "required": False,
            },
            "confirm_token": {
                "type": "string",
                "description": "Confirmation token (system-provided after user approval)",
                "required": False,
            },
        },
        "function": update_wlan_settings,
    },
    {
        "name": "update_firewall_rule_settings",
        "description": "Enable or disable a firewall rule. Requires confirmation due to security implications.",
        "parameters": {
            "rule_name": {
                "type": "string",
                "description": "Name of the firewall rule to modify",
                "required": True,
            },
            "enabled": {
                "type": "boolean",
                "description": "Set to true/false to enable/disable the rule",
                "required": True,
            },
            "confirm_token": {
                "type": "string",
                "description": "Confirmation token (system-provided after user approval)",
                "required": False,
            },
        },
        "function": update_firewall_rule_settings,
    },
]
