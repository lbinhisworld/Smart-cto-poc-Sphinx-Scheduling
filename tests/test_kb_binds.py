"""投影路径与卡片完整性。"""

from __future__ import annotations

from sealed_kb.coverage import repo_root, scan_engine_modules
from sealed_kb.roles import gate_ticket
from sealed_kb.store import load


def test_projection_paths_exist() -> None:
    kb = load()
    root = repo_root()
    missing: list[str] = []
    for fact in kb.facts.values():
        for path in fact.raw.get("落在哪个文件") or []:
            if not (root / path).exists():
                missing.append(f"{fact.id}:{path}")
    assert missing == [], missing


def test_every_engine_module_is_projected() -> None:
    kb = load()
    listed: set[str] = set()
    for fact in kb.facts.values():
        if fact.layer != "投影":
            continue
        for path in fact.raw.get("落在哪个文件") or []:
            listed.add(str(path))
    need = {a.id for a in scan_engine_modules()}
    assert need <= listed, sorted(need - listed)


_GENERIC_DOMAIN_NAMES = {
    "计划差异",
    "可行性",
    "冲突",
    "未安置",
    "插单",
    "齐套",
    "单位",
    "部门",
    "计划版本",
}


def test_domain_names_are_not_generic() -> None:
    kb = load()
    bad = [
        f"{fact.id}:{fact.name}"
        for fact in kb.facts.values()
        if fact.pack == "行业" and fact.name in _GENERIC_DOMAIN_NAMES
    ]
    assert bad == [], bad


def test_claim_field_follows_pack() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.pack == "行业":
            if "定义" not in fact.raw or "命题" in fact.raw:
                bad.append(fact.id)
        elif fact.pack == "运营":
            if "命题" not in fact.raw or "定义" in fact.raw:
                bad.append(fact.id)
    assert bad == [], bad


def test_sealed_cards_have_claim_and_note() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.status != "已封印":
            continue
        if not fact.claim.strip():
            label = "定义" if fact.pack == "行业" else "命题"
            bad.append(f"{fact.id}:无{label}")
        note = fact.raw.get("说明")
        if not (str(note).strip() if note is not None else ""):
            bad.append(f"{fact.id}:无说明")
    assert bad == [], bad


def test_ticket_engine_requires_kb_file() -> None:
    refused = gate_ticket(
        {
            "files": ["packages/engine/backward.py"],
            "facts": ["F.l3.backward_place"],
            "binds": ["D.order.due_date"],
            "must_not": ["BR-27"],
            "writes": [],
        }
    )
    assert not refused.ok
    ok = gate_ticket(
        {
            "files": ["packages/engine/backward.py", "kb/ops/l4_engine.yaml"],
            "facts": ["F.l3.backward_place"],
            "binds": ["D.order.due_date"],
            "must_not": ["BR-27"],
            "writes": [],
        }
    )
    assert ok.ok
