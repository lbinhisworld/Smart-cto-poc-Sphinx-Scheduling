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
from db.due_negotiate import pending_pmc_apply, pending_sales_todos
from db.qc_limits_loader import load_qc_limits
from db.qc_material import list_open_exceptions_past_sla
from db.qc_ledgers import list_complaints_need_action
from db.qc_seed import ensure_qc_seed
from db.qty_carryover import STATUS_PENDING, list_pending_rolls
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
        for row in pending_pmc_apply(session):
            todos.append(
                {
                    "id": f"due-apply-{row.id}",
                    "kind": "DUE_NEGOTIATE",
                    "title": f"销售已回确认日 · {row.order_no}",
                    "detail": f"客户确认 {row.sales_proposed_due.isoformat() if row.sales_proposed_due else '—'} · 改锚后请再倒排",
                    "path": f"/schedule?negotiate={row.order_no}",
                    "priority": "high",
                    "pulse": True,
                }
            )
        for roll in list_pending_rolls(session, status=STATUS_PENDING):
            todos.append(
                {
                    "id": f"qty-roll-{roll['id']}",
                    "kind": "QTY_CARRYOVER",
                    "title": f"未完尾数待确认 · {roll['source_order_no']} 剩 {roll['qty_board_remain']} 版",
                    "detail": f"{roll['item_code']} · 并入同品项下次或插单（不可取消）",
                    "path": "/modules/production/time-report",
                    "priority": "high",
                }
            )

    if role in ("SALES", "SALES_MGR", "GM"):
        for row in pending_sales_todos(session):
            todos.append(
                {
                    "id": f"due-neg-{row.id}",
                    "kind": "DUE_NEGOTIATE",
                    "title": f"请协商交期 · {row.order_no}",
                    "detail": (row.brief_text or "系统最快可完成日待与客户确认")[:120],
                    "path": f"/orders?dueNegotiate={row.order_no}",
                    "priority": "high",
                    "pulse": True,
                }
            )
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
                    "path": f"/modules/hr/roster?renewal={item['contract_status']}",
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

    if role in ("QC", "GM", "WH"):
        ensure_qc_seed(session)
        limits = load_qc_limits()
        sla = int(limits.get("exception_sla_days") or 7)
        for ex in list_open_exceptions_past_sla(session, today=today, sla_days=sla):
            todos.append(
                {
                    "id": f"qc-exc-{ex['id']}",
                    "kind": "QC_EXCEPTION_SLA",
                    "title": f"来料异常待闭环 · {ex['exception_no']}",
                    "detail": (ex.get("phenomenon") or "")[:80],
                    "path": "/qc/exceptions",
                    "priority": "high",
                }
            )

    if role in ("QC", "GM", "SALES", "SALES_MGR"):
        ensure_qc_seed(session)
        limits = load_qc_limits()
        csla = int(limits.get("complaint_action_sla_days") or 14)
        for c in list_complaints_need_action(session, today=today, sla_days=csla):
            todos.append(
                {
                    "id": f"qc-complaint-{c['id']}",
                    "kind": "QC_COMPLAINT",
                    "title": f"客诉待整改 · {c['customer_name']}",
                    "detail": (c.get("content") or "")[:80],
                    "path": "/qc/complaints",
                    "priority": "medium",
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
