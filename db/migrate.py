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

    if "hr_employee" in tables:
        cols = {c["name"] for c in insp.get_columns("hr_employee")}
        alters_hr: list[tuple[str, str]] = []
        if "employee_kind" not in cols:
            alters_hr.append(("employee_kind", "TEXT NOT NULL DEFAULT 'STAFF'"))
        if "is_team_leader" not in cols:
            alters_hr.append(("is_team_leader", "BOOLEAN NOT NULL DEFAULT 0"))
        if "schedule_dept" not in cols:
            alters_hr.append(("schedule_dept", "TEXT"))
        if "group_code" not in cols:
            alters_hr.append(("group_code", "TEXT"))
        if "contract_start" not in cols:
            alters_hr.append(("contract_start", "DATE"))
        if "contract_end" not in cols:
            alters_hr.append(("contract_end", "DATE"))
        if "contract_remind_days" not in cols:
            alters_hr.append(("contract_remind_days", "INTEGER NOT NULL DEFAULT 30"))
        if alters_hr:
            with engine.begin() as conn:
                for name, ddl in alters_hr:
                    conn.execute(text(f"ALTER TABLE hr_employee ADD COLUMN {name} {ddl}"))

    if "hr_labor_rate" not in tables:
        Base.metadata.tables["hr_labor_rate"].create(engine)

    if "prod_time_report" not in tables:
        Base.metadata.tables["prod_time_report"].create(engine)

    if "crm_opportunity" in tables:
        cols = {c["name"] for c in insp.get_columns("crm_opportunity")}
        if "sample_code" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE crm_opportunity ADD COLUMN sample_code TEXT")
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
        cols = {c["name"] for c in insp.get_columns("so_order")}
        if "contract_no" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE so_order ADD COLUMN contract_no TEXT"))

    for name in ("crm_contract", "crm_contract_payment_plan", "crm_payment_receipt"):
        if name not in tables:
            Base.metadata.tables[name].create(engine)

    if "wo" in tables:
        cols = {c["name"] for c in insp.get_columns("wo")}
        if "qty_board_done" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE wo ADD COLUMN qty_board_done INTEGER NOT NULL DEFAULT 0")
                )

    if "prod_qty_report" not in tables:
        Base.metadata.tables["prod_qty_report"].create(engine)
    if "pending_roll_pool" not in tables:
        Base.metadata.tables["pending_roll_pool"].create(engine)

    if "order_change_request" in tables:
        cols = {c["name"] for c in insp.get_columns("order_change_request")}
        alters_ocr: list[tuple[str, str]] = []
        if "source" not in cols:
            alters_ocr.append(("source", "TEXT NOT NULL DEFAULT 'SALES_CHANGE'"))
        if "suggested_due" not in cols:
            alters_ocr.append(("suggested_due", "DATE"))
        if "sales_proposed_due" not in cols:
            alters_ocr.append(("sales_proposed_due", "DATE"))
        if "brief_text" not in cols:
            alters_ocr.append(("brief_text", "TEXT NOT NULL DEFAULT ''"))
        if "run_id" not in cols:
            alters_ocr.append(("run_id", "TEXT NOT NULL DEFAULT ''"))
        if alters_ocr:
            with engine.begin() as conn:
                for name, ddl in alters_ocr:
                    conn.execute(
                        text(f"ALTER TABLE order_change_request ADD COLUMN {name} {ddl}")
                    )

    if "so_order_due_event" not in tables:
        Base.metadata.tables["so_order_due_event"].create(engine)

    if "crm_sample_step" in tables:
        cols = {c["name"] for c in insp.get_columns("crm_sample_step")}
        alters_step: list[tuple[str, str]] = []
        if "evidence_text" not in cols:
            alters_step.append(("evidence_text", "TEXT NOT NULL DEFAULT ''"))
        if "evidence_images_json" not in cols:
            alters_step.append(("evidence_images_json", "TEXT NOT NULL DEFAULT '[]'"))
        if "is_final" not in cols:
            alters_step.append(("is_final", "BOOLEAN NOT NULL DEFAULT 0"))
        if "round_no" not in cols:
            alters_step.append(("round_no", "INTEGER"))
        if alters_step:
            with engine.begin() as conn:
                for name, ddl in alters_step:
                    conn.execute(text(f"ALTER TABLE crm_sample_step ADD COLUMN {name} {ddl}"))
