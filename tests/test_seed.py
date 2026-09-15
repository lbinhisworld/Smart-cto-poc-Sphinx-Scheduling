"""阶段 0 验收：种子加载与引擎导入边界。"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

from tests.conftest import load_seed


def test_seed_demo_catalog_three_archetypes():
    seed = load_seed()
    cat = seed["meta"]["demo_catalog"]
    assert len(cat["MANUAL_NO_SEMI"]["orders"]) == 3
    assert len(cat["MOLD_WITH_SEMI"]["orders"]) == 3
    assert len(cat["POURING_NO_SEMI"]["orders"]) == 3
    assert "MULTI_SEMI_COMBO" in cat
    assert len(seed["items"]) == 15
    assert len(seed["orders"]) == 12
    assert seed["stock"]["S2"] == 130
    assert seed["stock"]["S6"] == 0


def test_conftest_builds_schedule_input(schedule_input):
    assert schedule_input.today == date(2026, 9, 15)
    assert len(schedule_input.items) == 15
    assert len(schedule_input.orders) == 12
    assert schedule_input.stock["S2"] == Decimal("130")
    assert schedule_input.config.reserved_ratio == Decimal("0")


def test_engine_has_no_forbidden_imports():
    engine_dir = Path(__file__).resolve().parents[1] / "engine"
    forbidden_modules = {"db", "requests", "httpx", "urllib", "http.client"}
    offenders: list[str] = []
    for path in engine_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden_modules:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in forbidden_modules:
                    offenders.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Attribute) and node.attr == "now":
                offenders.append(f"{path.name}: datetime.now")
            elif isinstance(node, ast.Attribute) and node.attr == "today":
                if isinstance(node.value, ast.Name) and node.value.id in {"date", "datetime"}:
                    offenders.append(f"{path.name}: {node.value.id}.today")
    assert offenders == []
