"""交互式 preview API。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from tests.conftest import ROOT, TODAY


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "interactive_api.db"
    engine = make_engine(db_path)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, ROOT / "seed" / "seed_data.json")
        session.commit()
    finally:
        session.close()
    app = create_app(factory)
    with TestClient(app) as client:
        yield client


def test_interactive_preview_crew_change(api_client):
    run = api_client.post(
        "/api/schedule/run",
        json={"order_nos": ["SO-001"], "today": TODAY.isoformat(), "reserved_ratio": 0},
    ).json()["data"]
    base = run["result"]
    tasks = base["tasks"]
    t0 = tasks[0]
    t0["crew_plan"] = 99
    resp = api_client.post(
        "/api/schedule/interactive-preview",
        json={
            "today": TODAY.isoformat(),
            "order_nos": ["SO-001"],
            "baseline_wos": base["wos"],
            "baseline_tasks": base["tasks"],
            "proposed_wos": base["wos"],
            "proposed_tasks": tasks,
            "trigger_task_id": t0["task_id"],
            "reserved_ratio": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(w["code"] == "CREW_OVER_HEAD" for w in data["headcount_warnings"])
    assert data["trigger_order_no"] == "SO-001"
