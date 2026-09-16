"""BR-27 / R-01：排产路径不得 UPDATE so_order.due_date。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_br27_so_order_due_date_only_via_repositories():
    """db 层仅 repositories.update_order_due_date_by_user 可写 row.due_date。"""
    db_dir = ROOT / "db"
    offenders: list[str] = []
    for path in db_dir.rglob("*.py"):
        if path.name in ("repositories.py", "seed.py", "demo_crm_seed.py", "tables.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "row.due_date =" in text.replace(" ", ""):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_br27_plan_store_does_not_touch_so_order_due():
    text = (ROOT / "db" / "plan_store.py").read_text(encoding="utf-8")
    assert "update_order_due_date" not in text
    assert "SoOrderRow" not in text
