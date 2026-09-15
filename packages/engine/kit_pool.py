"""运行内共享库存池（BR-38）。"""

from __future__ import annotations

from decimal import Decimal

from engine.models import KitAllocation


class KitSnapshot:
    def __init__(self, stock: dict[str, Decimal]) -> None:
        self._available: dict[str, int] = {k: int(v) for k, v in stock.items()}
        self.allocations: list[KitAllocation] = []

    def available(self, item_code: str) -> int:
        return self._available.get(item_code, 0)

    def consume(
        self,
        *,
        order_no: str,
        component_item_code: str,
        gross_board: int,
        line_no: int | None = None,
    ) -> tuple[int, int]:
        """返回 (from_stock, net_need)。"""
        avail = self.available(component_item_code)
        from_stock = min(gross_board, avail)
        net = gross_board - from_stock
        if from_stock > 0:
            self._available[component_item_code] = avail - from_stock
            self.allocations.append(
                KitAllocation(
                    order_no=order_no,
                    component_item_code=component_item_code,
                    qty_board=from_stock,
                    line_no=line_no,
                )
            )
        return from_stock, net
