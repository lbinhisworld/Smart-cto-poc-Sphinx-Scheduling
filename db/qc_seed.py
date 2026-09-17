"""M9 演示种子。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.master_data_kingdee import sync_raw_materials_from_mock, sync_suppliers_from_mock
from db.qc_ledgers import create_complaint
from db.qc_material import create_exception, create_receipt
from db.tables import (
    CrmCustomerRow,
    MdSupplierRow,
    QcCustomerComplaintRow,
    QcMaterialReceiptRow,
    QcSwabPointRow,
)


def ensure_qc_seed(session: Session) -> None:
    if (session.scalar(select(func.count()).select_from(MdSupplierRow)) or 0) == 0:
        sync_suppliers_from_mock(session)
        sync_raw_materials_from_mock(session)
        session.flush()

    if (session.scalar(select(func.count()).select_from(QcSwabPointRow)) or 0) == 0:
        points = [
            ("SP-A", "车间入口", "左墙"),
            ("SP-A", "车间入口", "右墙"),
            ("SP-B", "冷却线", "传送带"),
        ]
        for code, name, detail in points:
            session.add(
                QcSwabPointRow(point_code=code, point_name=name, detail_name=detail, is_active=True)
            )
        session.flush()

    if (session.scalar(select(func.count()).select_from(QcMaterialReceiptRow)) or 0) == 0:
        rcpt = create_receipt(
            session,
            {
                "incoming_date": "2026-09-10",
                "supplier_code": "SUP-001",
                "material_code": "RM-COCOA-70",
                "qty": "500",
                "batch_no": "BATCH-20260910",
                "attr": "原料",
            },
            actor="QC",
        )
        create_exception(
            session,
            {
                "receipt_id": rcpt["id"],
                "phenomenon": "外包装轻微破损",
                "discovered_at": "2026-09-10",
            },
            actor="WH",
        )

    cust = session.get(CrmCustomerRow, "C-001")
    if cust is not None:
        has = session.scalar(
            select(func.count())
            .select_from(QcCustomerComplaintRow)
            .where(QcCustomerComplaintRow.customer_code == "C-001")
        ) or 0
        if has == 0:
            create_complaint(
                session,
                {
                    "record_date": "2026-09-08",
                    "customer_code": "C-001",
                    "customer_name": cust.name,
                    "customer_project": "中秋礼盒",
                    "item_code": "P2",
                    "product_name": "经典礼盒",
                    "content": "客户反馈个别批次包装色差",
                    "category": "质量",
                    "status": "OPEN",
                },
                actor="QC",
            )
