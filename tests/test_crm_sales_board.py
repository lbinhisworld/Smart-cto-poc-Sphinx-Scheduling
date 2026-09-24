"""包 B：拜访确认后才进分布，金额按角色从接口删除。"""

from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from api.app_factory import app
from db.crm_sales import (
    build_funnel,
    customer_completeness,
    draft_from_text,
    goal_lines,
    match_customers,
    order_talk,
    place_visits,
    redact,
    sop_next,
    visit_is_valid,
)

client = TestClient(app)
SALES = {"X-Demo-Role": "SALES"}
MGR = {"X-Demo-Role": "SALES_MGR"}
FIN = {"X-Demo-Role": "FIN"}
RD = {"X-Demo-Role": "RD"}
GM = {"X-Demo-Role": "GM"}


def test_visit_under_15_minutes_is_invalid():
    assert visit_is_valid(datetime(2026, 9, 15, 9, 0), datetime(2026, 9, 15, 9, 14)) is False
    assert visit_is_valid(datetime(2026, 9, 15, 9, 0), datetime(2026, 9, 15, 9, 15)) is True


def test_match_and_keyword_draft():
    customers = [
        {"code": "C-001", "name": "好利来食品"},
        {"code": "C-006", "name": "蓝岛烘焙供应链（无锡）"},
    ]
    one = match_customers("今天见到了好利来的决策人", customers)
    assert [row["code"] for row in one] == ["C-001"]
    both = match_customers("好利来和蓝岛都见了", customers)
    assert {row["code"] for row in both} == {"C-001", "C-006"}
    assert match_customers("街边新店", customers) == []
    draft = draft_from_text("今天见到了好利来的决策人", customers, today=__import__("datetime").date(2026, 9, 15))
    assert draft["outcome"] == "触达决策人"
    assert draft["next_step"] == sop_next("触达决策人")
    assert draft["ask_create"] is False
    assert draft["opportunity_name"] == ""


def test_place_visits_dedupes_same_name_without_code():
    visits = [
        {
            "id": 1,
            "status": "CONFIRMED",
            "customer_code": None,
            "customer_name": "同一陌拜名",
            "outcome": "关系建联",
            "is_valid": True,
            "owner_sales": "李业务",
        },
        {
            "id": 99,
            "status": "CONFIRMED",
            "customer_code": None,
            "customer_name": "同一陌拜名",
            "outcome": "触达决策人",
            "is_valid": True,
            "owner_sales": "李业务",
        },
    ]
    placed = place_visits(visits, document_stage={}, include_all=True)
    cell = placed["触达决策人|还没成商机"]
    assert len(cell) == 1
    assert cell[0]["customer_name"] == "同一陌拜名"


def test_place_visits_moves_cell_and_hides_drafts():
    visits = [
        {
            "id": 1,
            "status": "CONFIRMED",
            "customer_code": "C-001",
            "customer_name": "好利来食品",
            "outcome": "关系建联",
            "is_valid": True,
            "owner_sales": "李业务",
        },
        {
            "id": 2,
            "status": "DRAFT",
            "customer_code": "C-009",
            "customer_name": "草稿客户",
            "outcome": "挖到商机",
            "is_valid": True,
            "owner_sales": "李业务",
        },
        {
            "id": 3,
            "status": "CONFIRMED",
            "customer_code": None,
            "customer_name": "街边饼店",
            "outcome": "关系建联",
            "is_valid": True,
            "owner_sales": "李业务",
        },
        {
            "id": 4,
            "status": "CONFIRMED",
            "customer_code": "C-002",
            "customer_name": "短拜访",
            "outcome": "关系建联",
            "is_valid": False,
            "owner_sales": "李业务",
        },
    ]
    valid_only = place_visits(visits, document_stage={"C-001": "报价"}, include_all=False)
    assert [p["customer_code"] for p in valid_only["关系建联|报价"]] == ["C-001"]
    assert valid_only["关系建联|还没成商机"] == []
    moved = place_visits(
        visits
        + [
            {
                "id": 5,
                "status": "CONFIRMED",
                "customer_code": "C-001",
                "customer_name": "好利来食品",
                "outcome": "触达决策人",
                "is_valid": True,
                "owner_sales": "李业务",
            }
        ],
        document_stage={"C-001": "报价"},
        include_all=False,
    )
    assert moved["关系建联|报价"] == []
    assert moved["触达决策人|报价"][0]["customer_name"] == "好利来食品"
    everyone = place_visits(visits, document_stage={"C-001": "报价"}, include_all=True)
    cold = [p for p in everyone["关系建联|还没成商机"] if p["customer_name"] == "街边饼店"]
    assert cold
    assert any(p["customer_name"] == "短拜访" for row in everyone.values() for p in row)


