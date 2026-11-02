"""Access control for the API.

Requests through Ingress arrive from the Supervisor (172.30.32.2) after Home
Assistant has authenticated the user. Every other caller needs the bearer token.
"""

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

INGRESS_PEERS = frozenset({"172.30.32.2"})
OPEN_PATHS = frozenset({"/api/v1/health"})


def is_ingress(request: Request) -> bool:
    return request.client is not None and request.client.host in INGRESS_PEERS


def is_trusted(request: Request) -> bool:
    """Ingress or dev mode: the caller is a logged-in Home Assistant user."""
    return request.app.state.config.dev or is_ingress(request)


def has_valid_token(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token, request.app.state.token)


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        if not (is_trusted(request) or has_valid_token(request)):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "Open AutoLedger from the Home Assistant sidebar, "
                        "or send the API token as a bearer token.",
                    }
                },
            )
    return await call_next(request)
