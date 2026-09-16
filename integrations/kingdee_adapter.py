"""金蝶 K/3 对接（POC：Push 模拟，DEMO_MODE 无真实 HTTP）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from db.contract_queries import pick_active_contract, validate_order_contract
from db.order_kitting import refresh_order_kitting
from db.repositories import create_order
from db.tables import KingdeeSyncLogRow, SoOrderRow
from engine.models import Order, Uom


@dataclass(frozen=True)
class PushOrderPayload:
    order_no: str
    customer: str
    sales_name: str
    item_code: str
    qty_order: Decimal
    unit: str
    due_date: date
    amount: Decimal
    customer_code: str | None = None
    contract_no: str | None = None


class KingdeeAdapter(Protocol):
    def push_order(self, session: Session, payload: PushOrderPayload, *, today: date) -> KingdeeSyncLogRow:
        ...


class MockKingdeeAdapter:
    """金蝶主动 Push 销售订单（模拟）。"""

    def push_order(self, session: Session, payload: PushOrderPayload, *, today: date) -> KingdeeSyncLogRow:
        existing = session.get(SoOrderRow, payload.order_no)
        if existing is not None:
            log = KingdeeSyncLogRow(
                direction="PUSH_IN",
                doc_type="SALES_ORDER",
                doc_no=payload.order_no,
                status="FAILED",
                message="订单号已存在",
                payload_json=json.dumps(payload.__dict__, default=str, ensure_ascii=False),
                created_at=datetime.now(UTC),
            )
            session.add(log)
            return log

        contract_no = payload.contract_no
        if not contract_no and payload.customer_code:
            contract_no = pick_active_contract(session, payload.customer_code)
        if payload.customer_code:
            if not contract_no:
                log = KingdeeSyncLogRow(
                    direction="PUSH_IN",
                    doc_type="SALES_ORDER",
                    doc_no=payload.order_no,
                    status="FAILED",
                    message="销售订单必须关联合同",
                    payload_json=json.dumps(payload.__dict__, default=str, ensure_ascii=False),
                    created_at=datetime.now(UTC),
                )
                session.add(log)
                return log
            try:
                validate_order_contract(
                    session,
                    customer_code=payload.customer_code,
                    contract_no=contract_no,
                )
            except ValueError as exc:
                log = KingdeeSyncLogRow(
                    direction="PUSH_IN",
                    doc_type="SALES_ORDER",
                    doc_no=payload.order_no,
                    status="FAILED",
                    message=str(exc),
                    payload_json=json.dumps(payload.__dict__, default=str, ensure_ascii=False),
                    created_at=datetime.now(UTC),
                )
                session.add(log)
                return log

        order = Order(
            order_no=payload.order_no,
            customer=payload.customer,
            sales_name=payload.sales_name,
            item_code=payload.item_code,
            qty_order=payload.qty_order,
            unit=Uom(payload.unit),
            due_date=payload.due_date,
            ready_date=today,
            customer_level=3,
            amount=payload.amount,
            is_urgent=False,
            schedule_phase="PENDING",
        )
        create_order(session, order)
        session.flush()
        row = session.get(SoOrderRow, payload.order_no)
        if row is None:
            raise RuntimeError(f"金蝶 Push 入库失败: {payload.order_no}")
        row.order_source = "KINGDEE"
        row.order_status = "CONFIRMED"
        row.customer_code = payload.customer_code
        row.owner_sales = payload.sales_name
        if contract_no:
            row.contract_no = contract_no

        kit = refresh_order_kitting(session, payload.order_no, today=today)

        log = KingdeeSyncLogRow(
            direction="PUSH_IN",
            doc_type="SALES_ORDER",
            doc_no=payload.order_no,
            status="SUCCESS",
            message=f"已入库并算料，齐套率 {kit.get('kitting_rate_pct')}%",
            payload_json=json.dumps(
                {**payload.__dict__, "kitting": kit},
                default=str,
                ensure_ascii=False,
            ),
            created_at=datetime.now(UTC),
        )
        session.add(log)
        return log


def get_kingdee_adapter() -> KingdeeAdapter:
    return MockKingdeeAdapter()
