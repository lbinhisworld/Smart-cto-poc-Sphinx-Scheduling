"""演示线：生命周期、谱系、反馈、重放、导出。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.guided_demo_clear import clear_run_transient, clear_step_seed_events
from db.guided_demo_step_apply import (
    apply_step_seed,
    clear_step_business,
    compact_apply_user_message,
    step_business_applied,
)
from db.guided_demo_seed_stub import build_stub_seed
from db.tables import (
    AppSettingRow,
    DemoRunFeedbackRow,
    DemoRunRow,
    DemoRunSeedEventRow,
    DemoRunStepSnapshotRow,
)
from shared.audit import write_audit
from shared.auth import user_for_role
from shared.guided_demo_path import (
    DEMO_ANCHOR_TODAY,
    GUIDED_STEPS,
    PATH_TEMPLATE_FULL,
    STEP_COUNT,
    GuidedStep,
    next_step,
    resolve_step_for_path,
    step_by_id,
    steps_for_api,
)

ACTIVE_RUN_KEY = "guided_demo_active_run_id"
REPLAY_RUN_KEY = "guided_demo_replay_run_id"


class GuidedDemoError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _default_run_title() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S")


def _get_setting(session: Session, key: str) -> str | None:
    row = session.get(AppSettingRow, key)
    return row.value if row else None


def _set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(AppSettingRow, key)
    if row is None:
        session.add(AppSettingRow(key=key, value=value))
    else:
        row.value = value


def _session_mode(session: Session, run_id: str) -> str | None:
    if _get_setting(session, ACTIVE_RUN_KEY) == run_id:
        row = session.get(DemoRunRow, run_id)
        if row and row.status == "ACTIVE":
            return "live"
    if _get_setting(session, REPLAY_RUN_KEY) == run_id:
        row = session.get(DemoRunRow, run_id)
        if row and row.status == "ENDED":
            return "replay"
    return None


def create_run(session: Session, *, title: str = "", role: str) -> dict:
    title = title.strip() or _default_run_title()
    run_id = str(uuid.uuid4())
    row = DemoRunRow(
        id=run_id,
        title=title,
        status="DRAFT",
        path_template=PATH_TEMPLATE_FULL,
        current_step_id=GUIDED_STEPS[0].step_id,
        created_by_role=role,
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return _run_dict(session, row)


def list_runs(session: Session, *, limit: int = 50) -> list[dict]:
    rows = list(
        session.scalars(select(DemoRunRow).order_by(DemoRunRow.created_at.desc()).limit(limit)).all()
    )
    return [_run_dict(session, r) for r in rows]


def get_run(session: Session, run_id: str) -> dict | None:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        return None
    return _run_dict(session, row)


def _run_dict(session: Session, row: DemoRunRow) -> dict:
    fb_count = int(
        session.scalar(
            select(func.count()).select_from(DemoRunFeedbackRow).where(DemoRunFeedbackRow.run_id == row.id)
        )
        or 0
    )
    seed_count = int(
        session.scalar(
            select(func.count()).select_from(DemoRunSeedEventRow).where(DemoRunSeedEventRow.run_id == row.id)
        )
        or 0
    )
    snap_count = int(
        session.scalar(
            select(func.count())
            .select_from(DemoRunStepSnapshotRow)
            .where(DemoRunStepSnapshotRow.run_id == row.id)
        )
        or 0
    )
    step = step_by_id(row.current_step_id or "")
    mode = _session_mode(session, row.id)
    chain_complete = _run_chain_complete(session, row.id)
    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "path_template": row.path_template,
        "current_step_id": row.current_step_id,
        "current_step_title": step.title if step else None,
        "current_seq": step.seq if step else None,
        "step_count": STEP_COUNT,
        "feedback_count": fb_count,
        "seed_event_count": seed_count,
        "snapshot_count": snap_count,
        "created_by_role": row.created_by_role,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "is_active": mode == "live",
        "is_replay": mode == "replay",
        "session_mode": mode,
        "can_replay": row.status == "ENDED" and snap_count > 0,
        "can_continue": row.status == "ACTIVE",
        "can_end": row.status == "ACTIVE" and chain_complete,
        "chain_complete": chain_complete,
    }


def _run_chain_complete(session: Session, run_id: str) -> bool:
    for s in GUIDED_STEPS:
        cnt = int(
            session.scalar(
                select(func.count())
                .select_from(DemoRunSeedEventRow)
                .where(DemoRunSeedEventRow.run_id == run_id, DemoRunSeedEventRow.step_id == s.step_id)
            )
            or 0
        )
        if cnt < 1:
            return False
    return True


def _latest_seeded_step_id(session: Session, run_id: str) -> str | None:
    step_ids = session.scalars(
        select(DemoRunSeedEventRow.step_id)
        .where(DemoRunSeedEventRow.run_id == run_id)
        .distinct()
    ).all()
    best: GuidedStep | None = None
    for sid in step_ids:
        st = step_by_id(sid)
        if st and (best is None or st.seq > best.seq):
            best = st
    return best.step_id if best else None


def resolve_resume_step_id(session: Session, run_id: str) -> str:
    """回到应继续的环节：当前步无数据时，落到最近一次已生成数据的环节。"""
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    cur_id = row.current_step_id or GUIDED_STEPS[0].step_id
    if saved_step_data(session, run_id, cur_id):
        return cur_id
    last_id = _latest_seeded_step_id(session, run_id)
    if last_id:
        cur = step_by_id(cur_id)
        last = step_by_id(last_id)
        if cur and last and cur.seq > last.seq:
            return cur_id
        return last_id
    return cur_id


def continue_run(session: Session, run_id: str, *, role: str) -> dict:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if row.status != "ACTIVE":
        raise GuidedDemoError("仅进行中的演示线可继续")
    active = _get_setting(session, ACTIVE_RUN_KEY)
    if active and active != run_id:
        other = session.get(DemoRunRow, active)
        title = other.title if other else active
        raise GuidedDemoError(f"已有其他进行中的演示线：{title}")
    if not active:
        _set_setting(session, ACTIVE_RUN_KEY, run_id)
    step_id = resolve_resume_step_id(session, run_id)
    row.current_step_id = step_id
    step = step_by_id(step_id)
    if step is None:
        raise GuidedDemoError("未知环节")
    saved = saved_step_data(session, run_id, step_id)
    _audit(session, role, "continue", run_id, after={"step_id": step_id, "has_seed": saved is not None})
    data = _run_dict(session, row)
    data["resume_step_id"] = step_id
    data["resume_list_path"] = step.list_path
    data["step_has_seed"] = saved is not None
    return data


def _persist_and_close_run(session: Session, run_id: str, *, role: str, action: str) -> dict | None:
    row = session.get(DemoRunRow, run_id)
    if row is None or row.status != "ACTIVE":
        return None
    _archive_step_snapshots(session, run_id)
    row.status = "ENDED"
    row.ended_at = _now()
    if _get_setting(session, ACTIVE_RUN_KEY) == run_id:
        _set_setting(session, ACTIVE_RUN_KEY, "")
    _audit(session, role, action, run_id)
    return _run_dict(session, row)


def start_run(session: Session, run_id: str, *, role: str) -> dict:
    from db.demo_system_reset import clear_demo_business_data

    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if row.status == "ENDED":
        raise GuidedDemoError("已结束的演示线请用「重放」或新建")
    replay = _get_setting(session, REPLAY_RUN_KEY)
    if replay:
        raise GuidedDemoError("请先退出重放模式")

    archived: dict | None = None
    active = _get_setting(session, ACTIVE_RUN_KEY)
    if active and active != run_id:
        other = session.get(DemoRunRow, active)
        if other and other.status == "ACTIVE":
            archived = _persist_and_close_run(session, active, role=role, action="auto-archive-on-start")
    business = clear_demo_business_data(session)
    cleared = clear_run_transient(session, run_id)
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    row.status = "ACTIVE"
    row.started_at = _now()
    row.ended_at = None
    row.current_step_id = GUIDED_STEPS[0].step_id
    _set_setting(session, ACTIVE_RUN_KEY, run_id)
    _set_setting(session, REPLAY_RUN_KEY, "")
    _audit(
        session,
        role,
        "start",
        run_id,
        after={"cleared_run_draft": cleared, "archived_previous": archived, "business_reset": business},
    )
    data = _run_dict(session, row)
    if archived:
        data["archived_previous_run"] = archived
    data["business_reset"] = business
    return data


def end_run(session: Session, run_id: str, *, role: str) -> dict:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if row.status != "ACTIVE":
        raise GuidedDemoError("仅进行中的演示线可结束")
    if not _run_chain_complete(session, run_id):
        raise GuidedDemoError("须走完全部 17 个环节并生成数据后，才可结束演示线")
    _archive_step_snapshots(session, run_id)
    row.status = "ENDED"
    row.ended_at = _now()
    if _get_setting(session, ACTIVE_RUN_KEY) == run_id:
        _set_setting(session, ACTIVE_RUN_KEY, "")
    _audit(session, role, "end", run_id)
    return _run_dict(session, row)


def start_replay(session: Session, run_id: str, *, role: str) -> dict:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if row.status != "ENDED":
        raise GuidedDemoError("仅已结束的演示线可重放")
    snap_count = int(
        session.scalar(
            select(func.count())
            .select_from(DemoRunStepSnapshotRow)
            .where(DemoRunStepSnapshotRow.run_id == run_id)
        )
        or 0
    )
    if snap_count < 1:
        raise GuidedDemoError("该演示线尚无归档环节数据，无法重放")
    active = _get_setting(session, ACTIVE_RUN_KEY)
    if active:
        other = session.get(DemoRunRow, active)
        if other and other.status == "ACTIVE":
            raise GuidedDemoError(f"请先结束进行中的演示线：{other.title}")
    _set_setting(session, REPLAY_RUN_KEY, run_id)
    _set_setting(session, ACTIVE_RUN_KEY, "")
    if not row.current_step_id:
        row.current_step_id = GUIDED_STEPS[0].step_id
    _audit(session, role, "replay-start", run_id)
    return _run_dict(session, row)


def end_replay(session: Session, run_id: str, *, role: str) -> dict:
    if _get_setting(session, REPLAY_RUN_KEY) != run_id:
        raise GuidedDemoError("当前不在该演示线的重放模式")
    _set_setting(session, REPLAY_RUN_KEY, "")
    _audit(session, role, "replay-end", run_id)
    row = session.get(DemoRunRow, run_id)
    return _run_dict(session, row) if row else {"id": run_id}


def delete_run(session: Session, run_id: str, *, role: str) -> dict:
    from db.demo_system_reset import clear_demo_business_data

    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if _get_setting(session, ACTIVE_RUN_KEY) == run_id:
        _set_setting(session, ACTIVE_RUN_KEY, "")
    if _get_setting(session, REPLAY_RUN_KEY) == run_id:
        _set_setting(session, REPLAY_RUN_KEY, "")
    cleared = clear_run_transient(session, run_id)
    was_live = row.status == "ACTIVE"
    session.execute(delete(DemoRunRow).where(DemoRunRow.id == run_id))
    business = clear_demo_business_data(session) if was_live else None
    _audit(
        session,
        role,
        "delete",
        run_id,
        after={"run_cleared": cleared, "business_reset": business, "was_active": was_live},
    )
    return {"id": run_id, "deleted": True, "business_reset": business, "was_active": was_live}


def get_active_run(session: Session) -> dict | None:
    live_id = _get_setting(session, ACTIVE_RUN_KEY)
    if live_id:
        row = session.get(DemoRunRow, live_id)
        if row and row.status == "ACTIVE":
            data = _run_dict(session, row)
            data["session_mode"] = "live"
            return data
        _set_setting(session, ACTIVE_RUN_KEY, "")
    replay_id = _get_setting(session, REPLAY_RUN_KEY)
    if replay_id:
        row = session.get(DemoRunRow, replay_id)
        if row and row.status == "ENDED":
            data = _run_dict(session, row)
            data["session_mode"] = "replay"
            return data
        _set_setting(session, REPLAY_RUN_KEY, "")
    return None


def set_current_step(session: Session, run_id: str, step_id: str) -> dict:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if step_by_id(step_id) is None:
        raise GuidedDemoError("未知环节")
    mode = _session_mode(session, run_id)
    if mode is None:
        raise GuidedDemoError("演示线未处于进行中或重放会话")
    row.current_step_id = step_id
    return _run_dict(session, row)


def step_readiness(session: Session, run_id: str, step_id: str) -> dict:
    step = step_by_id(step_id)
    if step is None:
        raise GuidedDemoError("未知环节")
    mode = _session_mode(session, run_id)
    if mode == "replay":
        snap = session.get(DemoRunStepSnapshotRow, {"run_id": run_id, "step_id": step_id})
        return {
            "run_id": run_id,
            "step_id": step_id,
            "ready": snap is not None,
            "missing_steps": [] if snap else ["本环节尚无归档数据"],
            "replay": True,
        }
    missing: list[str] = []
    for req in step.requires:
        cnt = int(
            session.scalar(
                select(func.count())
                .select_from(DemoRunSeedEventRow)
                .where(DemoRunSeedEventRow.run_id == run_id, DemoRunSeedEventRow.step_id == req)
            )
            or 0
        )
        if cnt < 1:
            req_step = step_by_id(req)
            missing.append(req_step.title if req_step else req)
    return {
        "run_id": run_id,
        "step_id": step_id,
        "ready": len(missing) == 0,
        "missing_steps": missing,
        "replay": False,
    }


def saved_step_data(session: Session, run_id: str, step_id: str) -> dict | None:
    mode = _session_mode(session, run_id)
    if mode == "replay":
        snap = session.get(DemoRunStepSnapshotRow, {"run_id": run_id, "step_id": step_id})
        if snap is None:
            return None
        try:
            refs = json.loads(snap.refs_json)
        except json.JSONDecodeError:
            refs = []
        return {
            "step_id": step_id,
            "summary": snap.summary,
            "refs": refs,
            "source": "snapshot",
            "seeded_at": snap.seeded_at.isoformat() if snap.seeded_at else None,
        }
    evt = session.scalar(
        select(DemoRunSeedEventRow)
        .where(DemoRunSeedEventRow.run_id == run_id, DemoRunSeedEventRow.step_id == step_id)
        .order_by(DemoRunSeedEventRow.batch_index.desc(), DemoRunSeedEventRow.id.desc())
        .limit(1)
    )
    if evt is None:
        return None
    try:
        refs = json.loads(evt.refs_json)
    except json.JSONDecodeError:
        refs = []
    return {
        "step_id": step_id,
        "summary": evt.summary,
        "refs": refs,
        "source": "live",
        "seeded_at": evt.created_at.isoformat() if evt.created_at else None,
    }


def seed_step(session: Session, run_id: str, step_id: str, *, role: str, count: int = 5) -> dict:
    if count != 5:
        raise GuidedDemoError("固定每次生成 5 条故事线")
    if _session_mode(session, run_id) == "replay":
        raise GuidedDemoError("重放模式不可生成数据")
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    if row.status != "ACTIVE":
        raise GuidedDemoError("请先启动演示线")
    if _get_setting(session, ACTIVE_RUN_KEY) != run_id:
        raise GuidedDemoError("该演示线不是当前活跃线")
    ready = step_readiness(session, run_id, step_id)
    if not ready["ready"]:
        raise GuidedDemoError("缺少前序数据：" + "、".join(ready["missing_steps"]))

    removed = clear_step_seed_events(session, run_id, step_id)
    clear_step_business(session, run_id, step_id)
    batch_index = 1

    refs, stub_summary, snapshot = build_stub_seed(run_id, step_id)
    apply_stats = apply_step_seed(session, run_id, step_id, refs)
    snapshot = {**snapshot, "lineage_summary": stub_summary, "apply": apply_stats}
    summary = compact_apply_user_message(step_id, apply_stats)
    evt = DemoRunSeedEventRow(
        run_id=run_id,
        step_id=step_id,
        batch_index=batch_index,
        refs_json=json.dumps(refs, ensure_ascii=False),
        summary=summary,
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        actor_role=role,
        created_at=_now(),
    )
    session.add(evt)
    session.flush()
    _audit(
        session,
        role,
        f"seed-{step_id}",
        run_id,
        after={"batch_index": batch_index, "event_id": evt.id, "replaced": removed},
    )
    return {
        "event_id": evt.id,
        "run_id": run_id,
        "step_id": step_id,
        "batch_index": batch_index,
        "refs": refs,
        "summary": summary,
        "stub": step_id not in ("roster", "product", "customer"),
        "replaced_events": removed,
        "apply": apply_stats,
        "warnings": []
        if apply_stats.get("applied")
        else ["本环节尚未接入业务落库，仅写入演示谱系"],
    }


def list_feedback(
    session: Session, run_id: str, *, step_id: str | None = None
) -> list[dict]:
    q = select(DemoRunFeedbackRow).where(DemoRunFeedbackRow.run_id == run_id)
    if step_id:
        q = q.where(DemoRunFeedbackRow.step_id == step_id)
    rows = list(session.scalars(q.order_by(DemoRunFeedbackRow.created_at, DemoRunFeedbackRow.id)).all())
    out: list[dict] = []
    for fb in rows:
        st = step_by_id(fb.step_id)
        out.append(
            {
                "id": fb.id,
                "step_id": fb.step_id,
                "step_title": st.title if st else fb.step_id,
                "story_index": fb.story_index,
                "category": fb.category,
                "severity": fb.severity,
                "body": fb.body,
                "expectation": fb.expectation,
                "reporter_role": fb.reporter_role,
                "created_at": fb.created_at.isoformat() if fb.created_at else None,
            }
        )
    return out


def add_feedback(
    session: Session,
    run_id: str,
    *,
    step_id: str,
    category: str,
    severity: str,
    body: str,
    expectation: str,
    story_index: int | None,
    seed_event_id: int | None,
    refs: list[dict] | None,
    role: str,
) -> dict:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    mode = _session_mode(session, run_id)
    if mode is None:
        raise GuidedDemoError("请先启动演示线或进入重放")
    body = body.strip()
    if not body:
        raise GuidedDemoError("请填写现象描述")
    step = step_by_id(step_id)
    if step is None:
        raise GuidedDemoError("未知环节")
    fb = DemoRunFeedbackRow(
        run_id=run_id,
        step_id=step_id,
        story_index=story_index,
        category=category,
        severity=severity,
        body=body,
        expectation=(expectation or "").strip(),
        refs_json=json.dumps(refs or [], ensure_ascii=False),
        seed_event_id=seed_event_id,
        reporter_role=role,
        created_at=_now(),
    )
    session.add(fb)
    session.flush()
    return {
        "id": fb.id,
        "run_id": run_id,
        "step_id": step_id,
        "step_title": step.title,
        "category": category,
        "severity": severity,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


def _archive_step_snapshots(session: Session, run_id: str) -> None:
    session.execute(delete(DemoRunStepSnapshotRow).where(DemoRunStepSnapshotRow.run_id == run_id))
    now = _now()
    for step in GUIDED_STEPS:
        evt = session.scalar(
            select(DemoRunSeedEventRow)
            .where(DemoRunSeedEventRow.run_id == run_id, DemoRunSeedEventRow.step_id == step.step_id)
            .order_by(DemoRunSeedEventRow.batch_index.desc(), DemoRunSeedEventRow.id.desc())
            .limit(1)
        )
        if evt is None:
            continue
        session.add(
            DemoRunStepSnapshotRow(
                run_id=run_id,
                step_id=step.step_id,
                refs_json=evt.refs_json,
                summary=evt.summary,
                snapshot_json=evt.snapshot_json,
                seed_event_id=evt.id,
                seeded_at=evt.created_at,
                archived_at=now,
            )
        )


def _latest_seed_event_per_step(events: list[DemoRunSeedEventRow]) -> list[DemoRunSeedEventRow]:
    by_step: dict[str, DemoRunSeedEventRow] = {}
    for ev in events:
        prev = by_step.get(ev.step_id)
        if prev is None or (ev.batch_index, ev.id) > (prev.batch_index, prev.id):
            by_step[ev.step_id] = ev
    out: list[DemoRunSeedEventRow] = []
    for step in GUIDED_STEPS:
        hit = by_step.get(step.step_id)
        if hit is not None:
            out.append(hit)
    return out


def export_markdown(session: Session, run_id: str) -> str:
    row = session.get(DemoRunRow, run_id)
    if row is None:
        raise GuidedDemoError("演示线不存在")
    events = list(
        session.scalars(
            select(DemoRunSeedEventRow)
            .where(DemoRunSeedEventRow.run_id == run_id)
            .order_by(DemoRunSeedEventRow.created_at, DemoRunSeedEventRow.id)
        ).all()
    )
    live_events = _latest_seed_event_per_step(events)
    snapshots = list(
        session.scalars(
            select(DemoRunStepSnapshotRow)
            .where(DemoRunStepSnapshotRow.run_id == run_id)
            .order_by(DemoRunStepSnapshotRow.step_id)
        ).all()
    )
    feedbacks = list(
        session.scalars(
            select(DemoRunFeedbackRow)
            .where(DemoRunFeedbackRow.run_id == run_id)
            .order_by(DemoRunFeedbackRow.created_at, DemoRunFeedbackRow.id)
        ).all()
    )
    block_count = sum(1 for f in feedbacks if f.severity == "演示阻断")
    steps_hit = sorted({f.step_id for f in feedbacks})

    lines: list[str] = [
        f"# 演示过程 · {row.title}",
        "",
        f"- run_id: `{row.id}`",
        f"- 状态: {row.status}",
        f"- 路径模板: {row.path_template}",
        f"- 演示锚日: {DEMO_ANCHOR_TODAY}",
        f"- 开始: {row.started_at.isoformat() if row.started_at else '—'}",
        f"- 结束: {row.ended_at.isoformat() if row.ended_at else '—'}",
        "",
        "## 摘要",
        "",
        f"- 反馈 {len(feedbacks)} 条 · 演示阻断 {block_count} · 涉及环节: "
        + ("、".join(steps_hit) if steps_hit else "无"),
        f"- seed 事件 {len(events)} 条 · 已生成环节 {len(live_events)}/{STEP_COUNT}"
        + (f" · 归档环节 {len(snapshots)}" if snapshots else ""),
        "",
    ]
    if row.status == "ACTIVE":
        lines.extend(["## 数据谱系（进行中 · 各环节最新 seed）", ""])
        if not live_events:
            lines.append("（尚无生成数据）")
        else:
            for ev in live_events:
                st = step_by_id(ev.step_id)
                seq = st.seq if st else "?"
                lines.append(f"### {seq}. {st.title if st else ev.step_id}")
                lines.append(f"- 生成: {ev.created_at.isoformat() if ev.created_at else '—'}")
                lines.append(f"- 摘要: {ev.summary}")
                try:
                    snap = json.loads(ev.snapshot_json or "{}")
                    apply = snap.get("apply") if isinstance(snap, dict) else None
                    if isinstance(apply, dict) and apply.get("applied"):
                        lines.append(f"- 落库: {json.dumps(apply, ensure_ascii=False)}")
                except json.JSONDecodeError:
                    pass
                try:
                    refs = json.loads(ev.refs_json)
                except json.JSONDecodeError:
                    refs = []
                for ref in refs:
                    lines.append(
                        f"- story #{ref.get('story_index')} · `{ref.get('entity_id')}` · {ref.get('display')}"
                    )
                lines.append("")
    elif snapshots:
        lines.extend(["## 数据谱系（归档）", ""])
        for snap in snapshots:
            st = step_by_id(snap.step_id)
            lines.append(f"### {st.title if st else snap.step_id}")
            lines.append(f"- 归档: {snap.archived_at.isoformat() if snap.archived_at else '—'}")
            lines.append(f"- 摘要: {snap.summary}")
            try:
                refs = json.loads(snap.refs_json)
            except json.JSONDecodeError:
                refs = []
            for ref in refs:
                lines.append(
                    f"- story #{ref.get('story_index')} · `{ref.get('entity_id')}` · {ref.get('display')}"
                )
            lines.append("")
    elif live_events:
        lines.extend(["## 数据谱系", ""])
        for ev in live_events:
            st = step_by_id(ev.step_id)
            lines.append(f"### {st.title if st else ev.step_id}")
            lines.append(f"- 摘要: {ev.summary}")
            lines.append("")
    else:
        lines.extend(["## 数据谱系", "", "（尚无数据）", ""])

    lines.extend(["## 各环节反馈时间线", ""])
    for step in GUIDED_STEPS:
        step_fbs = [f for f in feedbacks if f.step_id == step.step_id]
        lines.append(f"### {step.seq}. {step.title} (`{step.step_id}`)")
        if not step_fbs:
            lines.append("- （本环节无反馈）")
        else:
            for fb in step_fbs:
                lines.append(
                    f"- **{fb.created_at.isoformat() if fb.created_at else '—'}** · "
                    f"{fb.category} · {fb.severity} · {fb.reporter_role}"
                )
                lines.append(f"  - 现象: {fb.body}")
                if fb.expectation:
                    lines.append(f"  - 期望: {fb.expectation}")
        lines.append("")

    lines.extend(
        [
            "## 反馈明细（全局时间序）",
            "",
        ]
    )
    if not feedbacks:
        lines.append("（无）")
    else:
        for i, fb in enumerate(feedbacks, 1):
            st = step_by_id(fb.step_id)
            lines.append(
                f"### FB-{i:03d} · {st.title if st else fb.step_id} · "
                f"{fb.created_at.isoformat() if fb.created_at else '—'}"
            )
            lines.append(f"- 类型: {fb.category} · 严重度: {fb.severity}")
            lines.append(f"- 现象: {fb.body}")
            if fb.expectation:
                lines.append(f"- 期望: {fb.expectation}")
            lines.append("")

    lines.extend(
        [
            "## 待解析员（假设，未确认）",
            "",
            "- 出处 `demo_run/" + row.id + "`",
            "",
            "## 待工匠 Ticket",
            "",
            "- 须绑对象与 BR 禁止项（含不写回约定日）",
            "",
            "## 明确不交付",
            "",
            "- 计件发薪系统（Excel 导入为将来输入）",
            "",
        ]
    )
    return "\n".join(lines)


def guided_context_for_path(session: Session, pathname: str) -> dict | None:
    active = get_active_run(session)
    if not active:
        return None
    step = resolve_step_for_path(pathname, active.get("current_step_id"))
    if step is None:
        return None
    nxt = next_step(step.step_id)
    ready = step_readiness(session, active["id"], step.step_id)
    saved = saved_step_data(session, active["id"], step.step_id)
    mode = active.get("session_mode") or "live"
    business_ok = step_business_applied(session, active["id"], step.step_id) if saved else True
    needs_business_sync = saved is not None and not business_ok
    seed_allowed = mode == "live" and ready["ready"] and (saved is None or needs_business_sync)
    return {
        "run": active,
        "session_mode": mode,
        "step": {
            "step_id": step.step_id,
            "title": step.title,
            "seq": step.seq,
            "seed_kind": step.seed_kind,
            "list_path": step.list_path,
        },
        "next": {
            "step_id": nxt.step_id,
            "title": nxt.title,
            "list_path": nxt.list_path,
        }
        if nxt
        else None,
        "readiness": ready,
        "saved_step": saved,
        "seed_allowed": seed_allowed,
        "step_has_seed": saved is not None and business_ok,
        "needs_business_sync": needs_business_sync,
        "step_count": STEP_COUNT,
    }


def path_catalog() -> dict:
    return {
        "path_template": PATH_TEMPLATE_FULL,
        "step_count": STEP_COUNT,
        "anchor_today": DEMO_ANCHOR_TODAY,
        "steps": steps_for_api(),
    }


def _audit(session: Session, role: str, action: str, run_id: str, after: dict | None = None) -> None:
    user = user_for_role(role)
    write_audit(
        session,
        actor_role=role,
        actor_name=user.name if user else role,
        entity_type="demo_run",
        entity_id=run_id,
        action=action,
        after=after or {},
    )
