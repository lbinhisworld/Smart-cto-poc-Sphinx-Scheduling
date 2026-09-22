from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_SKIP_NAMES = {
    "schema.yaml",
    "coverage.yaml",
    "inventory.yaml",
    "pending_batches.yaml",
    "nods.yaml",
    "probe_journal.yaml",
}
_MAIN_LAYERS = frozenset({"对象", "槽"})
_HIDDEN_MAIN_ROOTS = frozenset({"D.dept", "D.wo.finished", "D.wo.semi"})


@dataclass
class Fact:
    id: str
    name: str = ""
    pack: str = ""
    layer: str = ""
    status: str = "已封印"
    claim: str = ""
    true_when: list[str] = field(default_factory=list)
    false_when: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)
    binds: list[str] = field(default_factory=list)
    belongs_to: str | None = None
    relates_to: list[str] = field(default_factory=list)
    is_a: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    say: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Argument:
    id: str
    premises: list[str]
    supports: str
    defeats: list[str] = field(default_factory=list)


@dataclass
class KnowledgeBase:
    facts: dict[str, Fact] = field(default_factory=dict)
    arguments: list[Argument] = field(default_factory=list)
    binds: list[tuple[str, str]] = field(default_factory=list)
    must_not_writes: list[str] = field(default_factory=list)

    def arguments_for(self, claim_id: str) -> list[Argument]:
        return [a for a in self.arguments if a.supports == claim_id]

    def children_of(self, fact_id: str) -> list[str]:
        fact = self.facts.get(fact_id)
        return list(fact.children) if fact else []

    def declared_under(self, fact_id: str) -> list[str]:
        fact = self.facts.get(fact_id)
        if fact is None:
            return []
        return _as_list(fact.raw.get("其下"))

    def streams_for_claim(self, claim_id: str) -> list[str]:
        return sorted(
            fact.id
            for fact in self.facts.values()
            if fact.layer == "价值流" and claim_id in fact.supports
        )

    def capabilities_for_claim(self, claim_id: str) -> list[str]:
        return sorted(
            fact.id
            for fact in self.facts.values()
            if fact.layer == "权责" and claim_id in fact.supports
        )

    def unattached_capabilities(self) -> list[str]:
        claims = {fact.id for fact in self.facts.values() if fact.layer == "主张"}
        return sorted(
            fact.id
            for fact in self.facts.values()
            if fact.layer == "权责" and not any(claim_id in claims for claim_id in fact.supports)
        )

    def owners_of(self, fact_id: str) -> list[str]:
        fact = self.facts.get(fact_id)
        if fact is None or fact.layer not in {"环节", "节点"}:
            return []
        found: list[str] = []
        for ref in _as_list(fact.raw.get("谁有权")):
            owner = self.facts.get(ref)
            if owner is not None and owner.layer == "权责" and owner.id not in found:
                found.append(owner.id)
        return found

    def constitution_roots(self) -> list[Fact]:
        return sorted(
            (
                fact
                for fact in self.facts.values()
                if fact.pack == "行业"
                and not fact.belongs_to
                and fact.layer in _MAIN_LAYERS
                and fact.id not in _HIDDEN_MAIN_ROOTS
            ),
            key=lambda f: f.id,
        )

    def runtime_roots(self) -> list[Fact]:
        return sorted(
            (
                fact
                for fact in self.facts.values()
                if fact.pack == "行业" and not fact.belongs_to and fact.layer == "运行结果"
            ),
            key=lambda f: f.id,
        )


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


