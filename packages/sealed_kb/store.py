from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_SKIP_NAMES = {"schema.yaml", "coverage.yaml"}


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

    def constitution_roots(self) -> list[Fact]:
        return sorted(
            (
                fact
                for fact in self.facts.values()
                if fact.pack == "行业" and not fact.belongs_to
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
        fact.children.sort()


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
    return "\n".join(lines)


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
