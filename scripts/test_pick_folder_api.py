"""Smoke-test pick-folder API without opening a dialog."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.routes.system import pick_folder_endpoint


def main() -> None:
    with patch(
        "backend.routes.system.pick_delivery_source_folder",
        return_value=Path(r"D:\Shows\SampleAssets\DeliveryFolder\v1"),
    ) as mocked:
        result = pick_folder_endpoint(
            title="test",
            mode="delivery_source",
            start_dir=r"D:\Shows\SampleAssets",
        )
        mocked.assert_called_once()
    assert result == {
        "cancelled": False,
        "path": r"D:\Shows\SampleAssets\DeliveryFolder\v1",
    }
    print("pick-folder?mode=delivery_source: OK")


if __name__ == "__main__":
    main()
