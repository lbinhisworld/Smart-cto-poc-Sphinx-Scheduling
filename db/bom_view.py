"""BOM / 工艺路线只读视图（设计态 + 数量展开，公式与 engine 一致）。"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import (
    MdBomLineRow,
    MdItemRouteRow,
    MdItemRow,
    MdSphRow,
    MdUomConvertRow,
    StockRow,
)
from engine.bom import gross_board_for_line
from engine.expand import expand_order, gross_semi_board
from engine.kit_pool import KitSnapshot
from engine.models import (
    BomLine,
    ComponentRole,
    Dept,
    GroupCode,
    Item,
    ItemRoute,
    Order,
    Sph,
    SphBasis,
    Uom,
    UomConvert,
)
from engine.uom import to_board

_GROUP_LABEL = {
    "MANUAL": "手工组",
    "MOLD": "模具组",
    "POURING": "浇注组",
    "SEMI": "二部半成品组",
}

_UOM_ZH = {
    "PCS": "枚",
    "BOARD": "版",
    "BOX": "盒",
    "PACK": "包",
    "BAG": "袋",
    "CARTON": "箱",
}

_CONFIDENCE_ZH = {"HIGH": "高", "MID": "中", "LOW": "低"}


def _uom_zh(uom: Uom | str) -> str:
    key = uom.value if isinstance(uom, Uom) else uom
    return _UOM_ZH.get(key, key)


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _display_num(value: Decimal | int | float) -> str:
    """界面展示用量：最多 4 位小数，去掉无意义的尾零（内部仍用 Decimal）。"""
    d = _dec(value).quantize(Decimal("0.0001"))
    if d == d.to_integral_value():
        return str(int(d))
    text = format(d.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _load_item(session: Session, item_code: str) -> Item | None:
    row = session.get(MdItemRow, item_code)
    if row is None:
        return None
    return Item(
        item_code=row.item_code,
        item_name=row.item_name,
        dept=Dept(row.dept),
        group_code=GroupCode(row.group_code),
        unit_sale=Uom(row.unit_sale),
        pcs_per_board=row.pcs_per_board,
        board_per_box=_dec(row.board_per_box),
        loss_rate=_dec(row.loss_rate),
        color=row.color,
        is_semi=row.is_semi,
        computable=row.computable,
    )


def _converts_for(session: Session, item_code: str) -> list[UomConvert]:
    rows = session.scalars(
        select(MdUomConvertRow).where(MdUomConvertRow.item_code == item_code)
    ).all()
    return [
        UomConvert(
            item_code=r.item_code,
            from_uom=Uom(r.from_uom),
            to_uom=Uom(r.to_uom),
            factor=_dec(r.factor),
        )
        for r in rows
    ]


def _route_for(session: Session, item_code: str) -> ItemRoute | None:
    row = session.get(MdItemRouteRow, item_code)
    if row is None:
        return None
    return ItemRoute(
        item_code=row.item_code,
        needs_semi=row.needs_semi,
        semi_item_code=row.semi_item_code,
        semi_board_per_box=_dec(row.semi_board_per_box) if row.semi_board_per_box else None,
        lead_time_days=row.lead_time_days,
        changeover_min=row.changeover_min,
    )


def _sph_for(session: Session, item_code: str, group_code: str) -> Sph | None:
    row = session.get(MdSphRow, {"item_code": item_code, "group_code": group_code})
    if row is None:
        return None
    return Sph(
        item_code=row.item_code,
        group_code=GroupCode(row.group_code),
        sph_value=_dec(row.sph_value),
        sph_basis=SphBasis(row.sph_basis),
        sph_crew=row.sph_crew,
        sph_uom=Uom(row.sph_uom),
        crew_std=row.crew_std,
        confidence=row.confidence,
        effective_date=row.effective_date,
        source=row.source,
    )


def _stock_qty(session: Session, item_code: str) -> Decimal:
    row = session.get(StockRow, item_code)
    if row is None:
        return Decimal(0)
    return _dec(row.qty_available)


def _format_uom_chain(converts: list[UomConvert], item: Item) -> list[str]:
    lines: list[str] = []
    for c in converts:
        lines.append(
            f"1 {_uom_zh(c.from_uom)} = {_display_num(c.factor)} {_uom_zh(c.to_uom)}"
        )
    lines.append(
        f"{item.pcs_per_board} 枚/版 · {_display_num(item.board_per_box)} 版/盒"
    )
    return lines


def _sph_summary(sph: Sph | None) -> dict | None:
    if sph is None:
        return None
    u = _uom_zh(sph.sph_uom)
    conf = _CONFIDENCE_ZH.get(sph.confidence.value, sph.confidence.value)
    if sph.sph_basis.value == "CREW":
        crew = sph.sph_crew or "—"
        basis = f"班组产能（{crew} 人协作，不再乘人数）"
    else:
        basis = f"按单人产能 × 标准 {sph.crew_std} 人"
    label = f"标准产能 {_display_num(sph.sph_value)} {u}/小时 · {basis} · 置信度{conf}"
    return {
        "sph_value": float(sph.sph_value),
        "sph_basis": sph.sph_basis.value,
        "sph_uom": sph.sph_uom.value,
        "crew_std": sph.crew_std,
        "confidence": sph.confidence.value,
        "source": sph.source,
        "label": label,
    }


def _item_node(session: Session, item: Item) -> dict:
    converts = _converts_for(session, item.item_code)
    sph = _sph_for(session, item.item_code, item.group_code.value)
    stock = _stock_qty(session, item.item_code) if item.is_semi else None
    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "is_semi": item.is_semi,
        "group_code": item.group_code.value,
        "group_label": _GROUP_LABEL.get(item.group_code.value, item.group_code.value),
        "color": item.color,
        "loss_rate": float(item.loss_rate),
        "computable": item.computable,
        "uom_chain": _format_uom_chain(converts, item),
        "sph": _sph_summary(sph),
        "stock_board": float(stock) if stock is not None else None,
    }


def _bom_lines_for(session: Session, parent: str) -> list[BomLine]:
    rows = session.scalars(
        select(MdBomLineRow)
        .where(MdBomLineRow.parent_item_code == parent)
        .order_by(MdBomLineRow.line_no)
    ).all()
    return [
        BomLine(
            parent_item_code=r.parent_item_code,
            line_no=r.line_no,
            component_item_code=r.component_item_code,
            component_role=ComponentRole(r.component_role),
            qty_per_parent=_dec(r.qty_per_parent),
            qty_basis_uom=Uom(r.qty_basis_uom),
            scrap_rate=_dec(r.scrap_rate) if r.scrap_rate is not None else None,
            offset_days=r.offset_days,
            lead_time_days=r.lead_time_days,
            kit_critical=r.kit_critical,
        )
        for r in rows
    ]


def bom_design(session: Session, item_code: str) -> dict | None:
    """成品品项的设计态 BOM + 工艺路线（一层半成品）。"""
    item = _load_item(session, item_code)
    if item is None:
        return None
    route = _route_for(session, item_code)
    finished = _item_node(session, item)
    semi_node = None
    edge = None
    pattern = "SINGLE_LAYER"
    components = []
    for line in _bom_lines_for(session, item_code):
        comp_item = _load_item(session, line.component_item_code)
        if comp_item:
            node = _item_node(session, comp_item)
            if line.component_role == ComponentRole.PURCHASED:
                node["stock_board"] = float(_stock_qty(session, line.component_item_code))
            components.append(
                {
                    "line_no": line.line_no,
                    "role": line.component_role.value,
                    "node": node,
                    "qty_per_parent": float(line.qty_per_parent),
                    "qty_basis_uom": line.qty_basis_uom.value,
                    "lead_time_days": line.lead_time_days,
                }
            )
    semi_components = [c for c in components if c["role"] == "SEMI"]
    if len(semi_components) >= 2:
        pattern = "MULTI_BOM"
        semi_node = semi_components[0]["node"]
        semi_labels = "、".join(
            f"{c['node']['item_code']}×{c['qty_per_parent']:g}{c['qty_basis_uom']}/盒"
            for c in semi_components
        )
        edge = {
            "semi_board_per_box": None,
            "lead_time_days": route.lead_time_days if route else 4,
            "dep_type": "FS",
            "changeover_min": route.changeover_min if route else 0,
            "label": (
                f"多半成品 BOM：{semi_labels} · 各行独立提前期 · "
                "倒排生成 WO-…-SEMI-1/2/3…"
            ),
        }
    elif route and route.needs_semi and route.semi_item_code:
        pattern = "TWO_LAYER"
        semi_item = _load_item(session, route.semi_item_code)
        if semi_item:
            semi_node = _item_node(session, semi_item)
        edge = {
            "semi_board_per_box": float(route.semi_board_per_box)
            if route.semi_board_per_box is not None
            else None,
            "lead_time_days": route.lead_time_days,
            "dep_type": "FS",
            "changeover_min": route.changeover_min,
            "label": (
                f"每盒成品需 {_display_num(route.semi_board_per_box)} 版半成品 · "
                f"提前 {route.lead_time_days} 自然日（半成品完工后衔接成品）"
            ),
        }
    elif route:
        edge = {
            "semi_board_per_box": None,
            "lead_time_days": route.lead_time_days,
            "dep_type": "FS",
            "changeover_min": route.changeover_min,
            "label": "无半成品 · 单层成品",
        }
    if components and pattern == "SINGLE_LAYER" and len(components) >= 1:
        pattern = "MULTI_BOM"
        edge = edge or {
            "semi_board_per_box": None,
            "lead_time_days": route.lead_time_days if route else 4,
            "dep_type": "FS",
            "changeover_min": route.changeover_min if route else 0,
            "label": "多行 BOM（子件见下方列表）",
        }
    return {
        "item_code": item_code,
        "pattern": pattern,
        "finished": finished,
        "semi": semi_node,
        "edge": edge,
        "components": components,
    }


def bom_explode(
    session: Session,
    item_code: str,
    qty: Decimal,
    unit: str,
    *,
    today: date | None = None,
) -> dict | None:
    """按订单量展开到「版」与半成品净需求（与 expand_order / gross_semi_board 一致）。"""
    item = _load_item(session, item_code)
    if item is None:
        return None
    if not item.computable:
        return {
            "item_code": item_code,
            "computable": False,
            "message": "缺少换算链，不可自动排产",
        }

    uom = Uom(unit)
    converts = _converts_for(session, item_code)
    route = _route_for(session, item_code)
    sph = _sph_for(session, item_code, item.group_code.value)
    anchor = today or date(2026, 9, 15)

    pseudo = Order(
        order_no="BOM-EXPLODE",
        customer="—",
        item_code=item_code,
        qty_order=qty,
        unit=uom,
        due_date=anchor,
        ready_date=anchor,
        customer_level=3,
        amount=Decimal("0"),
    )
    qty_board = to_board(qty, uom, converts)
    wo = expand_order(pseudo, item, converts, anchor, sph=sph)
    if wo is None:
        return {"item_code": item_code, "computable": False, "message": "无法展开成品工单"}

    uom_name = _uom_zh(uom)
    loss_s = _display_num(item.loss_rate)
    steps = [
        f"订货 {_display_num(qty)} {uom_name} → {_display_num(qty_board)} 版（换算链，未含损耗）",
        f"成品计划版 = 向上取整({_display_num(qty_board)} × (1 + {loss_s})) = {wo.qty_board_plan} 版",
    ]

    semi_block = None
    line_details: list[dict] = []
    bom_lines = _bom_lines_for(session, item_code)
    stock_map = {
        r.item_code: _dec(r.qty_available)
        for r in session.scalars(select(StockRow)).all()
    }
    if bom_lines:
        pool = KitSnapshot(stock_map)
        for line in bom_lines:
            gross = gross_board_for_line(pseudo, line, item)
            from_st, net = pool.consume(
                order_no=pseudo.order_no,
                component_item_code=line.component_item_code,
                gross_board=gross,
                line_no=line.line_no,
            )
            line_details.append(
                {
                    "line_no": line.line_no,
                    "component_item_code": line.component_item_code,
                    "role": line.component_role.value,
                    "gross_board": gross,
                    "from_stock": from_st,
                    "net_board": net if line.component_role == ComponentRole.SEMI else 0,
                    "shortage_board": net if line.component_role == ComponentRole.PURCHASED else 0,
                }
            )
            role_label = "半成品" if line.component_role == ComponentRole.SEMI else "外购"
            steps.append(
                f"{role_label} {line.component_item_code}：毛 {gross} 版，占库 {from_st}，"
                f"{'净工单 ' + str(net) if line.component_role == ComponentRole.SEMI else '缺料 ' + str(net)} 版"
            )
            if line.component_role == ComponentRole.SEMI and semi_block is None:
                semi_block = {
                    "semi_item_code": line.component_item_code,
                    "gross_board": gross,
                    "stock_available": float(from_st + pool.available(line.component_item_code)),
                    "net_board": net,
                    "generates_semi_wo": net > 0,
                }
    elif route and route.needs_semi and route.semi_item_code and route.semi_board_per_box:
        gross = gross_semi_board(wo, route, item)
        available = _stock_qty(session, route.semi_item_code)
        net = max(0, gross - int(available))
        steps.append(
            f"半成品毛需求 = ceil({_display_num(qty)} 盒 × {_display_num(route.semi_board_per_box)} 版/盒 × "
            f"(1 + {loss_s})) = {gross} 版"
        )
        steps.append(
            f"净需求 = max(0, {gross} − 库存 {int(available)}) = {net} 版"
            + (" → 不生成半成品工单" if net == 0 else " → 生成半成品工单")
        )
        semi_block = {
            "semi_item_code": route.semi_item_code,
            "gross_board": gross,
            "stock_available": float(available),
            "net_board": net,
            "generates_semi_wo": net > 0,
        }

    return {
        "item_code": item_code,
        "computable": True,
        "qty_order": float(qty),
        "unit": uom.value,
        "unit_label": uom_name,
        "qty_board_before_loss": float(qty_board),
        "finished_plan_board": wo.qty_board_plan,
        "semi": semi_block,
        "line_details": line_details,
        "steps": steps,
    }


def bom_catalog(session: Session, seed_path: Path) -> dict:
    """演示目录 + 全部成品品项索引。"""
    with seed_path.open(encoding="utf-8") as fh:
        seed = json.load(fh)
    meta = seed.get("meta", {})
    demo = meta.get("demo_catalog", {})

    def _names(codes: list[str]) -> list[dict]:
        out = []
        for code in codes:
            row = session.get(MdItemRow, code)
            if row:
                out.append({"item_code": code, "item_name": row.item_name})
        return out

    catalog = []
    for key, block in demo.items():
        catalog.append(
            {
                "key": key,
                "desc": block.get("desc", ""),
                "items": _names(block.get("items", [])),
                "semi_items": _names(block.get("semi_items", [])),
            }
        )

    finished_rows = session.scalars(
        select(MdItemRow).where(MdItemRow.is_semi.is_(False)).order_by(MdItemRow.item_code)
    ).all()
    index = []
    for row in finished_rows:
        route = session.get(MdItemRouteRow, row.item_code)
        index.append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "group_code": row.group_code,
                "group_label": _GROUP_LABEL.get(row.group_code, row.group_code),
                "needs_semi": bool(route.needs_semi) if route else False,
            }
        )
    return {
        "seed_version": meta.get("seed_version"),
        "today": meta.get("today"),
        "catalog": catalog,
        "items": index,
    }
