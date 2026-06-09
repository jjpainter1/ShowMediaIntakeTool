"""User-data path helpers for Show Media Intake Tool."""

import os
from pathlib import Path

_APP_NAME = "ShowMediaIntakeTool"


def get_user_data_root() -> Path:
    """Return %LOCALAPPDATA%\\ShowMediaIntakeTool\\, creating it if needed.

    Raises OSError if LOCALAPPDATA is not set (should not happen on Windows).
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        raise OSError("LOCALAPPDATA environment variable is not set.")
    root = Path(local_app_data) / _APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root
