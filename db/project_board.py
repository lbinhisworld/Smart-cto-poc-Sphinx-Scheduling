"""大客户专项进度大盘。步骤日期由人登记，不写销售订单交期。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.tables import AppSettingRow, CrmCustomerRow, DeliveryProjectRow, DeliveryProjectStepRow

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"
PROJECT_VERSION_KEY = "project_demo_version"

# 大盘列。格内时间线写死，POC 不做自定义流程。
STAGES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("INIT", "立项", ("商机确认", "方案演示", "立项批准")),
    ("PROCURE", "采购", ("设备选型", "采购下单", "到货")),
    ("TRIAL", "试机", ("进场", "调试", "试产")),
    ("RAMP", "投产", ("试产通过", "转正式生产", "交排程")),
)
STAGE_BY_CODE = {code: (name, steps) for code, name, steps in STAGES}


class ProjectBoardError(Exception):
    pass


def _load_demo() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def _stored_version(session: Session) -> str | None:
    row = session.get(AppSettingRow, PROJECT_VERSION_KEY)
    return row.value if row else None


def _set_version(session: Session, version: str) -> None:
    row = session.get(AppSettingRow, PROJECT_VERSION_KEY)
    if row is None:
        session.add(AppSettingRow(key=PROJECT_VERSION_KEY, value=version))
    else:
        row.value = version


def _reload(session: Session, projects: list[dict]) -> int:
    session.execute(delete(DeliveryProjectStepRow))
    session.execute(delete(DeliveryProjectRow))
    n = 0
    for proj in projects:
        session.add(
            DeliveryProjectRow(
                code=proj["code"],
                name=proj["name"],
                customer_code=proj["customer_code"],
                order_no=proj.get("order_no") or "",
            )
        )
        dated: dict[tuple[str, int], dict] = {}
        for step in proj.get("steps") or []:
            dated[(step["stage_code"], int(step["step_no"]))] = step
        for stage_code, _stage_name, names in STAGES:
            for step_no, step_name in enumerate(names, start=1):
                spec = dated.get((stage_code, step_no), {})
                raw_date = spec.get("event_date")
                session.add(
                    DeliveryProjectStepRow(
                        project_code=proj["code"],
                        stage_code=stage_code,
                        step_no=step_no,
                        step_name=step_name,
                        event_date=date.fromisoformat(raw_date) if raw_date else None,
                        note=spec.get("note") or "",
                    )
                )
        n += 1
    return n


def ensure_project_board(session: Session, *, force: bool = False) -> dict:
    data = _load_demo()
    meta = data.get("meta") or {}
    target = str(meta.get("project_demo_version") or "project-v1")
    projects = list(data.get("projects") or [])
    stored = _stored_version(session)
    count = int(session.scalar(select(func.count()).select_from(DeliveryProjectRow)) or 0)
    reloaded = False
    if force or stored != target or (projects and count == 0):
        count = _reload(session, projects)
        _set_version(session, target)
        reloaded = True
    return {"project_demo_version": target, "projects": count, "reloaded": reloaded}


def _steps(session: Session, project_code: str, stage_code: str) -> list[DeliveryProjectStepRow]:
    return list(
        session.scalars(
            select(DeliveryProjectStepRow)
            .where(
                DeliveryProjectStepRow.project_code == project_code,
                DeliveryProjectStepRow.stage_code == stage_code,
            )
            .order_by(DeliveryProjectStepRow.step_no)
        ).all()
    )


def _cell(steps: list[DeliveryProjectStepRow]) -> dict:
    if steps and all(s.event_date is not None for s in steps):
        done_on = max(s.event_date for s in steps if s.event_date is not None)
        return {"done": True, "completed_on": done_on.isoformat()}
    return {"done": False, "completed_on": None}


def _handoff(stage_code: str, done: bool, order_no: str) -> str | None:
    if stage_code != "RAMP" or not done:
        return None
    if order_no:
        return "可交排程"
    return "尚未建生产订单"


def stage_detail(session: Session, project_code: str, stage_code: str) -> dict | None:
    if stage_code not in STAGE_BY_CODE:
        return None
    project = session.get(DeliveryProjectRow, project_code)
    if project is None:
        return None
    stage_name, _names = STAGE_BY_CODE[stage_code]
    steps = _steps(session, project_code, stage_code)
    cell = _cell(steps)
    cust = session.get(CrmCustomerRow, project.customer_code)
    order_no = project.order_no or None
    return {
        "project_code": project.code,
        "project_name": project.name,
        "customer_code": project.customer_code,
        "customer_name": cust.name if cust else project.customer_code,
        "stage_code": stage_code,
        "stage_name": stage_name,
        "done": cell["done"],
        "completed_on": cell["completed_on"],
        "order_no": order_no,
        "handoff": _handoff(stage_code, cell["done"], project.order_no),
        "steps": [
            {
                "step_no": s.step_no,
                "name": s.step_name,
                "event_date": s.event_date.isoformat() if s.event_date else None,
                "note": s.note,
            }
            for s in steps
        ],
    }


def project_board(session: Session) -> dict:
    rows = list(session.scalars(select(DeliveryProjectRow).order_by(DeliveryProjectRow.code)).all())
    projects = []
    launched = 0
    for row in rows:
        cells = {}
        for stage_code, _name, _steps_names in STAGES:
            cells[stage_code] = _cell(_steps(session, row.code, stage_code))
        status = "已投产" if all(c["done"] for c in cells.values()) else "进行中"
        if status == "已投产":
            launched += 1
        cust = session.get(CrmCustomerRow, row.customer_code)
        projects.append(
            {
                "code": row.code,
                "name": row.name,
                "customer_code": row.customer_code,
                "customer_name": cust.name if cust else row.customer_code,
                "order_no": row.order_no or None,
                "status": status,
                "cells": cells,
            }
        )
    return {
        "stages": [{"code": code, "name": name} for code, name, _steps_names in STAGES],
        "projects": projects,
        "active_projects": len(projects) - launched,
        "launched_projects": launched,
        "note": "大客户专项进度。投产格变绿只表示可交排程，不改订单交期。",
    }


def project_summary(session: Session) -> dict:
    board = project_board(session)
    return {
        "active_projects": board["active_projects"],
        "launched_projects": board["launched_projects"],
        "note": board["note"],
    }


def set_step_date(
    session: Session,
    project_code: str,
    stage_code: str,
    step_no: int,
    event_date: str,
) -> dict:
    if stage_code not in STAGE_BY_CODE:
        raise ProjectBoardError("未知环节")
    project = session.get(DeliveryProjectRow, project_code)
    if project is None:
        raise ProjectBoardError("项目不存在")
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError as exc:
        raise ProjectBoardError("发生日期格式应为 YYYY-MM-DD") from exc
    step = session.scalar(
        select(DeliveryProjectStepRow).where(
            DeliveryProjectStepRow.project_code == project_code,
            DeliveryProjectStepRow.stage_code == stage_code,
            DeliveryProjectStepRow.step_no == step_no,
        )
    )
    if step is None:
        raise ProjectBoardError("步骤不存在")
    step.event_date = parsed
    session.flush()
    detail = stage_detail(session, project_code, stage_code)
    if detail is None:
        raise ProjectBoardError("项目不存在")
    return detail
