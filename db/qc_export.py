"""M9 台账 CSV 导出（Excel 可打开）。"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from db.qc_material import list_exceptions, list_receipts


def export_receipts_csv(session: Session, *, month: str | None = None) -> bytes:
    rows = list_receipts(session, month=month)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "月份",
            "来料日期",
            "属性",
            "来料批次",
            "保质期",
            "供应商编码",
            "供应商",
            "物料编码",
            "品名",
            "规格",
            "数量",
            "单位",
            "备注",
        ]
    )
    for r in rows:
        w.writerow(
            [
                r["month_key"],
                r["incoming_date"],
                r["attr"],
                r["batch_no"],
                r["shelf_life_until"] or r["shelf_life_text"],
                r["supplier_code"],
                r["supplier_name"],
                r["material_code"],
                r["material_name"],
                r["spec"],
                r["qty"],
                r["uom"],
                r["remark"],
            ]
        )
    return buf.getvalue().encode("utf-8-sig")


def export_exceptions_csv(session: Session, *, month: str | None = None) -> bytes:
    rows = list_exceptions(session, month=month)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["月份", "异常单号", "来料单号", "发现日期", "异常现象", "状态", "处置", "关闭结果"])
    for r in rows:
        rcpt = r.get("receipt") or {}
        w.writerow(
            [
                r["month_key"],
                r["exception_no"],
                rcpt.get("receipt_no", ""),
                r["discovered_at"],
                r["phenomenon"],
                r["status"],
                r["disposition"],
                r["close_result"],
            ]
        )
    return buf.getvalue().encode("utf-8-sig")
