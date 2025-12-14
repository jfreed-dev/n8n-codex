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
            logger.info("Successfully authenticated with UniFi controller")
            return True

        logger.error(f"Authentication failed: {response.status_code}")
        return False

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make an authenticated API request."""
        if not self._authenticated:
            await self.authenticate()

        client = await self._get_client()
        url = f"{self.base_url}/proxy/network/api/s/{self.site}{path}"

        logger.debug(f"API request: {method} {url}")
        response = await client.request(method, url, **kwargs)

        # Re-authenticate if session expired
        if response.status_code == 401:
            logger.info("Session expired, re-authenticating")
            self._authenticated = False
            await self.authenticate()
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
