"""电脑拜访签到 · 15 分钟签退 · 时间线 · 达标归纳。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from db.crm_sales import VALID_MINUTES, visit_is_valid
from db.tables import CrmFieldVisitLogRow, CrmFieldVisitRow

DEMO_TODAY = date(2026, 9, 15)
DEMO_NOW = datetime(2026, 9, 15, 14, 0, 0)

ACTIVE_STATUSES = frozenset({"进行中", "已签到", "待签到"})


def demo_now(today: date | None = None) -> datetime:
    if today is not None:
        return datetime(today.year, today.month, today.day, 14, 0, 0)
    return DEMO_NOW


def _is_guided_demo_visit_code(code: str) -> bool:
    c = str(code or "")
    return c.startswith("GD-") and "-V" in c


def _next_code(session: Session) -> str:
    rows = session.scalars(select(CrmFieldVisitRow.code)).all()
    nums = [int(c[2:]) for c in rows if c.startswith("WF") and c[2:].isdigit()]
    return f"WF{(max(nums) if nums else 0) + 1:06d}"


def _minutes_between(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


def _started_at(row: CrmFieldVisitRow) -> datetime | None:
    return row.started_at or row.check_in_at


def _progress_tags(row: CrmFieldVisitRow) -> list[str]:
    try:
        data = json.loads(row.progress_tags_json or "[]")
        return [str(x) for x in data] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _set_progress_tags(row: CrmFieldVisitRow, tags: list[str]) -> None:
    row.progress_tags_json = json.dumps(tags, ensure_ascii=False)


def _timeline_rows(session: Session, code: str) -> list[CrmFieldVisitLogRow]:
    return list(
        session.scalars(
            select(CrmFieldVisitLogRow)
            .where(CrmFieldVisitLogRow.visit_code == code)
            .order_by(CrmFieldVisitLogRow.recorded_at.asc())
        ).all()
    )


def timeline_as_dicts(session: Session, code: str) -> list[dict]:
    return [
        {
            "id": r.id,
            "recorded_at": r.recorded_at.isoformat(),
            "body": r.body,
            "created_by": r.created_by,
        }
        for r in _timeline_rows(session, code)
    ]


def timeline_text(session: Session, code: str) -> str:
    parts = [r.body.strip() for r in _timeline_rows(session, code) if (r.body or "").strip()]
    note = (session.get(CrmFieldVisitRow, code).situation_note or "").strip() if session.get(CrmFieldVisitRow, code) else ""
    if note and note not in parts:
        parts.append(note)
    return "\n".join(parts)


def _tags_from_text(text: str) -> list[str]:
    t = (text or "").strip()
    if not t or len(t) < 4:
        return ["无成果"]
    tags: list[str] = []
    if any(k in t for k in ("决策人", "决策", "总监", "负责人", "总经理", "老板")):
        tags.append("触达决策人")
    if any(k in t for k in ("采购", "意向", "下单", "报价", "打样", "数量", "商机")):
        tags.append("挖掘到商机")
    if not tags:
        tags.append("关系建联")
    return tags


def rule_eval_visit(text: str) -> dict:
    tags = _tags_from_text(text)
    meets = tags != ["无成果"] and (
        "触达决策人" in tags or "挖掘到商机" in tags or tags == ["关系建联"]
    )
    reason = "" if meets else "无有效拜访成果，请补充时间线记录"
    summary = parse_situation_note(text) if text.strip() else "尚未记录拜访内容。"
    return {
        "summary": summary.replace("【AI整理】", "【规则归纳】", 1),
        "progress_tags": tags,
        "meets_standard": meets,
        "standard_reason": reason,
        "eval_source": "rule",
    }


def visit_finalize_llm(session: Session, text: str, *, today: date) -> dict | None:
    from db.crm_sales import _llm_draft
    from db.tables import CrmCustomerRow

    customers = [
        {"code": row.code, "name": row.name}
        for row in session.scalars(select(CrmCustomerRow).order_by(CrmCustomerRow.code)).all()
    ][:30]
    drafted = _llm_draft(session, text, customers, today=today)
    if drafted is None:
        return None
    outcome = str(drafted.get("outcome") or "")
    tags: list[str] = []
    if outcome == "挖到商机":
        tags.append("挖掘到商机")
    elif outcome == "触达决策人":
        tags.append("触达决策人")
    elif outcome == "关系建联":
        tags.append("关系建联")
    else:
        tags = _tags_from_text(text)
    meets = tags != ["无成果"] and (
        "触达决策人" in tags or "挖掘到商机" in tags or tags == ["关系建联"]
    )
    return {
        "summary": str(drafted.get("narrative") or text),
        "progress_tags": tags,
        "meets_standard": meets,
        "standard_reason": "" if meets else "模型认为成果不足，请补录",
        "eval_source": "llm",
        "opportunity_hint": str(drafted.get("opportunity_name") or ""),
    }


def finalize_field_visit(
    session: Session,
    *,
    code: str,
    today: date | None = None,
    prefer_llm: bool = True,
) -> dict:
    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    if row.status == "已确认":
        raise ValueError("已写入跟进，不可再归纳")
    text = timeline_text(session, code)
    anchor = today or DEMO_TODAY
    eval_result: dict | None = None
    if prefer_llm and text.strip():
        eval_result = visit_finalize_llm(session, text, today=anchor)
    if eval_result is None:
        eval_result = rule_eval_visit(text)
        if prefer_llm:
            eval_result["eval_source"] = "keyword" if text.strip() else "rule"
    now = demo_now(anchor)
    row.summary = eval_result["summary"]
    _set_progress_tags(row, eval_result["progress_tags"])
    row.meets_standard = bool(eval_result["meets_standard"])
    row.eval_source = str(eval_result.get("eval_source") or "rule")
    row.standard_reason = str(eval_result.get("standard_reason") or "")
    row.finalized_at = now
    row.situation_note = row.summary
    row.updated_at = now
    session.flush()
    return get_field_visit(session, code, today=anchor) or {}


def add_field_visit_log(
    session: Session,
    *,
    code: str,
    body: str,
    actor: str,
    today: date | None = None,
) -> dict:
    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    if row.status == "已确认":
        raise ValueError("已写入跟进，不可再追加")
    when = demo_now(today)
    session.add(
        CrmFieldVisitLogRow(
            visit_code=code,
            recorded_at=when,
            body=body.strip(),
            created_by=actor,
        )
    )
    row.updated_at = when
    session.flush()
    return get_field_visit(session, code, today=today) or {}


def list_field_visit_stats(
    session: Session,
    *,
    role: str,
    actor: str,
    today: date | None = None,
) -> dict:
    rows = list_field_visits(session, role=role, actor=actor, today=today)
    by_tag: dict[str, int] = {}
    not_meeting = 0
    for r in rows:
        if r.get("meets_standard") is False:
            not_meeting += 1
        for tag in r.get("progress_tags") or []:
            by_tag[tag] = by_tag.get(tag, 0) + 1
    return {"not_meeting": not_meeting, "by_tag": by_tag, "total": len(rows)}


def list_field_visits(
    session: Session,
    *,
    role: str,
    actor: str,
    owner: str | None = None,
    today: date | None = None,
    tag: str | None = None,
    not_meeting_only: bool = False,
) -> list[dict]:
    q = select(CrmFieldVisitRow).order_by(CrmFieldVisitRow.created_at.desc())
    if role in ("SALES", "SALES_ASSIST"):
        actor_name = owner or actor
        q = q.where(
            or_(
                CrmFieldVisitRow.owner_sales == actor_name,
                CrmFieldVisitRow.code.like("GD-%-V%"),
            )
        )
    elif owner:
        q = q.where(CrmFieldVisitRow.owner_sales == owner)
    rows = session.scalars(q).all()
    out = [_serialize(session, r, today=today) for r in rows]
    if tag:
        out = [r for r in out if tag in (r.get("progress_tags") or [])]
    if not_meeting_only:
        out = [r for r in out if r.get("meets_standard") is False]
    return out


def get_field_visit(session: Session, code: str, *, today: date | None = None) -> dict | None:
    row = session.get(CrmFieldVisitRow, code)
    return _serialize(session, row, today=today) if row else None


def _serialize(session: Session, row: CrmFieldVisitRow, *, today: date | None = None) -> dict:
    now = demo_now(today)
    start = _started_at(row)
    mins: int | None = None
    elapsed: int | None = None
    if start and row.check_out_at:
        mins = _minutes_between(start, row.check_out_at)
        elapsed = mins
    elif start and row.status in ACTIVE_STATUSES:
        elapsed = _minutes_between(start, now)
    gap: int | None = None
    if row.status in ("已签到", "进行中") and start:
        elapsed_min = _minutes_between(start, now)
        elapsed = elapsed_min
        if elapsed_min < VALID_MINUTES:
            gap = VALID_MINUTES - elapsed_min
    tags = _progress_tags(row)
    return {
        "code": row.code,
        "owner_sales": row.owner_sales,
        "visit_plan": row.visit_plan,
        "title": row.title,
        "customer_code": row.customer_code,
        "customer_name": row.customer_name,
        "visit_kind": row.visit_kind,
        "expected_at": row.expected_at.isoformat() if row.expected_at else None,
        "expected_address": row.expected_address,
        "before_note": row.before_note,
        "situation_note": row.situation_note,
        "photo_note": row.photo_note,
        "status": row.status,
        "started_at": start.isoformat() if start else None,
        "check_in_at": row.check_in_at.isoformat() if row.check_in_at else None,
        "check_out_at": row.check_out_at.isoformat() if row.check_out_at else None,
        "check_in_location": row.check_in_location or "",
        "check_out_location": row.check_out_location or "-",
        "visit_minutes": mins,
        "elapsed_minutes": elapsed,
        "minutes_until_checkout_ok": gap,
        "linked_visit_id": row.linked_visit_id,
        "summary": row.summary or "",
        "progress_tags": tags,
        "meets_standard": row.meets_standard,
        "eval_source": row.eval_source or "",
        "standard_reason": row.standard_reason or "",
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
        "timeline": timeline_as_dicts(session, row.code),
    }


def create_field_visit(session: Session, *, actor: str, payload: dict, today: date | None = None) -> dict:
    now = demo_now(today)
    code = _next_code(session)
    has_cust = bool(payload.get("customer_code"))
    kind = str(payload.get("visit_kind") or ("老客户拜访" if has_cust else "陌生客户拜访"))
    row = CrmFieldVisitRow(
        code=code,
        owner_sales=actor,
        visit_plan=str(payload.get("visit_plan") or ""),
        title=str(payload.get("title") or "外勤拜访"),
        customer_code=payload.get("customer_code") or None,
        customer_name=str(payload.get("customer_name") or ""),
        visit_kind=kind,
        expected_at=payload.get("expected_at"),
        expected_address=str(payload.get("expected_address") or ""),
        before_note=str(payload.get("before_note") or ""),
        situation_note=str(payload.get("situation_note") or ""),
        photo_note=str(payload.get("photo_note") or ""),
        status="进行中",
        started_at=now,
        check_in_at=now,
        check_in_location="",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    note = str(payload.get("situation_note") or "").strip()
    if note:
        session.add(
            CrmFieldVisitLogRow(
                visit_code=code,
                recorded_at=now,
                body=note,
                created_by=actor,
            )
        )
    session.flush()
    return _serialize(session, row, today=today)


def check_in(session: Session, *, code: str, actor: str, at: datetime | None = None, today: date | None = None) -> dict:
    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    if row.status == "进行中" and row.check_in_at:
        return _serialize(session, row, today=today)
    when = at or demo_now(today)
    row.started_at = row.started_at or when
    row.check_in_at = when
    row.check_in_location = ""
    row.status = "进行中" if row.status == "待签到" else row.status
    if row.status == "待签到":
        row.status = "已签到"
    row.updated_at = when
    session.flush()
    return _serialize(session, row, today=today)


def check_out(
    session: Session,
    *,
    code: str,
    actor: str,
    at: datetime | None = None,
    today: date | None = None,
) -> dict:
    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    start = _started_at(row)
    if start is None:
        raise ValueError("尚未开始拜访")
    when = at or demo_now(today)
    if not visit_is_valid(start, when):
        gap = VALID_MINUTES - _minutes_between(start, when)
        raise ValueError(f"签退须满 {VALID_MINUTES} 分钟，还差 {max(gap, 1)} 分钟")
    row.check_out_at = when
    row.check_out_location = ""
    row.status = "已完成"
    row.updated_at = when
    session.flush()
    return _serialize(session, row, today=today)


def update_field_visit(
    session: Session,
    *,
    code: str,
    actor: str,
    payload: dict,
    today: date | None = None,
) -> dict:
    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    if row.status == "已确认":
        raise ValueError("已写入跟进，不可再改")
    for key in (
        "title",
        "visit_plan",
        "customer_code",
        "customer_name",
        "visit_kind",
        "expected_address",
        "before_note",
        "situation_note",
        "photo_note",
    ):
        if key in payload:
            setattr(row, key, payload[key])
    row.updated_at = demo_now(today)
    session.flush()
    return _serialize(session, row, today=today)


def match_customers_and_leads(session: Session, *, actor: str, text: str, customer_name: str = "") -> dict:
    from db.tables import CrmCustomerRow, CrmLeadRow

    needle = (customer_name or text or "").strip()
    customers: list[dict] = []
    for row in session.scalars(select(CrmCustomerRow)).all():
        if row.owner_sales != actor and actor and not str(row.code or "").startswith("GD-"):
            continue
        if needle and needle not in row.name and needle not in (row.code or ""):
            continue
        if not needle and row.owner_sales != actor and not str(row.code or "").startswith("GD-"):
            continue
        customers.append({"code": row.code, "name": row.name})
    if not customers and needle:
        for row in session.scalars(select(CrmCustomerRow)).all():
            if (row.owner_sales == actor or str(row.code or "").startswith("GD-")) and needle in row.name:
                customers.append({"code": row.code, "name": row.name})
    leads: list[dict] = []
    for lead in session.scalars(select(CrmLeadRow).where(CrmLeadRow.owner_sales == actor)).all():
        if needle and needle not in lead.company_name and needle not in lead.contact_name and needle not in lead.phone:
            continue
        leads.append({"code": lead.code, "company_name": lead.company_name, "contact_name": lead.contact_name})
    opp_draft = None
    if any(k in text for k in ("采购", "意向", "下单", "报价", "打样", "数量")):
        title = customer_name or (customers[0]["name"] if customers else "新客户商机")
        opp_draft = {"name": f"{title}·意向", "amount": 50000, "hint": "将建立商机（确认后落库）"}
    visit_kind = "老客户拜访" if customers else "陌生客户拜访"
    return {"customers": customers[:5], "leads": leads[:5], "visit_kind": visit_kind, "opp_draft": opp_draft}


def parse_situation_note(raw: str) -> str:
    """演示 · 将拜访草稿整理为结构化纪要（无外部 AI）。"""
    text = (raw or "").strip()
    if not text:
        return "【AI整理】未填写拜访情况，请补充现场沟通要点。"
    parts = [p.strip() for p in text.replace("；", "\n").replace("。", "\n").split("\n") if p.strip()]
    bullets = "\n".join(f"· {p}" for p in parts[:8])
    return f"【AI整理】\n{bullets}\n\n下次建议：确认决策人与打样时间表。"


def confirm_field_visit_follow(
    session: Session,
    *,
    code: str,
    actor: str,
    today: date | None = None,
    create_customer: bool = False,
    customer_code: str | None = None,
    lead_code: str | None = None,
    confirm_opportunity: bool = False,
    opp_name: str | None = None,
    opp_amount: float | None = None,
) -> dict:
    from db.crm_customer_portal import _set_cf
    from db.crm_follows import add_follow
    from db.crm_opportunity_ui import create_opportunity_for_customer
    from db.tables import CrmCustomerRow

    row = session.get(CrmFieldVisitRow, code)
    if row is None:
        raise ValueError("外勤单不存在")
    if row.status == "已确认":
        raise ValueError("已写入跟进")
    if row.status != "已完成":
        raise ValueError("须先完成签退后再写入跟进")
    if customer_code:
        row.customer_code = customer_code
        cust = session.get(CrmCustomerRow, customer_code)
        if cust:
            row.customer_name = cust.name
            row.visit_kind = "老客户拜访"
    elif create_customer and not row.customer_code:
        n = len(session.scalars(select(CrmCustomerRow)).all())
        new_code = f"C-V{n + 1:03d}"
        session.add(
            CrmCustomerRow(
                code=new_code,
                name=row.customer_name or row.title,
                channel_l1="未填",
                channel_l2="",
                owner_sales=actor,
                level=3,
                status="ACTIVE",
                duplicate_flag=False,
                custom_fields_json="{}",
            )
        )
        cust = session.get(CrmCustomerRow, new_code)
        if cust:
            _set_cf(cust, {"crm_status": "维护阶段", "created_at": DEMO_TODAY.isoformat()})
        row.customer_code = new_code
        row.visit_kind = "陌生客户拜访"
    content = (row.summary or row.situation_note or "").strip() or f"外勤拜访 · {row.title}"
    tags = _progress_tags(row)
    if tags:
        content = f"{content}\n标签：{'、'.join(tags)}"
    rec_type = "商机" if confirm_opportunity else ("客户" if row.customer_code else "线索")
    rec = add_follow(
        session,
        actor=actor,
        record_type=rec_type,
        content=f"【外勤 {code}】{content}",
        customer_code=row.customer_code,
        lead_code=lead_code,
        today=today or DEMO_TODAY,
        photo_note=f"field:{code}",
    )
    opp_info = None
    if confirm_opportunity and row.customer_code:
        opp_info = create_opportunity_for_customer(
            session,
            customer_code=row.customer_code,
            name=opp_name or f"{row.customer_name}·商机",
            amount=float(opp_amount or 0),
            owner_sales=actor,
            expect_close_date=None,
            actor=actor,
            source="线索转入" if lead_code else "客户新增",
        )
        from db.tables import CrmFollowRecordRow

        fr = session.get(CrmFollowRecordRow, rec["id"])
        if fr is not None:
            fr.opportunity_id = opp_info.get("id")
            fr.record_type = "商机"
    row.linked_visit_id = rec["id"]
    row.status = "已确认"
    row.updated_at = demo_now(today)
    session.flush()
    return {"visit": get_field_visit(session, code, today=today), "follow": rec, "opportunity": opp_info}


def clear_visit_logs(session: Session, visit_code: str) -> None:
    session.execute(delete(CrmFieldVisitLogRow).where(CrmFieldVisitLogRow.visit_code == visit_code))


def ensure_demo_field_visits(session: Session) -> None:
    from db.demo_manual_data import is_manual_data_mode

    if is_manual_data_mode(session):
        return
    if session.get(CrmFieldVisitRow, "WF000001"):
        return
    done_in = datetime(2026, 9, 14, 10, 0, 0)
    done_out = done_in + timedelta(minutes=20)
    session.add(
        CrmFieldVisitRow(
            code="WF000001",
            owner_sales="李业务",
            visit_plan="月度维护",
            title="好利来门店回访",
            customer_code="C-001",
            customer_name="好利来食品",
            visit_kind="老客户拜访",
            expected_at=done_in,
            expected_address="南京西路门店",
            before_note="带上新款样品册",
            situation_note="决策人同意加急打样",
            status="已完成",
            started_at=done_in,
            check_in_at=done_in,
            check_out_at=done_out,
            meets_standard=True,
            progress_tags_json='["挖掘到商机"]',
            eval_source="rule",
            created_at=done_in,
            updated_at=done_out,
        )
    )
    open_in = datetime(2026, 9, 15, 13, 50, 0)
    session.add(
        CrmFieldVisitRow(
            code="WF000002",
            owner_sales="李业务",
            visit_plan="陌拜",
            title="创意园陌生拜访",
            customer_name="",
            visit_kind="陌生客户拜访",
            expected_at=open_in,
            expected_address="浦东创意园",
            status="进行中",
            started_at=open_in,
            check_in_at=open_in,
            check_in_location="模拟定位",
            created_at=open_in,
            updated_at=open_in,
        )
    )
    session.flush()
