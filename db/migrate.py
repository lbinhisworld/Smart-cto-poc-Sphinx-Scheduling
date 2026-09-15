"""SQLite 轻量迁移（POC：补列/补表，不丢数据）。"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from db.base import Base


def ensure_schema(engine: Engine) -> None:
    import db.tables  # noqa: F401

    Base.metadata.create_all(engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "plan_version" in tables:
        cols = {c["name"] for c in insp.get_columns("plan_version")}
        if "conflicts_json" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE plan_version "
                        "ADD COLUMN conflicts_json TEXT NOT NULL DEFAULT '[]'"
                    )
                )
        cols = {c["name"] for c in insp.get_columns("plan_version")}
        if "kit_json" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE plan_version "
                        "ADD COLUMN kit_json TEXT NOT NULL DEFAULT '{}'"
                    )
                )

    if "wo_insert_log" not in tables:
        Base.metadata.tables["wo_insert_log"].create(engine)

    if "stock" in tables:
        cols = {c["name"] for c in insp.get_columns("stock")}
        alters: list[tuple[str, str]] = []
        if "uom_display" not in cols:
            alters.append(("uom_display", "TEXT NOT NULL DEFAULT 'BOARD'"))
        if "source" not in cols:
            alters.append(("source", "TEXT NOT NULL DEFAULT 'SEED'"))
        if "warehouse_code" not in cols:
            alters.append(("warehouse_code", "TEXT"))
        if "updated_at" not in cols:
            alters.append(("updated_at", "DATETIME"))
        if alters:
            with engine.begin() as conn:
                for name, ddl in alters:
                    conn.execute(text(f"ALTER TABLE stock ADD COLUMN {name} {ddl}"))

    if "md_bom_line" not in tables:
        Base.metadata.tables["md_bom_line"].create(engine)

    if "md_capacity_calendar" in tables:
        cols = {c["name"] for c in insp.get_columns("md_capacity_calendar")}
        if "dept" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE md_capacity_calendar "
                        "ADD COLUMN dept TEXT NOT NULL DEFAULT 'FINISHED_DEPT'"
                    )
                )

    if "wo_task" in tables:
        cols = {c["name"] for c in insp.get_columns("wo_task")}
        if "dept" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE wo_task "
                        "ADD COLUMN dept TEXT NOT NULL DEFAULT 'FINISHED_DEPT'"
                    )
                )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE md_item SET group_code = 'MOLD' "
                    "WHERE dept = 'SEMI_DEPT' AND group_code = 'SEMI'"
                )
            )

    if "so_order" in tables:
        cols = {c["name"] for c in insp.get_columns("so_order")}
        if "sales_name" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE so_order "
                        "ADD COLUMN sales_name TEXT NOT NULL DEFAULT ''"
                    )
                )
        cols = {c["name"] for c in insp.get_columns("so_order")}
        if "schedule_phase" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE so_order "
                        "ADD COLUMN schedule_phase TEXT NOT NULL DEFAULT 'PENDING'"
                    )
                )
        cols = {c["name"] for c in insp.get_columns("so_order")}
        alters_so: list[tuple[str, str]] = []
        if "customer_code" not in cols:
            alters_so.append(("customer_code", "TEXT"))
        if "owner_sales" not in cols:
            alters_so.append(("owner_sales", "TEXT NOT NULL DEFAULT ''"))
        if "order_status" not in cols:
            alters_so.append(("order_status", "TEXT NOT NULL DEFAULT 'CONFIRMED'"))
        if "kitting_rate_pct" not in cols:
            alters_so.append(("kitting_rate_pct", "INTEGER"))
        if "order_source" not in cols:
            alters_so.append(("order_source", "TEXT NOT NULL DEFAULT 'MANUAL'"))
        if alters_so:
            with engine.begin() as conn:
                for name, ddl in alters_so:
                    conn.execute(text(f"ALTER TABLE so_order ADD COLUMN {name} {ddl}"))