def _say(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _claim_text(card: dict[str, Any]) -> str:
    pack = str(card.get("套", ""))
    if pack == "行业":
        return str(card.get("定义") or "")
    return str(card.get("命题") or "")


def _fact_from_card(card: dict[str, Any]) -> Fact:
    parent = card.get("属于")
    return Fact(
        id=str(card["编号"]),
        name=str(card.get("名称", "")),
        pack=str(card.get("套", "")),
        layer=str(card.get("层", "")),
        status=str(card.get("状态", "已封印")),
        claim=_claim_text(card),
        true_when=_as_list(card.get("何时成立")),
        false_when=_as_list(card.get("何时不算")),
        supports=_as_list(card.get("撑住谁")),
        binds=_as_list(card.get("绑哪个对象")),
        belongs_to=str(parent) if parent else None,
        relates_to=_as_list(card.get("关联")),
        is_a=_as_list(card.get("是一种")),
        aliases=_as_list(card.get("别名")),
        say=_say(card.get("对外怎么说")),
        raw=card,
    )


def _index_constitution(kb: KnowledgeBase) -> None:
    for fact in kb.facts.values():
        fact.children = []
    for fact in kb.facts.values():
        parent_id = fact.belongs_to
        if not parent_id:
            continue
        parent = kb.facts.get(parent_id)
        if parent is None:
            continue
        parent.children.append(fact.id)
    for fact in kb.facts.values():
        declared = _as_list(fact.raw.get("其下"))
        if declared and set(declared) == set(fact.children):
            fact.children = list(declared)
        else:
            fact.children.sort()


_OPS_DEMOTE_CLAIMS = frozenset({"F.l1.board_is_meter", "F.l1.crew_in_sph"})


def _ops_down(kb: KnowledgeBase, fact_id: str) -> list[str]:
    fact = kb.facts.get(fact_id)
    if fact is None:
        return []
    if fact.layer == "主张":
        return kb.streams_for_claim(fact_id)
    return [cid for cid in fact.children if (kid := kb.facts.get(cid)) and kid.layer != "投影"]


def format_ops_tree(kb: KnowledgeBase | None = None) -> str:
    store = kb if kb is not None else load()
    lines: list[str] = []

    def walk(fact_id: str, depth: int) -> None:
        fact = store.facts.get(fact_id)
        if fact is None or fact.layer == "投影":
            return
        lines.append(f"{'  ' * depth}{fact.name} ({fact.id})")
        if fact.layer == "主张":
            for cap_id in store.capabilities_for_claim(fact_id):
                walk(cap_id, depth + 1)
        for child_id in _ops_down(store, fact_id):
            walk(child_id, depth + 1)

    roots = sorted(
        (
            fact
            for fact in store.facts.values()
            if fact.pack == "运营" and fact.layer == "主张" and fact.id not in _OPS_DEMOTE_CLAIMS
        ),
        key=lambda f: f.id,
    )
    for root in roots:
        walk(root.id, 0)
    return "\n".join(lines)


def format_tree(kb: KnowledgeBase | None = None) -> str:
    store = kb if kb is not None else load()
    lines: list[str] = []

    def walk(fact_id: str, depth: int) -> None:
        fact = store.facts.get(fact_id)
        if fact is None:
            return
        mark = f" [{fact.layer}]" if fact.layer == "槽" else ""
        lines.append(f"{'  ' * depth}{fact.name} ({fact.id}){mark}")
        for child_id in fact.children:
            walk(child_id, depth + 1)

    for root in store.constitution_roots():
        walk(root.id, 0)
    ops = format_ops_tree(store)
    if ops:
        lines.append("")
        lines.append("【运营】")
        lines.extend(ops.splitlines())
    return "\n".join(lines)


def format_runtime_tree(kb: KnowledgeBase | None = None) -> str:
    store = kb if kb is not None else load()
    lines: list[str] = []

    def walk(fact_id: str, depth: int) -> None:
        fact = store.facts.get(fact_id)
        if fact is None:
            return
        lines.append(f"{'  ' * depth}{fact.name} ({fact.id})")
        for child_id in fact.children:
            walk(child_id, depth + 1)

    for root in store.runtime_roots():
        walk(root.id, 0)
    return "\n".join(lines)


def _ops_public(fact: Fact) -> dict[str, Any]:
    return {
        "id": fact.id,
        "name": fact.name,
        "layer": fact.layer,
        "status": fact.status,
        "pack": fact.pack,
    }


def _ops_leaf(fact: Fact) -> dict[str, Any]:
    return {**_ops_public(fact), "children": []}


def ops_stream_tree(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()

    def node(fact_id: str) -> dict[str, Any] | None:
        fact = store.facts.get(fact_id)
        if fact is None or fact.layer == "投影":
            return None
        built: dict[str, Any] = {
            **_ops_public(fact),
            "children": [child for cid in _ops_down(store, fact_id) if (child := node(cid))],
        }
        if fact.layer == "主张":
            built["capabilities"] = [
                _ops_leaf(cap)
                for cid in store.capabilities_for_claim(fact.id)
                if (cap := store.facts.get(cid)) is not None
            ]
        if fact.layer in {"环节", "节点"}:
            built["owners"] = [
                _ops_leaf(owner)
                for oid in store.owners_of(fact.id)
                if (owner := store.facts.get(oid)) is not None
            ]
        return built

    roots = sorted(
        (
            fact
            for fact in store.facts.values()
            if fact.pack == "运营" and fact.layer == "主张" and fact.id not in _OPS_DEMOTE_CLAIMS
        ),
        key=lambda f: f.id,
    )
    return [built for root in roots if (built := node(root.id))]


def ops_unattached(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()
    return [
        _ops_leaf(fact)
        for cid in store.unattached_capabilities()
        if (fact := store.facts.get(cid)) is not None
    ]


def ops_projections(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()
    return [
        card_view(fact)
        for fact in sorted(store.facts.values(), key=lambda f: f.id)
        if fact.pack == "运营" and fact.layer == "投影"
    ]


def card_view(fact: Fact, kb: KnowledgeBase | None = None) -> dict[str, Any]:
    raw = fact.raw
    view: dict[str, Any] = {
        "编号": fact.id,
        "名称": fact.name,
        "套": fact.pack,
        "层": fact.layer,
        "状态": fact.status,
        "命题": raw.get("命题"),
        "定义": raw.get("定义"),
        "属于": fact.belongs_to,
        "关联": list(fact.relates_to),
        "是一种": list(fact.is_a),
        "别名": list(fact.aliases),
        "其下": list(fact.children),
        "撑住谁": list(fact.supports),
        "谁有权": _as_list(raw.get("谁有权")),
        "角色": raw.get("角色"),
        "持有": raw.get("持有"),
        "可以": _as_list(raw.get("可以")),
        "阶段产出": raw.get("阶段产出"),
        "绑哪个对象": list(fact.binds),
        "对外怎么说": dict(fact.say),
        "说明": raw.get("说明"),
        "出处": raw.get("出处"),
        "类型": raw.get("类型"),
        "必须有": raw.get("必须有"),
        "禁止": raw.get("禁止"),
    }
    if kb is not None and fact.layer == "主张":
        view["谁兑现"] = kb.capabilities_for_claim(fact.id)
    return view


def tree_node(kb: KnowledgeBase, fact_id: str) -> dict[str, Any] | None:
    fact = kb.facts.get(fact_id)
    if fact is None:
        return None
    return {
        "id": fact.id,
        "name": fact.name,
        "layer": fact.layer,
        "status": fact.status,
        "pack": fact.pack,
        "children": [node for cid in fact.children if (node := tree_node(kb, cid))],
    }


def domain_tree(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()
    return [node for root in store.constitution_roots() if (node := tree_node(store, root.id))]


def runtime_tree(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()
    return [node for root in store.runtime_roots() if (node := tree_node(store, root.id))]


def ops_cards(kb: KnowledgeBase | None = None) -> list[dict[str, Any]]:
    store = kb if kb is not None else load()
    return [
        card_view(fact, store)
        for fact in sorted(store.facts.values(), key=lambda f: (f.layer, f.id))
        if fact.pack == "运营"
    ]


def default_kb_root() -> Path:
    return Path(__file__).resolve().parents[2] / "kb"


def load(root: Path | None = None) -> KnowledgeBase:
    kb_root = root or default_kb_root()
    kb = KnowledgeBase()
    for path in sorted(kb_root.rglob("*.yaml")):
        if path.name in _SKIP_NAMES:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for card in data.get("卡片") or []:
            fact = _fact_from_card(card)
            kb.facts[fact.id] = fact
        for row in data.get("论证") or []:
            kb.arguments.append(
                Argument(
                    id=str(row["编号"]),
                    premises=_as_list(row.get("前提")),
                    supports=str(row.get("推出", "")),
                    defeats=_as_list(row.get("击败")),
                )
            )
        for row in data.get("绑定") or []:
            kb.binds.append((str(row["从"]), str(row["到"])))
        for row in data.get("禁止") or []:
            kb.must_not_writes.extend(_as_list(row.get("禁止写入")))
    _index_constitution(kb)
    return kb
