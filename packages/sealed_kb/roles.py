from __future__ import annotations

from dataclasses import dataclass, field

from sealed_kb.reasoner import HOLD, MISSING
from sealed_kb.store import load

_ENGINE_MARKERS = ("packages/engine/", "engine/")
_DUE_WRITES = ("so_order.due_date", "订单约定日", "due_date")


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""


@dataclass
class ConsultResult:
    verdict: str
    missing: list[str] = field(default_factory=list)


def harvest_guard(paths: list[str]) -> GuardResult:
    for path in paths:
        norm = path.replace("\\", "/")
        if any(norm.startswith(m) or f"/{m}" in f"/{norm}" for m in _ENGINE_MARKERS):
            return GuardResult(False, "解析员禁止改 engine")
        if not (norm.startswith("kb/") or "/kb/" in f"/{norm}"):
            return GuardResult(False, "解析员只能写入 kb/")
    return GuardResult(True)


def consult(slot_ids: list[str]) -> ConsultResult:
    kb = load()
    missing = [
        sid
        for sid in slot_ids
        if sid not in kb.facts or kb.facts[sid].status != "已封印"
    ]
    if missing:
        return ConsultResult(MISSING, missing=missing)
    return ConsultResult(HOLD)


def gate_ticket(ticket: dict) -> GuardResult:
    binds = ticket.get("binds") or []
    facts = ticket.get("facts") or []
    if not binds or not facts:
        return GuardResult(False, "工匠拒绝：Ticket 缺少绑定或事实")
    writes = [str(w) for w in (ticket.get("writes") or [])]
    for write in writes:
        if any(token in write for token in _DUE_WRITES):
            return GuardResult(False, "工匠拒绝：BR-27 禁止写回约定日")
    return GuardResult(True)
