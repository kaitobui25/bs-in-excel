"""Settings for the local, text-only Excel browser."""
from __future__ import annotations

import os
from pathlib import Path

SHEET_NAME = "Text Browser"
POLL_INTERVAL_SECONDS = 0.45
NAVIGATION_TIMEOUT_MS = 25_000
MAX_BODY_LINES = 140
MAX_LINKS = 55
MAX_HISTORY = 120
SIEMENS_URL = "https://www.siemens.com/ja-jp/products/tia-portal/"

LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "bs-in-excel"
CHROME_PORT_FILE = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "Google" / "Chrome" / "User Data" / "DevToolsActivePort"
)
