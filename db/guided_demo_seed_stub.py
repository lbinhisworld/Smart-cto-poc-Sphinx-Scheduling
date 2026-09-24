"""P0：演示线 stub seed（谱系 + 拟真 refs，不落业务表）。"""

from __future__ import annotations

from db.guided_demo_realism import assert_realistic_bundle, load_lexicon
from shared.guided_demo_path import GuidedStep, step_by_id


def _run_short(run_id: str) -> str:
    return run_id.replace("-", "")[:8].upper()


def _entity_id(run_id: str, kind: str, story_index: int) -> str:
    short = _run_short(run_id)
    return f"GD-{short}-{kind}{story_index:02d}"


def stub_refs_for_step(run_id: str, step: GuidedStep) -> tuple[list[dict], str]:
    lex = load_lexicon()
    stories = lex.get("story_bundles") or []
    if len(stories) < 5:
        raise ValueError("词库 story_bundles 不足 5 条")

    refs: list[dict] = []
    summaries: list[str] = []

    for story in stories[:5]:
        idx = int(story["story_index"])
        sid = _entity_id(run_id, _kind_prefix(step.step_id), idx)
        display = _display_for_step(step.step_id, story)
        refs.append(
            {
                "entity_type": step.step_id,
                "entity_id": sid,
                "display": display,
                "story_index": idx,
            }
        )
        summaries.append(f"{display}")

    summary = f"「{step.title}」拟真演示批次 · " + "；".join(summaries[:3])
    if len(summaries) > 3:
        summary += f" 等 {len(summaries)} 条故事线"
    assert_realistic_bundle(refs)
    return refs, summary


def _kind_prefix(step_id: str) -> str:
    return {
        "roster": "E",
        "product": "P",
        "customer": "C",
        "visit_stranger": "V",
        "opportunity": "O",
        "follow_up": "F",
        "sample": "S",
        "quote": "Q",
        "contract_payment": "H",
        "to_order": "SO",
        "schedule": "PL",
        "dispatch": "DP",
        "labor_report": "LB",
        "reschedule": "RS",
        "qc": "QC",
        "inbound": "IN",
        "order_cost": "CS",
    }.get(step_id, "X")


def _display_for_step(step_id: str, story: dict) -> str:
    if step_id == "roster":
        ops = story.get("owner_sales") or "陈雨桐"
        return f"{ops}（销售）"
    if step_id == "product":
        return str(story.get("item_name") or story.get("item_code"))
    if step_id == "customer":
        return str(story.get("customer_name"))
    if step_id == "visit_stranger":
        return f"{story.get('customer_name')} · {story.get('visit_summary')}"
    if step_id == "opportunity":
        return str(story.get("opportunity_title"))
    if step_id == "follow_up":
        return f"{story.get('opportunity_title')} · 跟进"
    if step_id == "sample":
        return f"{story.get('item_name')} · 打样第 1 轮"
    if step_id == "quote":
        return f"{story.get('item_name')} · 报价第 2 轮"
    if step_id == "contract_payment":
        return str(story.get("contract_title"))
    if step_id == "to_order":
        return f"{story.get('customer_name')} · 转销售订单"
    if step_id in ("schedule", "dispatch", "reschedule"):
        return f"{story.get('item_name')} · {step_id}"
    if step_id == "labor_report":
        return f"{story.get('item_name')} · 组×日报工"
    if step_id == "qc":
        return f"{story.get('item_name')} · 产品检测"
    if step_id == "inbound":
        return f"{story.get('item_name')} · 生产入库"
    if step_id == "order_cost":
        return f"{story.get('customer_name')} · 订单生产成本"
    return str(story.get("customer_name"))


def build_stub_seed(run_id: str, step_id: str) -> tuple[list[dict], str, dict]:
    step = step_by_id(step_id)
    if step is None:
        raise ValueError(f"未知环节 {step_id}")
    refs, summary = stub_refs_for_step(run_id, step)
    snapshot = {"mode": "stub", "step_id": step_id, "p0": True}
    return refs, summary, snapshot
