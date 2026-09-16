"""待办中心（按角色聚合演示待办）。"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.contract_queries import list_overdue_payment_todos
from db.demo_crm_seed import ensure_demo_crm
from db.hr_queries import list_contract_reminders
from db.hr_seed import ensure_hr_seed
from db.tables import CrmSampleRow, OrderChangeRequestRow, SoOrderRow, WecomMessageRow


def list_todos(session: Session, *, role: str, today: date) -> list[dict]:
    ensure_demo_crm(session)
    todos: list[dict] = []

    if role in ("PMC", "GM"):
        pending_changes = session.scalars(
            select(OrderChangeRequestRow)
            .where(OrderChangeRequestRow.status == "PENDING")
            .order_by(OrderChangeRequestRow.id.desc())
            .limit(20)
        ).all()
        for r in pending_changes:
            todos.append(
                {
                    "id": f"change-{r.id}",
                    "kind": "ORDER_CHANGE",
                    "title": f"订单变更待批 · {r.order_no}",
                    "detail": "查看影响清单后批准或驳回",
                    "path": "/changes",
                    "priority": "high",
                }
            )
        pool = session.scalars(
            select(SoOrderRow).where(SoOrderRow.schedule_phase == "IN_SCHEDULING")
        ).all()
        if pool:
            todos.append(
                {
                    "id": "pool-publish",
                    "kind": "SCHEDULE_POOL",
                    "title": f"排程池待发布 · {len(pool)} 单",
                    "detail": "倒排试算通过后保存发布",
                    "path": "/schedule",
                    "priority": "medium",
                }
            )

    if role in ("SALES", "SALES_MGR", "GM"):
        samples = session.scalars(select(CrmSampleRow)).all()
        for s in samples:
            if s.current_stage == "结案":
                continue
            if s.due_date and s.due_date < today:
                todos.append(
                    {
                        "id": f"sample-{s.code}",
                        "kind": "SAMPLE_OVERDUE",
                        "title": f"打样超期 · {s.code}",
                        "detail": f"{s.item_draft_name} · 阶段 {s.current_stage}",
                        "path": "/crm/samples",
                        "priority": "high",
                    }
                )

    msgs = session.scalars(
        select(WecomMessageRow)
        .where(WecomMessageRow.is_read.is_(False))
        .order_by(WecomMessageRow.id.desc())
        .limit(30)
    ).all()
    for m in msgs:
        targets = json.loads(m.role_targets_json or "[]")
        if targets and role not in targets and role != "GM":
            continue
        todos.append(
            {
                "id": f"wecom-{m.id}",
                "kind": "WECOM",
                "title": m.title,
                "detail": m.body[:120],
                "path": m.deep_link or "/portal",
                "priority": "medium",
            }
        )

    if role in ("HR", "GM"):
        ensure_hr_seed(session)
        for item in list_contract_reminders(session, today=today):
            todos.append(
                {
                    "id": f"hr-contract-{item['emp_no']}",
                    "kind": "HR_CONTRACT",
                    "title": item["title"],
                    "detail": item["detail"],
                    "path": "/modules/hr/roster",
                    "priority": item["priority"],
                }
            )

    if role in ("FIN", "GM", "SALES_MGR", "SALES"):
        for item in list_overdue_payment_todos(session, today=today):
            todos.append(
                {
                    "id": f"pay-{item['contract_no']}",
                    "kind": "PAYMENT_OVERDUE",
                    "title": item["title"],
                    "detail": item["detail"],
                    "path": f"/crm/customers/{item['customer_code']}",
                    "priority": "high",
                }
            )

    if role in ("WH", "GM", "PMC"):
        low_kit = session.scalars(
            select(SoOrderRow)
            .where(SoOrderRow.kitting_rate_pct.is_not(None))
            .where(SoOrderRow.kitting_rate_pct < 80)
            .limit(5)
        ).all()
        for o in low_kit:
            todos.append(
                {
                    "id": f"kit-{o.order_no}",
                    "kind": "KITTING",
                    "title": f"齐套不足 · {o.order_no}",
                    "detail": f"齐套率 {o.kitting_rate_pct}%",
                    "path": "/orders",
                    "priority": "low",
                }
            )

    order = {"high": 0, "medium": 1, "low": 2}
    todos.sort(key=lambda t: order.get(t.get("priority", "low"), 9))
    return todos
