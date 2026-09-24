"""商机列表/详情 · 来源、阶段门面、意向产品。"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crm_follows import list_follows
from db.tables import CrmLeadRow, CrmOpportunityRow, CrmQuoteRow, CrmSampleRow


def _meta(opp: CrmOpportunityRow) -> dict:
    raw = getattr(opp, "meta_json", None) or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def infer_source(session: Session, opp: CrmOpportunityRow) -> str:
    meta = _meta(opp)
    if meta.get("source"):
        return str(meta["source"])
    lead = session.scalar(
        select(CrmLeadRow)
        .where(CrmLeadRow.customer_code == opp.customer_code, CrmLeadRow.status == "已转化")
        .limit(1)
    )
    if lead is not None:
        return "线索转入"
    return "客户新增"


def stage_label(session: Session, opp: CrmOpportunityRow) -> str:
    if opp.lost_reason:
        return "已丢单"
    if opp.project_code:
        return "已签单"
    if opp.stage in ("成交", "谈判"):
        return "已签单" if opp.project_code else "方案报价"
    sample = None
    if opp.sample_code:
        sample = session.get(CrmSampleRow, opp.sample_code)
    if sample is None:
        sample = session.scalar(
            select(CrmSampleRow)
            .where(CrmSampleRow.customer_code == opp.customer_code, CrmSampleRow.owner_sales == opp.owner_sales)
            .order_by(CrmSampleRow.code.desc())
            .limit(1)
        )
    if sample is None or sample.current_stage == "结案":
        quote = session.scalar(
            select(CrmQuoteRow)
            .where(CrmQuoteRow.customer_code == opp.customer_code, CrmQuoteRow.status.in_(("SUBMITTED", "APPROVED")))
            .limit(1)
        )
        if quote:
            return "方案报价"
        return "尚未打样"
    if sample.current_stage != "结案":
        return "打样中"
    return "方案报价"


def enrich_list_row(session: Session, row: dict, opp: CrmOpportunityRow) -> dict:
    row["source"] = infer_source(session, opp)
    row["stage_label"] = stage_label(session, opp)
    row["created_at"] = _meta(opp).get("created_at") or ""
    return row


def enrich_detail(session: Session, opp: CrmOpportunityRow, base: dict, *, role: str, actor: str) -> dict:
    meta = _meta(opp)
    follows = list_follows(session, role=role, actor=actor, opportunity_id=opp.id)
    latest = follows[0] if follows else None
    products = meta.get("intent_products") or [
        {
            "item_name": opp.name,
            "spec": "",
            "unit": "BOX",
            "suggest_price": float(opp.amount),
            "qty": 1,
        }
    ]
    base.update(
        {
            "source": infer_source(session, opp),
            "stage_label": stage_label(session, opp),
            "win_rate": meta.get("win_rate"),
            "need_sample": meta.get("need_sample", "否"),
            "is_repurchase": meta.get("is_repurchase", "否"),
            "owner_dept": meta.get("owner_dept", "销售部"),
            "created_at": meta.get("created_at"),
            "next_communication": {
                "date": latest.get("next_follow_date") if latest else None,
                "content": latest.get("content") if latest else "",
                "place": meta.get("comm_place", ""),
            },
            "intent_products": products,
            "follow_records": follows,
            "amount_upper": _amount_upper(float(opp.amount)),
        }
    )
    return base


def _amount_upper(amount: float) -> str:
    return f"{amount:,.2f}元"


def create_opportunity_for_customer(
    session: Session,
    *,
    customer_code: str,
    name: str,
    amount: float,
    owner_sales: str,
    expect_close_date: date | None,
    actor: str,
    source: str = "客户新增",
) -> dict:
    from db.crm_customer_portal import _set_cf
    from db.tables import CrmCustomerRow

    cust = session.get(CrmCustomerRow, customer_code)
    if cust is None:
        raise ValueError("客户不存在")
    if cust.owner_sales and cust.owner_sales != actor and actor:
        pass
    opp = CrmOpportunityRow(
        name=name.strip() or f"{cust.name}·商机",
        customer_code=customer_code,
        stage="线索",
        amount=str(amount),
        owner_sales=owner_sales or cust.owner_sales or actor,
        expect_close_date=expect_close_date,
    )
    if hasattr(opp, "meta_json"):
        opp.meta_json = json.dumps(
            {
                "source": source,
                "created_at": date(2026, 9, 15).isoformat(),
                "owner_dept": "销售部",
                "win_rate": 30,
                "need_sample": "是",
                "is_repurchase": "否",
            },
            ensure_ascii=False,
        )
    session.add(opp)
    session.flush()
    if cust.owner_sales:
        _set_cf(cust, {"crm_status": "商机预备"})
    return {"id": opp.id, "name": opp.name}


OPPORTUNITY_FUNNEL_STAGES: tuple[str, ...] = ("尚未打样", "打样中", "方案报价", "已签单")


def _pipeline_rank(label: str) -> int:
    if label in OPPORTUNITY_FUNNEL_STAGES:
        return OPPORTUNITY_FUNNEL_STAGES.index(label)
    return 0


def opportunity_funnel(
    session: Session, *, role: str, owner_filter: str | None = None
) -> dict:
    """与商机列表同范围的阶段累计漏斗（相邻格转化率 = 下一格 ÷ 本格）。"""
    from db.crm_queries import list_opportunities

    rows = list_opportunities(session, role=role, owner_filter=owner_filter)
    active_labels: list[str] = []
    lost = 0
    for row in rows:
        label = str(row.get("stage_label") or row.get("stage") or "")
        if label == "已丢单":
            lost += 1
            continue
        active_labels.append(label)

    rank = {name: index for index, name in enumerate(OPPORTUNITY_FUNNEL_STAGES)}
    counts = {
        stage: sum(1 for lb in active_labels if _pipeline_rank(lb) >= rank[stage])
        for stage in OPPORTUNITY_FUNNEL_STAGES
    }
    steps: list[dict] = []
    for index, stage in enumerate(OPPORTUNITY_FUNNEL_STAGES):
        nxt = (
            OPPORTUNITY_FUNNEL_STAGES[index + 1]
            if index + 1 < len(OPPORTUNITY_FUNNEL_STAGES)
            else None
        )
        rate = None
        if nxt and counts[stage]:
            rate = round(counts[nxt] * 100 / counts[stage])
        steps.append({"stage": stage, "count": counts[stage], "to_next_pct": rate})

    overall = (
        round(counts["已签单"] * 100 / counts["尚未打样"])
        if counts["尚未打样"]
        else None
    )
    scope = "my" if role in ("SALES", "SALES_ASSIST") and owner_filter else "all"
    return {
        "steps": steps,
        "lost": lost,
        "overall_pct": overall,
        "scope": scope,
        "note": "累计口径：到达该阶段及之后的商机数；相邻转化率 = 下一格 ÷ 本格。",
    }
