"""演示线拟真展示名校验。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEXICON_PATH = ROOT / "seed" / "guided_demo_lexicon.json"

_BANNED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"测试\d*", re.I),
    re.compile(r"^客户\d+$"),
    re.compile(r"^产品\d+$"),
    re.compile(r"^(销售|仓库|财务|测试).{0,2}$"),
    re.compile(r"^Customer\s+[A-Z]$", re.I),
    re.compile(r"^test\s+user$", re.I),
)

_ROLE_PUN_NAMES = frozenset({"赵模具", "钱浇注"})


def load_lexicon() -> dict:
    if not LEXICON_PATH.is_file():
        return {}
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


class RealismError(ValueError):
    pass


def validate_display_name(display: str, *, entity_id: str | None = None) -> None:
    text = (display or "").strip()
    if len(text) < 2:
        raise RealismError(f"展示名过短: {display!r}")
    if entity_id and text == entity_id.strip():
        raise RealismError("展示名不得与内部编码相同")
    for pat in _BANNED_PATTERNS:
        if pat.search(text):
            raise RealismError(f"展示名命中禁止模式: {display!r}")
    if text in _ROLE_PUN_NAMES:
        raise RealismError(f"展示名不得使用占位 pun 名: {display!r}")


def assert_realistic_bundle(refs: list[dict]) -> None:
    for ref in refs:
        validate_display_name(str(ref.get("display") or ""), entity_id=str(ref.get("entity_id") or ""))


def scan_lexicon() -> None:
    lex = load_lexicon()
    for name in lex.get("sales_names", []) + lex.get("operator_names", []):
        validate_display_name(str(name))
    for story in lex.get("story_bundles", []):
        validate_display_name(str(story.get("customer_name", "")))
        validate_display_name(str(story.get("item_name", "")))
        validate_display_name(str(story.get("opportunity_title", "")))
        validate_display_name(str(story.get("owner_sales", "")))
