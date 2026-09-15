"""排程运行日志落盘（I/O 区，不进 engine）。"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from engine.models import ScheduleInput, ScheduleResult
from engine.run_log import build_schedule_run_log

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = ROOT / "data" / "schedule_logs"


def _slug(trigger: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", trigger, flags=re.UNICODE).strip("_")
    return (s or "run")[:32]


def default_run_id(trigger: str, plan_version: int) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    return f"{stamp}_{_slug(trigger)}_v{plan_version}"


def write_schedule_run_log(
    inp: ScheduleInput,
    result: ScheduleResult,
    *,
    trigger: str,
    plan_version: int,
    persist: bool,
    log_dir: Path | None = None,
    run_id: str | None = None,
    recorded_at: str | None = None,
) -> str:
    folder = Path(log_dir) if log_dir is not None else DEFAULT_LOG_DIR
    folder.mkdir(parents=True, exist_ok=True)
    rid = run_id or default_run_id(trigger, plan_version)
    at = recorded_at or datetime.now(UTC).isoformat()
    payload = build_schedule_run_log(
        inp,
        result,
        trigger=trigger,
        run_id=rid,
        recorded_at=at,
        persist=persist,
        plan_version=plan_version,
    )
    path = folder / f"{rid}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_index(folder, payload)
    return rid


def _append_index(folder: Path, payload: dict) -> None:
    idx = folder / "index.jsonl"
    row = {
        "run_id": payload["run"]["run_id"],
        "recorded_at": payload["run"]["recorded_at"],
        "trigger": payload["run"]["trigger"],
        "today": payload["run"]["today"],
        "sort_mode": payload["run"]["sort_mode"],
        "plan_version": payload["run"]["plan_version"],
        "persist": payload["run"]["persist"],
        "order_nos": [o["order_no"] for o in payload["input"]["orders"]],
        "conflict_count": len(payload["outcome"]["conflicts"]),
        "unplaced_count": payload["outcome"]["unplaced_count"],
    }
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_schedule_run_logs(log_dir: Path | None = None, *, limit: int = 50) -> list[dict]:
    folder = Path(log_dir) if log_dir is not None else DEFAULT_LOG_DIR
    idx = folder / "index.jsonl"
    if not idx.is_file():
        return []
    rows: list[dict] = []
    for line in idx.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.reverse()
    return rows[:limit]


def load_schedule_run_log(run_id: str, log_dir: Path | None = None) -> dict | None:
    folder = Path(log_dir) if log_dir is not None else DEFAULT_LOG_DIR
    path = folder / f"{run_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
