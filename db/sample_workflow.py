"""打样流程 · 环节子表。"""

from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.tables import CrmCustomerRow, CrmSampleRow, CrmSampleStepRow

DEFAULT_STAGES = ("申请", "打样", "寄样", "客户反馈", "结案")
STEP_STAGES = ("申请", "打样", "寄样", "客户反馈")
_ROUND_IN_TEXT = re.compile(r"第(\d+)轮")


def _parse_images(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if str(x).strip()]


def _infer_round_from_text(text: str) -> int | None:
    m = _ROUND_IN_TEXT.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _step_round_no(r: CrmSampleStepRow) -> int | None:
    if r.round_no is not None and r.round_no > 0:
        return r.round_no
    if r.stage == "打样":
        return _infer_round_from_text(r.product_desc) or _infer_round_from_text(r.situation_desc)
    return None


def _step_to_dict(r: CrmSampleStepRow) -> dict:
    rnd = _step_round_no(r)
    return {
        "step_no": r.step_no,
        "stage": r.stage,
        "event_date": r.event_date.isoformat(),
        "product_desc": r.product_desc,
        "situation_desc": r.situation_desc,
        "evidence_text": r.evidence_text or "",
        "evidence_images": _parse_images(r.evidence_images_json),
        "is_final": bool(r.is_final),
        "round_no": rnd,
    }


def _da_yang_rounds(steps: list[CrmSampleStepRow]) -> list[int]:
    out: list[int] = []
    for s in steps:
        if s.stage != "打样":
            continue
        rnd = _step_round_no(s)
        if rnd:
            out.append(rnd)
    return out


def _assign_round_for_new_step(
    sample: CrmSampleRow,
    existing: list[CrmSampleStepRow],
    *,
    stage: str,
    is_rework: bool,
    is_final: bool,
) -> int | None:
    if is_final:
        return sample.round_no or 1
    if stage != "打样":
        return sample.round_no or None
    dy_rounds = _da_yang_rounds(existing)
    if is_rework and dy_rounds:
        return max(dy_rounds)
    if dy_rounds:
        return max(dy_rounds) + 1
    return sample.round_no or 1


def _auto_product_desc(sample: CrmSampleRow, *, stage: str, round_no: int | None, product_desc: str) -> str:
    base = (product_desc or sample.item_draft_name).strip()
    if stage != "打样" or round_no is None:
        return base or sample.item_draft_name
    if _infer_round_from_text(base) is not None:
        return base
    suffix = f"第{round_no}轮"
    if base == sample.item_draft_name or not base:
        return f"{sample.item_draft_name} {suffix}"
    return f"{base} {suffix}"


def list_steps(session: Session, sample_code: str) -> list[dict]:
    rows = session.scalars(
        select(CrmSampleStepRow)
        .where(CrmSampleStepRow.sample_code == sample_code)
        .order_by(CrmSampleStepRow.step_no)
    ).all()
    return [_step_to_dict(r) for r in rows]


def _fallback_steps(sample: CrmSampleRow) -> list[dict]:
    """无子表种子时按当前阶段生成演示环节。"""
    idx = DEFAULT_STAGES.index(sample.current_stage) if sample.current_stage in DEFAULT_STAGES else 0
    steps: list[dict] = []
    base = sample.due_date or date(2026, 9, 15)
    for i, st in enumerate(DEFAULT_STAGES[: idx + 1]):
        steps.append(
            {
                "step_no": i + 1,
                "stage": st,
                "event_date": base.isoformat(),
                "product_desc": sample.item_draft_name,
                "situation_desc": f"{st}环节记录（演示自动生成）",
                "evidence_text": "",
                "evidence_images": [],
                "is_final": st == "结案",
                "round_no": sample.round_no if st == "打样" else None,
            }
        )
    return steps


def preview_next_round(
    session: Session,
    code: str,
    *,
    stage: str,
    is_rework: bool = False,
) -> dict:
    sample = session.get(CrmSampleRow, code)
    if sample is None:
        raise KeyError(code)
    existing = session.scalars(
        select(CrmSampleStepRow)
        .where(CrmSampleStepRow.sample_code == code)
        .order_by(CrmSampleStepRow.step_no)
    ).all()
    rnd = _assign_round_for_new_step(sample, list(existing), stage=stage, is_rework=is_rework, is_final=False)
    return {
        "stage": stage,
        "round_no": rnd,
        "sample_round_no": sample.round_no,
        "is_rework": is_rework,
    }


