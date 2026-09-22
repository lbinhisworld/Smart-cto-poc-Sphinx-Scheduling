"""封印库：树/卡/询问只读；点头与封印只写台账或路径上的假设卡。"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

_PACKAGES = Path(__file__).resolve().parents[3] / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from sealed_kb.ask import ask, suggestions
from sealed_kb.store import (
    card_view,
    domain_tree,
    load,
    ops_cards,
    ops_projections,
    ops_stream_tree,
    ops_unattached,
    runtime_tree,
)
from sealed_kb.workbench import (
    DEFAULT_THEME,
    can_nod_role,
    can_seal_role,
    journal_entries,
    list_themes,
    pending_as_dict,
    probe_as_dict,
    record_nod,
    seal_leaf,
)

router = APIRouter(prefix="/api/kb", tags=["kb"])


class AskBody(BaseModel):
    question: str = Field(min_length=1)
    role: str | None = None


class NodBody(BaseModel):
    叶子: str = Field(min_length=1)
    主题: str = DEFAULT_THEME
    结果: str = Field(min_length=1)
    断在: str = ""
    栏: str = ""
    探针: list[str] = Field(default_factory=list)


class SealBody(BaseModel):
    叶子: str = Field(min_length=1)
    主题: str = DEFAULT_THEME


def _ok(data):
    return {"code": 0, "message": "", "data": data}


def _role(x_demo_role: str | None) -> str:
    return x_demo_role or ""


@router.get("/tree")
def get_tree():
    return _ok({"roots": domain_tree(), "runtime": runtime_tree(), "readonly": True})


@router.get("/ops")
def get_ops():
    return _ok(
        {
            "roots": ops_stream_tree(),
            "unattached": ops_unattached(),
            "projections": ops_projections(),
            "cards": ops_cards(),
            "readonly": True,
        }
    )


@router.get("/card/{card_id}")
def get_card(card_id: str):
    kb = load()
    fact = kb.facts.get(card_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return _ok(card_view(fact, kb))


@router.get("/suggestions")
def get_suggestions():
    return _ok({"questions": suggestions()})


@router.post("/ask")
def post_ask(body: AskBody):
    result = ask(body.question, body.role)
    return _ok(
        {
            "verdict": result.verdict,
            "question": result.question,
            "intent": result.intent,
            "mode": result.mode,
            "slots": result.slots,
            "missing": result.missing,
            "claim": result.claim,
            "chain": result.chain,
            "text": result.text,
            "suggestions": result.suggestions,
            "workbench_kind": result.workbench_kind,
            "workbench_theme": result.workbench_theme,
            "workbench_id": result.workbench_id,
            "readonly": True,
        }
    )


@router.get("/themes")
def get_themes():
    return _ok({"themes": list_themes(), "default": DEFAULT_THEME, "readonly": True})


@router.get("/pending")
def get_pending(theme: str = DEFAULT_THEME):
    try:
        return _ok(pending_as_dict(theme))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/probe")
def get_probe(theme: str = DEFAULT_THEME):
    try:
        return _ok(probe_as_dict(theme))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/journal")
def get_journal():
    return _ok({"entries": journal_entries(), "readonly": True})


@router.post("/nod")
def post_nod(body: NodBody, x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
    role = _role(x_demo_role)
    if not can_nod_role(role):
        raise HTTPException(status_code=403, detail="无权点头")
    try:
        row = record_nod(
            leaf=body.叶子,
            theme=body.主题,
            result=body.结果,
            role=role,
            break_layer=body.断在,
            field=body.栏,
            probes=body.探针,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"row": row, "sealed": False})


@router.post("/seal")
def post_seal(body: SealBody, x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
    role = _role(x_demo_role)
    if not can_seal_role(role):
        raise HTTPException(status_code=403, detail="无权封印")
    try:
        changed = seal_leaf(body.叶子, body.主题, role)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _ok({"changed": changed})
