"""线索池、回收与跟进记录。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.crm_sales import DEMO_TODAY
from db.mis_orders import _sales_filter_for_role
from db.tables import CrmFollowRecordRow, CrmLeadPoolRuleRow, CrmLeadRow, CrmVisitRow

LEAD_STATUSES = ("待分配", "跟进中", "已转化", "已丢失")


def _sales_name(role: str) -> str | None:
    return _sales_filter_for_role(role)


def _next_lead_code(session: Session) -> str:
    n = int(session.scalar(select(func.count()).select_from(CrmLeadRow)) or 0)
    return f"LD{DEMO_TODAY.year}{n + 1:04d}"


def _last_valid_visit_date(session: Session, lead_code: str) -> date | None:
    from db.tables import CrmFieldVisitRow

    rows = session.scalars(
        select(CrmFollowRecordRow)
        .where(CrmFollowRecordRow.lead_code == lead_code, CrmFollowRecordRow.visit_id.isnot(None))
        .order_by(CrmFollowRecordRow.follow_date.desc())
    ).all()
    for rec in rows:
        visit = session.get(CrmVisitRow, rec.visit_id)
        if visit and visit.status == "CONFIRMED" and visit.is_valid and visit.confirmed_at:
            return visit.confirmed_at.date()
    for rec in session.scalars(
        select(CrmFollowRecordRow)
        .where(CrmFollowRecordRow.lead_code == lead_code)
        .order_by(CrmFollowRecordRow.follow_date.desc())
    ).all():
        note = rec.photo_note or ""
        if note.startswith("field:"):
            code = note[6:].strip()
            fv = session.get(CrmFieldVisitRow, code)
            if fv and fv.status == "已确认" and fv.check_out_at:
                return fv.check_out_at.date()
    return None


def apply_lead_recycle(session: Session, *, today: date | None = None) -> int:
    anchor = today or DEMO_TODAY
    rules = list(session.scalars(select(CrmLeadPoolRuleRow)).all())
    if not rules:
        return 0
    moved = 0
    for lead in session.scalars(
        select(CrmLeadRow).where(
            CrmLeadRow.status == "跟进中",
            CrmLeadRow.owner_sales != "",
        )
    ).all():
        rule = next((r for r in rules if r.pool_name == lead.pool_name and r.recycle_days), None)
        if rule is None or rule.recycle_days is None:
            continue
        members = json.loads(rule.member_names_json or "[]")
        if members and lead.owner_sales not in members:
            continue
        start = lead.assigned_at.date() if lead.assigned_at else lead.created_at.date()
        valid = _last_valid_visit_date(session, lead.code)
        if valid and valid > start:
            start = valid
        if (anchor - start).days < rule.recycle_days:
            continue
        lead.owner_sales = ""
        lead.owner_dept = ""
        lead.assigned_by = ""
        lead.assigned_at = None
        lead.status = "待分配"
        lead.updated_at = datetime.utcnow()
        moved += 1
    return moved


def _follow_summary(session: Session, lead_code: str) -> tuple[str, str | None, str | None]:
    valid_at = _last_valid_visit_date(session, lead_code)
    if valid_at:
        situation = "已有效跟进"
        last_date = valid_at.isoformat()
    else:
        situation = "未有效跟进"
        last_date = None
    next_row = session.scalar(
        select(CrmFollowRecordRow.next_follow_date)
        .where(CrmFollowRecordRow.lead_code == lead_code, CrmFollowRecordRow.next_follow_date.isnot(None))
        .order_by(CrmFollowRecordRow.next_follow_date.desc())
        .limit(1)
    )
    next_s = next_row.isoformat() if next_row else None
    return situation, last_date, next_s


def lead_to_dict(session: Session, row: CrmLeadRow) -> dict:
    situation, last_date, next_date = _follow_summary(session, row.code)
    return {
        "code": row.code,
        "status": row.status,
        "contact_name": row.contact_name,
        "gender": row.gender,
        "phone": row.phone,
        "wechat": row.wechat,
        "company_name": row.company_name,
        "follow_situation": situation,
        "last_follow_date": last_date,
        "next_follow_date": next_date,
        "owner_sales": row.owner_sales,
        "owner_dept": row.owner_dept,
        "detail_text": row.detail_text,
        "customer_level": row.customer_level,
        "tags": row.tags,
        "convert_note": row.convert_note,
        "pool_name": row.pool_name,
        "assigned_by": row.assigned_by,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "industry": row.industry,
        "source": row.source,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def list_leads(
    session: Session,
    *,
    role: str,
    pool: bool,
    contact: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    today: date | None = None,
) -> list[dict]:
    apply_lead_recycle(session, today=today)
    q = select(CrmLeadRow).order_by(CrmLeadRow.created_at.desc())
    if pool:
        q = q.where(CrmLeadRow.status == "待分配", CrmLeadRow.owner_sales == "")
    else:
        q = q.where(CrmLeadRow.owner_sales != "")
        sales = _sales_name(role)
        if role == "SALES" and sales:
            q = q.where(CrmLeadRow.owner_sales == sales)
    rows = list(session.scalars(q).all())
    if contact:
        rows = [r for r in rows if contact in r.contact_name]
    if phone:
        rows = [r for r in rows if phone in r.phone]
    if status:
        rows = [r for r in rows if r.status == status]
    return [lead_to_dict(session, r) for r in rows]


def get_lead(session: Session, code: str) -> dict | None:
    row = session.get(CrmLeadRow, code)
    if row is None:
        return None
    data = lead_to_dict(session, row)
    follows = session.scalars(
        select(CrmFollowRecordRow)
        .where(CrmFollowRecordRow.lead_code == code)
        .order_by(CrmFollowRecordRow.follow_date.desc())
    ).all()
    data["follow_records"] = [
        {
            "id": f.id,
            "follow_date": f.follow_date.isoformat(),
            "content": f.content,
            "next_follow_date": f.next_follow_date.isoformat() if f.next_follow_date else None,
            "owner_sales": f.owner_sales,
            "record_type": f.record_type,
            "photo_note": f.photo_note,
        }
        for f in follows
    ]
    return data


def match_lead_for_visit(
    session: Session,
    *,
    actor: str,
    customer_name: str,
    phone: str = "",
    lead_code: str | None = None,
) -> CrmLeadRow | None:
    if lead_code:
        row = session.get(CrmLeadRow, lead_code)
        if row is not None and row.status == "跟进中" and row.owner_sales == actor:
            return row
    name = customer_name.strip()
    if not name and not phone:
        return None
    for lead in session.scalars(
        select(CrmLeadRow).where(CrmLeadRow.status == "跟进中", CrmLeadRow.owner_sales == actor)
    ).all():
        if name and (name in lead.company_name or lead.company_name in name or name in lead.contact_name):
            return lead
        if phone and phone in (lead.phone or ""):
            return lead
    return None


def attach_valid_visit_to_lead(
    session: Session,
    *,
    lead: CrmLeadRow,
    visit_id: int,
    narrative: str,
    owner: str,
    next_date: date | None,
    confirmed_day: date,
) -> None:
    session.add(
        CrmFollowRecordRow(
            record_type="线索",
            lead_code=lead.code,
            visit_id=visit_id,
            follow_date=confirmed_day,
            content=(narrative or "").strip() or "移动端拜访",
            next_follow_date=next_date,
            owner_sales=owner,
            created_at=datetime.utcnow(),
        )
    )


def create_lead(session: Session, body: dict, *, actor: str, role: str) -> dict:
    now = datetime.utcnow()
    code = _next_lead_code(session)
    owner = (body.get("owner_sales") or "").strip()
    if role == "SALES":
        owner = actor
    if not owner and role in ("SALES_MGR", "GM"):
        owner = ""
    row = CrmLeadRow(
        code=code,
        status="跟进中" if owner else "待分配",
        contact_name=body["contact_name"],
        gender=body.get("gender") or "",
        phone=body.get("phone") or "",
        wechat=body.get("wechat") or "",
        company_name=body.get("company_name") or "",
        address_region=body.get("address_region") or "",
        address_detail=body.get("address_detail") or "",
        annual_revenue=body.get("annual_revenue") or "",
        industry=body.get("industry") or "",
        source=body.get("source") or "",
        detail_text=body.get("detail_text") or "",
        customer_level=body.get("customer_level") or "",
        tags=body.get("tags") or "",
        owner_sales=owner,
        owner_dept=body.get("owner_dept") or ("销售部" if owner else ""),
        pool_name=body.get("pool_name") or "默认线索池",
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    if owner:
        row.assigned_by = actor
        row.assigned_at = now
    session.add(row)
    session.flush()
    return lead_to_dict(session, row)


def assign_leads(session: Session, codes: list[str], owner_sales: str, *, actor: str) -> int:
    now = datetime.utcnow()
    n = 0
    for code in codes:
        row = session.get(CrmLeadRow, code)
        if row is None or row.status in ("已转化", "已丢失"):
            continue
        row.owner_sales = owner_sales
        row.owner_dept = "销售部"
        row.assigned_by = actor
        row.assigned_at = now
        row.status = "跟进中"
        row.updated_at = now
        n += 1
    return n


def add_lead_follow(
    session: Session,
    code: str,
    *,
    content: str,
    owner_sales: str,
    next_follow_date: date | None = None,
    visit_id: int | None = None,
) -> dict:
    row = session.get(CrmLeadRow, code)
    if row is None:
        raise ValueError("线索不存在")
    now = datetime.utcnow()
    rec = CrmFollowRecordRow(
        record_type="线索",
        lead_code=code,
        follow_date=now.date(),
        content=content,
        next_follow_date=next_follow_date,
        owner_sales=owner_sales,
        visit_id=visit_id,
        created_at=now,
    )
    session.add(rec)
    row.updated_at = now
    session.flush()
    return {"id": rec.id}


def list_pool_rules(session: Session) -> list[dict]:
    rows = session.scalars(select(CrmLeadPoolRuleRow).order_by(CrmLeadPoolRuleRow.pool_name)).all()
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "pool_name": r.pool_name,
                "admin_name": r.admin_name,
                "members": json.loads(r.member_names_json or "[]"),
                "recycle_days": r.recycle_days,
                "created_by": r.created_by,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
        )
    return out


def save_pool_rule(session: Session, body: dict, *, actor: str) -> dict:
    now = datetime.utcnow()
    pool_name = body["pool_name"].strip()
    existing = session.scalar(select(CrmLeadPoolRuleRow).where(CrmLeadPoolRuleRow.pool_name == pool_name))
    members = body.get("members") or []
    recycle = body.get("recycle_days")
    if existing:
        existing.admin_name = body["admin_name"]
        existing.member_names_json = json.dumps(members, ensure_ascii=False)
        existing.recycle_days = recycle
        existing.updated_at = now
        row = existing
    else:
        row = CrmLeadPoolRuleRow(
            pool_name=pool_name,
            admin_name=body["admin_name"],
            member_names_json=json.dumps(members, ensure_ascii=False),
            recycle_days=recycle,
            created_by=actor,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    session.flush()
    return {
        "id": row.id,
        "pool_name": row.pool_name,
        "admin_name": row.admin_name,
        "members": members,
        "recycle_days": row.recycle_days,
    }


def ensure_demo_leads(session: Session) -> None:
    if session.get(CrmLeadRow, "LD20260001"):
        return
    anchor = datetime.combine(DEMO_TODAY, datetime.min.time())
    now = anchor
    if not session.scalar(select(CrmLeadPoolRuleRow).limit(1)):
        session.add(
            CrmLeadPoolRuleRow(
                pool_name="默认线索池",
                admin_name="缪琳",
                member_names_json=json.dumps(["李业务"], ensure_ascii=False),
                recycle_days=7,
                created_by="缪琳",
                created_at=now,
                updated_at=now,
            )
        )
    session.add(
        CrmLeadRow(
            code="LD20260001",
            status="待分配",
            contact_name="王经理",
            phone="13800001111",
            company_name="待分配公司",
            pool_name="默认线索池",
            created_by="缪琳",
            created_at=anchor - timedelta(days=3),
            updated_at=now,
        )
    )
    old_assign = datetime.combine(date(2026, 9, 5), datetime.min.time())
    session.add(
        CrmLeadRow(
            code="LD20260002",
            status="跟进中",
            contact_name="仅手写跟进",
            phone="13800002222",
            company_name="南通鲜语食品",
            owner_sales="李业务",
            owner_dept="销售部",
            pool_name="默认线索池",
            assigned_by="缪琳",
            assigned_at=old_assign,
            created_by="李业务",
            created_at=old_assign,
            updated_at=now,
        )
    )
    session.add(
        CrmFollowRecordRow(
            record_type="线索",
            lead_code="LD20260002",
            follow_date=old_assign.date(),
            content="电话未接通",
            owner_sales="李业务",
            created_at=old_assign,
        )
    )
    good = datetime.combine(date(2026, 9, 13), datetime.min.time())
    session.add(
        CrmLeadRow(
            code="LD20260003",
            status="跟进中",
            contact_name="陈店长",
            phone="13800003333",
            company_name="杭州悦享门店",
            owner_sales="李业务",
            owner_dept="销售部",
            pool_name="默认线索池",
            assigned_by="缪琳",
            assigned_at=good,
            created_by="李业务",
            created_at=good,
            updated_at=now,
        )
    )
    visit = CrmVisitRow(
        status="CONFIRMED",
        owner_sales="李业务",
        customer_name="杭州悦享门店",
        narrative="现场沟通",
        outcome="关系建联",
        check_in_at=good,
        check_out_at=good + timedelta(minutes=20),
        is_valid=True,
        confirmed_at=good,
    )
    session.add(visit)
    session.flush()
    session.add(
        CrmFollowRecordRow(
            record_type="线索",
            lead_code="LD20260003",
            visit_id=visit.id,
            follow_date=good.date(),
            content="满 15 分钟现场拜访",
            owner_sales="李业务",
            created_at=good,
        )
    )


def convert_lead_to_customer(
    session: Session,
    code: str,
    *,
    actor: str,
    role: str,
    convert_note: str = "",
) -> dict:
    from db.crm_customer_portal import _set_cf
    from db.tables import CrmCustomerRow

    lead = session.get(CrmLeadRow, code)
    if lead is None:
        raise ValueError("线索不存在")
    if lead.status in ("已转化", "已丢失"):
        raise ValueError("线索已结案")
    if role == "SALES" and lead.owner_sales != actor:
        raise ValueError("无权转化")
    n = int(session.scalar(select(func.count()).select_from(CrmCustomerRow)) or 0)
    cust_code = f"C-L{n + 1:03d}"
    session.add(
        CrmCustomerRow(
            code=cust_code,
            name=lead.company_name or lead.contact_name,
            channel_l1=lead.industry or "未填",
            channel_l2="",
            owner_sales=lead.owner_sales or actor,
            level=3,
            status="ACTIVE",
            duplicate_flag=False,
            custom_fields_json="{}",
        )
    )
    cust = session.get(CrmCustomerRow, cust_code)
    if cust:
        _set_cf(
            cust,
            {
                "contact_name": lead.contact_name,
                "phone": lead.phone,
                "crm_status": "维护阶段",
                "created_at": DEMO_TODAY.isoformat(),
            },
        )
    lead.customer_code = cust_code
    lead.status = "已转化"
    lead.convert_note = convert_note or lead.convert_note
    lead.updated_at = datetime.utcnow()
    session.flush()
    return {"lead_code": code, "customer_code": cust_code}


def lose_lead(session: Session, code: str, *, reason: str, actor: str, role: str) -> None:
    lead = session.get(CrmLeadRow, code)
    if lead is None:
        raise ValueError("线索不存在")
    if role == "SALES" and lead.owner_sales != actor:
        raise ValueError("无权操作")
    allowed = ("价格", "交期", "样品未过", "客户取消", "其他")
    if reason not in allowed:
        raise ValueError("无效丢单原因")
    lead.status = "已丢失"
    lead.lost_reason = reason
    lead.updated_at = datetime.utcnow()


def convert_lead_to_opportunity(
    session: Session,
    code: str,
    *,
    actor: str,
    role: str,
    name: str,
    amount: float,
) -> dict:
    from db.crm_opportunity_ui import create_opportunity_for_customer

    lead = session.get(CrmLeadRow, code)
    if lead is None:
        raise ValueError("线索不存在")
    if lead.status == "已丢失":
        raise ValueError("线索已丢失")
    cust = lead.customer_code
    if not cust:
        data = convert_lead_to_customer(session, code, actor=actor, role=role, convert_note="转商机前建档")
        cust = data["customer_code"]
    opp = create_opportunity_for_customer(
        session,
        customer_code=cust,
        name=name or f"{lead.company_name}·商机",
        amount=amount,
        owner_sales=lead.owner_sales or actor,
        expect_close_date=None,
        actor=actor,
        source="线索转入",
    )
    lead.status = "已转化"
    lead.customer_code = cust
    lead.updated_at = datetime.utcnow()
    meta = opp
    return {"lead_code": code, "customer_code": cust, "opportunity": meta}
