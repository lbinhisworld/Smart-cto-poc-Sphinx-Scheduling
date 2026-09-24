"""演示线手工/生成数据模式：重置系统后禁止自动灌种子。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from db.tables import AppSettingRow

MANUAL_DATA_MODE_KEY = "demo_manual_data_mode"


def is_manual_data_mode(session: Session) -> bool:
    row = session.get(AppSettingRow, MANUAL_DATA_MODE_KEY)
    return bool(row and row.value == "1")


def set_manual_data_mode(session: Session, enabled: bool) -> None:
    value = "1" if enabled else "0"
    row = session.get(AppSettingRow, MANUAL_DATA_MODE_KEY)
    if row is None:
        session.add(AppSettingRow(key=MANUAL_DATA_MODE_KEY, value=value))
    else:
        row.value = value
