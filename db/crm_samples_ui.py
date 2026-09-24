"""打样列表 · 低代码列门面。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import CrmCustomerRow, CrmOpportunityRow, CrmSampleRow

DEMO_TODAY = date(2026, 9, 15)

PROGRESS_LABEL = {
    "申请": "下打样单",
    "打样": "出样品",
    "寄样": "客户审样",
    "客户反馈": "客户确认",
}


def enrich_sample_row(row: CrmSampleRow, base: dict) -> dict:
    overdue = bool(
        row.due_date
        and row.due_date < DEMO_TODAY
        and row.current_stage != "结案"
        and (row.result or "") != "确定方案"
    )
    base.update(
        {
            "start_date": row.ship_date.isoformat() if row.ship_date else (row.due_date.isoformat() if row.due_date else None),
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "sample_qty_total": None,
            "shipped_out": row.current_stage not in ("申请",),
            "progress_label": PROGRESS_LABEL.get(row.current_stage, row.current_stage),
            "is_overdue": overdue,
            "handler": row.owner_sales,
        }
    )
    return base


def _next_sample_code(session: Session) -> str:
    codes = session.scalars(select(CrmSampleRow.code)).all()
    n = 0
    for code in codes:
        if code.startswith("SP-") and code[3:].isdigit():
            n = max(n, int(code[3:]))
    return f"SP-{n + 1:03d}"


def launch_sample_flow(
    session: Session,
    *,
    actor: str,
    opportunity_id: int,
    due_date: date,
    item_draft_name: str = "",
    start_date: date | None = None,
    submit: bool = True,
) -> dict:
    opp = session.get(CrmOpportunityRow, opportunity_id)
    if opp is None:
        raise ValueError("商机不存在")
    cust = session.get(CrmCustomerRow, opp.customer_code)
    code = _next_sample_code(session)
    item = (item_draft_name or opp.name or "打样品").strip()
    row = CrmSampleRow(
        code=code,
        customer_code=opp.customer_code,
        item_draft_name=item,
        current_stage="申请",
        round_no=1,
        owner_sales=opp.owner_sales,
        due_date=due_date,
        ship_date=start_date,
        is_old_product=False,
    )
    session.add(row)
    session.flush()
    if submit:
        opp.sample_code = code
        if opp.stage in ("线索", "商机"):
            opp.stage = "商机"
    return {
        "code": code,
        "customer_code": opp.customer_code,
        "customer_name": cust.name if cust else opp.customer_code,
        "opportunity_id": opp.id,
        "submitted": submit,
        "progress_label": PROGRESS_LABEL["申请"],
    }
