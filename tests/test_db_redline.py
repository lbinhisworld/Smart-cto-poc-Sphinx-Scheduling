"""BR-27：plan_store 不触碰订单表。"""

from pathlib import Path


def test_plan_store_does_not_import_order_table_for_writes():
    text = (Path(__file__).resolve().parents[1] / "db" / "plan_store.py").read_text(
        encoding="utf-8"
    )
    assert "SoOrderRow" not in text
