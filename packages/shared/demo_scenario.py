"""演示场景台纯函数：交期窗 + 多行 SKU 集合相交。today 只由入参传入。"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from math import ceil


DEMO_TODAY = date(2026, 9, 15)
RNG_SEED_DEFAULT = 20260915

SELLABLE_FINISHED: tuple[str, ...] = (
    "P1",
    "P1M",
    "P1L",
    "P2",
    "P5",
    "P6",
    "P4",
    "P7",
    "P8",
    "P9",
)


@dataclass(frozen=True)
class RouteHint:
    needs_semi: bool
    lead_time_days: int


# 与 seed/seed_data.json routes 对齐；生成器只读这份表，禁止猜提前期。
SELLABLE_ROUTES: dict[str, RouteHint] = {
    "P1": RouteHint(False, 4),
    "P1M": RouteHint(False, 4),
    "P1L": RouteHint(False, 4),
    "P2": RouteHint(True, 4),
    "P5": RouteHint(True, 4),
    "P6": RouteHint(True, 5),
    "P4": RouteHint(False, 4),
    "P7": RouteHint(False, 4),
    "P8": RouteHint(False, 4),
    "P9": RouteHint(True, 4),
}

CORE_SHARE_1: tuple[str, ...] = ("P2",)
CORE_SHARE_4: tuple[str, ...] = ("P1", "P2", "P4", "P9")

CUSTOMERS: tuple[tuple[str, str, str, int], ...] = (
    ("SCEN-C01", "蓝岛烘焙供应链（无锡）", "陈雨桐", 2),
    ("SCEN-C02", "童乐坊创意礼品", "张伟", 3),
    ("SCEN-C03", "甜研西点工坊（杭州）", "周婷", 2),
    ("SCEN-C04", "云顶精选酒店集采", "王芷若", 1),
    ("SCEN-C05", "臻选味来电商", "孙悦", 3),
    ("SCEN-C06", "丰麦连锁烘焙（华东）", "李明轩", 4),
    ("SCEN-C07", "礼记婚庆礼仪（上海）", "刘思涵", 3),
    ("SCEN-C08", "优选乐活精品超市", "韩磊", 3),
    ("SCEN-C09", "绿源食品中央厨房", "林佳", 2),
    ("SCEN-C10", "禧年会展主题陈列", "周婷", 4),
    ("SCEN-C11", "快鲜优选社区团购", "韩磊", 3),
    ("SCEN-C12", "悦享下午茶连锁", "陈雨桐", 2),
)

WORK_CENTERS: tuple[tuple[str, str, str], ...] = (
    ("FINISHED_DEPT", "MANUAL", "一部·手工组"),
    ("FINISHED_DEPT", "MOLD", "一部·模具组"),
    ("FINISHED_DEPT", "POURING", "一部·浇注组"),
    ("SEMI_DEPT", "MANUAL", "二部·手工组"),
    ("SEMI_DEPT", "MOLD", "二部·模具组"),
    ("SEMI_DEPT", "POURING", "二部·浇注组"),
)

LEADERS: dict[tuple[str, str], tuple[str, str]] = {
    ("FINISHED_DEPT", "MANUAL"): ("E2001", "王强"),
    ("FINISHED_DEPT", "MOLD"): ("E2011", "赵模具"),
    ("FINISHED_DEPT", "POURING"): ("E2012", "钱浇注"),
    ("SEMI_DEPT", "MANUAL"): ("E2101", "陈静"),
    ("SEMI_DEPT", "MOLD"): ("E2103", "吴刚"),
    ("SEMI_DEPT", "POURING"): ("E2102", "周杰"),
}

OPERATOR_NAMES: tuple[str, ...] = (
    "李芳",
    "张磊",
    "孙丽",
    "王敏",
    "刘洋",
    "陈晨",
    "杨帆",
    "黄伟",
    "徐静",
    "马超",
    "朱婷",
    "胡斌",
    "郭宁",
    "何洁",
    "高翔",
    "林峰",
    "罗丹",
    "梁伟",
    "宋佳",
    "唐磊",
    "冯雪",
    "邓凯",
    "曹阳",
    "彭丽",
)

LOOP_ACTS: tuple[dict, ...] = (
    {
        "step": 0,
        "title": "清场 · 编制 · 造数",
        "role": "GM",
        "path": "/demo",
        "steps": (
            "初始化订单（清事务、库存归零、锁场景）",
            "初始产线人员（每组默认 5 人，同步日历与出勤）",
            "生成测试订单，确认全部为待排程",
        ),
    },
    {
        "step": 1,
        "title": "销售确认订单与合同",
        "role": "SALES",
        "path": "/orders",
        "steps": (
            "订单中心查看本轮场景单与合同",
            "可选：CTP 抽一单试算（不落库）",
        ),
    },
    {
        "step": 2,
        "title": "生管加入排程并倒排",
        "role": "PMC",
        "path": "/schedule",
        "steps": (
            "待排程全选 → 加入排程中",
            "试排 / 一键倒排，看冲突与过程 Tab",
            "无阻断红则保存发布，订单进生产中",
        ),
    },
    {
        "step": 3,
        "title": "班组长报工",
        "role": "TEAM_LEADER",
        "path": "/modules/production/time-report",
        "steps": ("确认组×日人·时", "部分完工走未完回池"),
    },
    {
        "step": 4,
        "title": "人事看生产成本",
        "role": "HR",
        "path": "/modules/hr/labor-cost",
        "steps": ("计划 vs 实际人·时", "品项人工成本"),
    },
    {
        "step": 5,
        "title": "财务回款",
        "role": "FIN",
        "path": "/crm/customers",
        "steps": ("打开场景客户合同", "按计划登记预收 / 尾款"),
    },
)


class DueMode(str, Enum):
    FOCUS_FENCE = "FOCUS_FENCE"
    FOCUS_MID = "FOCUS_MID"
    FOCUS_FAR = "FOCUS_FAR"
    UNIFORM = "UNIFORM"


class ItemShareMode(str, Enum):
    NONE = "NONE"
    SHARE_10_1 = "SHARE_10_1"
    SHARE_20_4 = "SHARE_20_4"


class ScenarioPlanError(ValueError):
    pass


@dataclass(frozen=True)
class ShareSpec:
    ratio: float
    core: tuple[str, ...]


SHARE_SPECS: dict[ItemShareMode, ShareSpec | None] = {
    ItemShareMode.NONE: None,
    ItemShareMode.SHARE_10_1: ShareSpec(0.10, CORE_SHARE_1),
    ItemShareMode.SHARE_20_4: ShareSpec(0.20, CORE_SHARE_4),
}


def workdays_between(start: date, end: date) -> list[date]:
    out: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.isoweekday() <= 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


def next_workday_on_or_after(d: date) -> date:
    while d.isoweekday() > 5:
        d += timedelta(days=1)
    return d


def min_due_for_skus(skus: list[str] | tuple[str, ...], today: date) -> date:
    """订单交期不得早于 today；含半成品时再保证「成品交期 − 提前期」≥ today。"""
    floor = today
    for code in skus:
        hint = SELLABLE_ROUTES[code]
        if hint.needs_semi:
            floor = max(floor, today + timedelta(days=hint.lead_time_days))
    return next_workday_on_or_after(floor)


def _due_window(mode: DueMode, today: date) -> tuple[date, date]:
    if mode is DueMode.FOCUS_FENCE:
        lo, hi = today + timedelta(days=2), today + timedelta(days=4)
    elif mode is DueMode.FOCUS_MID:
        lo, hi = today + timedelta(days=5), today + timedelta(days=15)
    elif mode is DueMode.FOCUS_FAR:
        lo, hi = today + timedelta(days=16), today + timedelta(days=30)
    else:
        lo, hi = today + timedelta(days=2), today + timedelta(days=30)
    lo = max(lo, today)
    if hi < lo:
        hi = lo
    return lo, hi


def _assign_dues(n: int, mode: DueMode, today: date) -> list[date]:
    lo, hi = _due_window(mode, today)
    days = workdays_between(lo, hi)
    if not days:
        raise ScenarioPlanError(f"交期窗 {lo}–{hi} 没有工作日")
    if mode is DueMode.UNIFORM and n > 1:
        last = len(days) - 1
        picked = [days[round(i * last / (n - 1))] for i in range(n)]
    else:
        picked = [days[i % len(days)] for i in range(n)]
    return [max(d, today) for d in picked]


def _ready_date(due: date, today: date, rng: random.Random) -> date:
    latest = due - timedelta(days=2)
    if latest < today:
        raise ScenarioPlanError(f"交期 {due} 无法满足下单不早于 {today} 且间隔≥2 天")
    span = (latest - today).days
    return today + timedelta(days=rng.randrange(span + 1))


def _due_bucket(due: date, today: date) -> str:
    delta = (due - today).days
    if delta <= 4:
        return "fence"
    if delta <= 15:
        return "mid"
    return "far"


def _dept_tag(dept: str) -> str:
    return "FIN" if dept == "FINISHED_DEPT" else "SEMI"


def _none_sets(n: int, catalog: tuple[str, ...]) -> list[list[str]]:
    need = n * 2
    if need > len(catalog):
        max_n = len(catalog) // 2
        raise ScenarioPlanError(
            f"成品仅 {len(catalog)} 个，无共享且每单 2 行时最多 {max_n} 单。请减少单数，或改选共享模式。"
        )
    return [[catalog[2 * i], catalog[2 * i + 1]] for i in range(n)]


def _share_sets(
    n: int,
    spec: ShareSpec,
    catalog: tuple[str, ...],
) -> tuple[list[list[str]], list[int], list[str], list[str]]:
    core = list(spec.core)
    cluster_size = max(2, ceil(spec.ratio * n))
    cluster_idx = list(range(cluster_size))
    privates = [s for s in catalog if s not in core]
    sets: list[list[str]] = []
    warnings: list[str] = []
    private_used = 0
    for i in range(cluster_size):
        if i < len(privates):
            sets.append([*core, privates[i]])
            private_used += 1
        else:
            sets.append(list(core))
    if private_used < cluster_size:
        warnings.append(f"仅前 {private_used} 单有私有行，其余集合相同")

    used_privates = set(privates[:private_used])
    outside_n = n - cluster_size
    pool = [s for s in catalog if s not in core and s not in used_privates]
    recycle = [s for s in catalog if s not in core]
    outside_reused = False
    for _ in range(outside_n):
        picked: list[str] = []
        for _need in range(2):
            if pool:
                picked.append(pool.pop(0))
            elif recycle:
                picked.append(recycle[_need % len(recycle)])
                outside_reused = True
            else:
                raise ScenarioPlanError("簇外没有可售成品可分配")
        if len(set(picked)) < 2 and recycle:
            alt = next((s for s in recycle if s not in picked), None)
            if alt:
                picked[1] = alt
        sets.append(picked)
    if outside_reused:
        warnings.append("簇外出现附带复用")
    return sets, cluster_idx, core, warnings


def plan_sku_sets(
    order_count: int,
    item_share: ItemShareMode,
    catalog: tuple[str, ...] = SELLABLE_FINISHED,
) -> tuple[list[list[str]], list[int], list[str], list[str]]:
    spec = SHARE_SPECS[item_share]
    if spec is None:
        return _none_sets(order_count, catalog), [], [], []
    return _share_sets(order_count, spec, catalog)


def plan_orders(
    order_count: int,
    due_mode: DueMode | str,
    item_share: ItemShareMode | str,
    today: date = DEMO_TODAY,
    rng_seed: int = RNG_SEED_DEFAULT,
) -> dict:
    if order_count not in (5, 10, 20, 50, 100):
        raise ScenarioPlanError("订单数量仅支持 5/10/20/50/100")
    mode = DueMode(due_mode)
    share = ItemShareMode(item_share)
    rng = random.Random(rng_seed)
    dues = _assign_dues(order_count, mode, today)
    sku_sets, cluster_idx, core, warnings = plan_sku_sets(order_count, share)
    cluster_set = set(cluster_idx)
    histo = {"fence": 0, "mid": 0, "far": 0}
    orders: list[dict] = []
    for i in range(order_count):
        skus = sku_sets[i]
        due = next_workday_on_or_after(max(dues[i], min_due_for_skus(skus, today)))
        histo[_due_bucket(due, today)] += 1
        cust_code, cust_name, sales, level = CUSTOMERS[i % len(CUSTOMERS)]
        if not str(sales).strip():
            raise ScenarioPlanError(f"{cust_code} 缺少销售姓名")
        lines = [
            {
                "item_code": code,
                "qty": 20,
                "unit": "BOX",
                "unit_price": "100",
                "line_amount": "2000",
            }
            for code in skus
        ]
        orders.append(
            {
                "order_no": f"SO-S{i + 1:03d}",
                "customer_code": cust_code,
                "customer_name": cust_name,
                "contract_no": f"HT-SCEN-{cust_code[-2:]}",
                "sales_name": sales,
                "customer_level": level,
                "due_date": due,
                "ready_date": _ready_date(due, today, rng),
                "item_codes": list(skus),
                "lines": lines,
                "amount": str(2000 * len(lines)),
                "in_cluster": i in cluster_set,
                "is_urgent": False,
                "schedule_phase": "PENDING",
                "order_source": "DEMO_SCENARIO",
            }
        )
    intersections: list[dict] = []
    clustered = [o for o in orders if o["in_cluster"]]
    for i, a in enumerate(clustered):
        for b in clustered[i + 1 :]:
            inter = sorted(set(a["item_codes"]) & set(b["item_codes"]))
            intersections.append(
                {
                    "a": a["order_no"],
                    "b": b["order_no"],
                    "intersection": inter,
                }
            )
    return {
        "today": today,
        "order_count": order_count,
        "due_mode": mode.value,
        "item_share": share.value,
        "rng_seed": rng_seed,
        "core_skus": list(core),
        "cluster_order_nos": [o["order_no"] for o in clustered],
        "due_histogram": histo,
        "warnings": warnings,
        "intersections": intersections,
        "orders": orders,
    }


def plan_to_api(plan: dict) -> dict:
    """date → iso，供 HTTP 预览。"""
    out = dict(plan)
    out["today"] = plan["today"].isoformat() if isinstance(plan["today"], date) else plan["today"]
    orders = []
    for o in plan["orders"]:
        row = dict(o)
        row["due_date"] = o["due_date"].isoformat() if isinstance(o["due_date"], date) else o["due_date"]
        row["ready_date"] = o["ready_date"].isoformat() if isinstance(o["ready_date"], date) else o["ready_date"]
        orders.append(row)
    out["orders"] = orders
    return out


def plan_roster(headcount: int = 5) -> dict:
    if headcount < 1 or headcount > 20:
        raise ScenarioPlanError("每组人数须在 1–20")
    groups: list[dict] = []
    name_i = 0
    for dept, group, label in WORK_CENTERS:
        leader_no, leader_name = LEADERS[(dept, group)]
        ops: list[dict] = []
        tag = _dept_tag(dept)
        for seq in range(2, headcount + 1):
            ops.append(
                {
                    "emp_no": f"P-{tag}-{group}-{seq:02d}",
                    "name": OPERATOR_NAMES[name_i % len(OPERATOR_NAMES)],
                }
            )
            name_i += 1
        groups.append(
            {
                "dept": dept,
                "group_code": group,
                "label": label,
                "headcount": headcount,
                "leader": {"emp_no": leader_no, "name": leader_name},
                "operators": ops,
            }
        )
    return {"headcount": headcount, "groups": groups}


def loop_acts_for_api() -> list[dict]:
    return [
        {**a, "steps": list(a["steps"])}
        for a in LOOP_ACTS
    ]
