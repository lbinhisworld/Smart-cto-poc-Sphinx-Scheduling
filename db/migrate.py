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

    if "md_item" in tables:
        cols = {c["name"] for c in insp.get_columns("md_item")}
        alters_item: list[tuple[str, str]] = []
        if "prod_category" not in cols:
            alters_item.append(("prod_category", "TEXT NOT NULL DEFAULT ''"))
        if "kg_per_board" not in cols:
            alters_item.append(("kg_per_board", "NUMERIC"))
        if "display_uom" not in cols:
            alters_item.append(("display_uom", "TEXT NOT NULL DEFAULT 'BOARD'"))
        if alters_item:
            with engine.begin() as conn:
                for name, ddl in alters_item:
                    conn.execute(text(f"ALTER TABLE md_item ADD COLUMN {name} {ddl}"))
        with engine.begin() as conn:
            for code, cat in (
                ("P1", "手工模具"),
                ("P1M", "手工模具"),
                ("P1L", "其他"),
                ("P2", "切片"),
                ("P5", "糖花"),
                ("P6", "切片"),
                ("P4", "logo"),
                ("P7", "logo"),
                ("P8", "logo"),
                ("P9", "抹面"),
            ):
                conn.execute(
                    text(
                        "UPDATE md_item SET prod_category = :cat "
                        "WHERE item_code = :code AND (prod_category IS NULL OR prod_category = '')"
                    ),
                    {"cat": cat, "code": code},
                )
            for code, kg in (
                ("P1", "0.25"),
                ("P1M", "0.20"),
                ("P1L", "0.15"),
                ("P2", "0.30"),
                ("P5", "0.08"),
                ("P6", "0.22"),
                ("P4", "0.18"),
                ("P7", "0.16"),
                ("P8", "0.14"),
                ("P9", "0.40"),
            ):
                conn.execute(
                    text(
                        "UPDATE md_item SET kg_per_board = :kg "
                        "WHERE item_code = :code AND kg_per_board IS NULL"
                    ),
                    {"kg": kg, "code": code},
                )
            conn.execute(
                text(
                    "UPDATE md_item SET display_uom = unit_sale "
                    "WHERE display_uom IS NULL OR display_uom = '' OR display_uom = 'BOARD'"
                )
            )

    if "wo_task" in tables:
        cols = {c["name"] for c in insp.get_columns("wo_task")}
        alters_task: list[tuple[str, str]] = []
        if "qty_actual" not in cols:
            alters_task.append(("qty_actual", "INTEGER"))
        if "kg_per_board_snap" not in cols:
            alters_task.append(("kg_per_board_snap", "NUMERIC"))
        if alters_task:
            with engine.begin() as conn:
                for name, ddl in alters_task:
                    conn.execute(text(f"ALTER TABLE wo_task ADD COLUMN {name} {ddl}"))

    if "prod_time_report" in tables:
        cols = {c["name"] for c in insp.get_columns("prod_time_report")}
        alters_tr: list[tuple[str, str]] = []
        if "hours_normal" not in cols:
            alters_tr.append(("hours_normal", "NUMERIC"))
        if "hours_ot" not in cols:
            alters_tr.append(("hours_ot", "NUMERIC"))
        if "headcount_indirect" not in cols:
            alters_tr.append(("headcount_indirect", "INTEGER"))
        if "hours_indirect_normal" not in cols:
            alters_tr.append(("hours_indirect_normal", "NUMERIC"))
        if "hours_indirect_ot" not in cols:
            alters_tr.append(("hours_indirect_ot", "NUMERIC"))
        if alters_tr:
            with engine.begin() as conn:
                for name, ddl in alters_tr:
                    conn.execute(text(f"ALTER TABLE prod_time_report ADD COLUMN {name} {ddl}"))

    tables = set(inspect(engine).get_table_names())
    for name in ("inv_inbound_daily", "inv_issue"):
        if name not in tables:
            Base.metadata.tables[name].create(engine)
