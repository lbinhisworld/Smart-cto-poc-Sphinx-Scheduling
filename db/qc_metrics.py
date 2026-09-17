"""M9 驾驶舱指标。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.qc_limits_loader import load_qc_limits
from db.qc_period import month_key
from db.tables import (
    QcCustomerComplaintRow,
    QcMaterialExceptionRow,
    QcMaterialReceiptRow,
    QcProductTestRow,
    QcSwabTestRow,
)


def qc_summary(session: Session, *, today: date) -> dict:
    mk = month_key(today)
    receipts = session.scalar(
        select(func.count()).select_from(QcMaterialReceiptRow).where(QcMaterialReceiptRow.month_key == mk)
    ) or 0
    open_exc = session.scalar(
        select(func.count())
        .select_from(QcMaterialExceptionRow)
        .where(QcMaterialExceptionRow.status != "CLOSED")
    ) or 0
    open_complaints = session.scalar(
        select(func.count())
        .select_from(QcCustomerComplaintRow)
        .where(QcCustomerComplaintRow.status != "CLOSED")
    ) or 0
    swab_fail = session.scalar(
        select(func.count())
        .select_from(QcSwabTestRow)
        .where(QcSwabTestRow.month_key == mk)
        .where(
            (QcSwabTestRow.verdict_final == "FAIL")
            | ((QcSwabTestRow.verdict_final.is_(None)) & (QcSwabTestRow.verdict_computed == "FAIL"))
        )
    ) or 0
    prod_fail = session.scalar(
        select(func.count())
        .select_from(QcProductTestRow)
        .where(QcProductTestRow.month_key == mk)
        .where(
            (QcProductTestRow.verdict_final == "FAIL")
            | ((QcProductTestRow.verdict_final.is_(None)) & (QcProductTestRow.verdict_computed == "FAIL"))
        )
    ) or 0
    limits = load_qc_limits()
    return {
        "month_key": mk,
        "receipts_mtd": receipts,
        "exceptions_open": open_exc,
        "complaints_open": open_complaints,
        "swab_fail_mtd": swab_fail,
        "product_fail_mtd": prod_fail,
        "exception_sla_days": limits.get("exception_sla_days", 7),
    }
