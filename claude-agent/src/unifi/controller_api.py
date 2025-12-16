"""UniFi Local Controller API client.

Uses cookie-based session authentication for full access to configuration.
API Reference: https://ubntwiki.com/products/software/unifi-controller/api
"""

import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)


class UniFiControllerAPI:
    """Client for UniFi Local Controller API with cookie authentication."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        site: str = "default",
        verify_ssl: bool = False,
    ):
        """Initialize the API client.

        Args:
            base_url: UniFi controller URL (e.g., https://192.168.1.1)
            username: UniFi controller username
            password: UniFi controller password
            site: Site name (default: "default")
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.site = site
        self.verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False
        self._csrf_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with cookie jar."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Accept": "application/json"},
                verify=self.verify_ssl,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._authenticated = False
            self._csrf_token = None

    async def authenticate(self) -> bool:
        """Authenticate with the controller and store session cookie.

        Returns:
            True if authentication succeeded
        """
        client = await self._get_client()
        url = f"{self.base_url}/api/auth/login"

        logger.debug(f"Authenticating to {url}")
        response = await client.post(
            url,
            json={"username": self.username, "password": self.password},
        )

        if response.status_code == 200:
            self._authenticated = True
            # Capture CSRF token from response headers (required for write operations on UniFi OS)
            self._csrf_token = response.headers.get("x-csrf-token")
            if self._csrf_token:
                logger.info(f"Successfully authenticated with UniFi controller (CSRF token captured)")
            else:
                logger.info("Successfully authenticated with UniFi controller (no CSRF token in response)")
            return True

        logger.error(f"Authentication failed: {response.status_code}")
        return False

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make an authenticated API request."""
        if not self._authenticated:
            await self.authenticate()

        client = await self._get_client()
        url = f"{self.base_url}/proxy/network/api/s/{self.site}{path}"

        # Add CSRF token header for write operations (required by UniFi OS)
        if method.upper() in ("POST", "PUT", "DELETE") and self._csrf_token:
            headers = kwargs.get("headers", {})
            headers["x-csrf-token"] = self._csrf_token
            kwargs["headers"] = headers
            logger.debug(f"API request: {method} {url} (with CSRF token)")
        else:
            logger.debug(f"API request: {method} {url}")

        response = await client.request(method, url, **kwargs)

        # Re-authenticate if session expired or forbidden (CSRF token may have expired)
        if response.status_code in (401, 403):
            logger.info(f"Request returned {response.status_code}, re-authenticating")
            self._authenticated = False
            await self.authenticate()
            # Re-add CSRF token after re-authentication
            if method.upper() in ("POST", "PUT", "DELETE") and self._csrf_token:
                headers = kwargs.get("headers", {})
                headers["x-csrf-token"] = self._csrf_token
                kwargs["headers"] = headers
            response = await client.request(method, url, **kwargs)

        response.raise_for_status()
        return response.json()

    async def get_networks(self) -> list[dict[str, Any]]:
        """Get network/VLAN configuration.

        Returns:
            List of network objects with name, vlan, purpose, etc.
        """
        result = await self._request("GET", "/rest/networkconf")
        return result.get("data", [])

    async def get_wlans(self) -> list[dict[str, Any]]:
        """Get wireless network (SSID) configuration.

        Returns:
            List of WLAN objects with name, security, wpa_mode, pmf_mode, etc.
        """
        result = await self._request("GET", "/rest/wlanconf")
        return result.get("data", [])

    async def get_firewall_rules(self) -> list[dict[str, Any]]:
        """Get firewall rules.

        Returns:
            List of firewall rule objects with name, action, etc.
        """
        result = await self._request("GET", "/rest/firewallrule")
        return result.get("data", [])

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get detailed device statistics.

        Returns:
            List of device objects with detailed stats including system-stats.
        """
        result = await self._request("GET", "/stat/device")
        return result.get("data", [])

    async def get_device_by_mac(self, mac: str) -> dict[str, Any] | None:
        """Get a specific device by MAC address.

        Args:
            mac: Device MAC address (e.g., "00:11:22:33:44:55")

        Returns:
            Device object or None if not found
        """
        devices = await self.get_devices()
        mac_normalized = mac.lower().replace("-", ":")
        for device in devices:
            if device.get("mac", "").lower() == mac_normalized:
                return device
        return None

    async def get_health(self) -> list[dict[str, Any]]:
        """Get site health metrics.

        Returns:
            List of health subsystem objects.
        """
        result = await self._request("GET", "/stat/health")
        return result.get("data", [])

    async def get_settings(self) -> list[dict[str, Any]]:
        """Get site settings.

        Returns:
            List of settings objects.
        """
        result = await self._request("GET", "/rest/setting")
        return result.get("data", [])

    # =========================================================================
    # Additional Read Methods (Phase 1)
    # =========================================================================

    async def get_clients(self) -> list[dict[str, Any]]:
        """Get all connected clients.

        Returns:
            List of client objects with MAC, IP, hostname, signal, traffic, etc.
        """
        result = await self._request("GET", "/stat/sta")
        return result.get("data", [])

    async def get_client_by_mac(self, mac: str) -> dict[str, Any] | None:
        """Get a specific client by MAC address.

        Args:
            mac: Client MAC address (e.g., "00:11:22:33:44:55")

        Returns:
            Client object or None if not found
        """
        clients = await self.get_clients()
        mac_normalized = mac.lower().replace("-", ":")
        for client in clients:
            if client.get("mac", "").lower() == mac_normalized:
                return client
        return None

    async def get_events(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get recent events.

        Args:
            hours: Number of hours of events to retrieve (default: 24)

        Returns:
            List of event objects
        """
        import time
        start = int((time.time() - hours * 3600) * 1000)
        result = await self._request("GET", f"/stat/event?start={start}")
        return result.get("data", [])

    async def get_alarms(self) -> list[dict[str, Any]]:
        """Get active alarms.

        Returns:
            List of alarm objects
        """
        result = await self._request("GET", "/stat/alarm")
        return result.get("data", [])

    async def get_dpi(self) -> list[dict[str, Any]]:
        """Get DPI (Deep Packet Inspection) statistics.

        Returns:
            List of DPI statistics by application category
        """
        result = await self._request("GET", "/stat/dpi")
        return result.get("data", [])

    async def get_hourly_site_stats(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get hourly traffic statistics for the site.

        Args:
            hours: Number of hours of stats to retrieve (default: 24)

        Returns:
            List of hourly statistics objects
        """
        attrs = ["bytes", "wan-tx_bytes", "wan-rx_bytes", "num_sta"]
        result = await self._request(
            "POST",
            "/stat/report/hourly.site",
            json={"attrs": attrs, "n": hours}
        )
        return result.get("data", [])

    # =========================================================================
    # Write Methods (Phase 3 - Administrative Actions)
    # =========================================================================

    async def device_command(self, mac: str, cmd: str) -> dict[str, Any]:
        """Send a command to a device.

        Args:
            mac: Device MAC address
            cmd: Command to execute:
                - "restart": Reboot the device
                - "locate": Blink LED for identification
                - "upgrade": Start firmware upgrade
                - "adopt": Adopt the device
                - "delete": Forget/remove the device

        Returns:
            API response dict
        """
        result = await self._request(
            "POST",
            "/cmd/devmgr",
            json={"mac": mac, "cmd": cmd}
        )
        return result

    async def client_command(self, mac: str, cmd: str) -> dict[str, Any]:
        """Send a command for a client.

        Args:
            mac: Client MAC address
            cmd: Command to execute:
                - "kick": Disconnect the client (can reconnect)
                - "block": Permanently block the client
                - "unblock": Remove from block list

        Returns:
            API response dict
        """
        result = await self._request(
            "POST",
            "/cmd/stamgr",
            json={"mac": mac, "cmd": f"{cmd}-sta"}
        )
        return result

    async def authorize_guest(
        self,
        mac: str,
        minutes: int = 60,
        up_kbps: int | None = None,
        down_kbps: int | None = None,
        bytes_quota: int | None = None,
    ) -> dict[str, Any]:
        """Authorize a guest client.

        Args:
            mac: Client MAC address
            minutes: Authorization duration in minutes
            up_kbps: Upload rate limit in Kbps (optional)
            down_kbps: Download rate limit in Kbps (optional)
            bytes_quota: Data quota in bytes (optional)

        Returns:
            API response dict
        """
        payload: dict[str, Any] = {
            "mac": mac,
            "cmd": "authorize-guest",
            "minutes": minutes
        }
        if up_kbps is not None:
            payload["up"] = up_kbps
        if down_kbps is not None:
            payload["down"] = down_kbps
        if bytes_quota is not None:
            payload["bytes"] = bytes_quota

        result = await self._request("POST", "/cmd/stamgr", json=payload)
        return result

    async def update_wlan(self, wlan_id: str, **updates) -> dict[str, Any]:
        """Update WLAN configuration.

        Args:
            wlan_id: The WLAN's _id field
            **updates: Fields to update (e.g., enabled=True, x_passphrase="newpass")

        Returns:
            API response dict
        """
        result = await self._request(
            "PUT",
            f"/rest/wlanconf/{wlan_id}",
            json=updates
        )
        return result

    async def get_wlan_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a WLAN by its name.

        Args:
            name: WLAN name (SSID)

        Returns:
            WLAN object or None if not found
        """
        wlans = await self.get_wlans()
        for wlan in wlans:
            if wlan.get("name", "").lower() == name.lower():
                return wlan
        return None

    async def update_firewall_rule(self, rule_id: str, **updates) -> dict[str, Any]:
        """Update a firewall rule.

        Args:
            rule_id: The rule's _id field
            **updates: Fields to update (e.g., enabled=True)

        Returns:
            API response dict
        """
        result = await self._request(
            "PUT",
            f"/rest/firewallrule/{rule_id}",
            json=updates
        )
        return result

    async def get_firewall_rule_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a firewall rule by its name.

        Args:
            name: Firewall rule name

        Returns:
            Rule object or None if not found
        """
        rules = await self.get_firewall_rules()
        for rule in rules:
            if rule.get("name", "").lower() == name.lower():
                return rule
        return None
