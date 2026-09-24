"""报价列表 · 电脑端状态分栏（与低代码 Tab 对齐）。"""

from __future__ import annotations

QUOTE_TABS = ("全部", "未发出", "谈判中", "已确认", "需重新报价")


def quote_ui_tab(row: dict) -> str:
    st = (row.get("status") or "").upper()
    note = row.get("note") or ""
    if "需重新报价" in note:
        return "需重新报价"
    if st == "DRAFT":
        return "未发出"
    if st == "SUBMITTED":
        return "谈判中"
    if st in ("APPROVED", "CONVERTED"):
        return "已确认"
    if st == "VOID":
        return "全部"
    return "未发出"


def filter_quotes_by_tab(rows: list[dict], tab: str | None) -> list[dict]:
    if not tab or tab == "全部":
        return rows
    return [r for r in rows if quote_ui_tab(r) == tab]


def quote_tab_counts(rows: list[dict]) -> dict[str, int]:
    counts = {t: 0 for t in QUOTE_TABS}
    for r in rows:
        ui = quote_ui_tab(r)
        if ui in counts:
            counts[ui] += 1
        counts["全部"] += 1
    return counts
