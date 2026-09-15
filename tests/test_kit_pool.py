"""共享库存池与多单占库（BR-38）。"""

from decimal import Decimal

from engine.kit_pool import KitSnapshot


def test_kit_pool_consume_sequence():
    pool = KitSnapshot({"S2": Decimal("130")})
    a_from, a_net = pool.consume(order_no="SO-A", component_item_code="S2", gross_board=100, line_no=1)
    b_from, b_net = pool.consume(order_no="SO-B", component_item_code="S2", gross_board=100, line_no=1)
    assert a_from == 100 and a_net == 0
    assert b_from == 30 and b_net == 70
    assert len(pool.allocations) == 2
