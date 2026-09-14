"""§11 T10 插单（BR-40~47）。"""

from datetime import date
from decimal import Decimal

from engine.insert import check_insert_feasible, schedule_insert
from engine.models import FeasibilityStatus, InsertStrategy, Order, Uom
from tests.conftest import _ripple_items_and_sph


def test_br47_insert_infeasible_by_leadtime(p2, schedule_input, order_with_due, so_002):
    order = order_with_due(so_002, date(2026, 9, 17))
    route = schedule_input.routes["P2"]
    result = check_insert_feasible(order, p2, route, schedule_input.stock, schedule_input.today)
    assert result.status == FeasibilityStatus.INFEASIBLE


def test_br40_insert_four_strategies(run_ripple, ripple_wos, ripple_input):
    wos = ripple_wos()
    baseline = run_ripple(wos)
    ripple_items = _ripple_items_and_sph(ripple_input)
    p1_route = ripple_items.routes["P1"]
    ripple_items = ripple_items.model_copy(
        update={
            "items": {
                **ripple_items.items,
                "N": ripple_items.items["A"].model_copy(
                    update={"item_code": "N", "item_name": "urgent-N", "loss_rate": Decimal("0")}
                ),
            },
            "uom": {**ripple_items.uom, "N": ripple_items.uom["A"]},
            "sph": {
                **ripple_items.sph,
                ("N", "MANUAL"): ripple_items.sph[("A", "MANUAL")],
            },
            "routes": {
                **ripple_items.routes,
                "N": p1_route.model_copy(update={"item_code": "N"}),
            },
        }
    )
    urgent = Order(
        order_no="SO-004",
        customer="插单",
        item_code="N",
        qty_order=Decimal("300"),
        unit=Uom.BOARD,
        due_date=date(2026, 9, 22),
        ready_date=date(2026, 9, 15),
        customer_level=5,
        amount=Decimal("1000"),
        is_urgent=True,
    )
    res = schedule_insert(ripple_items, urgent, baseline=baseline)
    assert {o.strategy for o in res.strategies} == {
        InsertStrategy.A,
        InsertStrategy.B,
        InsertStrategy.C,
        InsertStrategy.D,
    }
    assert res.diff.summary_text == "本次调整：新增 1、移动 2、延后 0、超交期 0"
