"""同组同日同品项共线识别（不并 WO）。today 不使用 datetime.now()。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from engine.models import (
    ColineGroup,
    ColineSummary,
    Conflict,
    ConflictLv,
    Dept,
    GroupCode,
    LotSummary,
    ScheduleResult,
    TraceAct,
    TraceEvent,
    Wo,
    WoType,
)
from engine.trace import append_event

GROUP_ZH = {
    "MANUAL": "手工组",
    "MOLD": "模具组",
    "POURING": "浇注组",
}


def header_order_no(order_no: str) -> str:
    return order_no.split("#L")[0]


def _md(d: date) -> str:
    return f"{d.month}/{d.day}"


def detect_coline(result: ScheduleResult) -> tuple[list[ColineGroup], ColineSummary]:
    wo_map = {w.wo_no: w for w in result.wos}
    buckets: dict[tuple, list] = defaultdict(list)
    for t in result.tasks:
        wo = wo_map.get(t.wo_no)
        if wo is None:
            continue
        key = (t.dept, t.group_code, t.task_date, wo.item_code, wo.wo_type)
        buckets[key].append((t, wo))

    groups: list[ColineGroup] = []
    for (dept, group, day, item, wtype), rows in sorted(
        buckets.items(),
        key=lambda kv: (kv[0][2], kv[0][3], kv[0][1].value),
    ):
        orders = sorted({header_order_no(wo.source_order_no) for _, wo in rows})
        if len(orders) < 2:
            continue
        qty = sum(t.qty_board for t, _ in rows)
        groups.append(
            ColineGroup(
                dept=dept,
                group_code=group,
                task_date=day,
                item_code=item,
                wo_type=wtype,
                order_nos=orders,
                qty_board=qty,
                wo_nos=sorted({wo.wo_no for _, wo in rows}),
            )
        )

    all_orders = sorted({o for g in groups for o in g.order_nos})
    all_skus = sorted({g.item_code for g in groups})
    summary = ColineSummary(
        point_count=len(groups),
        qty_board_total=sum(g.qty_board for g in groups),
        order_count=len(all_orders),
        sku_count=len(all_skus),
    )
    return groups, summary


def coline_decision_message(g: ColineGroup) -> str:
    label = GROUP_ZH.get(g.group_code.value, g.group_code.value)
    day = _md(g.task_date)
    bits = "、".join(f"{o}" for o in g.order_nos)
    return (
        f"{label} {day} 同格出现 {g.item_code}：{bits}。"
        f"并线决策：同组同日同品项，按共线展示（不并 WO、不改交期），换线一次。"
        f"本点并线 {len(g.order_nos)} 单 · {g.qty_board} 版"
    )


def coline_summary_message(s: ColineSummary) -> str:
    if s.point_count <= 0:
        return "本轮没有同组同日同品项的并线点。"
    return (
        f"本轮在 {s.point_count} 个点上实现并线，合计 {s.qty_board_total} 版"
        f"（涉及 {s.order_count} 张订单、{s.sku_count} 个品项）。"
    )


def coline_conflicts(groups: list[ColineGroup]) -> list[Conflict]:
    out: list[Conflict] = []
    for g in groups:
        out.append(
            Conflict(
                code="E7",
                level=ConflictLv.BLUE,
                wo_no=g.wo_nos[0] if g.wo_nos else None,
                message=(
                    f"{g.item_code} 共线 · {GROUP_ZH.get(g.group_code.value, g.group_code.value)} "
                    f"{_md(g.task_date)} · {' / '.join(g.order_nos)} · {g.qty_board} 版"
                ),
                suggest="REVIEW_COLINE",
                dept=g.dept.value,
                group_code=g.group_code.value,
                cell_date=g.task_date,
            )
        )
    return out


def _join_cn(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}和{parts[1]}"
    return "、".join(parts[:-1]) + f"和{parts[-1]}"


def _order_list_plain(orders: list[str], *, limit: int = 4) -> str:
    names = sorted(orders)
    if len(names) <= limit:
        return _join_cn(names)
    head = _join_cn(names[:limit])
    return f"{head}等共 {len(names)} 张"


def sku_share_message(skus: list[str], orders: list[str]) -> str:
    sku_s = _join_cn(sorted(skus))
    n = len(orders)
    who = _order_list_plain(orders)
    if len(skus) >= 2:
        return (
            f"有 {n} 张订单要做同一组货：{sku_s}。"
            f"分别是 {who}。"
            f"后面排程会尽量让相同品项落在同一组、同一天，少换一次线。"
        )
    return (
        f"还有 {n} 张订单都要做 {sku_s}（{who}）。"
        f"排到同一天就可以共线。"
    )


def emit_sku_intersect_events(events: list[TraceEvent], wos: list[Wo]) -> None:
    by_header: dict[str, set[str]] = defaultdict(set)
    for wo in wos:
        if wo.wo_type != WoType.FINISHED:
            continue
        by_header[header_order_no(wo.source_order_no)].add(wo.item_code)
    for header, items in sorted(by_header.items()):
        if len(items) < 2:
            continue
        append_event(
            events,
            act=TraceAct.EXPAND,
            kind="expand_lines",
            message=f"{header} 这张单要做：{_join_cn(sorted(items))}。",
            order_no=header,
        )
    item_orders: dict[str, set[str]] = defaultdict(set)
    for header, items in by_header.items():
        for it in items:
            item_orders[it].add(header)
    shared = {it: ords for it, ords in item_orders.items() if len(ords) >= 2}
    if not shared:
        return
    by_cluster: dict[frozenset[str], list[str]] = defaultdict(list)
    for it, ords in shared.items():
        by_cluster[frozenset(ords)].append(it)
    for ords, skus in sorted(by_cluster.items(), key=lambda kv: (-len(kv[1]), sorted(kv[0]))):
        append_event(
            events,
            act=TraceAct.EXPAND,
            kind="sku_intersect",
            message=sku_share_message(skus, list(ords)),
        )


def append_coline_trace(
    events: list[TraceEvent],
    groups: list[ColineGroup],
    summary: ColineSummary,
) -> None:
    for g in groups:
        append_event(
            events,
            act=TraceAct.CHECK,
            kind="coline_decision",
            message=coline_decision_message(g),
            item_code=g.item_code,
            dept=g.dept.value,
            group_code=g.group_code.value,
            task_date=g.task_date,
            qty_board=g.qty_board,
        )
    append_event(
        events,
        act=TraceAct.CHECK,
        kind="coline_summary",
        message=coline_summary_message(summary),
        qty_board=summary.qty_board_total,
    )


def empty_lot_summary() -> LotSummary:
    return LotSummary()
