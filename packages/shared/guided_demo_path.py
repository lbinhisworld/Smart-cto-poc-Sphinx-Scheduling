"""演示线路径注册表（P0：17 步，终点 order_cost）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SeedKind = Literal["data", "script", "placeholder"]

PATH_TEMPLATE_FULL = "full_chain_17"
DEMO_ANCHOR_TODAY = "2026-09-15"
STEP_COUNT = 17


@dataclass(frozen=True)
class GuidedStep:
    seq: int
    step_id: str
    title: str
    list_path: str
    menu_key: str
    requires: tuple[str, ...]
    seed_kind: SeedKind
    presenter_note: str = ""


GUIDED_STEPS: tuple[GuidedStep, ...] = (
    GuidedStep(1, "roster", "人员列表", "/modules/hr/roster", "hr_roster", (), "data"),
    GuidedStep(2, "product", "产品列表", "/bom", "bom", ("roster",), "data"),
    GuidedStep(3, "customer", "客户列表", "/crm/customers", "crm_customers", ("product",), "data"),
    GuidedStep(4, "visit_stranger", "陌生拜访", "/crm/checkin", "crm_checkin", ("customer",), "data"),
    GuidedStep(
        5,
        "opportunity",
        "产生商机",
        "/crm/opportunities-list",
        "crm_opps_list",
        ("visit_stranger",),
        "data",
    ),
    GuidedStep(6, "follow_up", "商机持续跟进", "/crm/follows", "crm_follows", ("opportunity",), "data"),
    GuidedStep(7, "sample", "打样（第 1 轮）", "/crm/samples", "crm_samples", ("follow_up",), "data"),
    GuidedStep(8, "quote", "报价（第 2 轮）", "/orders/quotes", "quotes", ("sample",), "data"),
    GuidedStep(
        9,
        "contract_payment",
        "签订合同与回款阶段",
        "/crm/payments",
        "crm_payments",
        ("quote",),
        "data",
    ),
    GuidedStep(10, "to_order", "转订单", "/orders", "orders", ("contract_payment",), "data"),
    GuidedStep(11, "schedule", "排产", "/schedule", "schedule", ("to_order",), "script"),
    GuidedStep(
        12,
        "dispatch",
        "出派工单",
        "/schedule",
        "schedule",
        ("schedule",),
        "script",
        presenter_note="已发布计划后导出《组》生产排程",
    ),
    GuidedStep(
        13,
        "labor_report",
        "报工",
        "/modules/production/time-report",
        "labor_time_report",
        ("dispatch",),
        "script",
    ),
    GuidedStep(14, "reschedule", "二次排产", "/schedule", "schedule", ("labor_report",), "script"),
    GuidedStep(
        15,
        "qc",
        "品质检查",
        "/qc/product-tests",
        "qc_product_tests",
        ("reschedule",),
        "data",
    ),
    GuidedStep(16, "inbound", "入库", "/modules/production/stats/dept1", "dept1_stats", ("qc",), "data"),
    GuidedStep(
        17,
        "order_cost",
        "订单生产成本核定",
        "/modules/hr/labor-cost",
        "hr_labor_cost",
        ("inbound",),
        "data",
        presenter_note="终局：计划 vs 实际人工；算薪 Excel 为将来输入，本期不接",
    ),
)

_STEP_BY_ID: dict[str, GuidedStep] = {s.step_id: s for s in GUIDED_STEPS}


def step_by_id(step_id: str) -> GuidedStep | None:
    return _STEP_BY_ID.get(step_id)


def next_step_id(step_id: str) -> str | None:
    for i, s in enumerate(GUIDED_STEPS):
        if s.step_id == step_id and i + 1 < len(GUIDED_STEPS):
            return GUIDED_STEPS[i + 1].step_id
    return None


def next_step(step_id: str) -> GuidedStep | None:
    nxt = next_step_id(step_id)
    return step_by_id(nxt) if nxt else None


def resolve_step_for_path(pathname: str, current_step_id: str | None) -> GuidedStep | None:
    candidates = [s for s in GUIDED_STEPS if s.list_path == pathname]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if current_step_id:
        for s in candidates:
            if s.step_id == current_step_id:
                return s
    return candidates[0]


def steps_for_api() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in GUIDED_STEPS:
        nxt = next_step(s.step_id)
        out.append(
            {
                "seq": s.seq,
                "step_id": s.step_id,
                "title": s.title,
                "list_path": s.list_path,
                "menu_key": s.menu_key,
                "requires": list(s.requires),
                "seed_kind": s.seed_kind,
                "presenter_note": s.presenter_note,
                "next_step_id": nxt.step_id if nxt else None,
                "next_title": nxt.title if nxt else None,
            }
        )
    return out


def all_list_paths() -> frozenset[str]:
    return frozenset(s.list_path for s in GUIDED_STEPS)
