"""Serve the app with a daylight-blocked planner, so the night page can be looked at.

    uv run python scripts/night_server.py

A screenshot aid only: it injects a PreviewPlanner whose outcome is DAYLIGHT_NIGHT, so
GET /results shows that page with its TC-002 copy. Nothing in the application changes.
"""

import os
import sys
from pathlib import Path
from typing import Final

import uvicorn

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.main import create_app
from wiggle_outside.preview_planner import PreviewPlanner

ROOT: Final = Path(__file__).resolve().parent.parent
PORT: Final = 8444


def main() -> int:
    os.environ["WO_PORT"] = str(PORT)
    uvicorn.run(
        create_app(planner=PreviewPlanner(outcome=ErrorCode.DAYLIGHT_NIGHT)),
        host="127.0.0.1",
        port=PORT,
        ssl_keyfile=str(ROOT / "out" / "devcert" / "key.pem"),
        ssl_certfile=str(ROOT / "out" / "devcert" / "cert.pem"),
        log_level="warning",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
