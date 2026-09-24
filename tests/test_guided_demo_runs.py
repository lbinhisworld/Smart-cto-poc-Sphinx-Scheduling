"""演示线：生命周期、重放、反馈时间线、导出。"""

from __future__ import annotations

from pathlib import Path

import re

import pytest
from sqlalchemy import func, select

from db.tables import DemoRunRow
from db.guided_demo_runs import (
    GuidedDemoError,
    add_feedback,
    continue_run,
    create_run,
    delete_run,
    end_replay,
    end_run,
    export_markdown,
    get_active_run,
    get_run,
    guided_context_for_path,
    list_feedback,
    list_runs,
    seed_step,
    start_replay,
    start_run,
)
from shared.guided_demo_path import GUIDED_STEPS
from db.tables import DemoRunStepSnapshotRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_guided_demo.db"


@pytest.fixture()
def db_session():
    from db.migrate import ensure_schema
    from db.session import init_db, make_engine, session_factory

    if DB.is_file():
        DB.unlink()
    engine = make_engine(DB)
    init_db(engine)
    ensure_schema(engine)
    factory = session_factory(engine)
    session = factory()
    yield session
    session.close()
    if DB.is_file():
        DB.unlink()


def test_create_run_default_timestamp_title(db_session):
    run = create_run(db_session, title="", role="GM")
    assert re.fullmatch(r"\d{8}-\d{6}", run["title"])


def _seed_all_steps(session, run_id: str) -> None:
    for s in GUIDED_STEPS:
        seed_step(session, run_id, s.step_id, role="GM")


def test_run_lifecycle_replay_feedback_export(db_session):
    run = create_run(db_session, title="P0 走查", role="GM")
    run_id = run["id"]

    with pytest.raises(GuidedDemoError):
        seed_step(db_session, run_id, "roster", role="GM")

    start_run(db_session, run_id, role="GM")
    db_session.commit()
    assert get_active_run(db_session)["session_mode"] == "live"

    seed_step(db_session, run_id, "roster", role="GM")
    seed_step(db_session, run_id, "roster", role="GM")
    db_session.commit()

    add_feedback(
        db_session,
        run_id,
        step_id="roster",
        category="流程不顺",
        severity="可绕过",
        body="第一次反馈",
        expectation="",
        story_index=1,
        seed_event_id=None,
        refs=[],
        role="SALES",
    )
    db_session.commit()

    _seed_all_steps(db_session, run_id)
    db_session.commit()

    end_run(db_session, run_id, role="GM")
    db_session.commit()

    snaps = list(
        db_session.scalars(
            select(DemoRunStepSnapshotRow).where(DemoRunStepSnapshotRow.run_id == run_id)
        ).all()
    )
    assert len(snaps) == len(GUIDED_STEPS)

    start_replay(db_session, run_id, role="GM")
    db_session.commit()
    active = get_active_run(db_session)
    assert active["session_mode"] == "replay"

    with pytest.raises(GuidedDemoError):
        seed_step(db_session, run_id, "roster", role="GM")

    add_feedback(
        db_session,
        run_id,
        step_id="roster",
        category="其他",
        severity="会后优化",
        body="重放期间追加",
        expectation="",
        story_index=None,
        seed_event_id=None,
        refs=[],
        role="GM",
    )
    db_session.commit()

    items = list_feedback(db_session, run_id, step_id="roster")
    assert len(items) == 2

    end_replay(db_session, run_id, role="GM")
    db_session.commit()
    assert get_active_run(db_session) is None

    md = export_markdown(db_session, run_id)
    assert "演示过程" in md
    assert "各环节反馈时间线" in md
    assert "第一次反馈" in md
    assert "重放期间追加" in md


