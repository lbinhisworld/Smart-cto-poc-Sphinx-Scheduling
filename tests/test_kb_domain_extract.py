"""行业提取 D0–D5：主林 / 运行结果林 / 别名 / 双端关联。"""

from __future__ import annotations

from pathlib import Path

import yaml

from sealed_kb.ask import ask, match_named_card
from sealed_kb.store import domain_tree, format_tree, load, runtime_tree


def _ids(nodes: list[dict]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        found.add(node["id"])
        found |= _ids(node.get("children") or [])
    return found


def test_sph_is_independent_and_relates_both_ends() -> None:
    kb = load()
    sph = kb.facts["D.sph"]
    assert sph.belongs_to is None
    assert "D.item" in sph.relates_to
    assert "D.group" in sph.relates_to
    assert "D.sph" not in kb.children_of("D.item")
    assert "D.sph.value" in kb.children_of("D.sph")
    assert "D.sph.basis" in kb.children_of("D.sph")


def test_wo_task_has_two_hour_slots() -> None:
    kb = load()
    wall = kb.facts["D.wo_task.hours_wall"]
    man = kb.facts["D.wo_task.hours_man"]
    assert wall.belongs_to == "D.wo_task"
    assert man.belongs_to == "D.wo_task"
    assert wall.layer == "槽"
    assert "墙钟" in wall.aliases or "hours_wall" in wall.aliases


def test_main_tree_hides_runtime_and_dept() -> None:
    text = format_tree(load())
    assert "销售订单 (D.order)" in text
    assert "版 (D.board)" in text
    assert "品项在组上的标准小时产能 (D.sph)" in text
    assert "五幕" not in text
    assert "一次倒排" not in text
    assert "一部成品与二部半成品" not in text
    ids = _ids(domain_tree())
    assert "D.order" in ids
    assert "D.sph" in ids
    assert "D.wo_task.hours_wall" in ids
    assert "D.trace" not in ids
    assert "D.schedule_io" not in ids
    assert "D.dept" not in ids


def test_runtime_tree_has_trace_and_kit() -> None:
    ids = _ids(runtime_tree())
    assert "D.schedule_io" in ids
    assert "D.trace" in ids
    assert "D.kit" in ids
    assert "D.feasibility" in ids
    assert "D.order" not in ids


def test_wo_classifies_finished_and_semi() -> None:
    kb = load()
    assert kb.facts["D.wo.finished"].is_a == ["D.wo"]
    assert kb.facts["D.wo.semi"].is_a == ["D.wo"]
    assert kb.facts["D.wo.finished"].belongs_to is None
    assert "D.order" in kb.facts["D.wo"].relates_to
    assert "D.item" in kb.facts["D.wo"].relates_to
    assert "D.group" in kb.facts["D.wo_task"].relates_to


def test_order_qty_and_unit_slots() -> None:
    kb = load()
    assert kb.facts["D.order.qty"].belongs_to == "D.order"
    assert kb.facts["D.order.unit"].belongs_to == "D.order"
    assert "D.order.qty" in kb.children_of("D.order")
    assert "D.feasibility" not in kb.children_of("D.order")
    assert "D.item" in kb.facts["D.order"].relates_to


def test_inventory_lists_exist() -> None:
    path = Path(__file__).resolve().parents[1] / "kb" / "domain" / "inventory.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    kb = load()
    for fid in data["主林"]:
        assert fid in kb.facts, fid
        assert kb.facts[fid].layer in {"对象", "槽"}
    for fid in data["运行结果林"]:
        assert fid in kb.facts, fid


def test_ask_sph_alias_hits_sealed_card() -> None:
    result = ask("什么是 SPH")
    assert result.verdict == "成立"
    assert result.slots == ["D.sph"]
    assert "四元组" in result.text


def test_ask_bom_lands_on_domain_card() -> None:
    hit = match_named_card("什么是 BOM")
    assert hit is not None
    assert hit.id == "D.bom"
    result = ask("什么是 BOM")
    assert result.slots == ["D.bom"]
    assert result.verdict == "缺前提"


def test_ask_goods_spec_lands_on_item() -> None:
    hit = match_named_card("货物规格是什么")
    assert hit is not None
    assert hit.id == "D.item"


def test_ask_pmc_lands_on_plan_capability() -> None:
    hit = match_named_card("PMC 是什么")
    assert hit is not None
    assert hit.id == "F.l2.cap_plan"
    result = ask("PMC 是什么")
    assert result.slots == ["F.l2.cap_plan"]


def test_ask_wall_clock_lands_on_hour_slot() -> None:
    hit = match_named_card("什么是墙钟")
    assert hit is not None
    assert hit.id == "D.wo_task.hours_wall"
    result = ask("什么是墙钟")
    assert result.slots == ["D.wo_task.hours_wall"]
    assert result.verdict == "缺前提"
