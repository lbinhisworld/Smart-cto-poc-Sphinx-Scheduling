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


def _md(d: date) -> str:
    return f"{d.month}/{d.day}"


def unplaced_audit_message(
    *,
    order_no: str,
    item_code: str,
    due_date: date,
    earliest_start: date,
    remaining: int,
    attempts: list[dict],
) -> str:
    """二次审计旁白：逐日尝试 → 剩余 → 结论。attempts 不改变落位。"""
    bits: list[str] = []
    for a in attempts:
        d = a["date"]
        kind = a.get("kind")
        if kind == "place":
            extra = ""
            if a.get("cap") is not None:
                extra = f"（日产能 {a['cap']} 版，已占 {a.get('occupied', 0)}）"
            bits.append(f"{_md(d)} 放下 {a['qty']} 版{extra}")
        elif a.get("reason") == "REST":
            bits.append(f"{_md(d)} 非工作日跳过")
        elif a.get("reason") == "FULL":
            cap = a.get("cap")
            extra = f"（上限 {cap} 版）" if cap is not None else ""
            bits.append(f"{_md(d)} 产能已满跳过{extra}")
        else:
            bits.append(f"{_md(d)} 跳过")
    trail = "；".join(bits) if bits else "交期到最早可排日之间没有放下任何版"
    return (
        f"{order_no} {item_code} 从交期 {_md(due_date)} 往回填。\n"
        f"安排尝试：{trail}。\n"
        f"碰到最早可排日 {_md(earliest_start)}，还剩 {remaining} 版。\n"
        f"所以结论：未能在最早可排日前安置完（E1）。"
    )
