"""认链与探针：主题闭包、两队、日志门禁、点头不改状态。"""

from __future__ import annotations

from pathlib import Path

import yaml

from sealed_kb.ask import ask, classify_mode
from sealed_kb.store import load
from sealed_kb.workbench import (
    DEFAULT_THEME,
    FORBIDDEN_PROBE_WORDS,
    append_journal,
    append_nod,
    can_seal,
    journal_entries,
    list_themes,
    pending_items,
    probe_queue,
    seal_path,
    theme_closure,
    validate_journal_row,
)


def test_menu_and_insert_excluded_from_default_theme() -> None:
    items = pending_items(DEFAULT_THEME)
    ids = {item.shallow_id for item in items}
    assert "F.l3.menu_kb" not in ids
    assert "D.insert" not in ids
    assert "F.l3.due_change_via_approval" not in ids
    assert ids == {
        "F.l3.stg.demand",
        "F.l3.stg.schedule",
        "F.l3.stg.make",
        "F.l3.stg.fulfill",
    }
    schedule = next(item for item in items if item.shallow_id == "F.l3.stg.schedule")
    assert "F.l3.backward_place" in schedule.captured
    assert "F.l3.sph_and_hours" in schedule.captured
    assert "从交付模式上看" in schedule.speech


def test_unnamed_runtime_not_in_default_probe() -> None:
    queue = probe_queue(DEFAULT_THEME)
    anchors = {row.anchor for row in queue}
    assert "D.insert" not in anchors
    assert "F.l3.due_change_via_approval" not in anchors
    assert "F.l3.menu_kb" not in anchors
    assert "F.l1.mto_no_fg_stock" in anchors
    assert any(row.field == "何时不算" and row.anchor == "F.l1.mto_no_fg_stock" for row in queue)
    assert any(row.anchor.startswith("F.l3.stg.") for row in queue)


def test_probe_templates_forbid_industry_fiction() -> None:
    mto = next(
        row
        for row in probe_queue(DEFAULT_THEME)
        if row.anchor == "F.l1.mto_no_fg_stock" and row.field == "何时不算"
    )
    assert "按单" in mto.question or "成品仓" in mto.question or "零仓" in mto.question
    blob = " ".join(row.question for row in probe_queue(DEFAULT_THEME))
    for word in FORBIDDEN_PROBE_WORDS:
        assert word not in blob


def test_main_forest_theme_folds_to_item_and_task() -> None:
    items = pending_items("履约主林未封叶子")
    ids = {item.shallow_id for item in items}
    assert "D.item" in ids
    assert "D.wo_task" in ids
    assert "D.insert" not in ids
    item = next(row for row in items if row.shallow_id == "D.item")
    assert "D.bom" in item.captured
    assert "从对象上看" in item.speech


def test_runtime_insert_theme_requires_named_leaf() -> None:
    items = pending_items("运行结果·插单")
    ids = {item.shallow_id for item in items}
    assert "D.insert" in ids
    assert "D.trace" not in ids
    insert = items[0]
    assert "F.l3.backward_place" in insert.permits


def test_default_theme_list() -> None:
    themes = list_themes()
    names = [row["主题"] for row in themes]
    assert names[0] == DEFAULT_THEME
    assert themes[0]["默认打开"] is True
    assert "运行结果·插单" in names


def test_journal_reject_must_have_empty_delta() -> None:
    bad = {
        "编号": "P.test-reject",
        "状态": "拒收",
        "锚点": "F.l1.mto_no_fg_stock",
        "增量": {"新卡": [], "改栏": [{"编号": "F.l1.mto_no_fg_stock", "栏": "何时不算", "从": [], "到": ["x"]}], "新边": []},
    }
    assert "增量" in validate_journal_row(bad)
    ok = {
        "编号": "P.test-reject-ok",
        "状态": "拒收",
        "锚点": "F.l1.mto_no_fg_stock",
        "增量": {"新卡": [], "改栏": [], "新边": []},
    }
    assert validate_journal_row(ok) == ""


