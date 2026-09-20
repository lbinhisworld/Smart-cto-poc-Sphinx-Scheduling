"""三角色门禁：假设不繁殖已在 prove；这里锁顾问与工匠。"""

from __future__ import annotations

from sealed_kb.roles import consult, gate_ticket, harvest_guard


def test_harvest_only_kb() -> None:
    assert harvest_guard(["kb/ops/l1_claims.yaml"]).ok
    blocked = harvest_guard(["packages/engine/backward.py"])
    assert not blocked.ok
    assert "engine" in blocked.reason


def test_consult_missing_slot() -> None:
    result = consult(["D.not_a_slot"])
    assert result.verdict == "缺前提"
    assert "D.not_a_slot" in result.missing


def test_consult_sealed_due_slot() -> None:
    result = consult(["D.order.due_date"])
    assert result.verdict == "成立"


def test_ticket_without_bind_refused() -> None:
    result = gate_ticket(
        {
            "files": ["web/src/foo.tsx"],
            "facts": [],
            "binds": [],
            "must_not": [],
            "writes": [],
        }
    )
    assert not result.ok
    assert "绑定" in result.reason


def test_ticket_br27_write_refused() -> None:
    result = gate_ticket(
        {
            "files": ["db/plan_store.py"],
            "facts": ["F.l4.br27_no_write_due"],
            "binds": ["D.order.due_date"],
            "must_not": ["BR-27"],
            "writes": ["so_order.due_date"],
        }
    )
    assert not result.ok
    assert "约定日" in result.reason or "BR-27" in result.reason