def test_redact_drops_forbidden_money():
    row = {
        "visit_text": {"narrative": "见了面"},
        "sample_cost": {"material": "1.00"},
        "internal_quote": {"planned_labor": "2.00", "gap": "3.00"},
        "customer_quote": {"amount": "5.00"},
        "column_status": {"对客报价": "已完成", "打样": "进行中"},
        "sign": {"status": "未到", "items": ["雪花"], "contract_amount": "9.00", "received": "1.00"},
    }
    sales = redact(row, "SALES")
    assert "sample_cost" not in sales and "internal_quote" not in sales
    assert sales["customer_quote"]["amount"] == "5.00"
    assert "received" not in sales["sign"]
    rd = redact(row, "RD")
    assert "customer_quote" not in rd and "visit_text" not in rd
    assert "对客报价" not in rd["column_status"]
    assert rd["sample_cost"]["material"] == "1.00"
    assert rd["sign"] == {"status": "未到"}
    mgr = redact(row, "SALES_MGR")
    assert mgr["customer_quote"]["amount"] == "5.00"
    assert "sample_cost" not in mgr and "internal_quote" not in mgr
    fin = redact(row, "FIN")
    assert fin["internal_quote"]["gap"] == "3.00"
    assert "visit_text" not in fin


def test_funnel_rates_and_completeness_are_separate():
    visits = [
        {"status": "CONFIRMED", "is_valid": False, "customer_code": "C-1", "customer_name": "短", "outcome": "关系建联", "narrative": "短", "next_step": "约", "next_date": "2026-09-20"},
        {"status": "CONFIRMED", "is_valid": True, "customer_code": None, "customer_name": "街边", "outcome": "关系建联", "narrative": "陌拜", "next_step": "约", "next_date": "2026-09-20"},
        {"status": "CONFIRMED", "is_valid": True, "customer_code": "C-2", "customer_name": "好利来", "outcome": "关系建联", "narrative": "建联", "next_step": "约见", "next_date": "2026-09-20", "owner_sales": "李业务"},
        {"status": "DRAFT", "is_valid": True, "customer_code": "C-9", "customer_name": "草稿", "outcome": "挖到商机", "narrative": "不算"},
    ]
    facts = {
        "C-2": {"name": "好利来", "lost": False, "has_opp": True, "has_sample": True, "has_quote": False, "has_sign": False, "owner_sales": "李业务"},
    }
    funnel = build_funnel(visits, facts)
    counts = {step["stage"]: step["count"] for step in funnel["steps"]}
    assert counts["全部拜访"] == 3
    assert counts["有效拜访"] == 2
    assert counts["已建客户"] == 1
    assert counts["商机"] == 1
    assert counts["打样"] == 1
    assert counts["报价"] == 0
    rates = {step["stage"]: step["to_next_pct"] for step in funnel["steps"]}
    assert rates["有效拜访"] == 50
    assert rates["全部拜访"] == round(2 * 100 / 3)
    stuck_all = funnel["steps"][0]["stuck"]
    assert any(row["name"] == "短" for row in stuck_all)
    assert any(row["name"] == "街边" for row in funnel["steps"][1]["stuck"])
    score = customer_completeness([visits[2]])
    assert score["percent"] == 60
    assert "见了谁" in score["missing"]
    seen = customer_completeness(
        [
            visits[2],
            {
                "status": "CONFIRMED",
                "is_valid": True,
                "customer_code": "C-2",
                "outcome": "触达决策人",
                "narrative": "见到了决策人张厂长",
                "next_step": "问是否打样",
                "next_date": "2026-09-22",
                "opportunity_name": "",
            },
        ]
    )
    assert seen["percent"] == 80
    assert "见了谁" in seen["filled"]
    invalid = customer_completeness([visits[0]])
    assert invalid["percent"] == 0


def test_order_talk_does_not_invent_a_due_change():
    assert order_talk(has_tasks=False, due=date(2026, 9, 23), plan_end=None, earliest=None)["talk"] == "还没进排程"
    late = order_talk(has_tasks=True, due=date(2026, 9, 16), plan_end=date(2026, 9, 29), earliest=date(2026, 9, 29))
    assert late["talk"] == "来不及"
    assert late["earliest"] == "2026-09-29"
    ok = order_talk(has_tasks=True, due=date(2026, 10, 7), plan_end=date(2026, 10, 7), earliest=None)
    assert ok["talk"] == "交期内可做"


