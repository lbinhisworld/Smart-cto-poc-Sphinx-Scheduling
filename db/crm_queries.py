"""CRM 列表与固定报表（Phase 6）。"""

from __future__ import annotations

import json
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.contract_queries import customer_payment_summary, list_contracts
from db.qc_ledgers import list_complaints_for_customer
from db.sample_workflow import sample_detail
from db.tables import CrmCustomerRow, CrmOpportunityRow, CrmQuoteRow, CrmSampleRow, SoOrderRow


def _resolve_opportunity_sample_code(session: Session, opp: CrmOpportunityRow) -> str | None:
    if opp.sample_code:
        return opp.sample_code
    row = session.scalars(
        select(CrmSampleRow)
        .where(CrmSampleRow.customer_code == opp.customer_code)
        .where(CrmSampleRow.owner_sales == opp.owner_sales)
        .where(CrmSampleRow.current_stage != "结案")
        .order_by(CrmSampleRow.due_date.desc(), CrmSampleRow.code)
    ).first()
    return row.code if row else None


def list_customers(session: Session, *, role: str, owner_filter: str | None = None) -> list[dict]:
    q = select(CrmCustomerRow).order_by(CrmCustomerRow.code)
    rows = session.scalars(q).all()
    out: list[dict] = []
    for r in rows:
        if role == "SALES" and owner_filter and r.owner_sales != owner_filter:
            continue
        out.append(
            {
                "code": r.code,
                "name": r.name,
                "channel_l1": r.channel_l1,
                "channel_l2": r.channel_l2,
                "owner_sales": r.owner_sales,
                "level": r.level,
                "status": r.status,
                "duplicate_flag": r.duplicate_flag,
                "custom_fields": json.loads(r.custom_fields_json or "{}"),
            }
        )
    return out


def customer_detail(
    session: Session,
    code: str,
    *,
    role: str = "GM",
    actor: str = "",
) -> dict | None:
    r = session.get(CrmCustomerRow, code)
    if r is None:
        return None
    orders = session.scalars(
        select(SoOrderRow)
        .where(SoOrderRow.customer_code == code)
        .order_by(SoOrderRow.due_date.desc())
        .limit(20)
    ).all()
    opps = session.scalars(
        select(CrmOpportunityRow).where(CrmOpportunityRow.customer_code == code)
    ).all()
    samples = session.scalars(
        select(CrmSampleRow).where(CrmSampleRow.customer_code == code)
    ).all()
    from db.crm_follows import list_follows

    payload = {
        "customer": {
            "code": r.code,
            "name": r.name,
            "channel_l1": r.channel_l1,
            "channel_l2": r.channel_l2,
            "owner_sales": r.owner_sales,
            "level": r.level,
            "duplicate_flag": r.duplicate_flag,
            "custom_fields": json.loads(r.custom_fields_json or "{}"),
        },
        "opportunities": [
            {
                "id": o.id,
                "name": o.name,
                "stage": o.stage,
                "amount": float(o.amount),
                "expect_close_date": o.expect_close_date.isoformat() if o.expect_close_date else None,
            }
            for o in opps
        ],
        "samples": [
            {
                "code": s.code,
                "item_draft_name": s.item_draft_name,
                "current_stage": s.current_stage,
                "round_no": s.round_no,
                "due_date": s.due_date.isoformat() if s.due_date else None,
            }
            for s in samples
        ],
        "orders": [
            {
                "order_no": o.order_no,
                "item_code": o.item_code,
                "due_date": o.due_date.isoformat(),
                "order_status": o.order_status,
                "amount": float(o.amount),
                "schedule_phase": o.schedule_phase,
                "contract_no": o.contract_no,
            }
            for o in orders
        ],
        "contracts": list_contracts(session, customer_code=code),
        "payment_summary": customer_payment_summary(session, code),
        "complaints": list_complaints_for_customer(session, code),
    }
    payload["follow_timeline"] = list_follows(
        session, role=role, actor=actor, customer_code=code
    )
    return payload


