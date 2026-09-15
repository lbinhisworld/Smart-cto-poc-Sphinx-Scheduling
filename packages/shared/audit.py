"""统一留痕写入。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from db.tables import AuditLogRow


def write_audit(
    session: Session,
    *,
    actor_role: str,
    actor_name: str,
    entity_type: str,
    entity_id: str,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLogRow(
            actor_role=actor_role,
            actor_name=actor_name,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=json.dumps(before or {}, ensure_ascii=False),
            after_json=json.dumps(after or {}, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
    )
