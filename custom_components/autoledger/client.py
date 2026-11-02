"""REST client for the AutoLedger add-on API (docs/api.md)."""

from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)


class AutoLedgerError(Exception):
    """The add-on answered with an error."""


class AutoLedgerConnectionError(AutoLedgerError):
    """The add-on could not be reached."""


class AutoLedgerAuthError(AutoLedgerError):
    """The token was refused."""


class AutoLedgerClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.url = url.rstrip("/")
        self._token = token

    async def _request(self, method: str, path: str, json: Any = None, params: dict | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self.url}/api/v1{path}",
                json=json,
                params=params,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise AutoLedgerAuthError("The AutoLedger add-on refused the token")
                data = await response.json(content_type=None) if response.status != 204 else None
                if response.status >= 400:
                    message = (data or {}).get("error", {}).get("message", response.reason)
                    raise AutoLedgerError(f"{response.status}: {message}")
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AutoLedgerConnectionError(f"Cannot reach the AutoLedger add-on at {self.url}: {err}") from err

    async def info(self) -> dict:
        return await self._request("GET", "/info")

    async def settings(self) -> dict:
        return await self._request("GET", "/settings")

    async def vehicles(self) -> list[dict]:
        return (await self._request("GET", "/vehicles"))["items"]

    async def summary(self) -> dict:
        return await self._request("GET", "/summary")

    async def ingest(self, events: list[dict]) -> dict:
        return await self._request("POST", "/ingest", json={"events": events})

    async def create(self, resource: str, body: dict) -> dict:
        return await self._request("POST", f"/{resource}", json=body)
