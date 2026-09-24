"""包 B：拜访确认、成果分布、列级金额。未确认草稿不进大盘。不写销售订单交期。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib import error, request

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.project_board import STAGES
from db.sample_workflow import sample_detail
from db.tables import (
    AppSettingRow,
    CrmCustomerRow,
    CrmOpportunityRow,
    CrmQuoteRow,
    CrmSalesGoalRow,
    CrmSampleRow,
    CrmVisitRow,
    DeliveryProjectRow,
    DeliveryProjectStepRow,
    SoOrderRow,
)

DEMO_TODAY = date(2026, 9, 15)
VALID_MINUTES = 15
PACK_KEY = "crm_sales_pack_version"
PACK_VERSION = "2026-09-24-no-aux-visits"
ASSIST_TEAM = ("李业务",)
LOST_REASONS = ("价格", "交期", "样品未过", "客户取消", "其他")
OUTCOMES = ("关系建联", "触达决策人", "挖到商机")
STAGE_COLS = ("还没成商机", "打样", "报价", "签单")
GOAL_METRICS = ("新客", "有效拜访", "商机", "签单")
SOP = {
    "关系建联": "约见决策人",
    "触达决策人": "问是否打样",
    "挖到商机": "补打样或报价",
}
LLM_URL_KEY = "crm_llm_base_url"
LLM_KEY_KEY = "crm_llm_api_key"
LLM_MODEL_KEY = "crm_llm_model"


def visit_is_valid(check_in: datetime, check_out: datetime, *, minutes: int = VALID_MINUTES) -> bool:
    if check_out < check_in:
        return False
    return (check_out - check_in).total_seconds() >= minutes * 60


def sop_next(outcome: str) -> str:
    return SOP.get(_norm_outcome(outcome), "约见决策人")


def _norm_outcome(outcome: str) -> str:
    text = (outcome or "").strip()
    if "决策" in text:
        return "触达决策人"
    if text in OUTCOMES:
        return text
    if "商机" in text:
        return "挖到商机"
    return "关系建联"


def match_customers(text: str, customers: list[dict]) -> list[dict]:
    hits: list[tuple[int, dict]] = []
    for cust in customers:
        name = str(cust.get("name") or "")
        bases = [name]
        if "（" in name:
            bases.append(name.split("（", 1)[0])
        best = 0
        for base in bases:
            if base and base in text:
                best = max(best, len(base))
            for n in range(min(len(base), 8), 1, -1):
                if base[:n] in text:
                    best = max(best, n)
                    break
        if best >= 2:
            hits.append((best, cust))
    if not hits:
        return []
    hits.sort(key=lambda item: -item[0])
    top = hits[0][0]
    chosen: list[dict] = []
    seen: set[str] = set()
    for score, cust in hits:
        if score < max(2, top - 1):
            continue
        code = str(cust.get("code") or "")
        if code in seen:
            continue
        seen.add(code)
        chosen.append(cust)
        if len(chosen) == 3:
            break
    return chosen


def draft_from_text(text: str, customers: list[dict], *, today: date) -> dict:
    raw = text.strip()
    if "商机" in raw or "意向订单" in raw:
        outcome = "挖到商机"
    elif "决策" in raw:
        outcome = "触达决策人"
    else:
        outcome = "关系建联"
    matches = match_customers(raw, customers)
    kind = "陌拜" if "陌拜" in raw or not matches else "现有客户"
    name = matches[0]["name"] if len(matches) == 1 else ""
    opp_name = ""
    if outcome == "挖到商机":
        opp_name = f"{name or '新客户'}商机"
    return {
        "source": "keyword",
        "customer_name": name,
        "matches": matches,
        "ask_create": len(matches) == 0,
        "visit_kind": kind,
        "narrative": raw,
        "outcome": outcome,
        "next_step": sop_next(outcome),
        "next_date": (today + timedelta(days=7)).isoformat(),
        "opportunity_name": opp_name,
    }


def goal_lines(targets: dict[str, int], done: dict[str, int]) -> list[dict]:
    lines = []
    for metric in GOAL_METRICS:
        target = int(targets.get(metric, 0))
        finished = int(done.get(metric, 0))
        lines.append(
            {
                "metric": metric,
                "target": target,
                "done": finished,
                "gap": target - finished,
            }
        )
    return lines


def _visit_person_key(visit: dict) -> str:
    code = (visit.get("customer_code") or "").strip()
    owner = (visit.get("owner_sales") or "").strip()
    name = (visit.get("customer_name") or "").strip()
    if code:
        return f"code:{code}"
    if name:
        return f"name:{owner}:{name}"
    return f"visit:{visit.get('id')}"


AUX_VISIT_CUSTOMER_NAMES = frozenset(
    {
        "分布演示饼屋",
        "短访客户",
        "街边饼店",
        "留存演示",
        "回收演示",
    }
)
AUX_VISIT_NARRATIVE_PREFIXES = ("【包B种子】", "【大盘演示", "【演示】")


def purge_auxiliary_visits(session: Session) -> int:
    """删除集成测试与历史演示种子写入的拜访，避免大盘重复占位。"""
    from sqlalchemy import delete

    from db.tables import CrmFollowRecordRow

    remove_ids: list[int] = []
    for row in session.scalars(select(CrmVisitRow)).all():
        name = (row.customer_name or "").strip()
        narrative = row.narrative or ""
        if name in AUX_VISIT_CUSTOMER_NAMES or name.endswith("演示饼屋"):
            remove_ids.append(row.id)
            continue
        if any(narrative.startswith(prefix) for prefix in AUX_VISIT_NARRATIVE_PREFIXES):
            remove_ids.append(row.id)
    if not remove_ids:
        return 0
    session.execute(delete(CrmFollowRecordRow).where(CrmFollowRecordRow.visit_id.in_(remove_ids)))
    session.execute(delete(CrmVisitRow).where(CrmVisitRow.id.in_(remove_ids)))
    session.flush()
    return len(remove_ids)


def place_visits(
    visits: list[dict],
    *,
    document_stage: dict[str, str],
    include_all: bool,
) -> dict[str, list[dict]]:
    """最新一条已确认拜访决定成果行。草稿由调用方排除。"""
    cells: dict[str, list[dict]] = {
        f"{outcome}|{stage}": [] for outcome in OUTCOMES for stage in STAGE_COLS
    }
    grouped: dict[str, list[dict]] = {}
    for visit in visits:
        if visit.get("status") not in (None, "CONFIRMED"):
            continue
        if not include_all and not visit.get("is_valid"):
            continue
        code = visit.get("customer_code") or ""
        if not code and not include_all:
            continue
        key = _visit_person_key(visit)
        grouped.setdefault(key, []).append(visit)
    for key, rows in grouped.items():
        latest = max(rows, key=lambda row: int(row.get("id") or 0))
        code = latest.get("customer_code") or ""
        stage = "还没成商机" if not code else document_stage.get(code, "还没成商机")
        if stage not in STAGE_COLS:
            stage = "还没成商机"
        outcome = _norm_outcome(str(latest.get("outcome") or ""))
        cells[f"{outcome}|{stage}"].append(
            {
                "visit_id": latest.get("id"),
                "customer_code": code or None,
                "customer_name": latest.get("customer_name") or "未建客户",
                "owner_sales": latest.get("owner_sales") or "",
                "outcome": outcome,
                "stage": stage,
                "is_valid": bool(latest.get("is_valid")),
            }
        )
    return cells


FUNNEL_STAGES = ("全部拜访", "有效拜访", "已建客户", "商机", "打样", "报价", "签单")
CUSTOMER_FUNNEL = ("已建客户", "商机", "打样", "报价", "签单")
COMPLETE_SLOTS = ("客户是谁", "见了谁", "要什么", "这次说清了", "下一步约好了")


def visit_slots(visit: dict) -> set[str]:
    """无效拜访和草稿不加分。一条有效拜访可以同时补上多条信息。"""
    if visit.get("status") not in (None, "CONFIRMED"):
        return set()
    if not visit.get("is_valid"):
        return set()
    slots: set[str] = set()
    if visit.get("customer_code"):
        slots.add("客户是谁")
    outcome = str(visit.get("outcome") or "")
    narrative = str(visit.get("narrative") or "")
    if outcome == "触达决策人" or "决策" in narrative:
        slots.add("见了谁")
    if outcome == "挖到商机" and (visit.get("opportunity_name") or visit.get("opportunity_id")):
        slots.add("要什么")
    if narrative.strip():
        slots.add("这次说清了")
    if visit.get("next_step") and visit.get("next_date"):
        slots.add("下一步约好了")
    return slots


def customer_completeness(visits: list[dict]) -> dict:
    filled: set[str] = set()
    for visit in visits:
        filled |= visit_slots(visit)
    missing = [name for name in COMPLETE_SLOTS if name not in filled]
    return {
        "percent": len(filled) * 20,
        "filled": [name for name in COMPLETE_SLOTS if name in filled],
        "missing": missing,
    }


def completeness_delta(before_visits: list[dict], new_visit: dict) -> dict:
    before = customer_completeness(before_visits)
    after = customer_completeness([*before_visits, new_visit])
    gained = [name for name in after["filled"] if name not in before["filled"]]
    return {
        "before_percent": before["percent"],
        "after_percent": after["percent"],
        "gained": gained,
        "missing": after["missing"],
    }


def _furthest_stage(fact: dict) -> str:
    if fact.get("lost"):
        return "已建客户"
    if fact.get("has_sign"):
        return "签单"
    if fact.get("has_quote"):
        return "报价"
    if fact.get("has_sample"):
        return "打样"
    if fact.get("has_opp"):
        return "商机"
    return "已建客户"


def build_funnel(visits: list[dict], facts: dict[str, dict]) -> dict:
    """前两格按拜访次数，从已建客户起一家客户只算一次，并累计进前面的格子。"""
    confirmed = [v for v in visits if v.get("status") in (None, "CONFIRMED")]
    valid = [v for v in confirmed if v.get("is_valid")]
    codes: list[str] = []
    seen: set[str] = set()
    for visit in valid:
        code = visit.get("customer_code") or ""
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    furthest = {code: _furthest_stage(facts.get(code) or {}) for code in codes}
    rank = {name: index for index, name in enumerate(CUSTOMER_FUNNEL)}
    counts = {
        "全部拜访": len(confirmed),
        "有效拜访": len(valid),
    }
    for stage in CUSTOMER_FUNNEL:
        counts[stage] = sum(1 for code in codes if rank[furthest[code]] >= rank[stage])
    stuck: dict[str, list[dict]] = {stage: [] for stage in FUNNEL_STAGES}
    for visit in confirmed:
        if visit.get("is_valid"):
            continue
        stuck["全部拜访"].append(
            {
                "kind": "visit",
                "name": visit.get("customer_name") or "未命名",
                "customer_code": visit.get("customer_code"),
                "owner_sales": visit.get("owner_sales") or "",
            }
        )
    for visit in valid:
        if visit.get("customer_code"):
            continue
        stuck["有效拜访"].append(
            {
                "kind": "visit",
                "name": visit.get("customer_name") or "未建客户",
                "customer_code": None,
                "owner_sales": visit.get("owner_sales") or "",
            }
        )
    for code in codes:
        stage = furthest[code]
        fact = facts.get(code) or {}
        stuck[stage].append(
            {
                "kind": "customer",
                "name": fact.get("name") or code,
                "customer_code": code,
                "owner_sales": fact.get("owner_sales") or "",
            }
        )
    steps = []
    for index, stage in enumerate(FUNNEL_STAGES):
        nxt = FUNNEL_STAGES[index + 1] if index + 1 < len(FUNNEL_STAGES) else None
        rate = None
        if nxt and counts[stage]:
            rate = round(counts[nxt] * 100 / counts[stage])
        steps.append(
            {
                "stage": stage,
                "count": counts[stage],
                "to_next_pct": rate,
                "stuck": stuck[stage],
            }
        )
    overall = round(counts["签单"] * 100 / counts["全部拜访"]) if counts["全部拜访"] else None
    lost = sum(1 for code in codes if (facts.get(code) or {}).get("lost"))
    return {
        "steps": steps,
        "overall_pct": overall,
        "lost": lost,
        "note": "相邻转化率 = 下一格 ÷ 这一格。前两格是拜访次数，从已建客户起是客户数。草稿不算。无效拜访只进全部拜访。丢单停在已建客户。",
    }


def order_talk(
    *,
    has_tasks: bool,
    due: date,
    plan_end: date | None,
    earliest: date | None,
) -> dict:
    if not has_tasks:
        return {"talk": "还没进排程", "earliest": None}
    late = None
    if earliest and earliest > due:
        late = earliest
    elif plan_end and plan_end > due:
        late = plan_end
    if late:
        return {"talk": "来不及", "earliest": late.isoformat()}
    return {"talk": "交期内可做", "earliest": None}


def redact(row: dict, role: str) -> dict:
    """无权字段直接不返回。研发连对客报价这一列的进度也不给。"""
    out = dict(row)
    if role in ("FIN", "RD"):
        out.pop("visit_text", None)
    if role in ("SALES", "SALES_ASSIST", "SALES_MGR"):
        out.pop("sample_cost", None)
        out.pop("internal_quote", None)
    if role == "RD":
        out.pop("customer_quote", None)
        out.pop("internal_quote", None)
        out["amount"] = None
        status = dict(out.get("column_status") or {})
        status.pop("对客报价", None)
        out["column_status"] = status
        sign = out.get("sign")
        if isinstance(sign, dict):
            out["sign"] = {"status": sign.get("status") or "未到"}
    if role == "SALES":
        sign = out.get("sign")
        if isinstance(sign, dict):
            out["sign"] = {
                "status": sign.get("status") or "未到",
                "contract_no": sign.get("contract_no"),
                "items": sign.get("items") or [],
            }
    if role == "SALES_ASSIST":
        sign = out.get("sign")
        if isinstance(sign, dict):
            out["sign"] = {
                "status": sign.get("status") or "未到",
                "contract_no": sign.get("contract_no"),
                "items": sign.get("items") or [],
                "contract_amount": sign.get("contract_amount"),
            }
    if role == "SALES_MGR":
        sign = out.get("sign")
        if isinstance(sign, dict):
            kept = {
                "status": sign.get("status") or "未到",
                "contract_no": sign.get("contract_no"),
                "items": sign.get("items") or [],
                "contract_amount": sign.get("contract_amount"),
            }
            out["sign"] = kept
    return out


def _setting(session: Session, key: str) -> str:
    row = session.get(AppSettingRow, key)
    return row.value if row else ""


def _set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(AppSettingRow, key)
    if row is None:
        session.add(AppSettingRow(key=key, value=value))
    else:
        row.value = value


def llm_public_config(session: Session) -> dict:
    return {
        "base_url": _setting(session, LLM_URL_KEY) or "https://api.deepseek.com/v1",
        "model": _setting(session, LLM_MODEL_KEY) or "deepseek-chat",
        "has_key": bool(_setting(session, LLM_KEY_KEY)),
    }


def save_llm_config(session: Session, *, base_url: str, model: str, api_key: str | None) -> dict:
    if base_url.strip():
        _set_setting(session, LLM_URL_KEY, base_url.strip().rstrip("/"))
    if model.strip():
        _set_setting(session, LLM_MODEL_KEY, model.strip())
    if api_key:
        _set_setting(session, LLM_KEY_KEY, api_key.strip())
    return llm_public_config(session)


def _llm_draft(session: Session, text: str, customers: list[dict], *, today: date) -> dict | None:
    key = _setting(session, LLM_KEY_KEY)
    if not key:
        return None
    base = (_setting(session, LLM_URL_KEY) or "https://api.deepseek.com/v1").rstrip("/")
    model = _setting(session, LLM_MODEL_KEY) or "deepseek-chat"
    names = [c["name"] for c in customers[:30]]
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "只输出 JSON。字段：customer_name, visit_kind(现有客户或陌拜), "
                    "narrative, outcome(关系建联、触达决策人、挖到商机之一), "
                    "next_step, next_date, opportunity_name。"
                    "挖到商机才填 opportunity_name。不要建议交期改写。"
                ),
            },
            {"role": "user", "content": f"已知客户：{names}\n今天：{today.isoformat()}\n原文：{text}"},
        ],
    }
    req = request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
        content = body["choices"][0]["message"]["content"]
        start = content.find("{")
        end = content.rfind("}")
        parsed = json.loads(content[start : end + 1])
    except (error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
        return None
    outcome = _norm_outcome(str(parsed.get("outcome") or ""))
    matches = match_customers(text, customers)
    named = str(parsed.get("customer_name") or "")
    if named:
        named_hits = match_customers(named, customers)
        if named_hits:
            matches = named_hits
    return {
        "source": "llm",
        "customer_name": matches[0]["name"] if len(matches) == 1 else named,
        "matches": matches,
        "ask_create": len(matches) == 0,
        "visit_kind": parsed.get("visit_kind") if parsed.get("visit_kind") in ("现有客户", "陌拜") else "现有客户",
        "narrative": str(parsed.get("narrative") or text),
        "outcome": outcome,
        "next_step": sop_next(outcome),
        "next_date": str(parsed.get("next_date") or (today + timedelta(days=7)).isoformat()),
        "opportunity_name": str(parsed.get("opportunity_name") or "") if outcome == "挖到商机" else "",
    }


def build_draft(session: Session, text: str, *, today: date) -> dict:
    customers = [
        {"code": row.code, "name": row.name}
        for row in session.scalars(select(CrmCustomerRow).order_by(CrmCustomerRow.code))
    ]
    drafted = _llm_draft(session, text, customers, today=today)
    if drafted is None:
        drafted = draft_from_text(text, customers, today=today)
        if _setting(session, LLM_KEY_KEY):
            drafted["source"] = "keyword"
            drafted["note"] = "模型没有返回可用草稿，已按关键词起草"
    drafted["check_in_at"] = datetime(today.year, today.month, today.day, 9, 0).isoformat(timespec="minutes")
    drafted["check_out_at"] = datetime(today.year, today.month, today.day, 9, 20).isoformat(timespec="minutes")
    drafted["location_note"] = ""
    drafted["photo_note"] = ""
    return drafted


def _money(value) -> str | None:
    if value is None or value == "":
        return None
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _document_stage(session: Session, customer_code: str) -> str:
    quote = session.scalar(
        select(CrmQuoteRow.code).where(
            CrmQuoteRow.customer_code == customer_code,
            CrmQuoteRow.status != "VOID",
        )
    )
    opp_signed = session.scalar(
        select(CrmOpportunityRow.id).where(
            CrmOpportunityRow.customer_code == customer_code,
            CrmOpportunityRow.project_code.is_not(None),
        )
    )
    from db.tables import CrmContractRow

    contract = session.scalar(
        select(CrmContractRow.contract_no).where(
            CrmContractRow.customer_code == customer_code,
            CrmContractRow.status == "ACTIVE",
        )
    )
    if contract or opp_signed:
        return "签单"
    if quote:
        return "报价"
    sample = session.scalar(
        select(CrmSampleRow.code).where(CrmSampleRow.customer_code == customer_code)
    )
    if sample:
        return "打样"
    return "还没成商机"


def _scope_owner(role: str, actor: str) -> str | None:
    if role == "SALES":
        return actor or None
    if role == "SALES_ASSIST":
        return ASSIST_TEAM[0]
    return None


def _can_see_owner(role: str, actor: str, owner: str) -> bool:
    if role in ("GM", "SALES_MGR", "FIN"):
        return True
    if role == "SALES":
        return owner == actor
    if role == "SALES_ASSIST":
        return owner in ASSIST_TEAM
    if role == "RD":
        return True
    return False


def ensure_sales_pack(session: Session) -> None:
    purge_auxiliary_visits(session)
    if _setting(session, PACK_KEY) == PACK_VERSION:
        return
    targets = {"新客": 4, "有效拜访": 12, "商机": 3, "签单": 1}
    for metric, qty in targets.items():
        existing = session.scalar(
            select(CrmSalesGoalRow).where(
                CrmSalesGoalRow.owner_sales == "李业务",
                CrmSalesGoalRow.metric == metric,
            )
        )
        if existing is None:
            session.add(CrmSalesGoalRow(owner_sales="李业务", metric=metric, target_qty=qty))
        else:
            existing.target_qty = qty
    opp = session.scalar(
        select(CrmOpportunityRow).where(CrmOpportunityRow.name == "李业务·好利来加急")
    )
    if opp is None:
        opp = CrmOpportunityRow(
            name="李业务·好利来加急",
            customer_code="C-001",
            stage="报价",
            amount=Decimal("15000"),
            owner_sales="李业务",
            expect_close_date=date(2026, 9, 30),
            sample_code="SP-001",
        )
        session.add(opp)
        session.flush()
    opp.sample_cost_qty = 20
    opp.sample_cost_material = Decimal("1200.00")
    opp.sample_cost_labor = Decimal("300.00")
    opp.planned_labor_amount = Decimal("8000.00")
    opp.customer_quote_amount = Decimal("15000.00")
    opp.urgent_order_no = "SO-002"
    opp.owner_sales = "李业务"
    _set_setting(session, PACK_KEY, PACK_VERSION)
    session.flush()


def _done_counts(session: Session, owner: str) -> dict[str, int]:
    visits = session.scalars(
        select(CrmVisitRow).where(
            CrmVisitRow.owner_sales == owner,
            CrmVisitRow.status == "CONFIRMED",
            CrmVisitRow.is_valid.is_(True),
        )
    ).all()
    signed_n = session.scalars(
        select(CrmOpportunityRow).where(
            CrmOpportunityRow.owner_sales == owner,
            CrmOpportunityRow.project_code.is_not(None),
        )
    ).all()
    return {
        "新客": sum(1 for row in visits if row.created_customer),
        "有效拜访": len(visits),
        "商机": sum(1 for row in visits if row.outcome == "挖到商机" and row.opportunity_id),
        "签单": len(signed_n),
    }


def home_for(session: Session, *, role: str, actor: str, today: date) -> dict:
    from db.crm_goal_period import ensure_demo_goal_period, mobile_goal_blocks

    ensure_sales_pack(session)
    ensure_demo_goal_period(session)
    owner = _scope_owner(role, actor) or actor
    if role in ("SALES_MGR", "GM"):
        from db.tables import CrmSalesGoalPeriodRow

        owners = sorted(
            {
                row.owner_sales
                for row in session.scalars(
                    select(CrmSalesGoalPeriodRow).where(CrmSalesGoalPeriodRow.period_kind == "YEAR")
                ).all()
            }
            or {actor}
        )
    else:
        owners = [owner]
    blocks = []
    goal_blocks_by_owner: dict[str, dict] = {}
    for name in owners:
        goal_blocks_by_owner[name] = mobile_goal_blocks(session, name, today)
        blocks.append(
            {
                "owner_sales": name,
                "lines": goal_blocks_by_owner[name]["month"]["lines"],
            }
        )
    actions = _actions(session, owner if role in ("SALES", "SALES_ASSIST") else None, today)
    primary = goal_blocks_by_owner.get(owner) or mobile_goal_blocks(session, owner, today)
    return {
        "goals": blocks,
        "goal_blocks": primary,
        "actions": actions[:3],
        "today": today.isoformat(),
    }


def _actions(session: Session, owner: str | None, today: date) -> list[dict]:
    rows = session.scalars(
        select(CrmVisitRow).where(CrmVisitRow.status == "CONFIRMED").order_by(CrmVisitRow.id.desc())
    ).all()
    latest: dict[str, CrmVisitRow] = {}
    for row in rows:
        if owner and row.owner_sales != owner:
            continue
        key = row.customer_code or f"visit:{row.id}"
        if key not in latest:
            latest[key] = row
    pending = []
    for row in latest.values():
        if row.next_date is None:
            continue
        overdue = row.next_date < today
        pending.append(
            {
                "customer_code": row.customer_code,
                "customer_name": row.customer_name,
                "outcome": row.outcome,
                "next_step": row.next_step or sop_next(row.outcome),
                "next_date": row.next_date.isoformat(),
                "overdue": overdue,
                "owner_sales": row.owner_sales,
            }
        )
    pending.sort(key=lambda item: (not item["overdue"], item["next_date"]))
    return pending


def _next_customer_code(session: Session) -> str:
    codes = session.scalars(select(CrmCustomerRow.code)).all()
    nums = [int(code[2:]) for code in codes if code.startswith("C-") and code[2:].isdigit()]
    return f"C-{(max(nums) if nums else 0) + 1:03d}"


def confirm_visit(session: Session, *, actor: str, payload: dict, today: date) -> dict:
    ensure_sales_pack(session)
    outcome = _norm_outcome(str(payload.get("outcome") or ""))
    check_in = payload["check_in_at"]
    check_out = payload["check_out_at"]
    if isinstance(check_in, str):
        check_in = datetime.fromisoformat(check_in)
    if isinstance(check_out, str):
        check_out = datetime.fromisoformat(check_out)
    valid = visit_is_valid(check_in, check_out)
    code = payload.get("customer_code") or None
    created = False
    name = str(payload.get("customer_name") or "").strip()
    kind = payload.get("visit_kind") or "现有客户"
    if payload.get("create_customer"):
        if not name:
            raise ValueError("新建客户需要名称")
        code = _next_customer_code(session)
        session.add(
            CrmCustomerRow(
                code=code,
                name=name,
                channel_l1="待定",
                channel_l2="陌拜" if kind == "陌拜" else "现有",
                owner_sales=actor,
                level=3,
            )
        )
        created = True
        session.flush()
    elif code:
        cust = session.get(CrmCustomerRow, code)
        if cust is None:
            raise ValueError("客户不存在")
        name = cust.name
    if outcome == "挖到商机" and not code:
        raise ValueError("挖到商机前要先确定客户")
    prior: list[dict] = []
    if code:
        prior = [
            _visit_dict(old)
            for old in session.scalars(
                select(CrmVisitRow).where(
                    CrmVisitRow.customer_code == code,
                    CrmVisitRow.status == "CONFIRMED",
                )
            )
        ]
    opp_id = None
    opp_name = str(payload.get("opportunity_name") or "").strip()
    if outcome == "挖到商机" and opp_name and code:
        opp = CrmOpportunityRow(
            name=opp_name,
            customer_code=code,
            stage="商机",
            amount=Decimal("0"),
            owner_sales=actor,
            expect_close_date=None,
            sample_code=None,
        )
        session.add(opp)
        session.flush()
        opp_id = opp.id
    next_date = payload.get("next_date")
    if isinstance(next_date, str) and next_date:
        next_date = date.fromisoformat(next_date)
    row = CrmVisitRow(
        status="CONFIRMED",
        owner_sales=actor,
        customer_code=code,
        customer_name=name,
        visit_kind=kind,
        narrative=str(payload.get("narrative") or ""),
        outcome=outcome,
        next_step=sop_next(outcome),
        next_date=next_date,
        opportunity_name=opp_name,
        opportunity_id=opp_id,
        check_in_at=check_in,
        check_out_at=check_out,
        is_valid=valid,
        location_note=str(payload.get("location_note") or ""),
        photo_note=str(payload.get("photo_note") or ""),
        created_customer=created,
        confirmed_at=datetime(today.year, today.month, today.day, 12, 0),
    )
    session.add(row)
    session.flush()
    if valid:
        from db.crm_leads import attach_valid_visit_to_lead, match_lead_for_visit

        lead = match_lead_for_visit(
            session,
            actor=actor,
            customer_name=name,
            phone=str(payload.get("phone") or ""),
            lead_code=payload.get("lead_code"),
        )
        if lead is not None:
            attach_valid_visit_to_lead(
                session,
                lead=lead,
                visit_id=row.id,
                narrative=row.narrative,
                owner=actor,
                next_date=next_date if isinstance(next_date, date) else None,
                confirmed_day=today,
            )
    new_visit = _visit_dict(row)
    score = completeness_delta(prior, new_visit)
    due_guard = None
    urgent = payload.get("urgent_order_no")
    if urgent:
        order = session.get(SoOrderRow, urgent)
        due_guard = order.due_date.isoformat() if order else None
    return {
        "id": row.id,
        "is_valid": row.is_valid,
        "customer_code": row.customer_code,
        "customer_name": row.customer_name,
        "outcome": row.outcome,
        "opportunity_id": opp_id,
        "created_customer": created,
        "due_date_unchanged": due_guard,
        "completeness": score,
    }


def _visits_for_board(session: Session, *, role: str, actor: str) -> list[dict]:
    rows = session.scalars(select(CrmVisitRow).where(CrmVisitRow.status == "CONFIRMED")).all()
    out = []
    for row in rows:
        if not _can_see_owner(role, actor, row.owner_sales):
            continue
        out.append(_visit_dict(row))
    return out


def _visit_dict(row: CrmVisitRow) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "customer_code": row.customer_code,
        "customer_name": row.customer_name,
        "outcome": row.outcome,
        "is_valid": row.is_valid,
        "owner_sales": row.owner_sales,
        "narrative": row.narrative,
        "next_step": row.next_step,
        "next_date": row.next_date.isoformat() if row.next_date else None,
        "opportunity_name": row.opportunity_name,
        "opportunity_id": row.opportunity_id,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "visit_kind": row.visit_kind,
    }


def _visits_by_customer(visits: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for visit in visits:
        if visit.get("status") not in (None, "CONFIRMED"):
            continue
        code = visit.get("customer_code")
        if not code:
            continue
        grouped.setdefault(code, []).append(visit)
    return grouped


def _enrich_matrix_people(matrix: list[dict], visits: list[dict]) -> None:
    by_code = _visits_by_customer(visits)
    for row in matrix:
        for cell in row["cells"]:
            people: list[dict] = []
            for person in cell["people"]:
                code = person.get("customer_code") or ""
                rows = by_code.get(code, [])
                valid = [v for v in rows if v.get("is_valid")]
                score = customer_completeness(valid or rows)
                people.append(
                    {
                        **person,
                        "visit_count": len(valid),
                        "completeness_percent": score["percent"],
                        "missing": score["missing"],
                    }
                )
            cell["people"] = people


def _compact_board_alerts(alerts: list[dict], *, limit: int = 6) -> list[dict]:
    priority = {
        "拜访低于目标": 0,
        "打样停滞": 1,
        "报价停滞": 2,
        "未打样": 3,
        "多次建联": 4,
        "信息齐了还没打样": 5,
        "拜访未齐": 6,
    }
    seen: set[str] = set()
    uniq: list[dict] = []
    for alert in alerts:
        text = alert.get("text") or ""
        if text in seen:
            continue
        seen.add(text)
        uniq.append(alert)
    uniq.sort(key=lambda item: (priority.get(str(item.get("kind")), 9), item.get("text") or ""))
    return uniq[:limit]


def board(session: Session, *, role: str, actor: str, include_all: bool) -> dict:
    ensure_sales_pack(session)
    visits = _visits_for_board(session, role=role, actor=actor)
    stages = {}
    for visit in visits:
        code = visit.get("customer_code")
        if code and code not in stages:
            stages[code] = _document_stage(session, code)
    cells = place_visits(visits, document_stage=stages, include_all=include_all)
    matrix = []
    for outcome in OUTCOMES:
        row = {"outcome": outcome, "cells": []}
        for stage in STAGE_COLS:
            people = cells[f"{outcome}|{stage}"]
            row["cells"].append({"stage": stage, "count": len(people), "people": people})
        matrix.append(row)
    _enrich_matrix_people(matrix, visits)
    valid_n = sum(1 for visit in visits if visit.get("is_valid"))
    shown = sum(cell["count"] for row in matrix for cell in row["cells"])
    facts = _customer_facts(session, [code for code in stages])
    funnel = build_funnel(visits, facts)
    bands = _completeness_bands(visits, facts)
    alerts_raw: list[dict] = []
    alerts_raw.extend(_alerts(session, role=role, actor=actor))
    alerts_raw.extend(_stall_alerts(session, today=DEMO_TODAY, role=role))
    alerts_raw.extend(_matrix_alerts(visits, stages, facts, role=role))
    alerts_raw.extend(_completeness_alerts(bands, facts, role=role))
    alerts = _compact_board_alerts(alerts_raw)
    follow_owner = None if role in ("SALES_MGR", "GM") else actor
    follow_actions = _actions(session, follow_owner, DEMO_TODAY)[:5]
    return {
        "include_all": include_all,
        "note": funnel["note"],
        "outcomes": list(OUTCOMES),
        "stages": list(STAGE_COLS),
        "matrix": matrix,
        "funnel": funnel,
        "completeness": bands,
        "totals": {
            "shown_customers": shown,
            "valid_visits": valid_n,
            "lost": funnel["lost"],
            "conversion_pct": funnel.get("overall_pct"),
        },
        "alerts": alerts,
        "alerts_total": len(alerts_raw),
        "follow_actions": follow_actions,
    }


def _customer_facts(session: Session, codes: list[str]) -> dict[str, dict]:
    from db.tables import CrmContractRow

    facts: dict[str, dict] = {}
    for code in codes:
        cust = session.get(CrmCustomerRow, code)
        opps = session.scalars(
            select(CrmOpportunityRow).where(CrmOpportunityRow.customer_code == code)
        ).all()
        open_opps = [opp for opp in opps if not opp.lost_reason]
        lost = bool(opps) and not open_opps
        has_sample = (
            session.scalar(select(CrmSampleRow.code).where(CrmSampleRow.customer_code == code))
            is not None
        )
        has_quote = any(opp.customer_quote_amount is not None for opp in open_opps) or (
            session.scalar(
                select(CrmQuoteRow.code).where(
                    CrmQuoteRow.customer_code == code,
                    CrmQuoteRow.status != "VOID",
                )
            )
            is not None
        )
        has_sign = any(opp.project_code for opp in open_opps) or (
            session.scalar(
                select(CrmContractRow.contract_no).where(
                    CrmContractRow.customer_code == code,
                    CrmContractRow.status == "ACTIVE",
                )
            )
            is not None
        )
        facts[code] = {
            "name": cust.name if cust else code,
            "owner_sales": cust.owner_sales if cust else "",
            "lost": lost,
            "has_opp": bool(open_opps),
            "has_sample": has_sample and not lost,
            "has_quote": has_quote and not lost,
            "has_sign": has_sign and not lost,
        }
    return facts


def _completeness_bands(visits: list[dict], facts: dict[str, dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for visit in visits:
        code = visit.get("customer_code") or ""
        if not code:
            continue
        grouped.setdefault(code, []).append(visit)
    bands: dict[int, list[dict]] = {pct: [] for pct in (0, 20, 40, 60, 80, 100)}
    for code, rows in grouped.items():
        score = customer_completeness(rows)
        valid_n = sum(1 for row in rows if row.get("is_valid"))
        bands[score["percent"]].append(
            {
                "customer_code": code,
                "customer_name": (facts.get(code) or {}).get("name") or rows[-1].get("customer_name") or code,
                "owner_sales": (facts.get(code) or {}).get("owner_sales") or "",
                "percent": score["percent"],
                "filled": score["filled"],
                "missing": score["missing"],
                "visit_count": valid_n,
                "reached_sample": bool((facts.get(code) or {}).get("has_sample")),
            }
        )
    return [{"percent": pct, "count": len(bands[pct]), "people": bands[pct]} for pct in (0, 20, 40, 60, 80, 100)]


STALL_DAYS = 7


def _matrix_alerts(
    visits: list[dict],
    stages: dict[str, str],
    facts: dict[str, dict],
    *,
    role: str,
) -> list[dict]:
    if role not in ("SALES_MGR", "GM"):
        return []
    grouped: dict[str, list[dict]] = {}
    for visit in visits:
        if not visit.get("is_valid"):
            continue
        code = visit.get("customer_code") or ""
        if not code:
            continue
        grouped.setdefault(code, []).append(visit)
    alerts: list[dict] = []
    for code, rows in grouped.items():
        latest = max(rows, key=lambda row: int(row.get("id") or 0))
        outcome = _norm_outcome(str(latest.get("outcome") or ""))
        stage = stages.get(code, "还没成商机")
        fact = facts.get(code) or {}
        name = fact.get("name") or latest.get("customer_name") or code
        owner = fact.get("owner_sales") or latest.get("owner_sales") or ""
        valid_n = len(rows)
        if valid_n >= 2 and outcome == "关系建联" and stage == "还没成商机":
            alerts.append(
                {
                    "kind": "多次建联",
                    "owner_sales": owner,
                    "text": f"{name} 有效拜访 {valid_n} 次仍停在建联，尚未成商机",
                }
            )
        if outcome == "触达决策人" and not fact.get("has_sample") and not fact.get("lost"):
            alerts.append(
                {
                    "kind": "未打样",
                    "owner_sales": owner,
                    "text": f"{name} 已触达决策人，还没有打样",
                }
            )
    return alerts


def _stall_alerts(session: Session, *, today: date, role: str) -> list[dict]:
    if role not in ("SALES_MGR", "GM"):
        return []
    alerts: list[dict] = []
    for sample in session.scalars(select(CrmSampleRow)).all():
        if sample.current_stage == "结案" or (sample.result or "") == "确定方案":
            continue
        if sample.due_date is None:
            continue
        if (today - sample.due_date).days < STALL_DAYS:
            continue
        alerts.append(
            {
                "kind": "打样停滞",
                "owner_sales": sample.owner_sales,
                "text": f"样品 {sample.code} 预交 {sample.due_date.isoformat()}，打样/报价已停超过 {STALL_DAYS} 天",
            }
        )
    for opp in session.scalars(
        select(CrmOpportunityRow).where(CrmOpportunityRow.lost_reason.is_(None))
    ).all():
        if opp.project_code or opp.customer_quote_amount is not None:
            continue
        if opp.stage not in ("报价", "方案", "谈判"):
            continue
        anchor = opp.expect_close_date
        if anchor is None or (today - anchor).days < STALL_DAYS:
            continue
        alerts.append(
            {
                "kind": "报价停滞",
                "owner_sales": opp.owner_sales,
                "text": f"商机 {opp.name} 在报价阶段已超过 {STALL_DAYS} 天",
            }
        )
    return alerts


def _completeness_alerts(bands: list[dict], facts: dict[str, dict], *, role: str) -> list[dict]:
    if role not in ("SALES_MGR", "GM"):
        return []
    alerts = []
    for band in bands:
        for person in band["people"]:
            if person["visit_count"] >= 2 and person["percent"] < 100:
                alerts.append(
                    {
                        "kind": "拜访未齐",
                        "owner_sales": person["owner_sales"],
                        "text": f"{person['customer_name']} 有效拜访 {person['visit_count']} 次，完整度 {person['percent']}%",
                    }
                )
            if person["percent"] == 100 and not person["reached_sample"] and not (facts.get(person["customer_code"]) or {}).get("lost"):
                alerts.append(
                    {
                        "kind": "信息齐了还没打样",
                        "owner_sales": person["owner_sales"],
                        "text": f"{person['customer_name']} 拜访信息已齐，还没有打样",
                    }
                )
    return alerts


def _lost_count(session: Session, *, role: str, actor: str) -> int:
    n = 0
    for opp in session.scalars(select(CrmOpportunityRow)).all():
        if not opp.lost_reason:
            continue
        if _can_see_owner(role, actor, opp.owner_sales) and role != "RD":
            n += 1
    return n


def _alerts(session: Session, *, role: str, actor: str) -> list[dict]:
    if role not in ("SALES_MGR", "GM"):
        return []
    alerts = []
    goals = session.scalars(select(CrmSalesGoalRow).where(CrmSalesGoalRow.metric == "有效拜访")).all()
    for goal in goals:
        done = _done_counts(session, goal.owner_sales)["有效拜访"]
        if done < goal.target_qty:
            alerts.append(
                {
                    "kind": "拜访低于目标",
                    "owner_sales": goal.owner_sales,
                    "text": f"{goal.owner_sales} 有效拜访 {done}，目标 {goal.target_qty}",
                }
            )
    return alerts


def _column_status(opp: CrmOpportunityRow, sample: CrmSampleRow | None) -> dict:
    sample_status = "未到"
    if sample is not None:
        sample_status = "已完成" if sample.current_stage == "结案" else "进行中"
    cost_status = "已完成" if opp.sample_cost_material is not None else "未到"
    labor_status = "已完成" if opp.planned_labor_amount is not None else "未到"
    quote_status = "已完成" if opp.customer_quote_amount is not None else "未到"
    if opp.project_code:
        sign_status = "已转项目"
    else:
        sign_status = "未到"
    bom_status = "尚无计划人工" if opp.planned_labor_amount is None else "已完成"
    return {
        "打样": sample_status,
        "打样成本": cost_status,
        "工时BOM": bom_status,
        "内部报价": labor_status,
        "对客报价": quote_status,
        "签单": sign_status,
    }


def present_opportunity(session: Session, opp_id: int, *, role: str, actor: str) -> dict | None:
    ensure_sales_pack(session)
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        return None
    if not _can_see_owner(role, actor, opp.owner_sales):
        raise PermissionError("无权查看")
    sample = session.get(CrmSampleRow, opp.sample_code) if opp.sample_code else None
    if role == "RD" and (sample is None or sample.current_stage == "结案"):
        raise PermissionError("研发只看进行中的打样")
    cust = session.get(CrmCustomerRow, opp.customer_code)
    visits = session.scalars(
        select(CrmVisitRow)
        .where(CrmVisitRow.customer_code == opp.customer_code, CrmVisitRow.status == "CONFIRMED")
        .order_by(CrmVisitRow.id.desc())
    ).all()
    own_visits = [row for row in visits if row.owner_sales == opp.owner_sales]
    latest = own_visits[0] if own_visits else (visits[0] if visits else None)
    planned = _money(opp.planned_labor_amount)
    quoted = _money(opp.customer_quote_amount)
    gap = None
    if planned is not None and quoted is not None:
        gap = format((Decimal(quoted) - Decimal(planned)).quantize(Decimal("0.01")), "f")
    sample_payload = sample_detail(session, opp.sample_code) if opp.sample_code else None
    from db.tables import CrmContractRow

    contract = session.scalar(
        select(CrmContractRow)
        .where(CrmContractRow.customer_code == opp.customer_code, CrmContractRow.status == "ACTIVE")
        .limit(1)
    )
    contract_amount = _money(contract.contract_amount) if contract else None
    row = {
        "id": opp.id,
        "name": opp.name,
        "stage": opp.stage,
        "amount": float(opp.amount),
        "sales_name": opp.owner_sales,
        "expect_close_date": opp.expect_close_date.isoformat() if opp.expect_close_date else None,
        "sample_code": opp.sample_code,
        "customer_code": opp.customer_code,
        "customer_name": cust.name if cust else opp.customer_code,
        "customer": {
            "code": opp.customer_code,
            "name": cust.name if cust else opp.customer_code,
        },
        "sample": sample_payload,
        "owner_sales": opp.owner_sales,
        "grade": opp.grade,
        "lost_reason": opp.lost_reason,
        "project_code": opp.project_code,
        "urgent_order_no": opp.urgent_order_no,
        "column_status": _column_status(opp, sample),
        "visit_text": None
        if latest is None
        else {
            "narrative": latest.narrative,
            "outcome": latest.outcome,
            "next_step": latest.next_step,
            "next_date": latest.next_date.isoformat() if latest.next_date else None,
            "overdue": bool(latest.next_date and latest.next_date < DEMO_TODAY),
        },
        "sample_process": None
        if sample is None
        else {
            "code": sample.code,
            "stage": sample.current_stage,
            "item": sample.item_draft_name,
            "round_no": sample.round_no,
        },
        "sample_cost": None
        if opp.sample_cost_material is None
        else {
            "qty": opp.sample_cost_qty,
            "material": _money(opp.sample_cost_material),
            "labor_overhead": _money(opp.sample_cost_labor),
        },
        "bom": {"status": "尚无计划人工", "hours_wall": None, "hours_man": None},
        "internal_quote": None
        if planned is None
        else {"planned_labor": planned, "gap": gap},
        "customer_quote": None if quoted is None else {"amount": quoted},
        "sign": {
            "status": "已转项目" if opp.project_code else "未到",
            "contract_no": contract.contract_no if contract else None,
            "items": [],
            "contract_amount": contract_amount,
            "project_code": opp.project_code,
        },
    }
    from db.crm_opportunity_ui import enrich_detail

    enrich_detail(session, opp, row, role=role, actor=actor)
    return redact(row, role)


def set_sample_cost(session: Session, opp_id: int, *, qty: int, material: Decimal, labor: Decimal) -> None:
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        raise KeyError(opp_id)
    opp.sample_cost_qty = qty
    opp.sample_cost_material = material
    opp.sample_cost_labor = labor


def set_customer_quote(session: Session, opp_id: int, amount: Decimal) -> None:
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        raise KeyError(opp_id)
    opp.customer_quote_amount = amount


def set_planned_labor(session: Session, opp_id: int, amount: Decimal) -> None:
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        raise KeyError(opp_id)
    opp.planned_labor_amount = amount


def lose_opportunity(session: Session, opp_id: int, reason: str) -> None:
    if reason not in LOST_REASONS:
        raise ValueError("丢单原因要用：价格、交期、样品未过、客户取消、其他")
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        raise KeyError(opp_id)
    opp.lost_reason = reason


def grade_opportunity(session: Session, opp_id: int, grade: str) -> dict:
    if grade not in ("A", "B", "C"):
        raise ValueError("分级只能是 A、B、C")
    opp = session.get(CrmOpportunityRow, opp_id)
    if opp is None:
        raise KeyError(opp_id)
    opp.grade = grade
    if grade != "A":
        return {"grade": grade, "project_code": opp.project_code}
    code = opp.project_code or f"PRJ-OPP-{opp.id}"
    if session.get(DeliveryProjectRow, code) is None:
        session.add(
            DeliveryProjectRow(
                code=code,
                name=opp.name,
                customer_code=opp.customer_code,
                order_no="",
            )
        )
        for stage_code, _stage_name, names in STAGES:
            for step_no, step_name in enumerate(names, start=1):
                session.add(
                    DeliveryProjectStepRow(
                        project_code=code,
                        stage_code=stage_code,
                        step_no=step_no,
                        step_name=step_name,
                        event_date=None,
                        note="",
                    )
                )
    opp.project_code = code
    session.flush()
    return {"grade": grade, "project_code": code, "sign_status": "已转项目"}


def _scoped_visits(session: Session, *, role: str, actor: str) -> list[dict]:
    ensure_sales_pack(session)
    return _visits_for_board(session, role=role, actor=actor)


def mobile_customers(session: Session, *, role: str, actor: str, query: str = "") -> dict:
    visits = _scoped_visits(session, role=role, actor=actor)
    grouped: dict[str, list[dict]] = {}
    unlinked = []
    for visit in visits:
        code = visit.get("customer_code") or ""
        if not code:
            unlinked.append(visit)
            continue
        grouped.setdefault(code, []).append(visit)
    facts = _customer_facts(session, list(grouped))
    needle = query.strip()
    people = []
    for code, rows in grouped.items():
        name = (facts.get(code) or {}).get("name") or rows[-1].get("customer_name") or code
        if needle and needle not in name and needle not in code:
            continue
        latest = max(rows, key=lambda row: int(row.get("id") or 0))
        score = customer_completeness(rows)
        next_date = latest.get("next_date")
        people.append(
            {
                "customer_code": code,
                "customer_name": name,
                "percent": score["percent"],
                "missing": score["missing"],
                "last_outcome": latest.get("outcome"),
                "next_step": latest.get("next_step"),
                "next_date": next_date,
                "overdue": bool(next_date and next_date < DEMO_TODAY.isoformat()),
            }
        )
    people.sort(key=lambda row: (-int(row["overdue"]), row["percent"], row["customer_name"]))
    cold = []
    for visit in unlinked:
        name = visit.get("customer_name") or "未建客户"
        if needle and needle not in name:
            continue
        cold.append(
            {
                "visit_id": visit.get("id"),
                "customer_name": name,
                "is_valid": visit.get("is_valid"),
                "next_step": visit.get("next_step"),
                "next_date": visit.get("next_date"),
            }
        )
    return {"customers": people, "unlinked": cold}


def mobile_customer(session: Session, *, role: str, actor: str, code: str) -> dict | None:
    visits = [row for row in _scoped_visits(session, role=role, actor=actor) if row.get("customer_code") == code]
    if not visits and session.get(CrmCustomerRow, code) is None:
        return None
    facts = _customer_facts(session, [code])
    score = customer_completeness(visits)
    cust = session.get(CrmCustomerRow, code)
    if role in ("SALES", "SALES_ASSIST") and cust and not _can_see_owner(role, actor, cust.owner_sales) and not visits:
        raise PermissionError("无权查看")
    orders = [
        row
        for row in mobile_orders(session, role=role, actor=actor)
        if row.get("customer_code") == code
    ]
    timeline = sorted(visits, key=lambda row: int(row.get("id") or 0))
    return {
        "customer_code": code,
        "customer_name": cust.name if cust else code,
        "percent": score["percent"],
        "filled": score["filled"],
        "missing": score["missing"],
        "timeline": [
            {
                "id": row.get("id"),
                "narrative": row.get("narrative"),
                "outcome": row.get("outcome"),
                "is_valid": row.get("is_valid"),
                "next_step": row.get("next_step"),
                "next_date": row.get("next_date"),
            }
            for row in timeline
        ],
        "orders": orders,
    }


def mobile_orders(session: Session, *, role: str, actor: str) -> list[dict]:
    from db.plan_store import current_plan_version, load_schedule_result
    from db.prod_stats_seed import is_capacity_fixture_order
    from db.snapshot import header_order_no
    from db.tables import MdItemRow

    visits = _scoped_visits(session, role=role, actor=actor)
    visited = {row.get("customer_code") for row in visits if row.get("customer_code")}
    owner = actor if role == "SALES" else (ASSIST_TEAM[0] if role == "SALES_ASSIST" else None)
    version = current_plan_version(session)
    result = load_schedule_result(session, version) if version > 0 else None
    wos_by: dict[str, list] = {}
    if result is not None:
        for wo in result.wos:
            wos_by.setdefault(header_order_no(wo.source_order_no), []).append(wo)
    out = []
    for order in session.scalars(select(SoOrderRow).order_by(SoOrderRow.due_date)).all():
        if is_capacity_fixture_order(order.order_no, order.order_source):
            continue
        if owner and order.sales_name != owner and order.owner_sales != owner and order.customer_code not in visited:
            continue
        own = wos_by.get(order.order_no, [])
        ends = [wo.plan_end for wo in own if wo.plan_end]
        plan_end = max(ends) if ends else None
        earliest = None
        own_nos = {wo.wo_no for wo in own}
        if result is not None:
            dates = []
            for conflict in result.conflicts:
                if conflict.wo_no in own_nos and conflict.suggest and str(conflict.suggest).startswith("EARLIEST:"):
                    dates.append(date.fromisoformat(str(conflict.suggest).split(":", 1)[1]))
            for miss in result.unplaced:
                if miss.wo_no in own_nos and miss.earliest_finish:
                    dates.append(miss.earliest_finish)
            if dates:
                earliest = max(dates)
        talk = order_talk(has_tasks=bool(own), due=order.due_date, plan_end=plan_end, earliest=earliest)
        groups = []
        for wo in own:
            label = wo.group_code.value if hasattr(wo.group_code, "value") else str(wo.group_code)
            if label not in groups:
                groups.append(label)

        def _progress(kind: str) -> str | None:
            picked = [
                wo
                for wo in own
                if (wo.wo_type.value if hasattr(wo.wo_type, "value") else wo.wo_type) == kind
            ]
            if not picked:
                return None
            done = sum(int(wo.qty_board_done or 0) for wo in picked)
            plan = sum(int(wo.qty_board_plan or 0) for wo in picked)
            return f"{done}/{plan}"

        item = session.get(MdItemRow, order.item_code)
        out.append(
            {
                "order_no": order.order_no,
                "customer": order.customer,
                "customer_code": order.customer_code,
                "item_code": order.item_code,
                "item_name": item.item_name if item else order.item_code,
                "due_date": order.due_date.isoformat(),
                "talk": talk["talk"],
                "earliest": talk["earliest"],
                "plan_end": plan_end.isoformat() if plan_end else None,
                "groups": groups,
                "semi": _progress("SEMI"),
                "finished": _progress("FINISHED"),
            }
        )
    return out
