"""User settings (in the database) and the API token (in /data/secret.json)."""

import json
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Setting
from .schemas import SettingsModel

_SETTINGS_KEY = "general"


def get_settings(db: Session) -> SettingsModel:
    row = db.get(Setting, _SETTINGS_KEY)
    return SettingsModel.model_validate(row.value if row else {})


def save_settings(db: Session, settings: SettingsModel) -> SettingsModel:
    row = db.get(Setting, _SETTINGS_KEY)
    if row is None:
        row = Setting(key=_SETTINGS_KEY)
        db.add(row)
    row.value = settings.model_dump()
    db.commit()
    return settings


def load_token(secret_path: Path) -> str:
    """Return the API token, creating it on first use."""
    if secret_path.exists():
        data = json.loads(secret_path.read_text(encoding="utf-8"))
        if data.get("token"):
            return data["token"]
    return regenerate_token(secret_path)


def regenerate_token(secret_path: Path) -> str:
    token = secrets.token_urlsafe(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(json.dumps({"token": token}), encoding="utf-8")
    return token
