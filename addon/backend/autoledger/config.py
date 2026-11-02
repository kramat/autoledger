"""Runtime configuration, read from the environment and the add-on options file."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    data_dir: Path
    static_dir: Path | None
    tz: ZoneInfo
    log_level: str = "info"
    dev: bool = False
    host: str = "0.0.0.0"
    port: int = 8099

    @property
    def db_path(self) -> Path:
        return self.data_dir / "autoledger.db"

    @property
    def secret_path(self) -> Path:
        return self.data_dir / "secret.json"


def load_config() -> Config:
    data_dir = Path(os.environ.get("AUTOLEDGER_DATA_DIR", "/data"))
    static_dir = os.environ.get("AUTOLEDGER_STATIC_DIR")

    options: dict = {}
    options_file = data_dir / "options.json"
    if options_file.exists():
        options = json.loads(options_file.read_text(encoding="utf-8"))

    # The Supervisor passes the Home Assistant time zone as TZ.
    tz_name = os.environ.get("TZ") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        _LOGGER.warning("Unknown time zone %r, using UTC", tz_name)
        tz = ZoneInfo("UTC")

    return Config(
        data_dir=data_dir,
        static_dir=Path(static_dir) if static_dir else None,
        tz=tz,
        log_level=options.get("log_level", "info"),
        dev=os.environ.get("AUTOLEDGER_DEV") == "1",
        host=os.environ.get("AUTOLEDGER_HOST", "0.0.0.0"),
        port=int(os.environ.get("AUTOLEDGER_PORT", "8099")),
    )
