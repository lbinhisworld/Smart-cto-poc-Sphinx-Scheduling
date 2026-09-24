"""订单调度阶段（Tab）与发布。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from db.plan_store import current_plan_version, load_schedule_result
from db.repositories import run_schedule
from db.snapshot import header_order_no
from db.tables import PlanVersionRow, SoOrderRow, WoRow
from engine.models import ConflictLv, ScheduleResult, WoStatus, WoType

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
        if (row.order_status or "") not in ("CANCELLED", "CLOSED"):
            row.order_status = "SCHEDULED"
    session.flush()


def remove_from_scheduling_pool(session: Session, order_nos: list[str]) -> None:
    for no in order_nos:
        row = session.get(SoOrderRow, no)
        if row is None:
            continue
        if row.schedule_phase == PHASE_IN_SCHEDULING:
            row.schedule_phase = PHASE_PENDING
            if (row.order_status or "") == "SCHEDULED":
                row.order_status = "CONFIRMED"
    session.flush()


def commitments_for_orders(result: ScheduleResult, order_nos: list[str]) -> list[dict]:
    wanted = set(order_nos)
    wo_by_order: dict[str, list] = {}
    for wo in result.wos:
        key = header_order_no(wo.source_order_no)
        if key in wanted:
            wo_by_order.setdefault(key, []).append(wo)

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
        if wo and header_order_no(wo.source_order_no) in wanted:
            hits.append(
                {
                    "order_no": header_order_no(wo.source_order_no),
                    "code": c.code,
                    "message": c.message,
                }
            )
    return hits


def _confirmed_insert_plan(session: Session) -> tuple[int, ScheduleResult] | None:
    """当前计划若来自已确认插单，发布沿用该版，不再倒排。"""
    version = current_plan_version(session)
    if version <= 0:
        return None
    row = session.get(PlanVersionRow, version)
    if row is None or not (row.trigger or "").startswith("插单"):
        return None
    return version, load_schedule_result(session, version)


def _release_pool(
    session: Session,
    result: ScheduleResult,
    order_nos: list[str],
) -> tuple[ScheduleResult, list[dict]]:
    wanted = set(order_nos)
    like_conds = [WoRow.source_order_no.like(f"{no}#L%") for no in order_nos]
    session.execute(
        update(WoRow)
        .where(or_(WoRow.source_order_no.in_(order_nos), *like_conds))
        .values(status="RELEASED")
    )
    for no in order_nos:
        row = session.get(SoOrderRow, no)
        if row:
            row.schedule_phase = PHASE_IN_PRODUCTION
    released = [
        wo.model_copy(update={"status": WoStatus.RELEASED})
        if header_order_no(wo.source_order_no) in wanted
        else wo
        for wo in result.wos
    ]
    result = result.model_copy(update={"wos": released})
    return result, commitments_for_orders(result, order_nos)


def publish_scheduling_pool(
    session: Session,
    *,
    today: date,
    order_nos: list[str],
    reserved_ratio: Decimal = Decimal("0"),
    force_red: bool = False,
) -> tuple[ScheduleResult, int, list[dict]]:
    """整池发布：工单 RELEASED + 订单进生产中。

    当前计划来自已确认插单时，沿用该版，不再按默认顺序重算。
    """
    pool = scheduling_pool_order_nos(session)
    if set(pool) != set(order_nos):
        raise ValueError("发布须覆盖排程中池全部订单（整池同进退）")
    if not order_nos:
        raise ValueError("排程中池为空")

    confirmed = _confirmed_insert_plan(session)
    if confirmed is not None:
        version, result = confirmed
        covered = {header_order_no(wo.source_order_no) for wo in result.wos}
        missing = sorted(set(order_nos) - covered)
        if missing:
            raise ValueError(
                "排程中池含已确认插单计划之外的订单（"
                + "、".join(missing)
                + "），请重新插单试排或一键倒排后再发布"
            )
        blocks = pool_has_blocking_reds(result, order_nos)
        if blocks and not force_red:
            raise PublishBlockedError(blocks, result)
        result, commits = _release_pool(session, result, order_nos)
        return result, version, commits

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
    result, commits = _release_pool(session, result, order_nos)
    return result, version, commits


class PublishBlockedError(Exception):
    def __init__(self, blocks: list[dict], result: ScheduleResult):
        self.blocks = blocks
        self.result = result
        super().__init__("存在 E1/E2 红色冲突，禁止发布")
