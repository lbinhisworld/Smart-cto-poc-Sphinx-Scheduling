"""交期锚：prove / explain（先写断言）。"""

from __future__ import annotations

from sealed_kb.reasoner import explain, load, prove

CTX_E2 = {"按单", "无备货", "有客户约定", "E2"}
CTX_REWORK = {"内部返工"}


def test_e2_holds_and_says_no_due_rewrite() -> None:
    result = prove("C.give_earliest_keep_due", CTX_E2)
    assert result.verdict == "成立"
    assert "F.l1.due_is_shared_reality" in result.chain
    text = explain("C.give_earliest_keep_due", CTX_E2, "销售")
    assert "不会改订单日期" in text


def test_internal_rework_inapplicable() -> None:
    result = prove("C.give_earliest_keep_due", CTX_REWORK)
    assert result.verdict == "不适用"


def test_board_and_crew_explain() -> None:
    assert "归一到版" in explain("C.normalize_to_board", set())
    assert "禁止再乘人数" in explain("C.crew_no_double_count", set())


def test_hypothesis_does_not_breed() -> None:
    kb = load()
    kb.facts["F.l1.due_is_shared_reality"].status = "假设"
    result = prove("C.give_earliest_keep_due", CTX_E2, kb)
    assert result.verdict == "缺前提"
    assert "F.l1.due_is_shared_reality" in result.missing