def test_export_while_active_partial_steps(db_session):
    run = create_run(db_session, title="进行中导出", role="GM")
    run_id = run["id"]
    start_run(db_session, run_id, role="GM")
    db_session.commit()
    seed_step(db_session, run_id, "roster", role="GM")
    add_feedback(
        db_session,
        run_id,
        step_id="roster",
        category="其他",
        severity="会后优化",
        body="演示中途反馈",
        expectation="边演示边改",
        story_index=1,
        seed_event_id=None,
        refs=[],
        role="GM",
    )
    db_session.commit()
    row = db_session.get(DemoRunRow, run_id)
    assert row is not None and row.status == "ACTIVE"

    md = export_markdown(db_session, run_id)
    assert "进行中 · 各环节最新 seed" in md
    assert "演示中途反馈" in md
    assert "边演示边改" in md
    assert "人员列表" in md or "roster" in md


def test_delete_ended_and_draft_not_active(db_session):
    draft = create_run(db_session, title="待删草稿", role="GM")
    ended = create_run(db_session, title="待删已结束", role="GM")
    start_run(db_session, ended["id"], role="GM")
    db_session.commit()
    _seed_all_steps(db_session, ended["id"])
    end_run(db_session, ended["id"], role="GM")
    db_session.commit()

    delete_run(db_session, draft["id"], role="GM")
    delete_run(db_session, ended["id"], role="GM")
    db_session.commit()

    assert get_run(db_session, draft["id"]) is None
    assert get_run(db_session, ended["id"]) is None
    assert len(list_runs(db_session)) == 0


def test_end_incomplete_rejected(db_session):
    run = create_run(db_session, title="未走完", role="GM")
    start_run(db_session, run["id"], role="GM")
    db_session.commit()
    seed_step(db_session, run["id"], "roster", role="GM")
    db_session.commit()
    with pytest.raises(GuidedDemoError, match="17"):
        end_run(db_session, run["id"], role="GM")


def test_continue_resume_seeded_step_and_no_regenerate(db_session):
    run = create_run(db_session, title="继续", role="GM")
    run_id = run["id"]
    start_run(db_session, run_id, role="GM")
    db_session.commit()
    seed_step(db_session, run_id, "roster", role="GM")
    db_session.commit()

    data = continue_run(db_session, run_id, role="SALES")
    assert data["resume_step_id"] == "roster"
    assert data["resume_list_path"] == "/modules/hr/roster"
    assert data["step_has_seed"] is True

    ctx = guided_context_for_path(db_session, "/modules/hr/roster")
    assert ctx is not None
    assert ctx["seed_allowed"] is False
    assert ctx["step_has_seed"] is True


def test_delete_active_clears_business(db_session):
    from db.demo_manual_data import set_manual_data_mode
    from db.tables import HrEmployeeRow, MdItemRow

    run = create_run(db_session, title="进行中", role="GM")
    start_run(db_session, run["id"], role="GM")
    db_session.commit()
    seed_step(db_session, run["id"], "roster", role="GM")
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(HrEmployeeRow)) or 0 > 0

    delete_run(db_session, run["id"], role="GM")
    db_session.commit()
    assert get_run(db_session, run["id"]) is None
    assert db_session.scalar(select(func.count()).select_from(HrEmployeeRow)) == 0
    assert db_session.scalar(select(func.count()).select_from(MdItemRow)) == 0
    from db.demo_manual_data import is_manual_data_mode

    assert is_manual_data_mode(db_session)


def test_start_new_run_archives_previous_and_clears(db_session):
    from db.tables import DemoRunRow, HrEmployeeRow

    a = create_run(db_session, title="线A", role="GM")
    start_run(db_session, a["id"], role="GM")
    db_session.commit()
    seed_step(db_session, a["id"], "roster", role="GM")
    db_session.commit()

    b = create_run(db_session, title="线B", role="GM")
    start_run(db_session, b["id"], role="GM")
    db_session.commit()

    row_a = db_session.get(DemoRunRow, a["id"])
    assert row_a is not None
    assert row_a.status == "ENDED"
    assert db_session.scalar(select(func.count()).select_from(HrEmployeeRow)) == 0
    active = get_active_run(db_session)
    assert active["id"] == b["id"]
