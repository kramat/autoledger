"""FastAPI application factory."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, discovery
from .api import data, export, inbox, reports, resources, schedules, summary, system, trips
from .auth import auth_middleware
from .config import Config, load_config
from .db import make_engine
from .migrate import run_migrations
from .settings_store import load_token

_LOGGER = logging.getLogger(__name__)
API_PREFIX = "/api/v1"

_ERROR_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict"}


def create_app(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(config.db_path)
    run_migrations(config, engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await asyncio.to_thread(discovery.announce, config.port, app.state.token)
        yield
        engine.dispose()

    app = FastAPI(
        title="AutoLedger",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.state.config = config
    app.state.sessions = sessionmaker(engine, expire_on_commit=False)
    app.state.token = load_token(config.secret_path)

    app.middleware("http")(auth_middleware)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)

    for router in (system.router, summary.router, reports.router, export.router, data.router, inbox.router,
                   *trips.ROUTERS, *schedules.ROUTERS,
                   *resources.ROUTERS):
        app.include_router(router, prefix=API_PREFIX)

    if config.static_dir and config.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=config.static_dir, html=True), name="static")
    else:
        _LOGGER.warning("No frontend build found; serving the API only")

    return app


async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _ERROR_CODES.get(exc.status_code, "error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        loc = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
        message = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
        fields.setdefault(".".join(loc) or "_", message)
    summary_text = "; ".join(fields.values())
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": summary_text, "fields": fields}},
    )
