"""加载 config/qc_limits.yaml。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_qc_limits() -> dict[str, Any]:
    with (ROOT / "config" / "qc_limits.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
