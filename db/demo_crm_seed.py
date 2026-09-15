"""一体化 POC：CRM 演示数据（幂等）。"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.tables import CrmCustomerRow, CrmOpportunityRow, CrmSampleRow, SoOrderRow

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"


def _load_demo() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def ensure_demo_crm(session: Session) -> dict:
    """灌入 CRM 与订单扩展字段；可重复执行。"""
    data = _load_demo()
    crm = data.get("crm") or {}
    stats = {"customers": 0, "opportunities": 0, "samples": 0, "orders_patched": 0}

    for row in crm.get("customers", []):
        existing = session.get(CrmCustomerRow, row["code"])
        if existing is None:
            session.add(
                CrmCustomerRow(
                    code=row["code"],
                    name=row["name"],
                    channel_l1=row["channel_l1"],
                    channel_l2=row["channel_l2"],
                    owner_sales=row["owner_sales"],
                    level=row.get("level", 3),
                    status=row.get("status", "ACTIVE"),
                    custom_fields_json=json.dumps(row.get("custom_fields") or {}, ensure_ascii=False),
                    duplicate_flag=bool(row.get("duplicate_flag", False)),
                )
            )
            stats["customers"] += 1

    if stats["customers"] == 0 and crm.get("customers"):
        stats["customers"] = len(crm["customers"])

    opp_count = session.scalar(select(func.count()).select_from(CrmOpportunityRow)) or 0
    if opp_count == 0:
        for row in crm.get("opportunities", []):
            session.add(
                CrmOpportunityRow(
                    name=row["name"],
                    customer_code=row["customer_code"],
                    stage=row["stage"],
                    amount=str(row["amount"]),
                    owner_sales=row["owner_sales"],
                    expect_close_date=(
                        date.fromisoformat(row["expect_close_date"])
                        if row.get("expect_close_date")
                        else None
                    ),
                )
            )
            stats["opportunities"] += 1

    sample_count = session.scalar(select(func.count()).select_from(CrmSampleRow)) or 0
    if sample_count == 0:
        for row in crm.get("samples", []):
            session.add(
                CrmSampleRow(
                    code=row["code"],
                    customer_code=row["customer_code"],
                    item_draft_name=row["item_draft_name"],
                    current_stage=row["current_stage"],
                    round_no=row.get("round_no", 1),
                    owner_sales=row["owner_sales"],
                    due_date=date.fromisoformat(row["due_date"]) if row.get("due_date") else None,
                    is_old_product=bool(row.get("is_old_product", False)),
                    result=row.get("result"),
                )
            )
            stats["samples"] += 1

    enrich = data.get("order_enrichment") or {}
    for order_no, patch in enrich.items():
        row = session.get(SoOrderRow, order_no)
        if row is None:
            continue
        changed = False
        if patch.get("customer_code") and row.customer_code != patch["customer_code"]:
            row.customer_code = patch["customer_code"]
            changed = True
        if patch.get("kitting_rate_pct") is not None and row.kitting_rate_pct != patch["kitting_rate_pct"]:
            row.kitting_rate_pct = int(patch["kitting_rate_pct"])
            changed = True
        if patch.get("order_status") and row.order_status != patch["order_status"]:
            row.order_status = patch["order_status"]
            changed = True
        if not row.owner_sales and row.sales_name:
            row.owner_sales = row.sales_name
            changed = True
        if changed:
            stats["orders_patched"] += 1

    for row in session.scalars(select(SoOrderRow)):
        if not row.owner_sales and row.sales_name:
            row.owner_sales = row.sales_name

    return stats