def test_goal_gap():
    lines = goal_lines({"有效拜访": 12, "新客": 4, "商机": 3, "签单": 1}, {"有效拜访": 1})
    visit = next(row for row in lines if row["metric"] == "有效拜访")
    assert visit["gap"] == 11


def test_llm_config_is_system_setting_not_sales_page():
    denied = client.get("/api/crm/llm-config", headers=SALES)
    assert denied.status_code == 403
    shown = client.get("/api/crm/llm-config", headers=GM)
    assert shown.status_code == 200
    body = shown.json()["data"]
    assert "api_key" not in body
    assert "has_key" in body
    assert body["model"]
    sales_menu = client.get("/api/portal/menu", headers=SALES).json()["data"]["items"]
    assert all(row["key"] != "settings" for row in sales_menu)
    gm_menu = client.get("/api/portal/menu", headers=GM).json()["data"]["items"]
    assert any(row["key"] == "settings" and row["label"] == "系统配置" for row in gm_menu)


def _people(board: dict) -> list[dict]:
    return [p for row in board["matrix"] for cell in row["cells"] for p in cell["people"]]


def test_confirm_moves_board_and_keeps_due_date():
    client.post("/api/demo/ensure-crm-seed")
    before = client.get("/api/orders/SO-002", headers=GM).json()["data"]["due_date"]
    board = client.get("/api/crm/board", headers=SALES).json()["data"]

    cold_visit = client.post(
        "/api/crm/visits/confirm",
        headers=SALES,
        json={
            "customer_name": "联测陌拜未建档",
            "visit_kind": "陌拜",
            "narrative": "仅用于 include_all 口径",
            "outcome": "关系建联",
            "next_step": "约见决策人",
            "next_date": "2026-09-20",
            "check_in_at": "2026-09-15T08:00:00",
            "check_out_at": "2026-09-15T08:20:00",
        },
    )
    assert cold_visit.status_code == 200, cold_visit.text
    cold = client.get("/api/crm/board?include_all=true", headers=SALES).json()["data"]
    assert any(p["customer_name"] == "联测陌拜未建档" for p in _people(cold))
    assert all(p["customer_name"] != "联测陌拜未建档" for p in _people(board))

    opened = client.post(
        "/api/crm/visits/confirm",
        headers=SALES,
        json={
            "customer_name": "联测矩阵迁移客户",
            "create_customer": True,
            "visit_kind": "陌拜",
            "narrative": "先把关系建起来",
            "outcome": "关系建联",
            "next_step": "约见决策人",
            "next_date": "2026-09-01",
            "check_in_at": "2026-09-15T09:00:00",
            "check_out_at": "2026-09-15T09:20:00",
        },
    )
    assert opened.status_code == 200, opened.text
    code = opened.json()["data"]["customer_code"]
    placed = client.get("/api/crm/board", headers=SALES).json()["data"]
    link = next(row for row in placed["matrix"] if row["outcome"] == "关系建联")
    assert any(p["customer_code"] == code for cell in link["cells"] for p in cell["people"])

    confirm = client.post(
        "/api/crm/visits/confirm",
        headers=SALES,
        json={
            "customer_name": "联测矩阵迁移客户",
            "customer_code": code,
            "visit_kind": "现有客户",
            "narrative": "见到了决策人",
            "outcome": "触达决策人",
            "next_step": "问是否打样",
            "next_date": "2026-09-22",
            "check_in_at": "2026-09-15T10:00:00",
            "check_out_at": "2026-09-15T10:20:00",
        },
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()["data"]
    assert body["is_valid"] is True
    assert body["completeness"]["after_percent"] > body["completeness"]["before_percent"]
    assert "见了谁" in body["completeness"]["gained"]
    after_board = client.get("/api/crm/board", headers=SALES).json()["data"]
    link_after = next(row for row in after_board["matrix"] if row["outcome"] == "关系建联")
    seen_after = next(row for row in after_board["matrix"] if row["outcome"] == "触达决策人")
    assert all(p["customer_code"] != code for cell in link_after["cells"] for p in cell["people"])
    assert any(p["customer_code"] == code for cell in seen_after["cells"] for p in cell["people"])
    assert client.get("/api/orders/SO-002", headers=GM).json()["data"]["due_date"] == before
    board_body = client.get("/api/crm/board", headers=SALES).json()["data"]
    assert board_body["funnel"]["steps"][0]["stage"] == "全部拜访"
    assert "to_next_pct" in board_body["funnel"]["steps"][0]
    assert {row["percent"] for row in board_body["completeness"]} == {0, 20, 40, 60, 80, 100}
    customers = client.get("/api/crm/mobile/customers", headers=SALES).json()["data"]
    assert isinstance(customers.get("unlinked"), list)
    orders = client.get("/api/crm/mobile/orders", headers=SALES).json()["data"]
    assert isinstance(orders, list)
    home = client.get("/api/crm/visits/home", headers=SALES).json()["data"]
    assert home["actions"]
    assert len(home["actions"]) <= 3

    short = client.post(
        "/api/crm/visits/confirm",
        headers=SALES,
        json={
            "customer_name": "联测短访客户",
            "create_customer": True,
            "visit_kind": "陌拜",
            "narrative": "只待了几分钟",
            "outcome": "关系建联",
            "next_step": "约见决策人",
            "next_date": "2026-09-22",
            "check_in_at": "2026-09-15T11:00:00",
            "check_out_at": "2026-09-15T11:08:00",
        },
    )
    assert short.status_code == 200
    assert short.json()["data"]["is_valid"] is False
    code = short.json()["data"]["customer_code"]
    valid_names = [
        p["customer_code"]
        for row in client.get("/api/crm/board", headers=SALES).json()["data"]["matrix"]
        for cell in row["cells"]
        for p in cell["people"]
    ]
    assert code not in valid_names
    all_names = [
        p["customer_code"]
        for row in client.get("/api/crm/board?include_all=true", headers=SALES).json()["data"]["matrix"]
        for cell in row["cells"]
        for p in cell["people"]
    ]
    assert code in all_names


def test_board_alerts_include_stall_for_overdue_sample():
    client.post("/api/demo/ensure-crm-seed")
    board = client.get("/api/crm/board", headers=MGR).json()["data"]
    kinds = {a["kind"] for a in board["alerts"]}
    assert kinds & {"打样停滞", "拜访低于目标", "拜访未齐", "未打样", "多次建联", "报价停滞"}
    assert board["matrix"]


def test_role_money_and_grade_do_not_touch_due_date():
    client.post("/api/demo/ensure-crm-seed")
    before = client.get("/api/orders/SO-002", headers=GM).json()["data"]["due_date"]
    opps = client.get("/api/crm/opportunities", headers=SALES).json()["data"]
    assert opps
    assert all(row["owner_sales"] == "李业务" for row in opps)
    opp_id = next(row["id"] for row in opps if row["name"] == "李业务·好利来加急")
    sales = client.get(f"/api/crm/opportunities/{opp_id}", headers=SALES).json()["data"]
    assert sales["customer_quote"]["amount"] == "15000.00"
    assert "sample_cost" not in sales and "internal_quote" not in sales
    rd = client.get(f"/api/crm/opportunities/{opp_id}", headers=RD).json()["data"]
    assert rd["sample_cost"]["material"] == "1200.00"
    assert "customer_quote" not in rd and "visit_text" not in rd
    assert rd["amount"] is None
    fin = client.get(f"/api/crm/opportunities/{opp_id}", headers=FIN).json()["data"]
    assert fin["internal_quote"]["planned_labor"] == "8000.00"
    assert fin["internal_quote"]["gap"] == "7000.00"
    assert fin["sample_cost"]["labor_overhead"] == "300.00"
    mgr = client.get(f"/api/crm/opportunities/{opp_id}", headers=MGR).json()["data"]
    assert mgr["customer_quote"]["amount"] == "15000.00"
    assert "sample_cost" not in mgr
    graded = client.post(f"/api/crm/opportunities/{opp_id}/grade", headers=MGR, json={"grade": "A"})
    assert graded.status_code == 200, graded.text
    assert graded.json()["data"]["sign_status"] == "已转项目"
    again = client.get(f"/api/crm/opportunities/{opp_id}", headers=GM).json()["data"]
    assert again["sign"]["status"] == "已转项目"
    assert client.get("/api/orders/SO-002", headers=GM).json()["data"]["due_date"] == before
    home = client.get("/api/crm/visits/home", headers=SALES).json()["data"]
    assert home["goals"]
    assert len(home["actions"]) <= 3