def add_sample_step(
    session: Session,
    code: str,
    *,
    stage: str,
    event_date: date,
    product_desc: str = "",
    situation_desc: str = "",
    evidence_text: str = "",
    evidence_images: list[str] | None = None,
    is_final: bool = False,
    is_rework: bool = False,
) -> dict:
    sample = session.get(CrmSampleRow, code)
    if sample is None:
        raise KeyError(code)
    if sample.current_stage == "结案":
        raise ValueError("已结案，不能再新增打样记录")
    if stage not in STEP_STAGES and not is_final:
        raise ValueError(f"环节须为 {' / '.join(STEP_STAGES)} 之一")
    text = (evidence_text or "").strip()
    images = [str(x).strip() for x in (evidence_images or []) if str(x).strip()]
    if is_final and not text and not images:
        raise ValueError("最后定稿须上传聊天截图或填写文字描述作为完结证据")

    existing = session.scalars(
        select(CrmSampleStepRow)
        .where(CrmSampleStepRow.sample_code == code)
        .order_by(CrmSampleStepRow.step_no)
    ).all()
    step_round = _assign_round_for_new_step(
        sample,
        list(existing),
        stage=stage,
        is_rework=is_rework,
        is_final=is_final,
    )
    max_no = session.scalar(
        select(func.max(CrmSampleStepRow.step_no)).where(CrmSampleStepRow.sample_code == code)
    )
    next_no = int(max_no or 0) + 1
    row_stage = "结案" if is_final else stage
    final_product = _auto_product_desc(
        sample,
        stage=stage if not is_final else "客户反馈",
        round_no=step_round,
        product_desc=product_desc,
    )
    session.add(
        CrmSampleStepRow(
            sample_code=code,
            step_no=next_no,
            stage=row_stage,
            event_date=event_date,
            product_desc=final_product,
            situation_desc=situation_desc or (text if is_final else ""),
            evidence_text=text,
            evidence_images_json=json.dumps(images, ensure_ascii=False),
            is_final=is_final,
            round_no=step_round,
        )
    )
    if is_final:
        sample.current_stage = "结案"
        sample.result = "CLOSED"
    else:
        sample.current_stage = stage
        if stage == "打样" and step_round is not None:
            sample.round_no = step_round
    session.flush()
    detail = sample_detail(session, code)
    if detail is None:
        raise KeyError(code)
    return detail


def close_sample(
    session: Session,
    code: str,
    *,
    evidence_text: str = "",
    evidence_images: list[str] | None = None,
    event_date: date | None = None,
) -> dict:
    """兼容旧接口：等价于新增一条「最后定稿」记录。"""
    return add_sample_step(
        session,
        code,
        stage="客户反馈",
        event_date=event_date or date(2026, 9, 15),
        situation_desc=evidence_text or "客户反馈截图结案",
        evidence_text=evidence_text,
        evidence_images=evidence_images,
        is_final=True,
    )


def sample_detail(session: Session, code: str) -> dict | None:
    sample = session.get(CrmSampleRow, code)
    if sample is None:
        return None
    customer = session.get(CrmCustomerRow, sample.customer_code)
    steps = list_steps(session, code)
    if not steps:
        steps = _fallback_steps(sample)
    return {
        "code": sample.code,
        "item_draft_name": sample.item_draft_name,
        "current_stage": sample.current_stage,
        "round_no": sample.round_no,
        "owner_sales": sample.owner_sales,
        "due_date": sample.due_date.isoformat() if sample.due_date else None,
        "is_old_product": sample.is_old_product,
        "result": sample.result,
        "customer": {
            "code": sample.customer_code,
            "name": customer.name if customer else sample.customer_code,
        },
        "stages_pipeline": list(DEFAULT_STAGES),
        "step_stages": list(STEP_STAGES),
        "steps": steps,
    }
