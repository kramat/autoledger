"""Run Alembic migrations on start, with a database backup before each upgrade."""

import logging
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from .config import Config

_LOGGER = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config(url: str | None = None) -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(config: Config, engine: Engine) -> None:
    cfg = alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        return

    if current is not None:
        _backup(config.db_path, config.data_dir / "backups" / f"autoledger-{current}.db")

    _LOGGER.info("Migrating database from %s to %s", current or "empty", head)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def _backup(db_path: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    _LOGGER.info("Database backed up to %s", target)
