"""CTP 交期自助（Phase 6）：what-if 不落库。"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.bom_view import bom_explode
from db.order_lifecycle import scheduling_pool_order_nos
from db.repositories import get_order
from db.snapshot import load_schedule_input
from db.tables import MdItemRow, StockRow
from engine.models import ComponentRole, Order, ScheduleResult, Uom, WoType
from engine.schedule import schedule

_EARLIEST_RE = re.compile(r"EARLIEST:(\d{4}-\d{2}-\d{2})")

_ROLE_ZH = {
    ComponentRole.SEMI: "半成品",
    ComponentRole.PURCHASED: "包材",
}


def _item_label(session: Session, item_code: str) -> str:
    row = session.get(MdItemRow, item_code)
    if row and row.item_name:
        return f"{item_code} {row.item_name}"
    return item_code


def _stock_board(session: Session, item_code: str) -> int:
    row = session.get(StockRow, item_code)
    if row is None:
        return 0
    return int(Decimal(str(row.qty_available)))


def _parse_earliest_from_suggest(suggest: str | None) -> date | None:
    if not suggest:
        return None
    m = _EARLIEST_RE.search(suggest)
    if not m:
        return None
    return date.fromisoformat(m.group(1))


def _ctp_finished_wos(result: ScheduleResult, order_no: str = "CTP-TRY") -> list:
    return [
        w
        for w in result.wos
        if w.source_order_no == order_no and w.wo_type == WoType.FINISHED
    ]


def _ctp_earliest_delivery(
    result: ScheduleResult,
    finished_wos: list,
    *,
    plan_end: date | None,
) -> date | None:
    candidates: list[date] = []
    if plan_end:
        candidates.append(plan_end)
    fin_nos = {w.wo_no for w in finished_wos}
    for miss in result.unplaced:
        if miss.wo_no in fin_nos and miss.earliest_finish:
            candidates.append(miss.earliest_finish)
    for c in result.conflicts:
        if c.level.value != "RED":
            continue
        if c.wo_no and c.wo_no not in fin_nos:
            related = any(
                w.wo_no == c.wo_no
                for w in result.wos
                if w.source_order_no == "CTP-TRY"
            )
            if not related:
                continue
        ef = _parse_earliest_from_suggest(c.suggest)
        if ef:
            candidates.append(ef)
    return max(candidates) if candidates else None


def _material_lines(
    session: Session,
    explode: dict | None,
    kit_check,
) -> list[dict]:
    lines: list[dict] = []
    kit_by_line = {}
    if kit_check:
        kit_by_line = {ln.line_no: ln for ln in kit_check.lines}

    if explode and explode.get("line_details"):
        for ld in explode["line_details"]:
            line_no = ld["line_no"]
            code = ld["component_item_code"]
            role = ld["role"]
            kl = kit_by_line.get(line_no)
            gross = int(ld.get("gross_board") or 0)
            from_st = int(ld.get("from_stock") or 0)
            net = int(ld.get("net_board") or 0)
            shortage = int(ld.get("shortage_board") or 0)
            if kl:
                from_st = kl.from_stock
                net = kl.net_wo_board
                shortage = kl.shortage_board
            kind = _ROLE_ZH.get(ComponentRole(role), role)
            if role == ComponentRole.PURCHASED.value:
                if shortage > 0:
                    status, summary = "shortage", f"缺 {shortage} 版，需采购补货"
                elif net == 0 and from_st >= gross:
                    status, summary = "ok", f"现货 {from_st} 版，已齐套"
                else:
                    status, summary = "ok", f"可用 {from_st} 版"
            else:
                if net <= 0:
                    status, summary = "ok", f"现货 {from_st} 版，无需再排半成品"
                else:
                    status, summary = "need_make", f"现货 {from_st} 版，还需排产 {net} 版"
            lines.append(
                {
                    "item_code": code,
                    "name": _item_label(session, code),
                    "kind": kind,
                    "status": status,
                    "summary": summary,
                }
            )
        return lines

    semi = (explode or {}).get("semi")
    if semi:
        code = semi["semi_item_code"]
        gross = int(semi.get("gross_board") or 0)
        avail = int(semi.get("stock_available") or 0)
        net = int(semi.get("net_board") or 0)
        if net <= 0:
            status, summary = "ok", f"现货 {avail} 版，无需再排半成品"
        else:
            status, summary = "need_make", f"需 {gross} 版，现货 {avail} 版，还需排产 {net} 版"
        lines.append(
            {
                "item_code": code,
                "name": _item_label(session, code),
                "kind": "半成品",
                "status": status,
                "summary": summary,
            }
        )
    return lines


def _build_sales_brief(
    session: Session,
    *,
    item_code: str,
    due_date: date,
    explode: dict | None,
    result: ScheduleResult,
    finished_wos: list,
    plan_end: date | None,
    can_meet: bool,
    pool_size: int,
    order_no: str = "CTP-TRY",
) -> dict:
    kit_check = next((k for k in result.kit_checks if k.order_no == order_no), None)
    materials = _material_lines(session, explode, kit_check)
    earliest = _ctp_earliest_delivery(result, finished_wos, plan_end=plan_end)

    plan_board = int((explode or {}).get("finished_plan_board") or 0)
    fg_stock = _stock_board(session, item_code)
    fg_covers = plan_board > 0 and fg_stock >= plan_board
    unit_label = (explode or {}).get("unit_label") or "版"
    qty_order = (explode or {}).get("qty_order")

    finished_stock = {
        "available_board": fg_stock,
        "plan_board": plan_board,
        "covers_order": fg_covers,
        "summary": (
            f"成品库存 {fg_stock} 版，本单约需 {plan_board} 版，{'现货足够' if fg_covers else '现货不足，需排产补足'}"
            if plan_board
            else f"成品库存 {fg_stock} 版"
        ),
    }

    need_make = any(m["status"] == "need_make" for m in materials)
    shortages = [m for m in materials if m["status"] == "shortage"]
    all_materials_ok = not need_make and not shortages

    if can_meet:
        if fg_covers and all_materials_ok:
            headline = f"可以满足 {due_date.isoformat()} 交期（现货可覆盖本单）"
        else:
            headline = f"可以满足 {due_date.isoformat()} 交期"
        status = "ok"
    else:
        ef_txt = earliest.isoformat() if earliest else "—"
        headline = f"无法在 {due_date.isoformat()} 前交齐"
        if earliest and earliest != due_date:
            headline += f"，按当前产能预计最早 {ef_txt} 可交付"
        status = "late"

    reasons: list[str] = []
    if not can_meet:
        for c in result.conflicts:
            if c.level.value != "RED":
                continue
            if c.wo_no and not any(w.wo_no == c.wo_no for w in finished_wos):
                if not any(
                    w.wo_no == c.wo_no
                    for w in result.wos
                    if w.source_order_no == order_no
                ):
                    continue
            msg = (c.message or "").strip()
            if msg and msg not in reasons:
                reasons.append(msg)
        if not reasons:
            reasons.append("当前排程池产能紧张，目标交期排不进去")
    elif need_make:
        reasons.append("包材/半成品齐套，成品线已纳入试算排程")
    elif fg_covers:
        reasons.append("成品现货可发，仍建议与计划员确认出库与物流")
    else:
        reasons.append("物料齐套，成品按计划倒排可覆盖目标交期")

    committed = earliest if (not can_meet and earliest) else (plan_end or due_date if can_meet else earliest)

    return {
        "headline": headline,
        "status": status,
        "can_meet_due_date": can_meet,
        "target_due": due_date.isoformat(),
        "plan_finish": plan_end.isoformat() if plan_end else None,
        "earliest_delivery": committed.isoformat() if committed else None,
        "finished_stock": finished_stock,
        "materials": materials,
        "all_materials_in_stock": all_materials_ok and not fg_covers,
        "needs_production": need_make or not fg_covers,
        "reasons": reasons[:5],
        "context": f"试算未落库；已叠加当前排程池 {pool_size} 张在制订单，结果供销售沟通参考",
        "order_qty_label": f"{qty_order}{unit_label}" if qty_order is not None else None,
        "product_label": _item_label(session, item_code),
    }


def _score_line(
    session: Session,
    *,
    result: ScheduleResult,
    order_no: str,
    item_code: str,
    qty_order: Decimal,
    unit: str,
    due_date: date,
    today: date,
    pool_size: int,
) -> dict:
    finished = _ctp_finished_wos(result, order_no)
    plan_end = max((w.plan_end for w in finished if w.plan_end), default=None)
    reds = [
        c
        for c in result.conflicts
        if c.level.value == "RED"
        and c.wo_no
        and any(w.wo_no == c.wo_no for w in finished)
    ]
    earliest = _ctp_earliest_delivery(result, finished, plan_end=plan_end)
    can_meet = (
        len(reds) == 0
        and plan_end is not None
        and plan_end <= due_date
        and (earliest is None or earliest <= due_date)
    )
    explode = bom_explode(session, item_code, qty_order, unit, today=today)
    sales = _build_sales_brief(
        session,
        item_code=item_code,
        due_date=due_date,
        explode=explode,
        result=result,
        finished_wos=finished,
        plan_end=plan_end,
        can_meet=can_meet,
        pool_size=pool_size,
        order_no=order_no,
    )
    return {
        "item_code": item_code,
        "product_label": _item_label(session, item_code),
        "qty": int(qty_order),
        "unit": unit,
        "feasible": can_meet,
        "plan_end": plan_end.isoformat() if plan_end else None,
        "earliest_delivery": sales.get("earliest_delivery"),
        "red_conflicts": [{"code": c.code, "message": c.message} for c in reds[:5]],
        "sales": sales,
    }


def ctp_order_feasibility(
    session: Session,
    *,
    lines: list[dict],
    due_date: date,
    today: date,
    customer: str = "CTP 试算",
) -> dict:
    """多行明细 + 整单交期一次注入试算，共享产能。不落库。"""
    if not lines:
        raise ValueError("至少一行品项才能预检")
    pool = scheduling_pool_order_nos(session)
    inp = load_schedule_input(
        session,
        today=today,
        order_nos=list(pool) or ["__ctp_empty_pool__"],
    )
    ctp_orders = []
    parsed: list[tuple[str, str, Decimal, str]] = []
    for i, ln in enumerate(lines, start=1):
        item_code = str(ln["item_code"])
        qty = Decimal(str(ln.get("qty") if ln.get("qty") is not None else ln.get("qty_order")))
        unit = str(ln.get("unit") or "BOX")
        if qty <= 0 or qty != qty.to_integral_value():
            raise ValueError(f"{item_code} 数量必须为正整数")
        qty = qty.to_integral_value()
        ono = f"CTP-TRY#L{i}"
        parsed.append((ono, item_code, qty, unit))
        ctp_orders.append(
            Order(
                order_no=ono,
                customer=customer,
                sales_name="CTP",
                item_code=item_code,
                qty_order=qty,
                unit=Uom(unit),
                due_date=due_date,
                ready_date=today,
                customer_level=3,
                amount=Decimal("0"),
                is_urgent=False,
                schedule_phase="IN_SCHEDULING",
            )
        )
    inp = inp.model_copy(update={"orders": [*inp.orders, *ctp_orders]})
    result = schedule(inp)

    line_rows = [
        _score_line(
            session,
            result=result,
            order_no=ono,
            item_code=item_code,
            qty_order=qty,
            unit=unit,
            due_date=due_date,
            today=today,
            pool_size=len(pool),
        )
        for ono, item_code, qty, unit in parsed
    ]
    feasible = all(row["feasible"] for row in line_rows)
    plan_dates = [date.fromisoformat(row["plan_end"]) for row in line_rows if row["plan_end"]]
    early_dates = [
        date.fromisoformat(row["earliest_delivery"]) for row in line_rows if row["earliest_delivery"]
    ]
    plan_end = max(plan_dates) if plan_dates else None
    earliest = max(early_dates) if early_dates else plan_end
    if feasible:
        headline = f"整单可以满足 {due_date.isoformat()} 交期（{len(line_rows)} 行同池试算）"
        status = "ok"
    else:
        ef = earliest.isoformat() if earliest else "—"
        headline = f"整单无法在 {due_date.isoformat()} 前交齐"
        if earliest:
            headline += f"，建议不早于 {ef}"
        status = "late"
    return {
        "feasible": feasible,
        "requested_due": due_date.isoformat(),
        "plan_end": plan_end.isoformat() if plan_end else None,
        "earliest_delivery": earliest.isoformat() if earliest else None,
        "red_conflicts": [c for row in line_rows for c in row["red_conflicts"]][:8],
        "pool_size": len(pool),
        "note": "整单多行同池一次倒排；试算单 CTP-TRY 不落库；含当前排程池订单",
        "lines": line_rows,
        "sales": {
            "headline": headline,
            "status": status,
            "can_meet_due_date": feasible,
            "target_due": due_date.isoformat(),
            "plan_finish": plan_end.isoformat() if plan_end else None,
            "earliest_delivery": earliest.isoformat() if earliest else None,
        },
    }


def ctp_feasibility(
    session: Session,
    *,
    item_code: str,
    qty_order: Decimal,
    unit: str,
    due_date: date,
    today: date,
    customer: str = "CTP 试算",
) -> dict:
    data = ctp_order_feasibility(
        session,
        lines=[{"item_code": item_code, "qty": qty_order, "unit": unit}],
        due_date=due_date,
        today=today,
        customer=customer,
    )
    line = data["lines"][0]
    return {
        "feasible": data["feasible"],
        "requested_due": data["requested_due"],
        "plan_end": line["plan_end"],
        "earliest_delivery": line["earliest_delivery"],
        "red_conflicts": line["red_conflicts"],
        "pool_size": data["pool_size"],
        "note": data["note"],
        "sales": line["sales"],
        "lines": data["lines"],
    }


def ctp_from_template_order(
    session: Session,
    *,
    template_order_no: str,
    new_due: date,
    today: date,
) -> dict:
    """基于已有订单品项/数量改交期试算。"""
    row = get_order(session, template_order_no)
    return ctp_feasibility(
        session,
        item_code=row.item_code,
        qty_order=row.qty_order,
        unit=row.unit.value,
        due_date=new_due,
        today=today,
        customer=row.customer,
    )
