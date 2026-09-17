"""演示场景台落库：清场锁、编制、造数。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.order_kitting import refresh_order_kitting
from db.order_lifecycle import add_to_scheduling_pool
from db.tables import (
    AppSettingRow,
    CrmContractPaymentPlanRow,
    CrmContractRow,
    CrmCustomerRow,
    CrmPaymentReceiptRow,
    HrAttendancePunchRow,
    HrEmployeeRow,
    HrGroupAttendanceRow,
    KingdeeSyncLogRow,
    MdCapacityCalendarRow,
    MdItemRow,
    OrderChangeRequestRow,
    PendingRollRow,
    PlanVersionRow,
    ProdQtyReportRow,
    ProdTimeReportRow,
    SoOrderDueEventRow,
    SoOrderLineRow,
    SoOrderRow,
    StockRow,
    WecomMessageRow,
    WecomScheduleEventRow,
    WoDependencyRow,
    WoInsertLogRow,
    WoRow,
    WoTaskRow,
)
from shared.audit import write_audit
from shared.demo_scenario import (
    CUSTOMERS,
    DEMO_TODAY,
    WORK_CENTERS,
    DueMode,
    ItemShareMode,
    plan_orders,
    plan_roster,
    plan_to_api,
)

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "seed" / "seed_data.json"
SCENARIO_LOCK_KEY = "demo_scenario_lock"


def is_scenario_locked(session: Session) -> bool:
    row = session.get(AppSettingRow, SCENARIO_LOCK_KEY)
    return bool(row and row.value == "1")


def set_scenario_lock(session: Session, locked: bool) -> None:
    row = session.get(AppSettingRow, SCENARIO_LOCK_KEY)
    value = "1" if locked else "0"
    if row is None:
        session.add(AppSettingRow(key=SCENARIO_LOCK_KEY, value=value))
    else:
        row.value = value


def _delete_scen_crm(session: Session) -> dict[str, int]:
    contracts = list(
        session.scalars(select(CrmContractRow).where(CrmContractRow.contract_no.like("HT-SCEN-%"))).all()
    )
    nos = [c.contract_no for c in contracts]
    receipts = 0
    plans = 0
    if nos:
        receipts = session.execute(
            delete(CrmPaymentReceiptRow).where(CrmPaymentReceiptRow.contract_no.in_(nos))
        ).rowcount or 0
        plans = session.execute(
            delete(CrmContractPaymentPlanRow).where(CrmContractPaymentPlanRow.contract_no.in_(nos))
        ).rowcount or 0
        session.execute(delete(CrmContractRow).where(CrmContractRow.contract_no.in_(nos)))
    customers = session.execute(
        delete(CrmCustomerRow).where(CrmCustomerRow.code.like("SCEN-%"))
    ).rowcount or 0
    return {"scen_contracts": len(nos), "scen_customers": customers, "receipts": receipts, "plans": plans}


def reset_order_scenario(session: Session) -> dict:
    """清空订单事务链与库存数量，保留产品维表，并锁场景防种子重导。"""
    session.execute(delete(WoTaskRow))
    session.execute(delete(WoDependencyRow))
    session.execute(delete(WoInsertLogRow))
    session.execute(delete(WoRow))
    session.execute(delete(PlanVersionRow))
    session.execute(delete(SoOrderLineRow))
    session.execute(delete(SoOrderDueEventRow))
    session.execute(delete(OrderChangeRequestRow))
    session.execute(delete(PendingRollRow))
    session.execute(delete(ProdQtyReportRow))
    session.execute(delete(ProdTimeReportRow))
    session.execute(delete(KingdeeSyncLogRow))
    session.execute(delete(WecomMessageRow))
    session.execute(delete(WecomScheduleEventRow))
    session.execute(delete(SoOrderRow))
    crm = _delete_scen_crm(session)
    now = datetime.now(UTC).replace(tzinfo=None)
    stock_n = 0
    for row in session.scalars(select(StockRow)).all():
        row.qty_available = "0"
        row.source = "DEMO_RESET"
        row.updated_at = now
        stock_n += 1
    set_scenario_lock(session, True)
    session.flush()
    stats = {
        "orders": int(session.scalar(select(func.count()).select_from(SoOrderRow)) or 0),
        "wos": int(session.scalar(select(func.count()).select_from(WoRow)) or 0),
        "tasks": int(session.scalar(select(func.count()).select_from(WoTaskRow)) or 0),
        "stock_zeroed": stock_n,
        "items": int(session.scalar(select(func.count()).select_from(MdItemRow)) or 0),
        "locked": True,
        **crm,
    }
    return stats


def apply_roster(session: Session, *, headcount: int = 5) -> dict:
    plan = plan_roster(headcount)
    prod = list(
        session.scalars(select(HrEmployeeRow).where(HrEmployeeRow.employee_kind == "PRODUCTION")).all()
    )
    prod_nos = [e.emp_no for e in prod]
    if prod_nos:
        session.execute(delete(HrAttendancePunchRow).where(HrAttendancePunchRow.emp_no.in_(prod_nos)))
    session.execute(delete(HrEmployeeRow).where(HrEmployeeRow.employee_kind == "PRODUCTION"))
    session.execute(delete(HrGroupAttendanceRow))
    session.flush()

    hired = date(2020, 1, 15)
    for g in plan["groups"]:
        dept = g["dept"]
        group = g["group_code"]
        department = "生产一部" if dept == "FINISHED_DEPT" else "生产二部"
        people = [g["leader"], *g["operators"]]
        for i, person in enumerate(people):
            is_lead = i == 0
            end = date(2027, 12, 31) if is_lead else date(2026, 10, 10 + (i % 15))
            session.add(
                HrEmployeeRow(
                    emp_no=person["emp_no"],
                    name=person["name"],
                    department=department,
                    position="班组长" if is_lead else "操作工",
                    status="ACTIVE",
                    hired_date=hired + timedelta(days=30 * i),
                    employee_kind="PRODUCTION",
                    is_team_leader=is_lead,
                    schedule_dept=dept,
                    group_code=group,
                    contract_start=date(2025, 1, 1),
                    contract_end=end,
                    contract_remind_days=30,
                )
            )
        session.execute(
            MdCapacityCalendarRow.__table__.update()
            .where(MdCapacityCalendarRow.dept == dept)
            .where(MdCapacityCalendarRow.group_code == group)
            .values(headcount=headcount)
        )

    horizon_end = DEMO_TODAY + timedelta(days=30)
    cursor = DEMO_TODAY
    att_n = 0
    punch_n = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    new_emps = [
        e
        for g in plan["groups"]
        for e in (g["leader"], *g["operators"])
    ]
    while cursor <= horizon_end:
        if cursor.isoweekday() <= 5:
            for dept, group, _label in WORK_CENTERS:
                session.add(
                    HrGroupAttendanceRow(
                        schedule_dept=dept,
                        group_code=group,
                        work_date=cursor,
                        headcount_present=headcount,
                        source="DEMO_ROSTER",
                        updated_at=now,
                    )
                )
                att_n += 1
            for person in new_emps:
                session.add(
                    HrAttendancePunchRow(
                        emp_no=person["emp_no"],
                        punch_at=datetime(cursor.year, cursor.month, cursor.day, 8, 0, 0),
                        punch_type="上班",
                        device_code="KQ-DEMO",
                        device_name="场景台考勤",
                        synced_at=now,
                    )
                )
                session.add(
                    HrAttendancePunchRow(
                        emp_no=person["emp_no"],
                        punch_at=datetime(cursor.year, cursor.month, cursor.day, 17, 30, 0),
                        punch_type="下班",
                        device_code="KQ-DEMO",
                        device_name="场景台考勤",
                        synced_at=now,
                    )
                )
                punch_n += 2
        cursor += timedelta(days=1)
    session.flush()
    return {
        "groups": len(plan["groups"]),
        "employees": headcount * len(plan["groups"]),
        "headcount": headcount,
        "attendance_rows": att_n,
        "punches": punch_n,
    }


def _ensure_scen_customers(session: Session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    channels = (
        ("烘焙", "工厂"),
        ("礼品", "企业"),
        ("烘焙", "门店"),
        ("餐饮", "酒店"),
        ("电商", "平台"),
        ("烘焙", "连锁"),
        ("礼品", "婚庆"),
        ("零售", "超市"),
        ("餐饮", "央厨"),
        ("会展", "陈列"),
        ("零售", "社区"),
        ("餐饮", "茶饮"),
    )
    for i, (code, name, sales, level) in enumerate(CUSTOMERS):
        ch1, ch2 = channels[i]
        existing = session.get(CrmCustomerRow, code)
        if existing is None:
            session.add(
                CrmCustomerRow(
                    code=code,
                    name=name,
                    channel_l1=ch1,
                    channel_l2=ch2,
                    owner_sales=sales,
                    level=level,
                    status="ACTIVE",
                    custom_fields_json="{}",
                    duplicate_flag=False,
                )
            )
        else:
            existing.name = name
            existing.owner_sales = sales
            existing.level = level
            existing.status = "ACTIVE"
        contract_no = f"HT-SCEN-{code[-2:]}"
        contract = session.get(CrmContractRow, contract_no)
        if contract is None:
            session.add(
                CrmContractRow(
                    contract_no=contract_no,
                    customer_code=code,
                    title=f"{name} · 场景演示合同",
                    status="ACTIVE",
                    contract_amount="200000",
                    signed_date=DEMO_TODAY,
                    owner_sales=sales,
                    terms_json="{}",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            session.add(
                CrmContractPaymentPlanRow(
                    contract_no=contract_no,
                    line_no=1,
                    milestone="签约预收 30%",
                    condition_type="ON_SIGN",
                    plan_date=DEMO_TODAY + timedelta(days=3),
                    plan_amount="60000",
                    status="OPEN",
                )
            )
            session.add(
                CrmContractPaymentPlanRow(
                    contract_no=contract_no,
                    line_no=2,
                    milestone="发货尾款 70%",
                    condition_type="ON_DELIVERY",
                    plan_date=DEMO_TODAY + timedelta(days=30),
                    plan_amount="140000",
                    status="OPEN",
                )
            )
        else:
            contract.status = "ACTIVE"
            contract.customer_code = code


def apply_order_plan(
    session: Session,
    plan: dict,
    *,
    auto_add_to_pool: bool = False,
) -> dict:
    _ensure_scen_customers(session)
    session.flush()
    created = 0
    for o in plan["orders"]:
        if o["due_date"] < DEMO_TODAY:
            raise ValueError(f"{o['order_no']} 交期 {o['due_date']} 早于演示日 {DEMO_TODAY}")
        first = o["lines"][0]
        item = session.get(MdItemRow, first["item_code"])
        session.add(
            SoOrderRow(
                order_no=o["order_no"],
                customer=o["customer_name"],
                sales_name=o["sales_name"],
                customer_code=o["customer_code"],
                owner_sales=o["sales_name"],
                item_code=first["item_code"],
                qty_order=str(first["qty"]),
                unit=first["unit"],
                due_date=o["due_date"],
                ready_date=o["ready_date"],
                customer_level=o["customer_level"],
                amount=o["amount"],
                is_urgent=bool(o["is_urgent"]),
                schedule_phase="PENDING",
                order_status="CONFIRMED",
                order_source="DEMO_SCENARIO",
                contract_no=o["contract_no"],
            )
        )
        for i, ln in enumerate(o["lines"], start=1):
            md = session.get(MdItemRow, ln["item_code"])
            session.add(
                SoOrderLineRow(
                    order_no=o["order_no"],
                    line_no=i,
                    item_code=ln["item_code"],
                    item_name=(md.item_name if md else ln["item_code"]),
                    qty=str(ln["qty"]),
                    unit=ln["unit"],
                    unit_price=str(ln["unit_price"]),
                    line_amount=str(ln["line_amount"]),
                )
            )
        created += 1
        if item is None:
            raise ValueError(f"品项不存在: {first['item_code']}")
    session.flush()
    for o in plan["orders"]:
        refresh_order_kitting(session, o["order_no"], today=DEMO_TODAY)
    if auto_add_to_pool:
        add_to_scheduling_pool(session, [o["order_no"] for o in plan["orders"]])
    session.flush()
    return {
        "order_count": created,
        "customer_count": len({o["customer_code"] for o in plan["orders"]}),
        "contract_count": len({o["contract_no"] for o in plan["orders"]}),
        "locked": True,
        **plan_to_api(plan),
    }


def generate_orders(
    session: Session,
    *,
    order_count: int,
    due_mode: str,
    item_share: str,
    rng_seed: int = 20260915,
    auto_add_to_pool: bool = False,
) -> dict:
    plan = plan_orders(
        order_count,
        DueMode(due_mode),
        ItemShareMode(item_share),
        today=DEMO_TODAY,
        rng_seed=rng_seed,
    )
    reset_stats = reset_order_scenario(session)
    applied = apply_order_plan(session, plan, auto_add_to_pool=auto_add_to_pool)
    applied["reset"] = reset_stats
    return applied


def restore_official_seed(session: Session) -> dict:
    from db.demo_crm_seed import ensure_demo_crm
    from db.hr_seed import HR_VERSION_KEY, ensure_hr_seed
    from db.order_lines import LINES_VERSION_KEY, ensure_order_lines
    from db.seed import reload_seed_json, seed_manifest

    reset_order_scenario(session)
    set_scenario_lock(session, False)
    for key in (HR_VERSION_KEY, LINES_VERSION_KEY):
        row = session.get(AppSettingRow, key)
        if row is not None:
            session.delete(row)
    session.flush()
    manifest = reload_seed_json(session, SEED_PATH)
    ensure_hr_seed(session)
    ensure_demo_crm(session)
    ensure_order_lines(session)
    from db.prod_stats_seed import STATS_VERSION_KEY, ensure_dept1_stats_seed

    row = session.get(AppSettingRow, STATS_VERSION_KEY)
    if row is not None:
        session.delete(row)
        session.flush()
    ensure_dept1_stats_seed(session)
    session.flush()
    return {
        "locked": False,
        "orders": int(session.scalar(select(func.count()).select_from(SoOrderRow)) or 0),
        **manifest,
    }


def scenario_status(session: Session) -> dict:
    stock_rows = list(session.scalars(select(StockRow)).all())
    stock_zero = all(float(r.qty_available) == 0 for r in stock_rows) if stock_rows else True
    groups = []
    for dept, group, label in WORK_CENTERS:
        n = int(
            session.scalar(
                select(func.count()).select_from(HrEmployeeRow).where(
                    HrEmployeeRow.schedule_dept == dept,
                    HrEmployeeRow.group_code == group,
                    HrEmployeeRow.status == "ACTIVE",
                )
            )
            or 0
        )
        groups.append({"dept": dept, "group_code": group, "label": label, "headcount": n})
    return {
        "today": DEMO_TODAY.isoformat(),
        "locked": is_scenario_locked(session),
        "order_count": int(session.scalar(select(func.count()).select_from(SoOrderRow)) or 0),
        "item_count": int(session.scalar(select(func.count()).select_from(MdItemRow)) or 0),
        "stock_zero": stock_zero,
        "groups": groups,
    }


def audit_scenario(session: Session, *, role: str, action: str, after: dict) -> None:
    from shared.auth import user_for_role

    user = user_for_role(role)
    write_audit(
        session,
        actor_role=role,
        actor_name=user.name if user else role,
        entity_type="demo_scenario",
        entity_id=action,
        action=action,
        after=after,
    )
