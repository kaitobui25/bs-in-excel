"""Settings for the local, text-only Excel browser."""
from __future__ import annotations

import os
from pathlib import Path

MAX_LINKS = 55
MAX_HISTORY = 120
MAX_TEXT = 45_000

LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "bs-in-excel"
