"""§11 T2 需求展开（BR-02）。"""

from decimal import Decimal

from engine.expand import expand_order
from engine.models import Uom


def test_br02_expand_p1_100_box(p1, p1_converts, p1_sph, so_001, today):
    wo = expand_order(so_001, p1, p1_converts, today, sph=p1_sph)
    assert wo is not None
    assert wo.qty_board_plan == 420  # 100 * 4 * 1.05


def test_br02_expand_p2_200_box(p2, p2_converts, schedule_input, today):
    order = next(o for o in schedule_input.orders if o.order_no == "SO-002")
    sph = schedule_input.sph_of("P2", "MOLD")
    wo = expand_order(order, p2, p2_converts, today, sph=sph)
    assert wo is not None
    assert wo.qty_board_plan == 1236  # 200 * 6 * 1.03


def test_br02_expand_p4_60_box(p4, p4_converts, p4_sph, so_003, today):
    wo = expand_order(so_003, p4, p4_converts, today, sph=p4_sph)
    assert wo is not None
    assert wo.qty_board_plan == 312  # 60 * 5 * 1.04
    assert wo.due_date == so_003.due_date
    assert so_003.unit == Uom.BOX
    assert wo.qty_order == Decimal("60")
