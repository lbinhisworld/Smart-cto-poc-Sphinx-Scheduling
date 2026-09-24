"""演示线清场：环节重新生成前删除本 run 该步谱系；启动时清本 run 草稿。"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from db.tables import DemoRunFeedbackRow, DemoRunSeedEventRow, DemoRunStepSnapshotRow


def clear_run_transient(session: Session, run_id: str) -> dict:
    """启动演示线：清空本线尚未归档的谱系与反馈（不含已 END 归档快照）。"""
    seeds = session.execute(delete(DemoRunSeedEventRow).where(DemoRunSeedEventRow.run_id == run_id))
    fbs = session.execute(delete(DemoRunFeedbackRow).where(DemoRunFeedbackRow.run_id == run_id))
    snaps = session.execute(delete(DemoRunStepSnapshotRow).where(DemoRunStepSnapshotRow.run_id == run_id))
    return {
        "seed_events_removed": seeds.rowcount or 0,
        "feedback_removed": fbs.rowcount or 0,
        "snapshots_removed": snaps.rowcount or 0,
    }


def clear_step_seed_events(session: Session, run_id: str, step_id: str) -> int:
    """本环节重新生成：去掉该步旧谱系（P1 起同步删 GD- 业务行）。"""
    result = session.execute(
        delete(DemoRunSeedEventRow).where(
            DemoRunSeedEventRow.run_id == run_id,
            DemoRunSeedEventRow.step_id == step_id,
        )
    )
    return int(result.rowcount or 0)
