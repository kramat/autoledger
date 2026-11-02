"""Run the add-on on this machine for development.

    python dev_server.py

Serves the built frontend (../frontend/dist) on http://127.0.0.1:8099 with the
data in ../../dev-data. Dev mode skips the token check, so it only listens on
localhost.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

os.environ.setdefault("AUTOLEDGER_DATA_DIR", str(HERE.parent.parent / "dev-data"))
os.environ.setdefault("AUTOLEDGER_STATIC_DIR", str(HERE.parent / "frontend" / "dist"))
os.environ.setdefault("AUTOLEDGER_DEV", "1")
os.environ.setdefault("AUTOLEDGER_HOST", "127.0.0.1")
os.environ.setdefault("TZ", "Europe/Amsterdam")
sys.path.insert(0, str(HERE))

from autoledger.__main__ import main  # noqa: E402

main()
