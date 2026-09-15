"""排程运行日志：给人审阅或送大模型诊断/验收。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.schedule_run_log import list_schedule_run_logs, write_schedule_run_log
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from engine.run_log import ALGORITHM_CARD, build_schedule_run_log, render_llm_brief
from engine.schedule import schedule
from tests.conftest import ROOT


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "runlog_api.db"
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
        yield client, factory


def test_build_run_log_self_contained_for_llm(input_builder, schedule_input):
    core = [o for o in schedule_input.orders if o.order_no in ("SO-001", "SO-002")]
    inp = input_builder(core)
    result = schedule(inp)
    log = build_schedule_run_log(
        inp,
        result,
        trigger="试排",
        run_id="20260915T000000_trial_0",
        recorded_at="2026-09-15T00:00:00+00:00",
        persist=False,
        plan_version=0,
    )
    assert log["schema"] == "sphinx.schedule_run_log.v1"
    assert log["algorithm"]["name"] == ALGORITHM_CARD["name"]
    assert "BR-25" in " ".join(log["algorithm"]["rules"])
    assert log["run"]["trigger"] == "试排"
    assert log["run"]["today"] == "2026-09-15"
    assert log["run"]["sort_mode"] == "DUE_DESC"
    nos = [o["order_no"] for o in log["input"]["orders"]]
    assert nos == ["SO-001", "SO-002"] or set(nos) == {"SO-001", "SO-002"}
    assert log["trace"]["events"]
    assert any(e["kind"] == "queue_rank" for e in log["trace"]["events"])
    assert "outcome" in log
    brief = log["llm_brief"]
    assert "DUE_DESC" in brief
    assert "SO-002" in brief
    assert render_llm_brief(log).startswith("#")


def test_write_and_list_schedule_run_logs(tmp_path: Path, input_builder, schedule_input):
    so = next(o for o in schedule_input.orders if o.order_no == "SO-001")
    inp = input_builder([so])
    result = schedule(inp)
    run_id = write_schedule_run_log(
        inp,
        result,
        trigger="初始排产",
        plan_version=1,
        persist=True,
        log_dir=tmp_path,
        run_id="unit_so001",
        recorded_at="2026-09-15T00:00:00+00:00",
    )
    assert run_id == "unit_so001"
    assert (tmp_path / "unit_so001.json").is_file()
    listed = list_schedule_run_logs(tmp_path)
    assert listed[0]["run_id"] == "unit_so001"
    assert listed[0]["trigger"] == "初始排产"
    assert "SO-001" in listed[0]["order_nos"]


def test_api_schedule_run_writes_log(api_client, tmp_path, monkeypatch):
    from db import schedule_run_log as srl

    monkeypatch.setattr(srl, "DEFAULT_LOG_DIR", tmp_path)
    client, _factory = api_client
    r = client.post(
        "/api/schedule/run",
        json={"order_nos": ["SO-001"], "today": "2026-09-15", "reserved_ratio": 0},
    )
    assert r.status_code == 200
    run_id = r.json()["data"]["run_id"]
    assert run_id
    listed = client.get("/api/schedule/logs").json()["data"]["logs"]
    assert any(x["run_id"] == run_id for x in listed)
    one = client.get(f"/api/schedule/logs/{run_id}").json()["data"]
    assert one["schema"] == "sphinx.schedule_run_log.v1"
    brief = client.get(f"/api/schedule/logs/{run_id}", params={"brief": True}).json()["data"]
    assert "llm_brief" in brief
    assert "倒排" in brief["llm_brief"] or "DUE_DESC" in brief["llm_brief"]
