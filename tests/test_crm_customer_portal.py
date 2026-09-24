"""公海与我的客户。"""

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app
from db.crm_customer_portal import ensure_demo_customer_portal, list_mine, list_sea
from db.session import make_engine, session_factory

client = TestClient(app)
MGR = {"X-Demo-Role": "SALES_MGR"}
SALES = {"X-Demo-Role": "SALES"}


def test_sea_and_mine_db():
    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    s = session_factory(engine)()
    try:
        ensure_demo_customer_portal(s)
        s.commit()
        sea = list_sea(s, role="SALES", actor="李业务")
        assert any(row["code"] == "C-010" for row in sea)
        mine = list_mine(s, role="SALES", actor="李业务", today=date(2026, 9, 15))
        assert mine["status_counts"]["维护阶段"] >= 1
    finally:
        s.close()


def test_sea_api_claim():
    res = client.get("/api/crm/sea", headers=SALES)
    assert res.status_code == 200
    res2 = client.post(
        "/api/crm/sea/claim",
        headers=SALES,
        json={"codes": ["C-010"], "owner_sales": "李业务"},
    )
    assert res2.status_code == 200
