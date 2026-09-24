"""跟进记录全表与嵌入筛选。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crm_customer_portal import _can_see_customer
from db.tables import CrmCustomerRow, CrmFollowRecordRow, CrmLeadRow, CrmOpportunityRow

DEMO_TODAY = date(2026, 9, 15)


def _row_dict(session: Session, rec: CrmFollowRecordRow) -> dict:
    cust_name = ""
    if rec.customer_code:
        c = session.get(CrmCustomerRow, rec.customer_code)
        cust_name = c.name if c else rec.customer_code
    return {
        "id": rec.id,
        "record_type": rec.record_type,
        "lead_code": rec.lead_code,
        "opportunity_id": rec.opportunity_id,
        "customer_code": rec.customer_code,
        "customer_name": cust_name,
        "visit_id": rec.visit_id,
        "follow_date": rec.follow_date.isoformat(),
        "content": rec.content,
        "next_follow_date": rec.next_follow_date.isoformat() if rec.next_follow_date else None,
        "owner_sales": rec.owner_sales,
        "photo_note": rec.photo_note,
    }


def _scope_customer_codes(session: Session, *, role: str, actor: str) -> set[str] | None:
    if role in ("GM", "SALES_MGR"):
        return None
    codes: set[str] = set()
    for row in session.scalars(select(CrmCustomerRow)).all():
        if _can_see_customer(role, actor, row):
            codes.add(row.code)
    return codes


def list_follows(
    session: Session,
    *,
    role: str,
    actor: str,
    customer_code: str | None = None,
    lead_code: str | None = None,
    opportunity_id: int | None = None,
    record_type: str | None = None,
) -> list[dict]:
    q = select(CrmFollowRecordRow).order_by(
        CrmFollowRecordRow.follow_date.desc(), CrmFollowRecordRow.id.desc()
    )
    if customer_code:
        q = q.where(CrmFollowRecordRow.customer_code == customer_code)
    if lead_code:
        q = q.where(CrmFollowRecordRow.lead_code == lead_code)
    if opportunity_id is not None:
        q = q.where(CrmFollowRecordRow.opportunity_id == opportunity_id)
    if record_type:
        q = q.where(CrmFollowRecordRow.record_type == record_type)
    allowed = _scope_customer_codes(session, role=role, actor=actor)
    rows = session.scalars(q).all()
    out: list[dict] = []
    for rec in rows:
        if allowed is not None:
            if rec.customer_code and rec.customer_code not in allowed:
                if rec.owner_sales != actor:
                    continue
            elif rec.owner_sales != actor:
                continue
        out.append(_row_dict(session, rec))
    return out


def add_follow(
    session: Session,
    *,
    actor: str,
    record_type: str,
    content: str,
    customer_code: str | None = None,
    lead_code: str | None = None,
    opportunity_id: int | None = None,
    next_follow_date: date | None = None,
    today: date | None = None,
    photo_note: str = "",
) -> dict:
    if not content.strip():
        raise ValueError("跟进内容必填")
    if record_type not in ("线索", "商机", "客户"):
        raise ValueError("无效跟进类型")
    now = datetime.combine(today or DEMO_TODAY, datetime.min.time())
    rec = CrmFollowRecordRow(
        record_type=record_type,
        lead_code=lead_code,
        opportunity_id=opportunity_id,
        customer_code=customer_code,
        follow_date=today or DEMO_TODAY,
        content=content.strip(),
        next_follow_date=next_follow_date,
        owner_sales=actor,
        photo_note=photo_note,
        created_at=now,
    )
    session.add(rec)
    session.flush()
    return _row_dict(session, rec)


def ensure_demo_follows(session: Session) -> None:
    """李业务客户时间线：一条线索型历史 + 一条客户型拜访跟进。"""
    exists = session.scalar(
        select(CrmFollowRecordRow.id).where(
            CrmFollowRecordRow.customer_code == "C-001",
            CrmFollowRecordRow.content == "线索阶段曾电话沟通",
        )
    )
    if exists:
        return
    now = datetime(2026, 9, 1, 10, 0, 0)
    session.add(
        CrmFollowRecordRow(
            record_type="线索",
            customer_code="C-001",
            follow_date=date(2026, 9, 1),
            content="线索阶段曾电话沟通",
            owner_sales="李业务",
            created_at=now,
        )
    )
    session.add(
        CrmFollowRecordRow(
            record_type="客户",
            customer_code="C-001",
            follow_date=date(2026, 9, 8),
            content="有效拜访确认 · 好利来门店建联",
            owner_sales="李业务",
            visit_id=1,
            created_at=datetime(2026, 9, 8, 11, 0, 0),
        )
    )
    session.flush()
