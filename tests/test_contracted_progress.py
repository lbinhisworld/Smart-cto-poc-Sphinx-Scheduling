"""签约产品进度标签。"""

from db.contracted_progress import non_negative, progress_tags


def test_pending_order_is_amber_until_facts_arrive():
    tags = progress_tags(has_contract=False, schedule_phase="PENDING", sales_qty=12)
    assert tags["contract"]["label"] == "未签订"
    assert tags["schedule"]["label"] == "待排产"
    assert tags["purchase"]["label"] == "未采购"
    assert tags["material"]["label"] == "未回料"
    assert tags["produce"]["label"] == "未投产"
    assert tags["inbound"]["label"] == "未入库"
    assert all(row["tone"] == "open" for row in tags.values())


def test_signed_and_released_turns_contract_schedule_and_produce():
    tags = progress_tags(
        has_contract=True,
        schedule_phase="IN_PRODUCTION",
        sales_qty=12,
        plan_qty=12,
        reported_qty=12,
        inbound_qty=12,
    )
    assert tags["contract"]["label"] == "已签订"
    assert tags["schedule"]["label"] == "已排产"
    assert tags["produce"]["label"] == "已完工"
    assert tags["inbound"]["label"] == "已入库"
    assert tags["purchase"]["label"] == "未采购"


def test_partial_inbound_and_in_transit_material():
    tags = progress_tags(
        has_contract=True,
        schedule_phase="IN_SCHEDULING",
        purchased=True,
        received_qty=1,
        need_qty=4,
        inbound_qty=3,
        sales_qty=12,
    )
    assert tags["schedule"]["label"] == "排产中"
    assert tags["material"]["label"] == "在途中"
    assert tags["inbound"]["label"] == "部分入库"
    assert tags["produce"]["label"] == "未投产"


def test_gap_never_goes_negative():
    assert non_negative(-129) == 0
    assert non_negative(12) == 12


def test_demo_order_has_two_product_lines():
    from fastapi.testclient import TestClient

    from api.app_factory import app

    client = TestClient(app)
    client.post("/api/demo/ensure-crm-seed")
    rows = client.get("/api/crm/contracted-progress", headers={"X-Demo-Role": "GM"}).json()["data"]
    so5 = [r for r in rows if r["order_no"] == "SO-005"]
    assert len(so5) >= 2
    codes = {r["item_code"] for r in so5}
    assert "P1" in codes and "P2" in codes
