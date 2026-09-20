from __future__ import annotations

from dataclasses import dataclass, field

from sealed_kb.store import KnowledgeBase, load

HOLD = "成立"
DEFEATED = "被击败"
INAPPLICABLE = "不适用"
MISSING = "缺前提"
_MAX_DEPTH = 3


@dataclass
class ProveResult:
    verdict: str
    chain: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    defeater: str | None = None


@dataclass
class ExplainResult:
    verdict: str
    text: str
    chain: list[str] = field(default_factory=list)


def _hit_any(tags: list[str], ctx: set[str]) -> bool:
    return bool(set(tags) & ctx)


def _all_in(tags: list[str], ctx: set[str]) -> bool:
    return bool(tags) and set(tags) <= ctx


def prove(
    claim_id: str,
    ctx: set[str],
    kb: KnowledgeBase | None = None,
    *,
    _depth: int = 0,
) -> ProveResult:
    store = kb if kb is not None else load()
    if _depth > _MAX_DEPTH:
        return ProveResult(MISSING, missing=["深度超限"])
    fact = store.facts.get(claim_id)
    if fact is None:
        return ProveResult(MISSING, missing=[claim_id])
    if fact.status == "假设":
        return ProveResult(MISSING, missing=[claim_id])
    if _hit_any(fact.false_when, ctx):
        return ProveResult(INAPPLICABLE)
    if fact.true_when and not _all_in(fact.true_when, ctx):
        return ProveResult(INAPPLICABLE)

    args = store.arguments_for(claim_id)
    if not args:
        return ProveResult(HOLD, chain=[claim_id])

    saw_inapplicable = False
    missing: list[str] = []
    for argument in args:
        defeated = False
        for did in argument.defeats:
            if prove(did, ctx, store, _depth=_depth + 1).verdict == HOLD:
                return ProveResult(DEFEATED, defeater=did)
        prem_results = [prove(pid, ctx, store, _depth=_depth + 1) for pid in argument.premises]
        if any(r.verdict == MISSING for r in prem_results):
            for r in prem_results:
                missing.extend(r.missing)
            continue
        if any(r.verdict == DEFEATED for r in prem_results):
            defeated = True
        if any(r.verdict == INAPPLICABLE for r in prem_results):
            saw_inapplicable = True
            continue
        if defeated:
            continue
        if all(r.verdict == HOLD for r in prem_results):
            chain = [claim_id]
            for r in prem_results:
                chain.extend(r.chain)
            return ProveResult(HOLD, chain=chain)
    if missing:
        return ProveResult(MISSING, missing=list(dict.fromkeys(missing)))
    if saw_inapplicable:
        return ProveResult(INAPPLICABLE)
    return ProveResult(MISSING, missing=[claim_id])


def explain(
    claim_id: str,
    ctx: set[str],
    role: str = "默认",
    kb: KnowledgeBase | None = None,
) -> str:
    store = kb if kb is not None else load()
    result = prove(claim_id, ctx, store)
    if result.verdict != HOLD:
        return result.verdict
    parts: list[str] = []
    seen: set[str] = set()
    for fid in result.chain:
        if fid in seen:
            continue
        seen.add(fid)
        fact = store.facts.get(fid)
        if not fact:
            continue
        line = fact.say.get(role) or fact.say.get("默认")
        if line:
            parts.append(line)
    return "".join(parts) if parts else result.verdict
