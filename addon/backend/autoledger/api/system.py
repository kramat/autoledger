"""Info, health, settings and API token."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import API_VERSION, __version__
from ..auth import is_trusted
from ..db import get_db
from ..schemas import SettingsModel
from ..settings_store import get_settings, regenerate_token, save_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/info")
def info(request: Request, db: Session = Depends(get_db)):
    return {
        "name": "AutoLedger",
        "version": __version__,
        "api_version": API_VERSION,
        "currency": get_settings(db).currency,
        "timezone": str(request.app.state.config.tz),
    }


@router.get("/settings", response_model=SettingsModel)
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


@router.put("/settings", response_model=SettingsModel)
def write_settings(settings: SettingsModel, db: Session = Depends(get_db)):
    return save_settings(db, settings)


def _require_trusted(request: Request) -> None:
    if not is_trusted(request):
        raise HTTPException(403, "The token can only be managed from the AutoLedger panel")


@router.get("/settings/token")
def read_token(request: Request):
    _require_trusted(request)
    return {"token": request.app.state.token}


@router.post("/settings/token/regenerate")
def new_token(request: Request):
    _require_trusted(request)
    request.app.state.token = regenerate_token(request.app.state.config.secret_path)
    return {"token": request.app.state.token}