def opportunity_detail(session: Session, opp_id: int) -> dict | None:
    o = session.get(CrmOpportunityRow, opp_id)
    if o is None:
        return None
    cust = session.get(CrmCustomerRow, o.customer_code)
    sample_code = _resolve_opportunity_sample_code(session, o)
    sample = sample_detail(session, sample_code) if sample_code else None
    base = {
        "id": o.id,
        "name": o.name,
        "stage": o.stage,
        "amount": float(o.amount),
        "owner_sales": o.owner_sales,
        "sales_name": o.owner_sales,
        "expect_close_date": o.expect_close_date.isoformat() if o.expect_close_date else None,
        "sample_code": sample_code,
        "customer": {
            "code": o.customer_code,
            "name": cust.name if cust else o.customer_code,
        },
        "sample": sample,
    }
    from db.crm_opportunity_ui import enrich_detail

    return enrich_detail(session, o, base, role="GM", actor="")


def list_opportunities(
    session: Session, *, role: str, owner_filter: str | None = None
) -> list[dict]:
    rows = session.scalars(
        select(CrmOpportunityRow).order_by(CrmOpportunityRow.expect_close_date, CrmOpportunityRow.id)
    ).all()
    out: list[dict] = []
    for o in rows:
        if role in ("SALES", "SALES_ASSIST") and owner_filter and o.owner_sales != owner_filter:
            continue
        if role == "RD":
            if not o.sample_code:
                continue
            sample = session.get(CrmSampleRow, o.sample_code)
            if sample is None or sample.current_stage == "结案":
                continue
        cust = session.get(CrmCustomerRow, o.customer_code)
        row = {
            "id": o.id,
            "name": o.name,
            "customer_code": o.customer_code,
            "customer_name": cust.name if cust else o.customer_code,
            "stage": o.stage,
            "amount": float(o.amount),
            "owner_sales": o.owner_sales,
            "sales_name": o.owner_sales,
            "expect_close_date": o.expect_close_date.isoformat() if o.expect_close_date else None,
            "sample_code": o.sample_code,
        }
        from db.crm_opportunity_ui import enrich_list_row

        enrich_list_row(session, row, o)
        if role == "RD":
            row["amount"] = None
        out.append(row)
    return out


def list_samples(
    session: Session,
    *,
    role: str,
    owner_filter: str | None = None,
    active_only: bool = False,
) -> list[dict]:
    rows = session.scalars(select(CrmSampleRow).order_by(CrmSampleRow.code)).all()
    out = []
    for s in rows:
        if active_only and s.current_stage == "结案":
            continue
        if role == "SALES" and owner_filter and s.owner_sales != owner_filter:
            continue
        cust = session.get(CrmCustomerRow, s.customer_code)
        from db.crm_samples_ui import enrich_sample_row

        base = {
            "code": s.code,
            "customer_code": s.customer_code,
            "customer_name": cust.name if cust else s.customer_code,
            "item_draft_name": s.item_draft_name,
            "current_stage": s.current_stage,
            "round_no": s.round_no,
            "owner_sales": s.owner_sales,
            "due_date": s.due_date.isoformat() if s.due_date else None,
            "is_old_product": s.is_old_product,
            "result": s.result,
        }
        out.append(enrich_sample_row(s, base))
    return out


def funnel_report(session: Session) -> dict:
    stages = ["线索", "商机", "方案", "报价", "谈判", "成交"]
    counts = {}
    for st in stages:
        n = session.scalar(
            select(func.count())
            .select_from(CrmOpportunityRow)
            .where(CrmOpportunityRow.stage == st)
        ) or 0
        counts[st] = int(n)
    total = sum(counts.values())
    return {
        "stages": stages,
        "counts": counts,
        "total": total,
        "note": "口径：crm_opportunity.stage 计数；种子保证各阶段非 0",
    }


def sample_weekly_report(session: Session) -> dict:
    rows = session.scalars(select(CrmSampleRow)).all()
    active = [s for s in rows if s.current_stage not in ("结案",) and not s.is_old_product]
    overdue = [
        s
        for s in active
        if s.due_date and s.due_date.isoformat() < "2026-09-15"
    ]
    return {
        "active_count": len(active),
        "overdue_count": len(overdue),
        "overdue_codes": [s.code for s in overdue],
        "note": "老品 is_old_product 不计入转化率演示",
    }


def list_quotes(session: Session) -> list[dict]:
    from db.quote_service import list_quotes as _list_quotes

    return _list_quotes(session)
