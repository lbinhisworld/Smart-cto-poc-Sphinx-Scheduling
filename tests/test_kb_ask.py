"""顾问询问：只走已封印槽，对不上就停。"""

from __future__ import annotations

from sealed_kb.ask import ask, classify_mode, suggestions


def test_classify_three_inquiry_modes() -> None:
    assert classify_mode("为什么不能改交期") == "原理"
    assert classify_mode("冲突标红太死板了，应该自动往后延") == "质疑"
    assert classify_mode("系统到底怎么折算到版") == "细节"
    assert classify_mode("E2 了能不能改订单交期") == "原理"


def test_e2_due_question_explains_no_rewrite() -> None:
    result = ask("E2 了能不能改订单交期", role="销售")
    assert result.verdict == "成立"
    assert result.mode == "原理"
    assert result.claim == "C.give_earliest_keep_due"
    assert "D.order.due_date" in result.slots
    assert "不会改订单日期" in result.text
    assert "F.l1.due_is_shared_reality" in result.chain


def test_board_question() -> None:
    result = ask("算工时能直接拿盒去除 SPH 吗")
    assert result.verdict == "成立"
    assert result.claim == "C.normalize_to_board"
    assert "归一到版" in result.text


def test_unknown_question_does_not_invent() -> None:
    result = ask("冷链机台 APS 怎么排")
    assert result.verdict == "缺前提"
    assert result.missing
    assert result.claim is None
    titles = suggestions()
    assert any("交期" in t for t in titles)


def test_hypothesis_slot_stops() -> None:
    result = ask("已有计划上怎么插单")
    assert result.verdict == "缺前提"
    assert "D.insert" in result.missing


def test_what_is_work_order() -> None:
    result = ask("什么是工单")
    assert result.verdict == "成立"
    assert result.slots == ["D.wo"]
    assert "成品" in result.text or "半成品" in result.text


def test_what_is_unsealed_item_stops() -> None:
    result = ask("什么是装饰件品项")
    assert result.verdict == "缺前提"
    assert "D.item" in result.missing


def test_what_is_work_order_is_define() -> None:
    result = ask("什么是工单")
    assert result.mode == "定义"


def test_why_due_builds_l1_chain() -> None:
    result = ask("为什么排程不能改订单交期", role="销售")
    assert result.verdict == "成立"
    assert result.mode == "原理"
    assert "F.l1.due_is_shared_reality" in result.chain
    assert "F.l2.sales_owns_promise" in result.chain
    assert "F.l3.due_change_via_approval" in result.chain
    assert "【回答】" in result.text
    assert "从交付模式上看" in result.text
    assert "因此，从权责上看" in result.text
    assert "所以，" in result.text
    assert result.text.index("【回答】") < result.text.index("从交付模式上看")
    assert result.text.index("从交付模式上看") < result.text.index("因此，从权责上看")
    assert result.text.index("因此，从权责上看") < result.text.index("所以，")
    assert "不会改订单日期" in result.text or "约定" in result.text


def test_objection_defends_then_asks_break() -> None:
    result = ask("遇到冲突就标红太死板了，应该自动往后延")
    assert result.mode == "质疑"
    assert result.verdict == "成立"
    assert "F.l1.due_is_shared_reality" in result.chain
    assert "断" in result.text
    assert "解析员" in result.text
    assert "构拟" not in result.text
    assert "不受 BR-27" not in result.text


def test_detail_board_leads_with_rule() -> None:
    result = ask("系统到底怎么折算到版")
    assert result.mode == "细节"
    assert result.verdict == "成立"
    assert result.claim == "C.normalize_to_board"
    assert "归一" in result.text or "换成版" in result.text
    assert "从交付模式上看" in result.text or "所以，" in result.text


def test_rework_does_not_bypass_br27() -> None:
    result = ask("内部返工能不能自动改日")
    assert result.verdict == "不适用"
    assert "约定日" in result.text or "写回" in result.text
    assert "构拟" not in result.text
    assert "不受 BR-27" not in result.text
