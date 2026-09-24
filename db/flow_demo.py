"""派工演示四单。不改交期，不自动把待排单排进日历。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.demo_scenario import reset_order_scenario
from db.labor_cost_queries import confirm_time_report, upsert_time_report
from db.plan_store import current_plan_version
from db.qty_carryover import confirm_wo_qty
from db.tables import SoOrderLineRow, SoOrderRow, WoRow, WoTaskRow

DEMO_TODAY = date(2026, 9, 15)

# 手工组 P1：约 300 版/天（300 枚/时 ÷ 24 枚/版 × 3 人 × 8 小时）。
FLOW_ORDERS: tuple[dict, ...] = (
    {
        "order_no": "FLOW-OK",
        "customer": "蓝岛烘焙供应链（无锡）有限公司",
        "sales_name": "陈雨桐",
        "item_code": "P1",
        "item_name": "巧克力装饰片A",
        "qty": 8,
        "unit": "BOX",
        "due_date": date(2026, 9, 25),
        "amount": "9600",
        "role": "进排程池，一天排完，测试报工报满",
    },
    {
        "order_no": "FLOW-SHORT",
        "customer": "童乐坊创意礼品有限公司",
        "sales_name": "张伟",
        "item_code": "P1",
        "item_name": "巧克力装饰片A",
        "qty": 80,
        "unit": "BOX",
        "due_date": date(2026, 10, 8),
        "amount": "96000",
        "role": "进排程池，跨天排完；测试报工只报最早一天，余量进待确认池，再二次排产",
    },
    {
        "order_no": "FLOW-HOLD",
        "customer": "丰麦连锁烘焙（华东区）",
        "sales_name": "李明轩",
        "item_code": "P1M",
        "item_name": "手工铲花插件（拟真）",
        "qty": 15,
        "unit": "BOX",
        "due_date": date(2026, 10, 20),
        "amount": "18000",
        "role": "本轮不进池。未排汇总里算「已下单未排」，带需求料和需求工时",
    },
    {
        "order_no": "FLOW-CAP",
        "customer": "极速优选礼品（产能演示）",
        "sales_name": "韩磊",
        "item_code": "P1",
        "item_name": "巧克力装饰片A",
        "qty": 150,
        "unit": "BOX",
        "due_date": date(2026, 9, 17),
        "amount": "180000",
        "role": "交期只有两天，计划约 630 版，手工组一天约 300 版。本轮不进池，和 HOLD 一起出现在未排汇总",
    },
)

POOL_ORDER_NOS = ("FLOW-OK", "FLOW-SHORT")


def flow_playbook() -> list[str]:
    return [
        "演示台点「生成派工演示四单」。这会清空现有订单和计划，只留下这四张，库存数量清零。",
        "排程页只把 FLOW-OK、FLOW-SHORT 加入排程池。FLOW-HOLD、FLOW-CAP 留在待排。",
        "一键倒排，保存发布。导出派工单：一张《组》生产排程，表头与客户表一致。",
        "组×日报工点「测试报工」。FLOW-OK 按计划报满；FLOW-SHORT 只报最早一天，剩余版数进「未完尾数待确认」。",
        "尾数选「插单」或回到排程，把剩余再排一次。这是二次排产，不改客户交期。",
        "导出未排汇总：FLOW-HOLD、FLOW-CAP 在「已下单未排」，能看见还要多少料、多少需求工时。系统没有把它们偷偷排上日历。",
    ]


def seed_flow_demo(session: Session) -> dict:
    """清场后写入四张固定单，全部待排。不排程、不改交期。"""
    reset_order_scenario(session)
    for spec in FLOW_ORDERS:
        session.add(
            SoOrderRow(
                order_no=spec["order_no"],
                customer=spec["customer"],
                sales_name=spec["sales_name"],
                owner_sales=spec["sales_name"],
                item_code=spec["item_code"],
                qty_order=str(spec["qty"]),
                unit=spec["unit"],
                due_date=spec["due_date"],
                ready_date=DEMO_TODAY,
                customer_level=3,
                amount=spec["amount"],
                is_urgent=spec["order_no"] == "FLOW-CAP",
                schedule_phase="PENDING",
                order_status="CONFIRMED",
                order_source="FLOW_DEMO",
            )
        )
        session.add(
            SoOrderLineRow(
                order_no=spec["order_no"],
                line_no=1,
                item_code=spec["item_code"],
                item_name=spec["item_name"],
                qty=str(spec["qty"]),
                unit=spec["unit"],
                unit_price="0",
                line_amount=spec["amount"],
            )
        )
    session.flush()
    dues = {row.order_no: row.due_date for row in session.scalars(select(SoOrderRow)).all()}
    return {
        "today": DEMO_TODAY.isoformat(),
        "orders": [
            {
                "order_no": spec["order_no"],
                "item_code": spec["item_code"],
                "qty": spec["qty"],
                "unit": spec["unit"],
                "due_date": spec["due_date"].isoformat(),
                "role": spec["role"],
                "in_pool": spec["order_no"] in POOL_ORDER_NOS,
            }
            for spec in FLOW_ORDERS
        ],
        "pool": list(POOL_ORDER_NOS),
        "leave_out": ["FLOW-HOLD", "FLOW-CAP"],
        "steps": flow_playbook(),
        "due_dates": {no: d.isoformat() for no, d in dues.items()},
    }


def scripted_labor_report(session: Session, *, today: date, reported_by: str) -> dict:
    """按当前计划报工：FLOW-OK 报满，FLOW-SHORT 只报最早一天。不写交期。"""
    version = current_plan_version(session)
    if version <= 0:
        raise ValueError("请先把 FLOW-OK 和 FLOW-SHORT 倒排")

    dues_before = {
        row.order_no: row.due_date
        for row in session.scalars(select(SoOrderRow).where(SoOrderRow.order_no.like("FLOW-%"))).all()
    }
    if "FLOW-OK" not in dues_before or "FLOW-SHORT" not in dues_before:
        raise ValueError("缺少演示单，请先在演示台生成派工演示四单")

    finished = list(
        session.scalars(
            select(WoRow).where(
                WoRow.plan_version == version,
                WoRow.wo_type == "FINISHED",
                WoRow.source_order_no.in_(("FLOW-OK", "FLOW-SHORT")),
            )
        ).all()
    )
    by_order = {wo.source_order_no: wo for wo in finished}
    missing = [no for no in ("FLOW-OK", "FLOW-SHORT") if no not in by_order]
    if missing:
        raise ValueError("当前计划里没有 " + "、".join(missing) + "。请只排这两张并倒排后再点测试报工")

    reports: list[dict] = []
    cells: dict[tuple[date, str, str], Decimal] = {}
    for order_no, wo in by_order.items():
        tasks = list(
            session.scalars(
                select(WoTaskRow)
                .where(WoTaskRow.wo_no == wo.wo_no, WoTaskRow.plan_version == version)
                .order_by(WoTaskRow.task_date, WoTaskRow.seq)
            ).all()
        )
        if not tasks:
            raise ValueError(f"{order_no} 没有任务，不能报工")
        plan = int(wo.qty_board_plan)
        if order_no == "FLOW-OK":
            done = plan
            note = "按计划报满"
        else:
            first = tasks[0].task_date
            done = sum(int(t.qty_board) for t in tasks if t.task_date == first)
            if done >= plan:
                done = max(1, plan // 2)
            if done >= plan:
                done = plan - 1
            note = f"只报 {first.isoformat()} 当天，剩余进入待确认池"
        result = confirm_wo_qty(
            session,
            wo_no=wo.wo_no,
            qty_board_done=done,
            reported_by=reported_by,
            work_date=tasks[0].task_date,
        )
        reports.append(
            {
                "order_no": order_no,
                "wo_no": wo.wo_no,
                "qty_board_plan": plan,
                "qty_board_done": result["qty_board_done"],
                "qty_board_remain": result["qty_board_remain"],
                "note": note,
                "roll": result["roll"],
            }
        )
        for task in tasks:
            if order_no == "FLOW-SHORT" and task.task_date != tasks[0].task_date:
                continue
            key = (task.task_date, task.dept, task.group_code)
            cells[key] = cells.get(key, Decimal(0)) + Decimal(str(task.hours_man))

    time_notes: list[str] = []
    for (work_date, dept, group), hours in cells.items():
        try:
            saved = upsert_time_report(
                session,
                work_date=work_date,
                schedule_dept=dept,
                group_code=group,
                hours_man_actual=hours,
                headcount_actual=None,
                note="测试报工",
                reported_by=reported_by,
                plan_version=version,
            )
            confirm_time_report(session, saved["id"], reported_by=reported_by)
        except ValueError as exc:
            time_notes.append(f"{work_date.isoformat()} {group} 人·时未写入：{exc}")

    dues_after = {
        row.order_no: row.due_date
        for row in session.scalars(select(SoOrderRow).where(SoOrderRow.order_no.like("FLOW-%"))).all()
    }
    if dues_after != dues_before:
        raise RuntimeError("测试报工写了交期")

    return {
        "plan_version": version,
        "today": today.isoformat(),
        "reports": reports,
        "time_notes": time_notes,
        "next": "FLOW-SHORT 的剩余版数在报工页「未完尾数待确认」。插单或再排一次，客户交期不变。FLOW-HOLD 与 FLOW-CAP 仍在未排汇总。",
    }
