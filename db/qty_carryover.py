"""Wave 2：工单完工版数 → 待确认池；PMC 并入同品项或插单（不改 due_date）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.plan_store import current_plan_version, load_schedule_result, save_schedule_result
from db.snapshot import load_schedule_input
from db.tables import (
    MdItemRow,
    MdUomConvertRow,
    PendingRollRow,
    ProdQtyReportRow,
    SoOrderRow,
    WoRow,
    WoTaskRow,
)
from engine.models import Dept, GroupCode, SortMode, Uom, UomConvert, Wo, WoStatus, WoType
from engine.schedule import schedule
from engine.uom import convert_qty

STATUS_PENDING = "PENDING_CONFIRMATION"
STATUS_MERGED = "MERGED"
STATUS_INSERTED = "INSERTED"
ACTION_MERGE = "MERGE"
ACTION_INSERT = "INSERT"
ACTION_CANCEL = "CANCEL"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _roll_to_dict(r: PendingRollRow) -> dict:
    return {
        "id": r.id,
        "source_wo_no": r.source_wo_no,
        "source_order_no": r.source_order_no,
        "item_code": r.item_code,
        "group_code": r.group_code,
        "dept": r.dept,
        "qty_board_remain": r.qty_board_remain,
        "due_date": r.due_date.isoformat(),
        "status": r.status,
        "action": r.action,
        "target_order_no": r.target_order_no,
        "remainder_wo_no": r.remainder_wo_no,
        "created_at": r.created_at.isoformat(sep=" ", timespec="seconds"),
        "resolved_at": r.resolved_at.isoformat(sep=" ", timespec="seconds") if r.resolved_at else None,
        "resolved_by": r.resolved_by,
    }


def wo_qty_progress(session: Session, wo_no: str) -> dict:
    wo = session.get(WoRow, wo_no)
    if wo is None:
        raise KeyError(wo_no)
    done = int(getattr(wo, "qty_board_done", 0) or 0)
    plan = int(wo.qty_board_plan)
    return {
        "wo_no": wo.wo_no,
        "source_order_no": wo.source_order_no,
        "item_code": wo.item_code,
        "qty_board_plan": plan,
        "qty_board_done": done,
        "qty_board_remain": max(0, plan - done),
        "wo_status": wo.status,
    }


def list_pending_rolls(session: Session, *, status: str | None = STATUS_PENDING) -> list[dict]:
    q = select(PendingRollRow).order_by(PendingRollRow.id.desc())
    if status:
        q = q.where(PendingRollRow.status == status)
    return [_roll_to_dict(r) for r in session.scalars(q).all()]


def confirm_wo_qty(
    session: Session,
    *,
    wo_no: str,
    qty_board_done: int,
    reported_by: str,
    work_date: date | None = None,
) -> dict:
    """确认工单完工版数。remain>0 进待确认池；不建新任务、不升 plan_version、不写 due_date。"""
    if int(qty_board_done) != qty_board_done:
        raise ValueError("完工数量必须是整数版（BR-01）")
    done = int(qty_board_done)
    if done < 0:
        raise ValueError("完工版数不能为负")

    wo = session.get(WoRow, wo_no)
    if wo is None:
        raise KeyError(wo_no)
    plan = int(wo.qty_board_plan)
    if done > plan:
        raise ValueError(f"完工版数 {done} 超过计划 {plan}")

    existing = session.scalars(
        select(PendingRollRow)
        .where(PendingRollRow.source_wo_no == wo_no)
        .where(PendingRollRow.status == STATUS_PENDING)
    ).first()
    if existing is not None:
        raise ValueError("该工单已有待确认尾数，请先由 PMC 并入或插单")

    order = session.get(SoOrderRow, wo.source_order_no)
    if order is None:
        raise KeyError(wo.source_order_no)
    due_before = order.due_date

    prev_done = int(getattr(wo, "qty_board_done", 0) or 0)
    increment = done - prev_done
    remain = plan - done
    wo.qty_board_done = done
    wo.status = "DONE" if remain == 0 else "PARTIAL"
    if work_date is not None:
        item = session.get(MdItemRow, wo.item_code)
        kg = getattr(item, "kg_per_board", None) if item is not None else None
        tasks = session.scalars(
            select(WoTaskRow)
            .where(WoTaskRow.wo_no == wo_no)
            .where(WoTaskRow.task_date == work_date)
            .order_by(WoTaskRow.seq, WoTaskRow.task_id)
        ).all()
        if tasks:
            first = tasks[0]
            first.qty_actual = max(0, int(first.qty_actual or 0) + increment)
            if kg is not None:
                first.kg_per_board_snap = str(kg)

    report = ProdQtyReportRow(
        wo_no=wo_no,
        work_date=work_date,
        qty_board_done=done,
        status="CONFIRMED",
        reported_by=reported_by,
        confirmed_at=_now(),
        plan_version=wo.plan_version,
    )
    session.add(report)

    roll_dict = None
    if remain > 0:
        roll = PendingRollRow(
            source_wo_no=wo.wo_no,
            source_order_no=wo.source_order_no,
            item_code=wo.item_code,
            group_code=wo.group_code,
            dept=wo.dept,
            qty_board_remain=remain,
            due_date=order.due_date,
            status=STATUS_PENDING,
            created_at=_now(),
        )
        session.add(roll)
        session.flush()
        roll_dict = _roll_to_dict(roll)

    session.flush()
    if order.due_date != due_before:
        raise RuntimeError("禁止写回订单交期（BR-27）")

    return {
        **wo_qty_progress(session, wo_no),
        "roll": roll_dict,
    }


def _converts_for(session: Session, item_code: str) -> list[UomConvert]:
    rows = session.scalars(select(MdUomConvertRow).where(MdUomConvertRow.item_code == item_code)).all()
    return [
        UomConvert(
            item_code=r.item_code,
            from_uom=Uom(r.from_uom),
            to_uom=Uom(r.to_uom),
            factor=Decimal(str(r.factor)),
        )
        for r in rows
    ]


def _next_merge_target(session: Session, *, item_code: str, source_order_no: str) -> SoOrderRow | None:
    rows = session.scalars(
        select(SoOrderRow)
        .where(SoOrderRow.item_code == item_code)
        .where(SoOrderRow.order_no != source_order_no)
        .where(SoOrderRow.schedule_phase.in_(("PENDING", "IN_SCHEDULING")))
        .order_by(SoOrderRow.due_date, SoOrderRow.order_no)
    ).all()
    return rows[0] if rows else None


def _apply_merge(session: Session, roll: PendingRollRow, *, resolved_by: str, target_order_no: str | None) -> dict:
    if target_order_no:
        target = session.get(SoOrderRow, target_order_no)
        if target is None:
            raise KeyError(target_order_no)
        if target.item_code != roll.item_code:
            raise ValueError("并入目标必须是同品项")
        if target.schedule_phase not in ("PENDING", "IN_SCHEDULING"):
            raise ValueError("只能并入待排程或排程中的同品项订单")
    else:
        target = _next_merge_target(
            session, item_code=roll.item_code, source_order_no=roll.source_order_no
        )
        if target is None:
            raise ValueError("没有同品项待排/排程中订单可并入，请改为插单")

    src_due = session.get(SoOrderRow, roll.source_order_no)
    src_due_before = src_due.due_date if src_due else roll.due_date
    tgt_due_before = target.due_date

    converts = _converts_for(session, roll.item_code)
    add_qty = convert_qty(Decimal(roll.qty_board_remain), Uom.BOARD, Uom(target.unit), converts)
    target.qty_order = str(Decimal(str(target.qty_order)) + add_qty)

    roll.status = STATUS_MERGED
    roll.action = ACTION_MERGE
    roll.target_order_no = target.order_no
    roll.resolved_at = _now()
    roll.resolved_by = resolved_by
    session.flush()

    if src_due and src_due.due_date != src_due_before:
        raise RuntimeError("禁止写回订单交期（BR-27）")
    if target.due_date != tgt_due_before:
        raise RuntimeError("禁止写回并入订单交期（BR-27）")

    return {**_roll_to_dict(roll), "target_order_no": target.order_no}


def _apply_insert(session: Session, roll: PendingRollRow, *, today: date, resolved_by: str) -> dict:
    parent = session.get(SoOrderRow, roll.source_order_no)
    if parent is None:
        raise KeyError(roll.source_order_no)
    parent_due = parent.due_date

    rem_no = f"{roll.source_order_no}-R{roll.id}"
    if session.get(SoOrderRow, rem_no) is not None:
        raise ValueError(f"尾数订单 {rem_no} 已存在")

    rem_order = SoOrderRow(
        order_no=rem_no,
        customer=parent.customer,
        sales_name=parent.sales_name,
        customer_code=parent.customer_code,
        owner_sales=parent.owner_sales,
        item_code=parent.item_code,
        qty_order=str(roll.qty_board_remain),
        unit="BOARD",
        due_date=parent.due_date,
        ready_date=parent.ready_date,
        customer_level=parent.customer_level,
        amount="0",
        is_urgent=True,
        schedule_phase="IN_PRODUCTION",
        order_source="QTY_CARRYOVER",
        contract_no=parent.contract_no,
    )
    session.add(rem_order)
    session.flush()

    baseline_ver = current_plan_version(session)
    baseline = load_schedule_result(session, baseline_ver) if baseline_ver > 0 else None

    inp = load_schedule_input(session, today=today, order_nos=[rem_no], reserved_ratio=Decimal("0"))
    sph = inp.sph_of(roll.item_code, GroupCode(roll.group_code))
    rem_wo = Wo(
        wo_no=f"WO-{rem_no}-1",
        wo_type=WoType.FINISHED,
        source_order_no=rem_no,
        item_code=roll.item_code,
        group_code=GroupCode(roll.group_code),
        dept=Dept(roll.dept),
        qty_order=Decimal(roll.qty_board_remain),
        qty_board_plan=roll.qty_board_remain,
        due_date=parent.due_date,
        earliest_start=today,
        crew_plan=sph.crew_std,
        status=WoStatus.DRAFT,
        parent_wo_no=roll.source_wo_no,
    )
    locked = list(baseline.tasks) if baseline else list(inp.locked_tasks)
    cfg = inp.config.model_copy(
        update={"sort_mode": SortMode.PIN_FIRST, "pinned_wo_nos": [rem_wo.wo_no], "reserved_ratio": Decimal("0")}
    )
    result = schedule(
        inp.model_copy(
            update={
                "config": cfg,
                "finished_override": [rem_wo],
                "locked_tasks": locked,
            }
        )
    )

    if baseline is not None:
        kept: list[Wo] = []
        for w in baseline.wos:
            if w.wo_no == roll.source_wo_no:
                kept.append(
                    w.model_copy(
                        update={
                            "status": WoStatus.PARTIAL,
                            "qty_board_done": roll.qty_board_remain and (
                                w.qty_board_plan - roll.qty_board_remain
                            ),
                        }
                    )
                )
            else:
                kept.append(w)
        result = result.model_copy(
            update={
                "wos": kept + list(result.wos),
                "tasks": list(baseline.tasks) + list(result.tasks),
                "dependencies": list(baseline.dependencies) + list(result.dependencies),
            }
        )

    save_schedule_result(session, result, trigger="未完插单")

    orig = session.get(WoRow, roll.source_wo_no)
    if orig is not None:
        orig.status = "PARTIAL"
        orig.qty_board_done = orig.qty_board_plan - roll.qty_board_remain

    rem_wo_row = session.get(WoRow, rem_wo.wo_no)
    if rem_wo_row is not None:
        rem_wo_row.status = "RELEASED"

    roll.status = STATUS_INSERTED
    roll.action = ACTION_INSERT
    roll.target_order_no = rem_no
    roll.remainder_wo_no = rem_wo.wo_no
    roll.resolved_at = _now()
    roll.resolved_by = resolved_by
    session.flush()

    if parent.due_date != parent_due:
        raise RuntimeError("禁止写回订单交期（BR-27）")

    return {
        **_roll_to_dict(roll),
        "remainder_order_no": rem_no,
        "remainder_wo_no": rem_wo.wo_no,
    }


def resolve_roll(
    session: Session,
    *,
    roll_id: int,
    action: str,
    today: date,
    resolved_by: str,
    target_order_no: str | None = None,
) -> dict:
    act = (action or "").upper()
    if act == ACTION_CANCEL:
        raise ValueError("不考虑取消尾数，剩余必须继续生产")
    roll = session.get(PendingRollRow, roll_id)
    if roll is None:
        raise KeyError(roll_id)
    if roll.status != STATUS_PENDING:
        raise ValueError("该尾数已处理")
    if act == ACTION_MERGE:
        return _apply_merge(session, roll, resolved_by=resolved_by, target_order_no=target_order_no)
    if act == ACTION_INSERT:
        return _apply_insert(session, roll, today=today, resolved_by=resolved_by)
    raise ValueError("action 只能是 MERGE 或 INSERT")
