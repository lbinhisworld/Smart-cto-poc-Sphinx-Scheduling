"""BOM（一层半成品）+ 工艺路线摘要（本地种子 / 演示）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from sqlalchemy import select

from db.tables import MdBomLineRow, MdItemRouteRow, MdItemRow

_GROUP_LABEL = {
    "MANUAL": "手工组",
    "MOLD": "模具组",
    "POURING": "浇注组",
    "SEMI": "二部半成品组",
}


def route_summary_for_item(session: Session, item_code: str) -> dict | None:
    item = session.get(MdItemRow, item_code)
    if item is None:
        return None
    route = session.get(MdItemRouteRow, item_code)
    group_label = _GROUP_LABEL.get(item.group_code, item.group_code)
    lines: list[str] = []
    bom_rows = session.scalars(
        select(MdBomLineRow)
        .where(MdBomLineRow.parent_item_code == item_code)
        .order_by(MdBomLineRow.line_no)
    ).all()
    semi_rows = [r for r in bom_rows if r.component_role == "SEMI"]
    if len(semi_rows) >= 2:
        parts: list[str] = []
        for r in semi_rows:
            comp = session.get(MdItemRow, r.component_item_code)
            name = comp.item_name if comp else r.component_item_code
            parts.append(
                f"{r.component_item_code}（{name}）×{float(Decimal(str(r.qty_per_parent))):g}/盒"
            )
        lines.append(f"多半成品 BOM：{' + '.join(parts)}")
        purch = [r for r in bom_rows if r.component_role == "PURCHASED"]
        if purch:
            lines.append(f"外购 {len(purch)} 行（齐套校验）")
    elif len(semi_rows) == 1:
        r = semi_rows[0]
        comp = session.get(MdItemRow, r.component_item_code)
        name = comp.item_name if comp else r.component_item_code
        lines.append(
            f"BOM 半成品 {r.component_item_code}（{name}）"
            f"×{float(Decimal(str(r.qty_per_parent))):g}/盒 · 提前{r.lead_time_days}天"
        )
    elif route and route.needs_semi and route.semi_item_code:
        semi = session.get(MdItemRow, route.semi_item_code)
        semi_name = semi.item_name if semi else route.semi_item_code
        bb = route.semi_board_per_box
        bb_f = float(Decimal(str(bb))) if bb is not None else None
        qty = f"{bb_f:g}版/盒" if bb_f is not None else ""
        lines.append(
            f"半成品 {route.semi_item_code}（{semi_name}）{qty} · 提前{route.lead_time_days}天"
        )
    else:
        lines.append("无半成品 · 单层成品")
    return {
        "item_code": item_code,
        "item_name": item.item_name,
        "finished_group": item.group_code,
        "finished_group_label": group_label,
        "needs_semi": bool(route.needs_semi) if route else False,
        "semi_item_code": route.semi_item_code if route else None,
        "lead_time_days": route.lead_time_days if route else None,
        "summary_text": f"{group_label} · {'; '.join(lines)}",
    }
