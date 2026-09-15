"""库存快照 Provider（POC：本地 + ERP mock JSON）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MOCK = ROOT / "seed" / "erp_stock_mock.json"


class StockProvider(Protocol):
    def fetch_entries(self) -> tuple[list[dict], datetime]:
        """返回 ([{item_code, qty, uom?, warehouse_code?}, ...], as_of)。"""
        ...


class MockErpStockProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_MOCK

    def fetch_entries(self) -> tuple[list[dict], datetime]:
        with self._path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        as_of = datetime.fromisoformat(raw.get("as_of", datetime.now(UTC).isoformat()))
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        return raw.get("items", []), as_of
