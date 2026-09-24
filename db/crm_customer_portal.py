"""公海池、我的客户（行业树、状态分栏）。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import CrmCustomerRow, CrmFollowRecordRow

DEMO_TODAY = date(2026, 9, 15)
INDUSTRY_TREE = ("全部", "大客户", "民营企业", "世界500强", "小巨人", "终端客户", "专精特新")
CRM_STATUS_TABS = ("全部", "未分配", "维护阶段", "商机预备", "已成交", "已转售后", "关闭")
PACK_KEY = "crm_customer_portal_pack"
PACK_VERSION = "2026-09-23-cust-v2"


def _cf(row: CrmCustomerRow) -> dict[str, Any]:
    try:
        return json.loads(row.custom_fields_json or "{}")
    except json.JSONDecodeError:
        return {}


def _set_cf(row: CrmCustomerRow, patch: dict[str, Any]) -> None:
    data = _cf(row)
    data.update(patch)
    row.custom_fields_json = json.dumps(data, ensure_ascii=False)


def _crm_status(row: CrmCustomerRow) -> str:
    if not (row.owner_sales or "").strip():
        return "公海"
    st = _cf(row).get("crm_status") or "维护阶段"
    return str(st)


def _industry(row: CrmCustomerRow) -> str:
    cf = _cf(row)
    return str(cf.get("industry_type") or row.channel_l1 or "未填")


def _last_follow(session: Session, code: str) -> date | None:
    row = session.scalar(
        select(CrmFollowRecordRow.follow_date)
        .where(CrmFollowRecordRow.customer_code == code)
        .order_by(CrmFollowRecordRow.follow_date.desc())
        .limit(1)
    )
    return row


def _is_guided_demo_customer(row: CrmCustomerRow) -> bool:
    return str(row.code or "").startswith("GD-")


def _can_see_customer(role: str, actor: str, row: CrmCustomerRow) -> bool:
    # 演示线写入的客户：故事线负责人是词库销售名，与登录「李业务」等不一致，演示时销售角色也可见
    if _is_guided_demo_customer(row):
        return role in ("GM", "SALES_MGR", "SALES", "SALES_ASSIST", "FIN", "RD")
    if role in ("GM", "SALES_MGR", "FIN", "RD"):
        return True
    owner = (row.owner_sales or "").strip()
    if not owner:
        return role in ("GM", "SALES_MGR", "SALES", "SALES_ASSIST")
    if role == "SALES":
        if owner == actor:
            return True
        collab = _cf(row).get("collaborators") or []
        return actor in collab
    if role == "SALES_ASSIST":
        return owner == "李业务"
    return False


def _sea_row(session: Session, row: CrmCustomerRow) -> dict:
    cf = _cf(row)
    return {
        "code": row.code,
        "sea_pool_name": cf.get("sea_pool_name") or "-",
        "contact_name": cf.get("contact_name") or row.name,
        "customer_type": cf.get("customer_type") or "直销",
        "level": row.level,
        "company_name": row.name,
        "note": cf.get("note") or "",
        "created_by": cf.get("created_by") or "",
        "created_at": cf.get("created_at") or "",
    }


def _mine_row(session: Session, row: CrmCustomerRow, *, today: date) -> dict:
    cf = _cf(row)
    last = _last_follow(session, row.code)
    days_idle: int | None = None
    if last:
        days_idle = (today - last).days
    created = cf.get("created_at") or ""
    is_new = created.startswith("2026-09")
    return {
        "code": row.code,
        "contact_name": cf.get("contact_name") or row.name,
        "phone": cf.get("phone") or "",
        "customer_type": cf.get("customer_type") or "直销",
        "level": row.level,
        "crm_status": _crm_status(row),
        "last_follow_date": last.isoformat() if last else None,
        "days_without_follow": days_idle,
        "is_new_customer": is_new,
        "company_name": row.name,
        "owner_sales": row.owner_sales,
        "industry_type": _industry(row),
        "collaborators": list(_cf(row).get("collaborators") or []),
    }


def list_sea(
    session: Session,
    *,
    role: str,
    actor: str,
    pool_name: str | None = None,
    contact: str | None = None,
    customer_type: str | None = None,
) -> list[dict]:
    rows = session.scalars(select(CrmCustomerRow).order_by(CrmCustomerRow.code)).all()
    out: list[dict] = []
    for row in rows:
        if (row.owner_sales or "").strip():
            continue
        if role not in ("GM", "SALES_MGR", "SALES", "SALES_ASSIST"):
            continue
        cf = _cf(row)
        if pool_name and pool_name not in str(cf.get("sea_pool_name") or ""):
            continue
        if contact and contact not in str(cf.get("contact_name") or row.name):
            continue
        if customer_type and customer_type != str(cf.get("customer_type") or ""):
            continue
        out.append(_sea_row(session, row))
    return out


def list_mine(
    session: Session,
    *,
    role: str,
    actor: str,
    today: date,
    industry: str | None = None,
    status_tab: str | None = None,
    code: str | None = None,
    contact: str | None = None,
) -> dict:
    rows = session.scalars(select(CrmCustomerRow).order_by(CrmCustomerRow.code)).all()
    counts = {s: 0 for s in CRM_STATUS_TABS}
    filtered: list[dict] = []
    for row in rows:
        if not (row.owner_sales or "").strip():
            continue
        if not _can_see_customer(role, actor, row):
            continue
        st = _crm_status(row)
        for tab in CRM_STATUS_TABS:
            if tab == "全部" or tab == st:
                counts[tab] += 1
        if industry and industry != "全部" and _industry(row) != industry:
            continue
        if status_tab and status_tab != "全部" and st != status_tab:
            continue
        if code and code not in row.code:
            continue
        if contact and contact not in str(_cf(row).get("contact_name") or row.name):
            continue
        filtered.append(_mine_row(session, row, today=today))
    return {"items": filtered, "status_counts": counts, "industry_tree": list(INDUSTRY_TREE)}


def claim_sea(session: Session, *, codes: list[str], actor: str) -> int:
    n = 0
    for code in codes:
        row = session.get(CrmCustomerRow, code)
        if row is None or (row.owner_sales or "").strip():
            continue
        row.owner_sales = actor
        _set_cf(row, {"crm_status": "维护阶段"})
        n += 1
    return n


def assign_sea(session: Session, *, codes: list[str], owner_sales: str) -> int:
    n = 0
    for code in codes:
        row = session.get(CrmCustomerRow, code)
        if row is None or (row.owner_sales or "").strip():
            continue
        row.owner_sales = owner_sales
        _set_cf(row, {"crm_status": "维护阶段"})
        n += 1
    return n


def set_collaborators(session: Session, *, code: str, names: list[str], actor: str, role: str) -> None:
    row = session.get(CrmCustomerRow, code)
    if row is None:
        raise ValueError("客户不存在")
    if role == "SALES" and row.owner_sales != actor:
        raise ValueError("无权分配协作人")
    clean = [n.strip() for n in names if n and n.strip()]
    _set_cf(row, {"collaborators": clean})


def close_customer(session: Session, *, code: str, actor: str, role: str) -> None:
    row = session.get(CrmCustomerRow, code)
    if row is None:
        raise ValueError("客户不存在")
    if role == "SALES" and row.owner_sales != actor:
        raise ValueError("无权关闭")
    _set_cf(row, {"crm_status": "关闭"})


def ensure_demo_customer_portal(session: Session) -> None:
    from db.tables import AppSettingRow

    sea = session.get(CrmCustomerRow, "C-010")
    if sea:
        sea.owner_sales = ""
        _set_cf(
            sea,
            {
                "sea_pool_name": "默认公海",
                "contact_name": "孙悦",
                "customer_type": "直销",
                "crm_status": "公海",
                "created_by": "系统",
                "created_at": "2026-08-20",
            },
        )
    li = session.get(CrmCustomerRow, "C-001")
    if li:
        li.owner_sales = "李业务"
        _set_cf(
            li,
            {
                "industry_type": "大客户",
                "customer_type": "直销",
                "crm_status": "维护阶段",
                "contact_name": "门店采购",
                "phone": "13800001111",
                "created_at": "2026-09-05",
            },
        )
    marker = session.get(AppSettingRow, PACK_KEY)
    if marker is None:
        session.add(AppSettingRow(key=PACK_KEY, value=PACK_VERSION))
    else:
        marker.value = PACK_VERSION
    session.flush()
