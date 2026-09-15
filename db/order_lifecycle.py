"""订单调度阶段（Tab）与发布。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.repositories import run_schedule
from db.tables import SoOrderRow, WoRow
from engine.models import ConflictLv, ScheduleResult, WoType

PHASE_PENDING = "PENDING"
PHASE_IN_SCHEDULING = "IN_SCHEDULING"
PHASE_IN_PRODUCTION = "IN_PRODUCTION"
PHASE_COMPLETED = "COMPLETED"

BLOCKING_CODES = frozenset({"E1", "E2"})


def list_orders_by_phase(session: Session, phase: str | None = None) -> list[SoOrderRow]:
    q = select(SoOrderRow).order_by(SoOrderRow.due_date, SoOrderRow.order_no)
    if phase:
        q = q.where(SoOrderRow.schedule_phase == phase)
    return list(session.scalars(q).all())


def scheduling_pool_order_nos(session: Session) -> list[str]:
    return [r.order_no for r in list_orders_by_phase(session, PHASE_IN_SCHEDULING)]


def add_to_scheduling_pool(session: Session, order_nos: list[str]) -> None:
    for no in order_nos:
        row = session.get(SoOrderRow, no)
        if row is None:
            raise KeyError(no)
        if row.schedule_phase == PHASE_IN_PRODUCTION:
            raise ValueError(f"{no} 已在生产中，请先改单/插单流程")
        if row.schedule_phase == PHASE_COMPLETED:
            raise ValueError(f"{no} 已完结")
        row.schedule_phase = PHASE_IN_SCHEDULING
    session.flush()


def remove_from_scheduling_pool(session: Session, order_nos: list[str]) -> None:
    for no in order_nos:
        row = session.get(SoOrderRow, no)
        if row is None:
            continue
        if row.schedule_phase == PHASE_IN_SCHEDULING:
            row.schedule_phase = PHASE_PENDING
    session.flush()


def commitments_for_orders(result: ScheduleResult, order_nos: list[str]) -> list[dict]:
    wanted = set(order_nos)
    wo_by_order: dict[str, list] = {}
    for wo in result.wos:
        if wo.source_order_no in wanted:
            wo_by_order.setdefault(wo.source_order_no, []).append(wo)

    blocking_wo = {
        c.wo_no
        for c in result.conflicts
        if c.level == ConflictLv.RED and c.code in BLOCKING_CODES and c.wo_no
    }

    out: list[dict] = []
    for ono in sorted(wanted):
        wos = wo_by_order.get(ono, [])
        finished = [w for w in wos if w.wo_type == WoType.FINISHED]
        semi = [w for w in wos if w.wo_type == WoType.SEMI]
        plan_end = None
        plan_start = None
        if finished:
            plan_end = max(w.plan_end for w in finished if w.plan_end)
            starts = [w.plan_start for w in finished if w.plan_start]
            plan_start = min(starts) if starts else None
        has_red = any(w.wo_no in blocking_wo for w in wos)
        yellow = any(
            c.level == ConflictLv.YELLOW
            for c in result.conflicts
            if c.wo_no and c.wo_no in {w.wo_no for w in wos}
        )
        out.append(
            {
                "order_no": ono,
                "plan_start": plan_start.isoformat() if plan_start else None,
                "plan_end": plan_end.isoformat() if plan_end else None,
                "semi_wo_count": len(semi),
                "has_red_conflict": has_red,
                "has_yellow_conflict": yellow,
                "promised_finish": plan_end.isoformat() if plan_end else None,
            }
        )
    return out


def pool_has_blocking_reds(result: ScheduleResult, order_nos: list[str]) -> list[dict]:
    wos = {wo.wo_no: wo for wo in result.wos}
    wanted = set(order_nos)
    hits: list[dict] = []
    for c in result.conflicts:
        if c.code not in BLOCKING_CODES or c.level != ConflictLv.RED:
            continue
        if not c.wo_no:
            continue
        wo = wos.get(c.wo_no)
        if wo and wo.source_order_no in wanted:
            hits.append(
                {
                    "order_no": wo.source_order_no,
                    "code": c.code,
                    "message": c.message,
                }
            )
    return hits


def publish_scheduling_pool(
    session: Session,
    *,
    today: date,
    order_nos: list[str],
    reserved_ratio: Decimal = Decimal("0"),
    force_red: bool = False,
) -> tuple[ScheduleResult, int, list[dict]]:
    """整池发布：倒排落库 + 工单 RELEASED + 订单进生产中。"""
    pool = scheduling_pool_order_nos(session)
    if set(pool) != set(order_nos):
        raise ValueError("发布须覆盖排程中池全部订单（整池同进退）")
    if not order_nos:
        raise ValueError("排程中池为空")

    result, _, _ = run_schedule(
        session,
        today=today,
        order_nos=sorted(order_nos),
        reserved_ratio=reserved_ratio,
        persist=False,
        trigger="发布试算",
    )
    blocks = pool_has_blocking_reds(result, order_nos)
    if blocks and not force_red:
        raise PublishBlockedError(blocks, result)

    result, version, _ = run_schedule(
        session,
        today=today,
        order_nos=sorted(order_nos),
        reserved_ratio=reserved_ratio,
        persist=True,
        trigger="保存发布",
    )
    session.execute(
        update(WoRow)
        .where(WoRow.source_order_no.in_(order_nos))
        .values(status="RELEASED")
    )
    for no in order_nos:
        row = session.get(SoOrderRow, no)
        if row:
            row.schedule_phase = PHASE_IN_PRODUCTION
    commits = commitments_for_orders(result, order_nos)
    return result, version, commits


class PublishBlockedError(Exception):
    def __init__(self, blocks: list[dict], result: ScheduleResult):
        self.blocks = blocks
        self.result = result
        super().__init__("存在 E1/E2 红色冲突，禁止发布")
