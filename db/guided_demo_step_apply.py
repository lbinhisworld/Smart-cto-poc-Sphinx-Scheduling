"""演示线各环节「生成数据」落业务表（P1 起逐步扩展）。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.guided_demo_realism import load_lexicon
from db.seed import import_seed_items_subset
from db.tables import (
    CrmCustomerRow,
    CrmFieldVisitLogRow,
    CrmFieldVisitRow,
    CrmOpportunityRow,
    HrAttendancePunchRow,
    HrEmployeeRow,
    MdItemRow,
)
from shared.guided_demo_path import DEMO_ANCHOR_TODAY

SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "seed_data.json"


def _story_root_item_codes() -> list[str]:
    lex = load_lexicon()
    codes: list[str] = []
    for story in lex.get("story_bundles") or []:
        code = str(story.get("item_code") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def run_entity_prefix(run_id: str) -> str:
    return f"GD-{run_id.replace('-', '')[:8].upper()}"


def clear_step_business(session: Session, run_id: str, step_id: str) -> dict:
    if step_id == "roster":
        return _clear_roster_for_run(session, run_id)
    if step_id == "product":
        from db.seed import _collect_item_closure, delete_items_subset
        import json

        with SEED_PATH.open(encoding="utf-8") as fh:
            seed = json.load(fh)
        closure = _collect_item_closure(seed, _story_root_item_codes())
        delete_items_subset(session, closure)
        return {"items_removed": len(closure)}
    if step_id == "customer":
        return _clear_customers_for_run(session, run_id)
    if step_id == "visit_stranger":
        return _clear_visits_for_run(session, run_id)
    return {}


def _clear_roster_for_run(session: Session, run_id: str) -> dict:
    prefix = run_entity_prefix(run_id) + "-"
    emps = list(session.scalars(select(HrEmployeeRow).where(HrEmployeeRow.emp_no.like(f"{prefix}%"))).all())
    nos = [e.emp_no for e in emps]
    punches = 0
    if nos:
        punches = session.execute(
            delete(HrAttendancePunchRow).where(HrAttendancePunchRow.emp_no.in_(nos))
        ).rowcount or 0
    removed = session.execute(delete(HrEmployeeRow).where(HrEmployeeRow.emp_no.like(f"{prefix}%"))).rowcount or 0
    return {"employees_removed": removed, "punches_removed": punches}


def step_business_applied(session: Session, run_id: str, step_id: str) -> bool:
    if step_id == "roster":
        prefix = run_entity_prefix(run_id) + "-"
        n = int(
            session.scalar(
                select(func.count()).select_from(HrEmployeeRow).where(HrEmployeeRow.emp_no.like(f"{prefix}%"))
            )
            or 0
        )
        return n > 0
    if step_id == "product":
        roots = _story_root_item_codes()
        if not roots:
            return False
        n = int(
            session.scalar(
                select(func.count()).select_from(MdItemRow).where(MdItemRow.item_code.in_(roots))
            )
            or 0
        )
        return n >= len(roots)
    if step_id == "customer":
        prefix = f"{run_entity_prefix(run_id)}-C"
        n = int(
            session.scalar(
                select(func.count()).select_from(CrmCustomerRow).where(CrmCustomerRow.code.like(f"{prefix}%"))
            )
            or 0
        )
        return n >= 5
    if step_id == "visit_stranger":
        prefix = f"{run_entity_prefix(run_id)}-V"
        n = int(
            session.scalar(
                select(func.count())
                .select_from(CrmFieldVisitRow)
                .where(CrmFieldVisitRow.code.like(f"{prefix}%"))
            )
            or 0
        )
        return n >= 5
    return False


def compact_apply_user_message(step_id: str, apply_stats: dict) -> str:
    if not apply_stats.get("applied"):
        return "已记录演示谱系（本环节尚未写入业务表）"
    if step_id == "roster":
        n = int(apply_stats.get("employees_created") or 0)
        return f"已写入花名册 {n} 人，请在下方名单查看"
    if step_id == "product":
        n = int(apply_stats.get("story_items") or len(apply_stats.get("root_item_codes") or []) or 0)
        return f"已写入 {n} 个故事线成品（含 BOM），请在左侧列表选择浏览"
    if step_id == "customer":
        n = int(apply_stats.get("customers_created") or 0)
        return f"已写入我的客户 {n} 家，请在下方列表查看"
    if step_id == "visit_stranger":
        n = int(apply_stats.get("visits_created") or 0)
        return f"已写入拜访签到 {n} 条，请在下方列表查看"
    return "已生成本环节演示数据"


def apply_step_seed(session: Session, run_id: str, step_id: str, refs: list[dict]) -> dict:
    if step_id == "roster":
        return _apply_roster(session, run_id, refs)
    if step_id == "product":
        return _apply_product(session, run_id, refs)
    if step_id == "customer":
        return _apply_customer(session, run_id, refs)
    if step_id == "visit_stranger":
        return _apply_visit_stranger(session, run_id, refs)
    return {"applied": False, "step_id": step_id}


def _apply_roster(session: Session, run_id: str, refs: list[dict]) -> dict:
    """环节 1：仅落 5 条故事线对应的销售（与 stub refs 一一对应，不含产线编制）。"""
    _clear_roster_for_run(session, run_id)
    anchor = date.fromisoformat(DEMO_ANCHOR_TODAY)
    hired_base = date(2020, 1, 15)
    employees = 0

    for i, ref in enumerate(refs, start=1):
        display = str(ref.get("display") or "").strip()
        name = display.split("（")[0].strip() if display else f"销售{i}"
        emp_no = str(ref.get("entity_id") or "").strip()
        if not emp_no:
            continue
        session.add(
            HrEmployeeRow(
                emp_no=emp_no,
                name=name,
                department="营销中心",
                position="销售总监" if i == 1 else ("销售经理" if i <= 3 else "销售代表"),
                status="ACTIVE",
                hired_date=hired_base + timedelta(days=10 * i),
                employee_kind="STAFF",
                is_team_leader=i == 1,
                schedule_dept=None,
                group_code=None,
                contract_start=date(2025, 1, 1),
                contract_end=date(2027, 12, 31),
                contract_remind_days=30,
            )
        )
        employees += 1

    session.flush()
    return {
        "applied": True,
        "step_id": "roster",
        "employees_created": employees,
        "story_lines": len(refs),
        "anchor_today": anchor.isoformat(),
    }


def _clear_visits_for_run(session: Session, run_id: str) -> dict:
    from db.tables import CrmFieldVisitLogRow

    prefix = f"{run_entity_prefix(run_id)}-V"
    codes = list(
        session.scalars(select(CrmFieldVisitRow.code).where(CrmFieldVisitRow.code.like(f"{prefix}%"))).all()
    )
    logs_removed = 0
    if codes:
        logs_removed = (
            session.execute(delete(CrmFieldVisitLogRow).where(CrmFieldVisitLogRow.visit_code.in_(codes))).rowcount
            or 0
        )
    removed = session.execute(
        delete(CrmFieldVisitRow).where(CrmFieldVisitRow.code.like(f"{prefix}%"))
    ).rowcount or 0
    return {"visits_removed": removed, "logs_removed": logs_removed}


def _clear_customers_for_run(session: Session, run_id: str) -> dict:
    prefix = f"{run_entity_prefix(run_id)}-C"
    codes = list(
        session.scalars(select(CrmCustomerRow.code).where(CrmCustomerRow.code.like(f"{prefix}%"))).all()
    )
    if codes:
        session.execute(delete(CrmOpportunityRow).where(CrmOpportunityRow.customer_code.in_(codes)))
        session.execute(delete(CrmCustomerRow).where(CrmCustomerRow.code.in_(codes)))
    return {"customers_removed": len(codes)}


def _apply_customer(session: Session, run_id: str, refs: list[dict]) -> dict:
    """环节 3：5 条故事线客户写入 crm_customer（我的客户）。"""
    _clear_customers_for_run(session, run_id)
    lex = load_lexicon()
    stories = {int(s["story_index"]): s for s in lex.get("story_bundles") or []}
    created = 0
    anchor = date.fromisoformat(DEMO_ANCHOR_TODAY)

    for ref in refs:
        idx = int(ref.get("story_index") or 0)
        story = stories.get(idx) or {}
        code = str(ref.get("entity_id") or "").strip()
        if not code:
            continue
        channel = str(story.get("channel") or "未分类")
        parts = [p.strip() for p in channel.split("·") if p.strip()]
        if len(parts) == 1 and " · " in channel:
            parts = [p.strip() for p in channel.split(" · ") if p.strip()]
        channel_l1 = parts[0] if parts else "未填"
        channel_l2 = parts[1] if len(parts) > 1 else ""
        cf = {
            "contact_name": "采购负责人",
            "phone": f"138{1000 + idx:04d}{2000 + idx:04d}",
            "customer_type": "直销",
            "crm_status": "维护阶段",
            "industry_type": "终端客户" if "门店" in channel else "民营企业",
            "created_at": f"{anchor.isoformat()}T10:{idx:02d}:00",
            "guided_demo_run_id": run_id,
            "story_index": idx,
        }
        session.add(
            CrmCustomerRow(
                code=code,
                name=str(story.get("customer_name") or ref.get("display") or code),
                channel_l1=channel_l1,
                channel_l2=channel_l2,
                owner_sales=str(story.get("owner_sales") or ""),
                level=2 if idx <= 2 else 3,
                status="ACTIVE",
                custom_fields_json=json.dumps(cf, ensure_ascii=False),
                duplicate_flag=False,
            )
        )
        created += 1

    session.flush()
    return {
        "applied": True,
        "step_id": "customer",
        "customers_created": created,
        "story_lines": len(refs),
    }


def _apply_visit_stranger(session: Session, run_id: str, refs: list[dict]) -> dict:
    """环节 4：5 条故事线外勤单，关联本批次 GD 客户。"""
    _clear_visits_for_run(session, run_id)
    lex = load_lexicon()
    stories = {int(s["story_index"]): s for s in lex.get("story_bundles") or []}
    run_prefix = run_entity_prefix(run_id)
    anchor = date.fromisoformat(DEMO_ANCHOR_TODAY)
    base_day = datetime(anchor.year, anchor.month, anchor.day, 9, 0, 0)
    created = 0

    for i, ref in enumerate(refs):
        idx = int(ref.get("story_index") or 0)
        story = stories.get(idx) or {}
        code = str(ref.get("entity_id") or "").strip()
        if not code:
            continue
        cust_code = f"{run_prefix}-C{idx:02d}"
        cust = session.get(CrmCustomerRow, cust_code)
        customer_name = str(cust.name if cust else story.get("customer_name") or "")
        summary = str(story.get("visit_summary") or "外勤拜访")
        title = f"{customer_name} · {summary}" if customer_name else summary
        owner = str(story.get("owner_sales") or "")
        slot = base_day + timedelta(hours=2 * i)
        # 末条保留「进行中」便于演示签退；1 条不达标（无 log）；其余已完成且达标
        if i == len(refs) - 1:
            status = "进行中"
            check_in = slot
            check_out = None
            meets = None
            tags_json = "[]"
            visit_summary = ""
        elif i == 1:
            status = "已完成"
            check_in = slot
            check_out = slot + timedelta(minutes=25)
            meets = False
            tags_json = '["无成果"]'
            visit_summary = ""
        else:
            status = "已完成"
            check_in = slot
            check_out = slot + timedelta(minutes=25)
            meets = True
            tags_json = '["挖掘到商机"]' if i == 0 else '["触达决策人"]'
            visit_summary = summary
        session.add(
            CrmFieldVisitRow(
                code=code,
                owner_sales=owner,
                visit_plan="演示线陌拜" if i < 2 else "演示线回访",
                title=title,
                customer_code=cust_code if cust else None,
                customer_name=customer_name,
                visit_kind="陌生客户拜访" if i < 2 else "老客户拜访",
                expected_at=slot,
                expected_address=str(story.get("channel") or "客户现场"),
                before_note=f"故事线 {idx} · 演示批次 {run_id[:8]}",
                situation_note=visit_summary or summary,
                status=status,
                started_at=check_in,
                check_in_at=check_in,
                check_out_at=check_out,
                check_in_location="演示定位",
                check_out_location="演示定位" if check_out else "",
                meets_standard=meets,
                progress_tags_json=tags_json,
                eval_source="rule" if meets is not None else "",
                standard_reason="" if meets else ("无有效拜访成果" if meets is False else ""),
                summary=visit_summary,
                created_at=slot,
                updated_at=check_out or check_in,
            )
        )
        if visit_summary:
            session.add(
                CrmFieldVisitLogRow(
                    visit_code=code,
                    recorded_at=check_in + timedelta(minutes=5),
                    body=visit_summary,
                    created_by=owner,
                )
            )
        created += 1

    session.flush()
    return {
        "applied": True,
        "step_id": "visit_stranger",
        "visits_created": created,
        "story_lines": len(refs),
    }


def _apply_product(session: Session, run_id: str, refs: list[dict]) -> dict:
    """环节 2：5 条故事线对应成品（P1/P2/…）及其 BOM 闭包，不含整包种子。"""
    roots = _story_root_item_codes()
    stats = import_seed_items_subset(session, SEED_PATH, roots)
    lex = load_lexicon()
    stories = lex.get("story_bundles") or []
    for story in stories:
        code = str(story.get("item_code") or "")
        row = session.get(MdItemRow, code)
        if row and story.get("item_name"):
            name = str(story["item_name"]).replace("（拟真）", "").replace("(拟真)", "").strip()
            row.item_name = name or str(story["item_name"])
    session.flush()
    return {
        "applied": True,
        "step_id": "product",
        "run_id": run_id,
        "refs": len(refs),
        "story_items": len(roots),
        "root_item_codes": roots,
        **stats,
    }
