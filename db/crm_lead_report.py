"""销售线索报表 · 看板统计。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crm_leads import _follow_summary, _last_valid_visit_date
from db.mis_orders import _sales_filter_for_role
from db.tables import CrmContractRow, CrmLeadRow

DEMO_TODAY = date(2026, 9, 15)


def _in_scope(session: Session, lead: CrmLeadRow, *, role: str, actor: str) -> bool:
    if role in ("GM", "SALES_MGR"):
        if lead.status == "待分配" and not lead.owner_sales:
            return True
        return bool(lead.owner_sales) or lead.status in ("已转化", "已丢失")
    if role == "SALES":
        sales = _sales_filter_for_role(role)
        if lead.status == "待分配":
            return False
        return lead.owner_sales == (actor or sales)
    return False


def _has_active_contract(session: Session, customer_code: str | None) -> bool:
    if not customer_code:
        return False
    row = session.scalar(
        select(CrmContractRow)
        .where(CrmContractRow.customer_code == customer_code, CrmContractRow.status == "ACTIVE")
        .limit(1)
    )
    return row is not None


def _stage_bucket(session: Session, lead: CrmLeadRow) -> str:
    if lead.status == "待分配":
        return "待分配"
    if lead.status == "已丢失":
        return "已丢失"
    if lead.status == "已转化":
        if _has_active_contract(session, lead.customer_code):
            return "已成交"
        return "已转化"
    valid = _last_valid_visit_date(session, lead.code)
    if valid:
        return "已有效跟进"
    return "跟进中"


def lead_report(session: Session, *, role: str, actor: str, today: date | None = None) -> dict:
    _ = today or DEMO_TODAY
    leads = [l for l in session.scalars(select(CrmLeadRow)).all() if _in_scope(session, l, role=role, actor=actor)]
    total = len(leads)
    following = sum(1 for l in leads if l.status == "跟进中")
    converted = sum(1 for l in leads if l.status == "已转化")
    closed = sum(1 for l in leads if l.status == "已转化" and _has_active_contract(session, l.customer_code))
    lost = sum(1 for l in leads if l.status == "已丢失")

    stage_counts: Counter[str] = Counter()
    industry_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    new_by_month: dict[str, int] = defaultdict(int)
    convert_by_month: dict[str, int] = defaultdict(int)

    for lead in leads:
        stage_counts[_stage_bucket(session, lead)] += 1
        industry_counts[lead.industry or "未填"] += 1
        source_counts[lead.source or "未填"] += 1
        new_by_month[lead.created_at.strftime("%Y-%m")] += 1
        if lead.status == "已转化":
            convert_by_month[lead.updated_at.strftime("%Y-%m")] += 1

    months = sorted(set(new_by_month.keys()) | set(convert_by_month.keys()))[-12:]

    return {
        "summary": {
            "线索总数": total,
            "跟进线索数": following + sum(1 for l in leads if _stage_bucket(session, l) == "已有效跟进"),
            "线索转化数": converted,
            "成交线索数": closed,
            "丢失线索数": lost,
        },
        "stage_distribution": dict(stage_counts),
        "industry_distribution": dict(industry_counts),
        "source_distribution": dict(source_counts),
        "new_trend": [{"month": m, "count": new_by_month.get(m, 0)} for m in months],
        "convert_trend": [{"month": m, "count": convert_by_month.get(m, 0)} for m in months],
    }


def leads_for_drill(
    session: Session,
    *,
    role: str,
    actor: str,
    bucket: str,
) -> list[dict]:
    out: list[dict] = []
    for lead in session.scalars(select(CrmLeadRow)).all():
        if not _in_scope(session, lead, role=role, actor=actor):
            continue
        stage = _stage_bucket(session, lead)
        if bucket == "线索总数":
            pass
        elif bucket == "跟进线索数":
            if stage not in ("跟进中", "已有效跟进"):
                continue
        elif bucket == "线索转化数":
            if lead.status != "已转化":
                continue
        elif bucket == "成交线索数":
            if not (lead.status == "已转化" and _has_active_contract(session, lead.customer_code)):
                continue
        elif bucket == "丢失线索数":
            if lead.status != "已丢失":
                continue
        elif stage != bucket:
            continue
        out.append(
            {
                "code": lead.code,
                "contact_name": lead.contact_name,
                "company_name": lead.company_name,
                "status": lead.status,
            }
        )
    return out
