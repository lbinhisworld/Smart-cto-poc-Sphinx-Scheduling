"""倒排讲解事件（纯记录，不改变落位）。"""

from __future__ import annotations

from datetime import date

from engine.models import TraceAct, TraceEvent


def append_event(trace: list[TraceEvent] | None, **kwargs) -> None:
    if trace is None:
        return
    trace.append(TraceEvent(**kwargs))


def place_message(
    *,
    order_no: str,
    item_code: str,
    task_date: date,
    qty: int,
    remaining: int,
    free_before: int,
    occupied_before: int,
    cap: int,
) -> str:
    left = cap - occupied_before - qty
    return (
        f"{order_no} {item_code} · {task_date.isoformat()} 日产能 {cap} 版，"
        f"已占 {occupied_before}，本单吃 {qty}，还剩 {max(left, 0)} 版；"
        f"工单余量 {remaining} 版"
    )
