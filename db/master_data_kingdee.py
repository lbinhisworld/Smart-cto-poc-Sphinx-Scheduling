"""金蝶 Mock 主数据同步（BR-QC-03）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import KingdeeSyncLogRow, MdRawMaterialRow, MdSupplierRow

ROOT = Path(__file__).resolve().parents[1]
MOCK_PATH = ROOT / "seed" / "kingdee_master_mock.json"


def _load_mock() -> dict:
    with MOCK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def list_suppliers(session: Session, *, q: str | None = None, limit: int = 50) -> list[dict]:
    stmt = select(MdSupplierRow).where(MdSupplierRow.status == "ACTIVE").order_by(MdSupplierRow.supplier_code)
    rows = session.scalars(stmt).all()
    out = [
        {
            "supplier_code": r.supplier_code,
            "name": r.name,
            "name_alias": r.name_alias,
        }
        for r in rows
    ]
    if q:
        qn = q.strip().lower()
        out = [
            x
            for x in out
            if qn in x["supplier_code"].lower() or qn in x["name"].lower()
        ]
    return out[:limit]


def list_raw_materials(session: Session, *, q: str | None = None, limit: int = 50) -> list[dict]:
    stmt = (
        select(MdRawMaterialRow)
        .where(MdRawMaterialRow.is_active.is_(True))
        .order_by(MdRawMaterialRow.material_code)
    )
    rows = session.scalars(stmt).all()
    out = [
        {
            "material_code": r.material_code,
            "name": r.name,
            "spec": r.spec,
            "default_uom": r.default_uom,
            "attr_default": r.attr_default,
        }
        for r in rows
    ]
    if q:
        qn = q.strip().lower()
        out = [
            x
            for x in out
            if qn in x["material_code"].lower() or qn in x["name"].lower()
        ]
    return out[:limit]


def get_supplier(session: Session, supplier_code: str) -> MdSupplierRow | None:
    return session.get(MdSupplierRow, supplier_code)


def get_raw_material(session: Session, material_code: str) -> MdRawMaterialRow | None:
    return session.get(MdRawMaterialRow, material_code)


def sync_suppliers_from_mock(session: Session) -> KingdeeSyncLogRow:
    data = _load_mock()
    now = datetime.now(UTC)
    count = 0
    for row in data.get("suppliers") or []:
        code = row["supplier_code"]
        existing = session.get(MdSupplierRow, code)
        if existing is None:
            session.add(
                MdSupplierRow(
                    supplier_code=code,
                    name=row["name"],
                    name_alias=row.get("name_alias") or "",
                    status="ACTIVE",
                    kingdee_id=row.get("kingdee_id"),
                    synced_at=now,
                    source="KINGDEE",
                )
            )
        else:
            existing.name = row["name"]
            existing.name_alias = row.get("name_alias") or ""
            existing.kingdee_id = row.get("kingdee_id")
            existing.synced_at = now
            existing.status = "ACTIVE"
        count += 1
    log = KingdeeSyncLogRow(
        direction="PULL_IN",
        doc_type="SUPPLIER",
        doc_no=f"SYNC-{now.strftime('%Y%m%d%H%M%S')}",
        status="SUCCESS",
        message=f"已同步供应商 {count} 条",
        payload_json=json.dumps({"count": count}, ensure_ascii=False),
        created_at=now,
    )
    session.add(log)
    return log


def sync_raw_materials_from_mock(session: Session) -> KingdeeSyncLogRow:
    data = _load_mock()
    now = datetime.now(UTC)
    count = 0
    for row in data.get("raw_materials") or []:
        code = row["material_code"]
        existing = session.get(MdRawMaterialRow, code)
        if existing is None:
            session.add(
                MdRawMaterialRow(
                    material_code=code,
                    name=row["name"],
                    spec=row.get("spec") or "",
                    default_uom=row.get("default_uom") or "KG",
                    attr_default=row.get("attr_default") or "",
                    is_active=True,
                    kingdee_id=row.get("kingdee_id"),
                    synced_at=now,
                    source="KINGDEE",
                )
            )
        else:
            existing.name = row["name"]
            existing.spec = row.get("spec") or ""
            existing.default_uom = row.get("default_uom") or "KG"
            existing.attr_default = row.get("attr_default") or ""
            existing.kingdee_id = row.get("kingdee_id")
            existing.synced_at = now
            existing.is_active = True
        count += 1
    log = KingdeeSyncLogRow(
        direction="PULL_IN",
        doc_type="RAW_MATERIAL",
        doc_no=f"SYNC-{now.strftime('%Y%m%d%H%M%S')}",
        status="SUCCESS",
        message=f"已同步原辅料 {count} 条",
        payload_json=json.dumps({"count": count}, ensure_ascii=False),
        created_at=now,
    )
    session.add(log)
    return log
