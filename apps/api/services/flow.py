"""静态流程触发（M9 模拟企微/日程，禁止 router 直调 adapter）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import WecomMessageRow, WecomScheduleEventRow


def emit_wecom_message(
    session: Session,
    *,
    scene: str,
    title: str,
    body: str,
    deep_link: str,
    role_targets: list[str],
) -> WecomMessageRow:
    row = WecomMessageRow(
        scene=scene,
        title=title,
        body=body,
        deep_link=deep_link,
        role_targets_json=json.dumps(role_targets, ensure_ascii=False),
        is_read=False,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def emit_schedule_event(
    session: Session,
    *,
    scene: str,
    title: str,
    start_at: datetime,
    deep_link: str,
    idempotency_key: str,
    end_at: datetime | None = None,
) -> WecomScheduleEventRow | None:
    existing = session.scalar(
        select(WecomScheduleEventRow).where(
            WecomScheduleEventRow.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing
    row = WecomScheduleEventRow(
        scene=scene,
        title=title,
        start_at=start_at,
        end_at=end_at,
        deep_link=deep_link,
        idempotency_key=idempotency_key,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def on_order_change_submitted(session: Session, *, order_no: str, request_id: int) -> None:
    emit_wecom_message(
        session,
        scene="S1",
        title="订单变更待审批",
        body=f"{order_no} 交期/数量变更已提交，请 PMC 查看影响清单",
        deep_link=f"/changes?id={request_id}",
        role_targets=["PMC", "GM"],
    )


def on_order_change_approved(session: Session, *, order_no: str, new_due: str) -> None:
    emit_wecom_message(
        session,
        scene="S3",
        title="变更已批准",
        body=f"{order_no} 交期已更新为 {new_due}，排程将按新锚重算",
        deep_link="/schedule",
        role_targets=["SALES", "SALES_MGR", "PMC"],
    )
    start = datetime.now(UTC) + timedelta(days=1)
    emit_schedule_event(
        session,
        scene="S2",
        title=f"排产跟进 · {order_no}",
        start_at=start,
        end_at=start + timedelta(hours=1),
        deep_link="/schedule",
        idempotency_key=f"S2-{order_no}-{new_due}",
    )


def on_due_negotiate_ask(
    session: Session,
    *,
    order_no: str,
    request_id: int,
    old_due: str,
    suggested_due: str,
    brief_text: str,
) -> None:
    emit_wecom_message(
        session,
        scene="S6",
        title=f"请协商交期 · {order_no}",
        body=f"原交期 {old_due}，系统最快 {suggested_due}。{brief_text}",
        deep_link=f"/orders?dueNegotiate={order_no}",
        role_targets=["SALES", "SALES_MGR", "GM"],
    )


def on_due_negotiate_reply(
    session: Session,
    *,
    order_no: str,
    request_id: int,
    proposed_due: str,
) -> None:
    emit_wecom_message(
        session,
        scene="S7",
        title=f"销售已回客户确认日 · {order_no}",
        body=f"{order_no} 客户确认日 {proposed_due}，请 PMC 查看影响后改锚（不会自动重排）。",
        deep_link=f"/schedule?negotiate={order_no}&request={request_id}",
        role_targets=["PMC", "GM"],
    )


def on_due_negotiate_applied(
    session: Session,
    *,
    order_no: str,
    request_id: int,
    old_due: str,
    new_due: str,
) -> None:
    emit_wecom_message(
        session,
        scene="S8",
        title=f"交期已改锚 · {order_no}",
        body=f"{order_no} 交期已由 {old_due} 改为 {new_due}，请 PMC 再点倒排（系统未自动重排）。",
        deep_link="/schedule",
        role_targets=["SALES", "SALES_MGR", "PMC", "GM"],
    )
    start = datetime.now(UTC) + timedelta(hours=1)
    emit_schedule_event(
        session,
        scene="S2",
        title=f"再倒排 · {order_no}",
        start_at=start,
        end_at=start + timedelta(hours=1),
        deep_link="/schedule",
        idempotency_key=f"S8-{order_no}-{new_due}-{request_id}",
    )


def on_sample_overdue(session: Session, *, sample_code: str) -> None:
    emit_wecom_message(
        session,
        scene="S5",
        title="打样超期提醒",
        body=f"样品 {sample_code} 已超过计划节点，请销售跟进",
        deep_link="/crm/samples",
        role_targets=["SALES", "SALES_MGR"],
    )
