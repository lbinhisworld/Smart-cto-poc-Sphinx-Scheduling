"""种子 JSON → SQLite。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.tables import (
    MdCapacityCalendarRow,
    MdBomLineRow,
    MdItemRouteRow,
    MdItemRow,
    MdSphRow,
    MdUomConvertRow,
    SoOrderRow,
    StockRow,
)


def seed_manifest(seed_path: Path) -> dict:
    with seed_path.open(encoding="utf-8") as fh:
        seed = json.load(fh)
    return {
        "order_count": len(seed["orders"]),
        "item_count": len(seed["items"]),
        "seed_version": seed.get("meta", {}).get("seed_version"),
    }


def clear_master_and_orders(session: Session) -> None:
    """清空演示用主数据与订单（保留计划版本可选，POC 演示一并清计划）。"""
    from db.tables import (
        PlanVersionRow,
        WoDependencyRow,
        WoInsertLogRow,
        WoRow,
        WoTaskRow,
    )

    session.execute(delete(WoTaskRow))
    session.execute(delete(WoDependencyRow))
    session.execute(delete(WoInsertLogRow))
    session.execute(delete(WoRow))
    session.execute(delete(PlanVersionRow))
    session.execute(delete(SoOrderRow))
    session.execute(delete(MdCapacityCalendarRow))
    session.execute(delete(MdUomConvertRow))
    session.execute(delete(MdSphRow))
    session.execute(delete(MdItemRouteRow))
    session.execute(delete(MdBomLineRow))
    session.execute(delete(StockRow))
    session.execute(delete(MdItemRow))


def reload_seed_json(session: Session, seed_path: Path) -> dict:
    clear_master_and_orders(session)
    import_seed_json(session, seed_path)
    return seed_manifest(seed_path)


def needs_seed_reload(session: Session, seed_path: Path) -> bool:
    manifest = seed_manifest(seed_path)
    order_count = session.scalar(select(func.count()).select_from(SoOrderRow)) or 0
    item_count = session.scalar(select(func.count()).select_from(MdItemRow)) or 0
    return order_count != manifest["order_count"] or item_count != manifest["item_count"]


def backfill_order_sales_names(session: Session, seed_path: Path) -> int:
    """旧库缺销售姓名时按种子补上，不重导、不改排程阶段。"""
    with seed_path.open(encoding="utf-8") as fh:
        seed = json.load(fh)
    wanted = {
        str(row["order_no"]): str(row.get("sales_name") or "").strip()
        for row in seed.get("orders", [])
    }
    filled = 0
    for row in session.scalars(select(SoOrderRow)).all():
        name = wanted.get(row.order_no, "")
        if name and not (row.sales_name or "").strip():
            row.sales_name = name
            filled += 1
    return filled


def ensure_seed_current(session: Session, seed_path: Path) -> dict:
    """POC 演示：库内订单/品项数与种子不一致则自动重导。"""
    if needs_seed_reload(session, seed_path):
        return reload_seed_json(session, seed_path)
    manifest = seed_manifest(seed_path)
    filled = backfill_order_sales_names(session, seed_path)
    if filled:
        manifest = {**manifest, "sales_backfilled": filled}
    return manifest


def count_orders(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(SoOrderRow)) or 0)


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
                    dept=group["dept"],
                    group_code=group["code"],
                    work_date=cursor,
                    is_workday=is_wd,
                    hours_per_day=hours,
                    headcount=group["headcount"],
                    reserved_ratio=reserved,
                )
            )
        cursor += timedelta(days=1)
    now = datetime.now(UTC)
    for code, qty in seed["stock"].items():
        session.add(
            StockRow(
                item_code=code,
                qty_available=str(qty),
                uom_display="BOARD",
                source="SEED",
                updated_at=now,
            )
        )
    for row in seed.get("bom_lines", []):
        session.add(
            MdBomLineRow(
                parent_item_code=row["parent_item_code"],
                line_no=row["line_no"],
                component_item_code=row["component_item_code"],
                component_role=row["component_role"],
                qty_per_parent=str(row["qty_per_parent"]),
                qty_basis_uom=row.get("qty_basis_uom", "BOX"),
                scrap_rate=str(row["scrap_rate"]) if row.get("scrap_rate") is not None else None,
                offset_days=row.get("offset_days", 0),
                lead_time_days=row.get("lead_time_days", 4),
                kit_critical=row.get("kit_critical", True),
            )
        )
    for row in seed["orders"]:
        session.add(
            SoOrderRow(
                order_no=row["order_no"],
                customer=row["customer"],
                sales_name=row.get("sales_name", ""),
                item_code=row["item_code"],
                qty_order=str(row["qty_order"]),
                unit=row["unit"],
                due_date=date.fromisoformat(row["due_date"]),
                ready_date=date.fromisoformat(row["ready_date"]) if row.get("ready_date") else None,
                customer_level=row["customer_level"],
                amount=str(row["amount"]),
                is_urgent=row["is_urgent"],
                schedule_phase=row.get("schedule_phase", "PENDING"),
            )
        )
