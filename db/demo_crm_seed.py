"""一体化 POC：各模块演示数据（幂等 + demo_version 同步）。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.services import flow as flow_service
from db.order_change_service import create_change_request
from db.tables import (
    AppSettingRow,
    CrmContractPaymentPlanRow,
    CrmContractRow,
    CrmCustomerRow,
    CrmOpportunityRow,
    CrmPaymentReceiptRow,
    CrmQuoteRow,
    CrmSampleRow,
    CrmSampleStepRow,
    OrderChangeRequestRow,
    SoOrderRow,
    WecomMessageRow,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"
DEMO_VERSION_KEY = "demo_data_version"
ANCHOR_TODAY = date(2026, 9, 15)


def _load_demo() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def _stored_demo_version(session: Session) -> str | None:
    row = session.get(AppSettingRow, DEMO_VERSION_KEY)
    return row.value if row else None


def _set_demo_version(session: Session, version: str) -> None:
    row = session.get(AppSettingRow, DEMO_VERSION_KEY)
    if row is None:
        session.add(AppSettingRow(key=DEMO_VERSION_KEY, value=version))
    else:
        row.value = version


def _upsert_customers(session: Session, crm: dict) -> int:
    n = 0
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
            n += 1
        else:
            existing.name = row["name"]
            existing.channel_l1 = row["channel_l1"]
            existing.channel_l2 = row["channel_l2"]
            existing.owner_sales = row["owner_sales"]
            existing.level = row.get("level", 3)
            existing.duplicate_flag = bool(row.get("duplicate_flag", False))
    return n


def _reload_contracts(session: Session, crm: dict) -> int:
    session.execute(delete(CrmPaymentReceiptRow))
    session.execute(delete(CrmContractPaymentPlanRow))
    session.execute(delete(CrmContractRow))
    from datetime import UTC, datetime

    n = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in crm.get("contracts", []):
        session.add(
            CrmContractRow(
                contract_no=row["contract_no"],
                customer_code=row["customer_code"],
                title=row["title"],
                status=row.get("status", "ACTIVE"),
                contract_amount=str(row["contract_amount"]),
                signed_date=date.fromisoformat(row["signed_date"]) if row.get("signed_date") else None,
                owner_sales=row.get("owner_sales", ""),
                opportunity_id=row.get("opportunity_id"),
                terms_json=json.dumps(row.get("terms") or {}, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )
        plan_ids: dict[int, int] = {}
        for p in row.get("plans") or []:
            plan = CrmContractPaymentPlanRow(
                contract_no=row["contract_no"],
                line_no=int(p["line_no"]),
                milestone=p.get("milestone", ""),
                condition_type=p.get("condition_type", "CUSTOM"),
                condition_note=p.get("condition_note", ""),
                plan_date=date.fromisoformat(p["plan_date"]),
                plan_amount=str(p["plan_amount"]),
                status=p.get("status", "OPEN"),
            )
            session.add(plan)
            session.flush()
            plan_ids[int(p["line_no"])] = plan.id
        for rc in row.get("receipts") or []:
            plan_id = None
            if rc.get("plan_line_no") is not None:
                plan_id = plan_ids.get(int(rc["plan_line_no"]))
            session.add(
                CrmPaymentReceiptRow(
                    contract_no=row["contract_no"],
                    plan_id=plan_id,
                    receipt_date=date.fromisoformat(rc["receipt_date"]),
                    amount=str(rc["amount"]),
                    method=rc.get("method", "银行转账"),
                    ref_no=rc.get("ref_no", ""),
                    status=rc.get("status", "CONFIRMED"),
                    note=rc.get("note", ""),
                )
            )
        n += 1
    return n


def _reload_crm_rows(session: Session, crm: dict) -> dict:
    session.execute(delete(CrmOpportunityRow))
    session.execute(delete(CrmSampleStepRow))
    session.execute(delete(CrmSampleRow))
    session.execute(delete(CrmQuoteRow))
    stats = {"opportunities": 0, "samples": 0, "quotes": 0, "contracts": 0}
    for row in crm.get("opportunities", []):
        session.add(
            CrmOpportunityRow(
                name=row["name"],
                customer_code=row["customer_code"],
                stage=row["stage"],
                amount=str(row["amount"]),
                owner_sales=row["owner_sales"],
                expect_close_date=(
                    date.fromisoformat(row["expect_close_date"]) if row.get("expect_close_date") else None
                ),
                sample_code=row.get("sample_code"),
            )
        )
        stats["opportunities"] += 1
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
        for i, st in enumerate(row.get("steps") or [], start=1):
            session.add(
                CrmSampleStepRow(
                    sample_code=row["code"],
                    step_no=i,
                    stage=st.get("stage") or st.get("环节", "打样"),
                    event_date=date.fromisoformat(st["event_date"]),
                    product_desc=st.get("product_desc") or st.get("product") or row["item_draft_name"],
                    situation_desc=st.get("situation_desc") or st.get("description") or "",
                    round_no=st.get("round_no"),
                )
            )
    for row in crm.get("quotes", []):
        session.add(
            CrmQuoteRow(
                code=row["code"],
                customer_code=row["customer_code"],
                sample_code=row.get("sample_code"),
                total_amount=str(row["total_amount"]),
                status=row.get("status", "DRAFT"),
                owner_sales=row.get("owner_sales", ""),
                lines_json=json.dumps(row.get("lines") or [], ensure_ascii=False),
            )
        )
        stats["quotes"] += 1
    stats["contracts"] = _reload_contracts(session, crm)
    return stats


def _patch_orders(session: Session, enrich: dict) -> int:
    patched = 0
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
        phase = row.schedule_phase or "PENDING"
        if (
            phase == "PENDING"
            and patch.get("order_status")
            and row.order_status != patch["order_status"]
        ):
            row.order_status = patch["order_status"]
            changed = True
        if patch.get("contract_no") and row.contract_no != patch["contract_no"]:
            row.contract_no = patch["contract_no"]
            changed = True
        if changed:
            patched += 1
    for row in session.scalars(select(SoOrderRow)):
        if not row.owner_sales and row.sales_name:
            row.owner_sales = row.sales_name
    return patched


def _seed_wecom_messages(session: Session, messages: list[dict]) -> int:
    added = 0
    for msg in messages:
        title = msg["title"]
        exists = session.scalar(
            select(func.count())
            .select_from(WecomMessageRow)
            .where(WecomMessageRow.title == title)
        )
        if exists:
            continue
        flow_service.emit_wecom_message(
            session,
            scene=msg["scene"],
            title=title,
            body=msg.get("body", ""),
            deep_link=msg.get("deep_link", "/portal"),
            role_targets=list(msg.get("role_targets") or []),
        )
        added += 1
    return added


def _seed_pending_change(session: Session, spec: dict | None) -> int:
    if not spec:
        return 0
    order_no = spec["order_no"]
    if session.get(SoOrderRow, order_no) is None:
        return 0
    pending = session.scalar(
        select(func.count())
        .select_from(OrderChangeRequestRow)
        .where(
            OrderChangeRequestRow.order_no == order_no,
            OrderChangeRequestRow.status == "PENDING",
        )
    )
    if pending:
        return 0
    new_due = date.fromisoformat(spec["new_due"])
    create_change_request(
        session,
        order_no=order_no,
        new_due=new_due,
        requested_by=spec.get("requested_by", "演示销售"),
        requested_role=spec.get("requested_role", "SALES"),
        today=ANCHOR_TODAY,
    )
    return 1


def ensure_demo_crm(session: Session) -> dict:
    """灌入 CRM、订单扩展、企微与待办演示数据；demo_version 变更时重建 CRM 子表。"""
    data = _load_demo()
    meta = data.get("meta") or {}
    target_version = str(meta.get("demo_version") or "legacy")
    crm = data.get("crm") or {}

    stats: dict = {
        "demo_version": target_version,
        "resynced": False,
        "customers": 0,
        "opportunities": 0,
        "samples": 0,
        "quotes": 0,
        "orders_patched": 0,
        "wecom_added": 0,
        "pending_changes": 0,
    }

    stored = _stored_demo_version(session)
    need_resync = stored != target_version

    stats["customers"] = _upsert_customers(session, crm)

    seed_contract_n = len(crm.get("contracts") or [])
    contract_count = int(session.scalar(select(func.count()).select_from(CrmContractRow)) or 0)
    need_contracts = seed_contract_n > 0 and contract_count < seed_contract_n

    if need_resync or need_contracts:
        if need_resync:
            crm_stats = _reload_crm_rows(session, crm)
            stats.update(crm_stats)
            stats["resynced"] = True
            _set_demo_version(session, target_version)
        elif need_contracts:
            stats["contracts"] = _reload_contracts(session, crm)
    else:
        stats["opportunities"] = int(
            session.scalar(select(func.count()).select_from(CrmOpportunityRow)) or 0
        )
        stats["samples"] = int(session.scalar(select(func.count()).select_from(CrmSampleRow)) or 0)
        stats["quotes"] = int(session.scalar(select(func.count()).select_from(CrmQuoteRow)) or 0)
        stats["contracts"] = contract_count

    stats["orders_patched"] = _patch_orders(session, data.get("order_enrichment") or {})
    stats["wecom_added"] = _seed_wecom_messages(session, data.get("wecom_messages") or [])
    stats["pending_changes"] = _seed_pending_change(session, data.get("pending_order_change"))

    return stats
