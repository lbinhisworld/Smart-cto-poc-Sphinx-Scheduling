"""把人话对到已有槽和结论。对不上或槽未封印就停，不编主数据。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sealed_kb.reasoner import INAPPLICABLE, prove
from sealed_kb.roles import consult
from sealed_kb.store import KnowledgeBase, load

MODE_RATIONALE = "原理"
MODE_OBJECTION = "质疑"
MODE_DETAIL = "细节"
MODE_DEFINE = "定义"
MODE_PROBE = "探针"

_OBJECTION_KEYS = (
    "明显不对",
    "不合理",
    "太死板",
    "应该自动",
    "改掉",
    "怎么能",
    "明显有问题",
)
_RATIONALE_KEYS = ("为什么", "为啥", "为何", "出于什么", "底层逻辑")
_DETAIL_KEYS = ("怎么算", "如何算", "公式", "具体怎么", "有哪些步骤", "到底怎么")
_PROBE_KEYS = ("小白", "探针", "有没有要补充", "还缺什么栏", "空栏")
_LAYER_RANK = {
    "对象": 0,
    "槽": 0,
    "主张": 1,
    "权责": 2,
    "价值流": 3,
    "环节": 3,
    "节点": 3,
    "投影": 4,
    "运行结果": 5,
    "结论": 5,
}
_LAYER_CODE = {
    "主张": "L1",
    "权责": "L2",
    "价值流": "L3",
    "环节": "L3.1",
    "节点": "L3.2",
    "投影": "L4",
    "结论": "结论",
}
_GROUNDING_LAYERS = frozenset(_LAYER_CODE)
_LAYER_LEAD = {
    "主张": "从交付模式上看，",
    "权责": "因此，从权责上看，",
    "价值流": "因此，从履约过程上看，",
    "环节": "因此，从这一步上看，",
    "节点": "所以，",
    "投影": "落到系统上，",
    "结论": "所以结论是，",
}
_OBJECTION_ASK = (
    "请指出断在哪一层：主张不再成立、权责变了，还是许可不该这样？"
    "新前提交给解析员写假设链，顾问不改封印库。"
)
_INAPPLICABLE_TEXT = (
    "这条主张在当前情境下不算。现有链推不出改约定日，禁止写回订单约定日。"
)


@dataclass(frozen=True)
class Intent:
    id: str
    title: str
    keywords: tuple[str, ...]
    slots: tuple[str, ...]
    claim: str | None = None
    ctx: frozenset[str] = frozenset()
    default_role: str = "默认"


INTENTS: tuple[Intent, ...] = (
    Intent(
        id="who_owns_due",
        title="谁能改订单交期",
        keywords=("谁能改日", "谁能改交期", "谁有权改", "谁能改订单"),
        slots=("D.order.due_date",),
        claim="F.l3.due_change_via_approval",
        default_role="销售",
    ),
    Intent(
        id="due_e2",
        title="E2 了能不能改订单交期",
        keywords=(
            "改交期",
            "改订单日期",
            "改订单交期",
            "改约定日",
            "能不能改交期",
            "e2",
            "E2",
            "往后延",
            "顺延",
            "自动延",
            "改日",
            "交期",
        ),
        slots=("D.order.due_date",),
        claim="C.give_earliest_keep_due",
        ctx=frozenset({"按单", "无备货", "有客户约定", "E2"}),
        default_role="销售",
    ),
    Intent(
        id="board",
        title="数量能不能直接拿盒去除 SPH",
        keywords=("盒去除", "枚去除", "归一到版", "先换成版", "折算到版", "换算成版", "按版", "版是"),
        slots=("D.board",),
        claim="C.normalize_to_board",
    ),
    Intent(
        id="crew",
        title="CREW 口径还要再乘人数吗",
        keywords=("crew", "CREW", "再乘人数", "人数已"),
        slots=("D.sph",),
        claim="C.crew_no_double_count",
    ),
    Intent(
        id="insert",
        title="已有计划上怎么插单",
        keywords=("插单",),
        slots=("D.insert",),
    ),
)


@dataclass
class AskResult:
    verdict: str
    question: str
    intent: str | None = None
    mode: str = MODE_RATIONALE
    slots: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    claim: str | None = None
    chain: list[str] = field(default_factory=list)
    text: str = ""
    suggestions: list[str] = field(default_factory=list)
    workbench_kind: str = ""
    workbench_theme: str = ""
    workbench_id: str = ""


def suggestions() -> list[str]:
    return [intent.title for intent in INTENTS]


def classify_mode(question: str) -> str:
    text = question.strip()
    if any(key in text for key in _PROBE_KEYS):
        return MODE_PROBE
    if any(key in text for key in _OBJECTION_KEYS):
        return MODE_OBJECTION
    if any(key in text for key in _RATIONALE_KEYS):
        return MODE_RATIONALE
    if any(key in text for key in _DETAIL_KEYS):
        return MODE_DETAIL
    return MODE_RATIONALE


def match_intent(question: str) -> Intent | None:
    text = question.strip()
    if not text:
        return None
    for intent in INTENTS:
        if any(key.lower() in text.lower() if key.isascii() else key in text for key in intent.keywords):
            return intent
    return None


def _labels(fact) -> list[str]:
    seen: list[str] = []
    for label in (fact.name, *fact.aliases):
        if label and label not in seen:
            seen.append(label)
    return seen


def _label_hits(text: str, label: str) -> bool:
    if not label:
        return False
    if label.isascii():
        return label.lower() in text.lower()
    return label in text


def match_named_card(question: str):
    kb = load()
    text = question.strip().rstrip("？?")
    if not text:
        return None
    scored: list[tuple[int, int, int, object]] = []
    for fact in kb.facts.values():
        if fact.layer == "投影":
            continue
        best = 0
        for label in _labels(fact):
            if _label_hits(text, label):
                best = max(best, len(label))
        if not best:
            continue
        demo = 1 if "演示" in fact.name else 0
        pack_rank = 0 if fact.pack == "行业" else 1
        scored.append((demo, pack_rank, -best, fact))
    if not scored:
        return None
    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return scored[0][3]


def match_domain_card(question: str):
    hit = match_named_card(question)
    if hit is None or hit.pack != "行业":
        return None
    return hit


def _card_say(fact, role: str | None) -> str:
    say = fact.say.get(role or "") or fact.say.get("默认") or ""
    body = fact.claim.strip()
    if body and say:
        return f"{body} {say}"
    return body or say


def _question_ctx(question: str, base: frozenset[str]) -> set[str]:
    ctx = set(base)
    if "内部返工" in question:
        ctx.add("内部返工")
    return ctx


def _support_closure(kb: KnowledgeBase, seed_ids: list[str]) -> list[str]:
    seen: list[str] = []
    queue = list(seed_ids)
    while queue:
        fid = queue.pop(0)
        if fid in seen:
            continue
        fact = kb.facts.get(fid)
        if fact is None:
            continue
        seen.append(fid)
        for parent in (*fact.supports, *fact.binds):
            if parent not in seen:
                queue.append(parent)
    return _ordered_chain(kb, seen)


def _ordered_chain(kb: KnowledgeBase, ids: list[str]) -> list[str]:
    unique: list[str] = []
    for fid in ids:
        if fid not in unique:
            unique.append(fid)

    def sort_key(fid: str) -> tuple[int, str]:
        fact = kb.facts.get(fid)
        layer = fact.layer if fact else ""
        return (_LAYER_RANK.get(layer, 9), fid)

    return sorted(unique, key=sort_key)


def _layer_line(fact, role: str | None) -> str:
    if fact.layer in {"对象", "槽"}:
        return (fact.claim or fact.say.get("默认") or "").strip()
    return (fact.say.get(role or "") or fact.say.get("默认") or fact.claim or "").strip()


def _answer_block(kb: KnowledgeBase, claim_id: str, chain: list[str], role: str | None) -> str:
    parts = ["【回答】"]
    seen: set[str] = set()
    for fid in chain:
        fact = kb.facts.get(fid)
        if fact is None or fact.layer not in {"对象", "槽"}:
            continue
        line = _layer_line(fact, role)
        if line and line not in seen:
            parts.append(line)
            seen.add(line)
    fact = kb.facts.get(claim_id)
    if fact is not None:
        line = _layer_line(fact, role)
        if line and line not in seen:
            parts.append(line)
    return "\n".join(parts)


def _grounding_block(kb: KnowledgeBase, chain: list[str], role: str | None) -> str:
    steps: list[str] = []
    for fid in chain:
        fact = kb.facts.get(fid)
        if fact is None or fact.layer not in _GROUNDING_LAYERS:
            continue
        line = _layer_line(fact, role)
        if not line:
            continue
        lead = _LAYER_LEAD.get(fact.layer, "")
        steps.append(f"{lead}{line}")
    if not steps:
        return ""
    return "\n".join(steps)


def _detail_lead(kb: KnowledgeBase, claim_id: str, role: str | None) -> str:
    fact = kb.facts.get(claim_id)
    if fact is None:
        return ""
    head = _layer_line(fact, role)
    sources = fact.raw.get("出处")
    if isinstance(sources, list) and sources:
        return f"{head} 出处：{'、'.join(str(item) for item in sources)}。"
    if isinstance(sources, str) and sources:
        return f"{head} 出处：{sources}。"
    return head


def _pack_text(
    kb: KnowledgeBase,
    *,
    mode: str,
    claim_id: str,
    chain: list[str],
    role: str | None,
) -> str:
    answer = _answer_block(kb, claim_id, chain, role)
    ground = _grounding_block(kb, chain, role)
    if mode == MODE_DETAIL:
        lead = _detail_lead(kb, claim_id, role)
        return f"{lead}\n{ground}".strip()
    if mode == MODE_OBJECTION:
        return f"{answer}\n{ground}\n{_OBJECTION_ASK}".strip()
    return f"{answer}\n{ground}".strip()


def _with_workbench(result: AskResult) -> AskResult:
    if result.verdict != "缺前提":
        return result
    from sealed_kb.workbench import DEFAULT_THEME, workbench_hint_for

    hint = workbench_hint_for([*result.slots, *result.missing], DEFAULT_THEME)
    if not hint:
        return result
    extra = hint["text"]
    text = f"{result.text}\n{extra}" if result.text else extra
    result.workbench_kind = hint["kind"]
    result.workbench_theme = hint["theme"]
    result.workbench_id = hint["id"]
    result.text = text
    return result


def _probe_ask(question: str) -> AskResult:
    from sealed_kb.workbench import DEFAULT_THEME, probe_queue

    queue = probe_queue(DEFAULT_THEME)
    if not queue:
        return AskResult(
            verdict="成立",
            question=question,
            intent="probe",
            mode=MODE_PROBE,
            text="这次没有可补的栏。",
        )
    first = queue[0]
    return AskResult(
        verdict="成立",
        question=question,
        intent="probe",
        mode=MODE_PROBE,
        slots=[first.anchor],
        text=first.question,
        workbench_kind="probe",
        workbench_theme=DEFAULT_THEME,
        workbench_id=first.anchor,
    )


def ask(question: str, role: str | None = None) -> AskResult:
    hints = suggestions()
    mode = classify_mode(question)
    if mode == MODE_PROBE:
        return _probe_ask(question)
    intent = match_intent(question)
    if intent is None:
        card = match_named_card(question)
        if card is None:
            return _with_workbench(
                AskResult(
                    verdict="缺前提",
                    question=question,
                    mode=mode,
                    missing=["对不上已封印的槽"],
                    text="这句话对不上库里的对象槽，不能现场编主数据。",
                    suggestions=hints,
                )
            )
        checked = consult([card.id])
        if checked.verdict != "成立":
            return _with_workbench(
                AskResult(
                    verdict="缺前提",
                    question=question,
                    intent="define",
                    mode=MODE_DEFINE,
                    slots=[card.id],
                    missing=checked.missing,
                    chain=[card.id],
                    text="对象槽未封印或缺失，顾问停止。",
                    suggestions=hints,
                )
            )
        return AskResult(
            verdict="成立",
            question=question,
            intent="define",
            mode=MODE_DEFINE,
            slots=[card.id],
            chain=[card.id],
            text=_card_say(card, role),
            suggestions=hints,
        )
    checked = consult(list(intent.slots))
    if checked.verdict != "成立":
        return _with_workbench(
            AskResult(
                verdict="缺前提",
                question=question,
                intent=intent.id,
                mode=mode,
                slots=list(intent.slots),
                missing=checked.missing,
                text="对象槽未封印或缺失，顾问停止。",
                suggestions=hints,
            )
        )
    if not intent.claim:
        kb = load()
        names = [kb.facts[sid].name for sid in intent.slots if sid in kb.facts]
        return AskResult(
            verdict="成立",
            question=question,
            intent=intent.id,
            mode=mode,
            slots=list(intent.slots),
            text="问的是：" + "、".join(names) + "。没有已封印结论可讲。",
            suggestions=hints,
        )
    kb = load()
    who = role or intent.default_role
    ctx = _question_ctx(question, intent.ctx)
    proved = prove(intent.claim, ctx, kb)
    chain = _support_closure(kb, proved.chain or [intent.claim])
    if proved.verdict == INAPPLICABLE:
        return AskResult(
            verdict=proved.verdict,
            question=question,
            intent=intent.id,
            mode=mode,
            slots=list(intent.slots),
            claim=intent.claim,
            chain=chain,
            text=_INAPPLICABLE_TEXT,
            suggestions=hints,
        )
    if proved.verdict != "成立":
        return AskResult(
            verdict=proved.verdict,
            question=question,
            intent=intent.id,
            mode=mode,
            slots=list(intent.slots),
            missing=proved.missing,
            claim=intent.claim,
            chain=chain,
            text=proved.verdict,
            suggestions=hints,
        )
    return AskResult(
        verdict="成立",
        question=question,
        intent=intent.id,
        mode=mode,
        slots=list(intent.slots),
        claim=intent.claim,
        chain=chain,
        text=_pack_text(kb, mode=mode, claim_id=intent.claim, chain=chain, role=who),
        suggestions=hints,
    )
