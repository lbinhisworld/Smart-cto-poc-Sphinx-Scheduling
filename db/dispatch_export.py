"""派工单 Excel（T14 / Phase 5）。"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.plan_store import current_plan_version
from db.tables import MdItemRow, SoOrderRow, WoRow, WoTaskRow


def build_dispatch_workbook_bytes(session: Session) -> bytes:
    version = current_plan_version(session)
    if version <= 0:
        wb = Workbook()
        ws = wb.active
        ws.title = "派工单"
        ws.append(["提示", "暂无计划版本，请先倒排"])
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    tasks = session.scalars(
        select(WoTaskRow)
        .where(WoTaskRow.plan_version == version)
        .order_by(WoTaskRow.task_date, WoTaskRow.group_code, WoTaskRow.task_id)
    ).all()
    wo_nos = {t.wo_no for t in tasks}
    wos = {
        w.wo_no: w
        for w in session.scalars(select(WoRow).where(WoRow.wo_no.in_(wo_nos))).all()
    }
    orders = {
        o.order_no: o
        for o in session.scalars(
            select(SoOrderRow).where(
                SoOrderRow.order_no.in_({w.source_order_no for w in wos.values()})
            )
        ).all()
    }
    items = {
        i.item_code: i
        for i in session.scalars(
            select(MdItemRow).where(
                MdItemRow.item_code.in_({w.item_code for w in wos.values()})
            )
        ).all()
    }

    wb = Workbook()
    ws = wb.active
    ws.title = "派工单"
    ws.append(
        [
            "订单号",
            "客户",
            "品项",
            "品名",
            "工单",
            "类型",
            "组",
            "任务日",
            "版数",
            "墙钟工时",
            "人数",
            "计划版本",
        ]
    )
    for t in tasks:
        wo = wos.get(t.wo_no)
        if not wo:
            continue
        order = orders.get(wo.source_order_no)
        item = items.get(wo.item_code)
        ws.append(
            [
                wo.source_order_no,
                order.customer if order else "",
                wo.item_code,
                item.item_name if item else "",
                wo.wo_no,
                wo.wo_type,
                t.group_code,
                t.task_date.isoformat(),
                t.qty_board,
                float(t.hours_wall),
                t.crew_plan,
                version,
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