def test_journal_asked_cannot_have_field_patch() -> None:
    row = {
        "编号": "P.test-asked",
        "状态": "已问",
        "锚点": "F.l1.mto_no_fg_stock",
        "增量": {
            "新卡": [],
            "改栏": [{"编号": "F.l1.mto_no_fg_stock", "栏": "何时不算", "从": [], "到": ["内部返工"]}],
            "新边": [],
        },
    }
    assert "已问" in validate_journal_row(row)


def test_journal_delta_ids_must_exist() -> None:
    row = {
        "编号": "P.test-ghost",
        "状态": "已收假设",
        "锚点": "F.l1.mto_no_fg_stock",
        "增量": {"新卡": ["F.does.not.exist"], "改栏": [], "新边": []},
    }
    assert "F.does.not.exist" in validate_journal_row(row)


def test_nod_does_not_change_card_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sealed_kb.workbench._ledger_root", lambda: tmp_path)
    (tmp_path / "nods.yaml").write_text("记录: []\n", encoding="utf-8")
    before = load().facts["F.l3.stg.schedule"].status
    assert before == "假设"
    append_nod(
        {
            "叶子": "F.l3.stg.schedule",
            "主题": DEFAULT_THEME,
            "结果": "认",
            "链": ["F.l1.due_is_shared_reality", "F.l3.stg.schedule"],
            "谁": "PMC",
        }
    )
    assert load().facts["F.l3.stg.schedule"].status == "假设"
    assert can_seal("F.l3.stg.schedule", "认栏")[0] is False


def test_seal_only_path_hypothesis(tmp_path: Path) -> None:
    card_file = tmp_path / "cards.yaml"
    card_file.write_text(
        """卡片:
  - 编号: F.l3.stg.schedule
    名称: 倒排
    套: 运营
    层: 环节
    状态: 假设
    命题: 倒排
  - 编号: F.l4.keep
    名称: 投影
    套: 运营
    层: 投影
    状态: 假设
    命题: 文件
  - 编号: F.outside
    名称: 外头
    套: 运营
    层: 节点
    状态: 假设
    命题: 别动
""",
        encoding="utf-8",
    )
    seal_path(["F.l3.stg.schedule"], tmp_path)
    data = yaml.safe_load(card_file.read_text(encoding="utf-8"))
    by_id = {row["编号"]: row["状态"] for row in data["卡片"]}
    assert by_id["F.l3.stg.schedule"] == "已封印"
    assert by_id["F.l4.keep"] == "假设"
    assert by_id["F.outside"] == "假设"


def test_probe_intent_asks_queue_sentence() -> None:
    assert classify_mode("小白有没有要补充的") == "探针"
    result = ask("小白有没有要补充的")
    assert result.mode == "探针"
    assert result.verdict == "成立"
    assert result.slots
    assert "冷库" not in result.text
    assert "保质期" not in result.text


def test_ask_missing_insert_does_not_autolist() -> None:
    result = ask("已有计划上怎么插单")
    assert result.verdict == "缺前提"
    assert result.workbench_kind in {None, ""}


def test_ask_unsealed_stage_hints_pending() -> None:
    result = ask("需求与约定确认")
    assert result.verdict == "缺前提"
    assert result.workbench_kind == "pending"
    assert result.workbench_id == "F.l3.stg.demand"
    assert "待确认" in result.text


def test_theme_closure_excludes_projection() -> None:
    closed = theme_closure(DEFAULT_THEME)
    assert "F.l3.menu_kb" not in closed.path_ids
    assert "F.l4.br27_no_write_due" not in closed.path_ids


def test_append_journal_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sealed_kb.workbench._ledger_root", lambda: tmp_path)
    (tmp_path / "probe_journal.yaml").write_text("记录: []\n", encoding="utf-8")
    append_journal(
        {
            "编号": "P.test-1",
            "状态": "已问",
            "锚点": "F.l1.mto_no_fg_stock",
            "探针栏": "何时不算",
            "小白问": "内部返工还算吗？",
            "增量": {"新卡": [], "改栏": [], "新边": []},
        }
    )
    rows = journal_entries()
    assert rows[-1]["编号"] == "P.test-1"
    assert rows[-1]["状态"] == "已问"
