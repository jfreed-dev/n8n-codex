"""UniFi Integration API client.

Uses X-API-KEY header authentication for read-only access to sites and devices.
API Reference: https://developer.ui.com/site-manager-api/gettingstarted
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class UniFiIntegrationAPI:
    """Client for UniFi Network Integration API."""

    def __init__(self, base_url: str, api_token: str, verify_ssl: bool = False):
        """Initialize the API client.

        Args:
            base_url: UniFi controller URL (e.g., https://192.168.1.1)
            api_token: Integration API token from UniFi Network Application
            verify_ssl: Whether to verify SSL certificates (False for self-signed)
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "X-API-KEY": self.api_token,
                    "Accept": "application/json",
                },
                verify=self.verify_ssl,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make an API request."""
        client = await self._get_client()
        url = f"{self.base_url}/proxy/network/integration/v1{path}"

        logger.debug(f"API request: {method} {url}")
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()

        return response.json()

    async def get_sites(self) -> list[dict[str, Any]]:
        """Get all UniFi sites.

        Returns:
            List of site objects with id, internalReference, name, etc.
        """
        result = await self._request("GET", "/sites")
        return result.get("data", [])

    async def get_devices(self, site_id: str) -> list[dict[str, Any]]:
        """Get all devices for a site.

        Args:
            site_id: The site ID (UUID from get_sites)

        Returns:
            List of device objects with name, mac, state, model, version, etc.
        """
        result = await self._request("GET", f"/sites/{site_id}/devices")
        return result.get("data", [])

    async def get_site_by_reference(self, reference: str = "default") -> dict[str, Any] | None:
        """Get a site by its internal reference name.

        Args:
            reference: Site internal reference (e.g., "default")

        Returns:
            Site object or None if not found
        """
        sites = await self.get_sites()
        for site in sites:
            if site.get("internalReference") == reference:
                return site
        return sites[0] if sites else None
