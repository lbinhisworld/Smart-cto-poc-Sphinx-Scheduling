"""从 config/*.yaml 加载 ScheduleConfig（与 tests/conftest 同源）。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from engine.models import KitMode, PriorityWeights, ScheduleConfig, SortMode

ROOT = Path(__file__).resolve().parents[1]


def load_schedule_config(*, reserved_ratio: Decimal | None = None) -> ScheduleConfig:
    with (ROOT / "config" / "schedule.yaml").open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    with (ROOT / "config" / "weights.yaml").open(encoding="utf-8") as fh:
        weights = yaml.safe_load(fh)
    if reserved_ratio is None:
        reserved_ratio = Decimal(str(raw["reserved_ratio"]))
    return ScheduleConfig(
        fence_days=raw["fence_days"],
        protocol_days=raw["protocol_days"],
        ripple_limit=raw["ripple_limit"],
        deadband_days=Decimal(str(raw["deadband_days"])),
        deadband_hours_ratio=Decimal(str(raw["deadband_hours_ratio"])),
        reserved_ratio=reserved_ratio,
        horizon_days=raw["horizon_days"],
        jit=raw["jit"],
        sort_mode=SortMode(raw["sort_mode"]),
        default_lead_time_days=raw["default_lead_time_days"],
        weights=PriorityWeights.model_validate(weights),
        kit_mode=KitMode(raw.get("kit_mode", "WARN")),
    )
