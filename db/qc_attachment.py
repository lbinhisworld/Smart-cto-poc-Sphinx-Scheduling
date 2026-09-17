"""M9 统一附件（BR-QC-07）。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import QcAttachmentRow


def list_attachments(session: Session, *, entity_type: str, entity_id: int) -> list[dict]:
    rows = session.scalars(
        select(QcAttachmentRow)
        .where(
            QcAttachmentRow.entity_type == entity_type,
            QcAttachmentRow.entity_id == entity_id,
        )
        .order_by(QcAttachmentRow.sort_no, QcAttachmentRow.id)
    ).all()
    return [_row_dict(r) for r in rows]


def add_attachments(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    items: list[dict],
    uploaded_by: str,
) -> list[dict]:
    now = datetime.now(UTC)
    out: list[dict] = []
    base_sort = len(
        session.scalars(
            select(QcAttachmentRow).where(
                QcAttachmentRow.entity_type == entity_type,
                QcAttachmentRow.entity_id == entity_id,
            )
        ).all()
    )
    for i, item in enumerate(items):
        ref = (item.get("storage_ref") or item.get("data") or "").strip()
        if not ref:
            continue
        row = QcAttachmentRow(
            entity_type=entity_type,
            entity_id=entity_id,
            sort_no=base_sort + i,
            file_name=item.get("file_name") or f"image-{i + 1}.png",
            mime_type=item.get("mime_type") or "image/png",
            storage_kind=item.get("storage_kind") or "INLINE_B64",
            storage_ref=ref,
            caption=item.get("caption") or "",
            uploaded_at=now,
            uploaded_by=uploaded_by,
        )
        session.add(row)
        session.flush()
        out.append(_row_dict(row))
    return out


def delete_attachment(session: Session, attachment_id: int) -> bool:
    row = session.get(QcAttachmentRow, attachment_id)
    if row is None:
        return False
    session.delete(row)
    return True


def _row_dict(r: QcAttachmentRow) -> dict:
    return {
        "id": r.id,
        "entity_type": r.entity_type,
        "entity_id": r.entity_id,
        "sort_no": r.sort_no,
        "file_name": r.file_name,
        "mime_type": r.mime_type,
        "storage_kind": r.storage_kind,
        "storage_ref": r.storage_ref,
        "caption": r.caption,
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        "uploaded_by": r.uploaded_by,
    }
