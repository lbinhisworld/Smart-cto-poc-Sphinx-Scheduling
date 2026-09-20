from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_SKIP_NAMES = {"schema.yaml"}


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


def _fact_from_card(card: dict[str, Any]) -> Fact:
    return Fact(
        id=str(card["编号"]),
        name=str(card.get("名称", "")),
        pack=str(card.get("套", "")),
        layer=str(card.get("层", "")),
        status=str(card.get("状态", "已封印")),
        claim=str(card.get("这句话", "")),
        true_when=_as_list(card.get("何时成立")),
        false_when=_as_list(card.get("何时不算")),
        supports=_as_list(card.get("撑住谁")),
        binds=_as_list(card.get("绑哪个对象")),
        say=_say(card.get("对外怎么说")),
        raw=card,
    )


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
    return kb
