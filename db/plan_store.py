"""计划版本读写（禁止写 so_order.due_date）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from db.tables import PlanVersionRow, WoDependencyRow, WoRow, WoTaskRow
from engine.models import (
    Conflict,
    Dept,
    GroupCode,
    KitAllocation,
    KitCheckResult,
    ScheduleResult,
    Wo,
    WoDependency,
    WoStatus,
    WoTask,
    WoType,
)


def current_plan_version(session: Session) -> int:
    val = session.scalar(select(func.max(PlanVersionRow.version_no)))
    return int(val or 0)


def save_schedule_result(
    session: Session,
    result: ScheduleResult,
    *,
    trigger: str,
) -> int:
    """持久化排产结果。绝不 UPDATE so_order.due_date（BR-27）。"""
    version = PlanVersionRow(
        created_at=datetime.now(UTC),
        trigger=trigger,
        snapshot_hash="",
    )
    session.add(version)
    session.flush()
    version_no = version.version_no

    order_nos = {wo.source_order_no for wo in result.wos}
    if order_nos:
        old_wos = session.scalars(
            select(WoRow.wo_no).where(WoRow.source_order_no.in_(order_nos))
        ).all()
        if old_wos:
            session.execute(delete(WoTaskRow).where(WoTaskRow.wo_no.in_(old_wos)))
            session.execute(
                delete(WoDependencyRow).where(
                    or_(
                        WoDependencyRow.pred_wo_no.in_(old_wos),
                        WoDependencyRow.succ_wo_no.in_(old_wos),
                    )
                )
            )
            session.execute(delete(WoRow).where(WoRow.wo_no.in_(old_wos)))

    for wo in result.wos:
        session.add(
            WoRow(
                wo_no=wo.wo_no,
                wo_type=wo.wo_type.value,
                source_order_no=wo.source_order_no,
                item_code=wo.item_code,
                group_code=wo.group_code.value,
                dept=wo.dept.value,
                qty_order=str(wo.qty_order),
                qty_board_plan=wo.qty_board_plan,
                due_date=wo.due_date,
                plan_start=wo.plan_start,
                plan_end=wo.plan_end,
                earliest_start=wo.earliest_start,
                crew_plan=wo.crew_plan,
                status=wo.status.value,
                is_locked=wo.is_locked,
                override_reason=wo.override_reason,
                plan_version=version_no,
                parent_wo_no=wo.parent_wo_no,
            )
        )
    for task in result.tasks:
        session.add(
            WoTaskRow(
                wo_no=task.wo_no,
                dept=task.dept.value,
                group_code=task.group_code.value,
                task_date=task.task_date,
                qty_board=task.qty_board,
                hours_wall=str(task.hours_wall),
                hours_man=str(task.hours_man),
                crew_plan=task.crew_plan,
                seq=task.seq,
                changeover_min=task.changeover_min,
                plan_version=version_no,
            )
        )
    for dep in result.dependencies:
        session.add(
            WoDependencyRow(
                pred_wo_no=dep.pred_wo_no,
                succ_wo_no=dep.succ_wo_no,
                dep_type=dep.dep_type,
                offset_days=dep.offset_days,
            )
        )
    version.conflicts_json = json.dumps(
        [c.model_dump(mode="json") for c in result.conflicts],
        ensure_ascii=False,
    )
    version.kit_json = json.dumps(
        {
            "kit_checks": [k.model_dump(mode="json") for k in result.kit_checks],
            "kit_allocations": [a.model_dump(mode="json") for a in result.kit_allocations],
        },
        ensure_ascii=False,
    )
    session.flush()
    return version_no


def load_schedule_result(session: Session, version_no: int) -> ScheduleResult:
    pv = session.get(PlanVersionRow, version_no)
    conflicts: list[Conflict] = []
    if pv and pv.conflicts_json:
        conflicts = [Conflict.model_validate(row) for row in json.loads(pv.conflicts_json)]

    wos = [
        Wo(
            wo_no=r.wo_no,
            wo_type=WoType(r.wo_type),
            source_order_no=r.source_order_no,
            item_code=r.item_code,
            group_code=GroupCode(r.group_code),
            dept=Dept(r.dept),
            qty_order=Decimal(str(r.qty_order)),
            qty_board_plan=r.qty_board_plan,
            due_date=r.due_date,
            plan_start=r.plan_start,
            plan_end=r.plan_end,
            earliest_start=r.earliest_start,
            crew_plan=r.crew_plan,
            status=WoStatus(r.status),
            is_locked=r.is_locked,
            override_reason=r.override_reason,
            plan_version=r.plan_version,
            parent_wo_no=r.parent_wo_no,
        )
        for r in session.scalars(select(WoRow).where(WoRow.plan_version == version_no)).all()
    ]
    tasks = [
        WoTask(
            task_id=r.task_id,
            wo_no=r.wo_no,
            dept=Dept(getattr(r, "dept", None) or "FINISHED_DEPT"),
            group_code=GroupCode(r.group_code),
            task_date=r.task_date,
            qty_board=r.qty_board,
            hours_wall=Decimal(str(r.hours_wall)),
            hours_man=Decimal(str(r.hours_man)),
            crew_plan=r.crew_plan,
            seq=r.seq,
            changeover_min=r.changeover_min,
            plan_version=r.plan_version,
        )
        for r in session.scalars(select(WoTaskRow).where(WoTaskRow.plan_version == version_no)).all()
    ]
    deps = [
        WoDependency(
            pred_wo_no=r.pred_wo_no,
            succ_wo_no=r.succ_wo_no,
            dep_type=r.dep_type,
            offset_days=r.offset_days,
        )
        for r in session.scalars(
            select(WoDependencyRow).where(
                WoDependencyRow.pred_wo_no.in_([w.wo_no for w in wos])
            )
        ).all()
    ]
    kit_checks: list[KitCheckResult] = []
    kit_allocations: list[KitAllocation] = []
    if pv and pv.kit_json:
        raw = json.loads(pv.kit_json)
        kit_checks = [KitCheckResult.model_validate(k) for k in raw.get("kit_checks", [])]
        kit_allocations = [
            KitAllocation.model_validate(a) for a in raw.get("kit_allocations", [])
        ]
    return ScheduleResult(
        wos=wos,
        tasks=tasks,
        dependencies=deps,
        conflicts=conflicts,
        kit_checks=kit_checks,
        kit_allocations=kit_allocations,
    )


def log_insert(
    session: Session,
    *,
    wo_no: str,
    requester: str,
    reason: str,
    strategy: str,
    version_before: int,
    version_after: int,
) -> None:
    from db.tables import WoInsertLogRow

    session.add(
        WoInsertLogRow(
            wo_no=wo_no,
            requester=requester,
            requested_at=datetime.now(UTC),
            reason=reason,
            strategy=strategy,
            cost_json="{}",
            plan_version_before=version_before,
            plan_version_after=version_after,
        )
    )
