"""计划侧纯计算：领料按日分摊、未排口径。不读库、不写交期。"""

from __future__ import annotations

EXPORT_NOT_PLACED = "已下单未排"
EXPORT_WIP = "在制 / 在途未排"
EXPORT_PARTIAL = "只排了一部分"

# 2026-09-23 客户《模具组》生产排程。一张表，列名与列序不改。生产日期、组长在表头，不另做列。
DISPATCH_HEADERS = [
    "生产人员",
    "班别",
    "型号",
    "品名",
    "枚/版",
    "单位",
    "订单需求量",
    "单据编号",
    "购货单位",
    "巧克力颜色",
    "气泡垫",
    "真空袋/内衬",
    "回料袋颜色",
    "单位",
    "SPH",
    "人力/人",
    "计划盒数",
    "实际生产",
    "生产工时",
    "累计工时",
    "备注",
]


def split_gross(total: int, day_qtys: list[int], plan_qty: int) -> list[int]:
    """按各日任务版数占计划版数的比例分摊，前几天向下取整，最后一天吃掉尾差。

    各日数量之和等于 total。
    """
    if total < 0:
        raise ValueError("毛需求不能为负")
    if not day_qtys:
        return []
    if len(day_qtys) == 1:
        return [total]
    base = plan_qty if plan_qty > 0 else sum(day_qtys)
    if base <= 0:
        out = [0] * (len(day_qtys) - 1)
        return out + [total]
    used = 0
    out: list[int] = []
    for i, qty in enumerate(day_qtys):
        if i == len(day_qtys) - 1:
            out.append(total - used)
        else:
            part = (total * qty) // base
            part = min(part, total - used)
            out.append(part)
            used += part
    return out


def classify_order(
    *,
    phase: str,
    has_tasks: bool,
    has_unplaced: bool,
    has_completion: bool,
    has_pending_roll: bool,
) -> str:
    """返回 PLACED / NOT_PLACED / WIP_UNPLANNED / PARTIAL / POOL_OPEN。"""
    if has_tasks and not has_unplaced and not has_pending_roll:
        return "PLACED"
    if has_tasks and (has_unplaced or has_pending_roll):
        if phase == "IN_SCHEDULING":
            return "POOL_OPEN"
        return "PARTIAL"
    if phase == "IN_SCHEDULING":
        return "POOL_OPEN"
    if has_completion or phase == "IN_PRODUCTION":
        return "WIP_UNPLANNED"
    return "NOT_PLACED"


def export_label(bucket: str, *, has_tasks: bool) -> str | None:
    """对外三类。已排产不进未排汇总。池内未跑完按有没有任务并入。"""
    if bucket == "PLACED":
        return None
    if bucket == "WIP_UNPLANNED":
        return EXPORT_WIP
    if bucket == "PARTIAL":
        return EXPORT_PARTIAL
    if bucket == "POOL_OPEN":
        return EXPORT_PARTIAL if has_tasks else EXPORT_NOT_PLACED
    return EXPORT_NOT_PLACED


def issue_progress(*, gross: int, issued: int | None, today_issued: int | None) -> dict:
    """已领 / 待领 / 本次领。没有领料或报工记录时三列都空，不扣库存。"""
    if issued is None and today_issued is None:
        return {"issued": None, "pending": None, "this_time": None}
    issued_qty = 0 if issued is None else issued
    return {
        "issued": issued_qty,
        "pending": max(0, gross - issued_qty),
        "this_time": today_issued,
    }


def counts_as_pending_load(bucket: str) -> bool:
    """待排毛需求只含从未进当前计划的单，不含池内未跑完。"""
    return bucket == "NOT_PLACED"
