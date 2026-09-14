"""种子 JSON → SQLite。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from db.tables import (
    MdCapacityCalendarRow,
    MdItemRouteRow,
    MdItemRow,
    MdSphRow,
    MdUomConvertRow,
    SoOrderRow,
    StockRow,
)


def import_seed_json(session: Session, seed_path: Path) -> None:
    with seed_path.open(encoding="utf-8") as fh:
        seed = json.load(fh, parse_float=Decimal)

    for row in seed["items"]:
        session.add(
            MdItemRow(
                item_code=row["item_code"],
                item_name=row["item_name"],
                dept=row["dept"],
                group_code=row["group_code"],
                unit_sale=row["unit_sale"],
                pcs_per_board=row["pcs_per_board"],
                board_per_box=str(row["board_per_box"]),
                loss_rate=str(row["loss_rate"]),
                color=row["color"],
                is_semi=row["is_semi"],
                computable=row["computable"],
            )
        )
    for row in seed["uom_converts"]:
        session.add(
            MdUomConvertRow(
                item_code=row["item_code"],
                from_uom=row["from_uom"],
                to_uom=row["to_uom"],
                factor=str(row["factor"]),
            )
        )
    for row in seed["routes"]:
        session.add(
            MdItemRouteRow(
                item_code=row["item_code"],
                needs_semi=row["needs_semi"],
                semi_item_code=row.get("semi_item_code"),
                semi_board_per_box=str(row["semi_board_per_box"]) if row.get("semi_board_per_box") is not None else None,
                lead_time_days=row["lead_time_days"],
                changeover_min=row["changeover_min"],
            )
        )
    for row in seed["sph"]:
        session.add(
            MdSphRow(
                item_code=row["item_code"],
                group_code=row["group_code"],
                sph_value=str(row["sph_value"]),
                sph_basis=row["sph_basis"],
                sph_crew=row.get("sph_crew"),
                sph_uom=row["sph_uom"],
                crew_std=row["crew_std"],
                confidence=row["confidence"],
                effective_date=date.fromisoformat(row["effective_date"]),
                source=row["source"],
            )
        )
    cal = seed["calendar"]
    start = date.fromisoformat(cal["range"][0])
    end = date.fromisoformat(cal["range"][1])
    workdays = set(cal["workdays"])
    hours = str(cal["hours_per_day"])
    reserved = str(seed["config"].get("reserved_ratio_in_tests", seed["config"]["reserved_ratio"]))
    cursor = start
    while cursor <= end:
        is_wd = cursor.isoweekday() in workdays
        for group in seed["groups"]:
            session.add(
                MdCapacityCalendarRow(
                    group_code=group["code"],
                    work_date=cursor,
                    is_workday=is_wd,
                    hours_per_day=hours,
                    headcount=group["headcount"],
                    reserved_ratio=reserved,
                )
            )
        cursor += timedelta(days=1)
    for code, qty in seed["stock"].items():
        session.add(StockRow(item_code=code, qty_available=str(qty)))
    for row in seed["orders"]:
        session.add(
            SoOrderRow(
                order_no=row["order_no"],
                customer=row["customer"],
                item_code=row["item_code"],
                qty_order=str(row["qty_order"]),
                unit=row["unit"],
                due_date=date.fromisoformat(row["due_date"]),
                ready_date=date.fromisoformat(row["ready_date"]) if row.get("ready_date") else None,
                customer_level=row["customer_level"],
                amount=str(row["amount"]),
                is_urgent=row["is_urgent"],
            )
        )
