"""Announce the add-on to Home Assistant through the Supervisor discovery API.

The Collector integration receives the announcement as a ``hassio`` discovery
and can set itself up without asking for a URL or token. When the Supervisor
is not available (or refuses), the Collector falls back to manual setup.
"""

import json
import logging
import os
import socket
import urllib.error
import urllib.request

_LOGGER = logging.getLogger(__name__)
SERVICE = "autoledger"


def announce(port: int, token: str) -> bool:
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return False
    body = json.dumps(
        {"service": SERVICE, "config": {"host": socket.gethostname(), "port": port, "token": token}}
    ).encode()
    request = urllib.request.Request(
        "http://supervisor/discovery",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {supervisor_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            _LOGGER.info("Announced to Home Assistant (status %s)", response.status)
            return True
    except (urllib.error.URLError, OSError) as err:
        _LOGGER.warning("Could not announce to Home Assistant, set up the Collector manually: %s", err)
        return False
