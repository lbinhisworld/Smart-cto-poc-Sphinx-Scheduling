"""运营价值流：主张 → 流 → 环节 → 许可；旧 explain 不断。"""

from __future__ import annotations

from sealed_kb.ask import ask
from sealed_kb.reasoner import explain
from sealed_kb.roles import harvest_complete
from sealed_kb.store import (
    Fact,
    KnowledgeBase,
    card_view,
    format_ops_tree,
    format_tree,
    load,
    ops_stream_tree,
    ops_unattached,
)

_STREAM = "F.l3.vsm.order_to_delivery"
_STAGES = (
    "F.l3.stg.demand",
    "F.l3.stg.schedule",
    "F.l3.stg.make",
    "F.l3.stg.fulfill",
)
_FORBIDDEN = ("冷链", "茶饮", "原料组", "生巧组", "机台 APS")
_DEMOTE_L1 = {"F.l1.board_is_meter", "F.l1.crew_in_sph"}
_CTX_E2 = {"按单", "无备货", "有客户约定", "E2"}


def test_schema_layers_include_stream_and_stage() -> None:
    kb = load()
    assert kb.facts[_STREAM].layer == "价值流"
    for sid in _STAGES:
        assert kb.facts[sid].layer == "环节"


def test_ops_under_matches_belongs() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.pack != "运营":
            continue
        derived = set(fact.children)
        declared = set(kb.declared_under(fact.id))
        if derived and not declared:
            bad.append(f"{fact.id}:有孩子但未写其下")
        if declared != derived:
            bad.append(f"{fact.id}:其下{sorted(declared)}≠反查{sorted(derived)}")
    assert bad == [], bad


def test_stream_supports_due_and_mto() -> None:
    kb = load()
    stream = kb.facts[_STREAM]
    assert "F.l1.due_is_shared_reality" in stream.supports
    assert "F.l1.mto_no_fg_stock" in stream.supports
    assert stream.status == "已封印"
    assert kb.facts["F.l1.mto_no_fg_stock"].status == "已封印"


def test_every_stream_supports_at_least_one_claim() -> None:
    kb = load()
    empty = [f.id for f in kb.facts.values() if f.layer == "价值流" and not f.supports]
    assert empty == [], empty
    assert kb.streams_for_claim("F.l1.due_is_shared_reality") == [_STREAM]
    assert kb.streams_for_claim("F.l1.mto_no_fg_stock") == [_STREAM]


def test_sealed_vp_has_stream() -> None:
    kb = load()
    streams = [f for f in kb.facts.values() if f.layer == "价值流"]
    covered: set[str] = set()
    for stream in streams:
        covered.update(stream.supports)
    missing = []
    for fact in kb.facts.values():
        if fact.pack != "运营" or fact.layer != "主张" or fact.status != "已封印":
            continue
        if fact.id in _DEMOTE_L1:
            continue
        if fact.id not in covered:
            missing.append(fact.id)
    assert missing == [], missing


def test_stages_have_children_or_gap() -> None:
    kb = load()
    for sid in _STAGES:
        fact = kb.facts[sid]
        note = str(fact.raw.get("说明") or "")
        assert fact.children or "缺口" in note, sid


def test_eight_protocols_belong_to_stages() -> None:
    kb = load()
    expected = {
        "F.l3.due_change_via_approval": "F.l3.stg.demand",
        "F.l3.normalize_to_board": "F.l3.stg.demand",
        "F.l3.backward_place": "F.l3.stg.schedule",
        "F.l3.finished_then_semi": "F.l3.stg.schedule",
        "F.l3.kitting": "F.l3.stg.schedule",
        "F.l3.fence_ripple": "F.l3.stg.schedule",
        "F.l3.sph_and_hours": "F.l3.stg.schedule",
        "F.l3.soft_conflicts": "F.l3.stg.fulfill",
    }
    for nid, parent in expected.items():
        assert kb.facts[nid].belongs_to == parent, nid


def test_make_stage_has_attendance_and_pool() -> None:
    kb = load()
    kids = set(kb.children_of("F.l3.stg.make"))
    assert "F.l3.attendance_cap" in kids
    assert "F.l3.unfinished_to_pool" in kids
    assert kb.facts["F.l3.attendance_cap"].status == "假设"
    assert kb.facts["F.l3.unfinished_to_pool"].status == "假设"


def test_menus_modules_demo_roles_are_projections() -> None:
    kb = load()
    for fact in kb.facts.values():
        if fact.id.startswith(("F.l3.menu_", "F.l3.mod_", "F.l2.role_")):
            assert fact.layer == "投影", fact.id


def test_ops_tree_shows_claim_to_protocol() -> None:
    text = format_ops_tree(load())
    assert "交期是双方唯一的共同约定" in text
    assert "按单履约价值流" in text
    assert "需求与约定确认" in text
    assert "改约定必须走变更审批" in text
    assert "菜单·首页" not in text


def test_claim_lists_capabilities_before_stream_without_rewriting_under() -> None:
    kb = load()
    due = kb.facts["F.l1.due_is_shared_reality"]
    assert "F.l2.sales_owns_promise" not in due.children
    assert "F.l2.sales_owns_promise" not in kb.declared_under(due.id)
    text = format_ops_tree(kb)
    due_block = text.split("按单交付装饰件、不设成品仓")[0]
    assert "销售持有对外约定 (F.l2.sales_owns_promise)" in due_block
    assert "计划的倒排与可承诺能力 (F.l2.cap_plan)" in due_block
    assert due_block.index("计划的倒排与可承诺能力") < due_block.index("销售持有对外约定")
    assert due_block.index("销售持有对外约定") < due_block.index("按单履约价值流")
    assert "菜单·首页" not in text
    roots = {node["id"]: node for node in ops_stream_tree(kb)}
    due_node = roots["F.l1.due_is_shared_reality"]
    assert [cap["id"] for cap in due_node["capabilities"]] == [
        "F.l2.cap_plan",
        "F.l2.sales_owns_promise",
    ]
    assert "F.l2.sales_owns_promise" not in {child["id"] for child in due_node["children"]}
    demand = next(stage for stage in due_node["children"][0]["children"] if stage["id"] == "F.l3.stg.demand")
    assert [owner["id"] for owner in demand["owners"]] == ["F.l2.sales_owns_promise"]
    approval = next(kid for kid in demand["children"] if kid["id"] == "F.l3.due_change_via_approval")
    assert approval["owners"] == []
    mto = roots["F.l1.mto_no_fg_stock"]
    assert [cap["id"] for cap in mto["capabilities"]] == [
        "F.l2.cap_dept1",
        "F.l2.cap_dept2",
        "F.l2.cap_kit",
        "F.l2.cap_plan",
    ]


def test_card_view_exposes_capability_fields() -> None:
    kb = load()
    sales = card_view(kb.facts["F.l2.sales_owns_promise"], kb)
    assert sales["层"] == "权责"
    assert sales["角色"] == "销售"
    assert sales["持有"] == "承诺"
    assert "发起交期变更" in sales["可以"]
    assert "F.l1.due_is_shared_reality" in sales["撑住谁"]
    due = card_view(kb.facts["F.l1.due_is_shared_reality"], kb)
    assert due["谁兑现"] == ["F.l2.cap_plan", "F.l2.sales_owns_promise"]
    demand = card_view(kb.facts["F.l3.stg.demand"], kb)
    assert demand["谁有权"] == ["F.l2.sales_owns_promise"]
    assert demand["阶段产出"] == "约定日进系统，数量能说到版"


def test_unattached_capability_stays_out_of_claim_tree() -> None:
    kb = KnowledgeBase(
        facts={
            "C.l1": Fact(id="C.l1", name="主张甲", pack="运营", layer="主张", status="已封印"),
            "C.l2.loose": Fact(id="C.l2.loose", name="未挂能力", pack="运营", layer="权责", status="假设"),
            "C.vsm": Fact(
                id="C.vsm",
                name="甲流",
                pack="运营",
                layer="价值流",
                status="假设",
                supports=["C.l1"],
            ),
        }
    )
    text = format_ops_tree(kb)
    assert "未挂能力" not in text
    assert "甲流" in text
    assert [row["id"] for row in ops_unattached(kb)] == ["C.l2.loose"]


def test_domain_tree_still_prints() -> None:
    text = format_tree(load())
    assert "销售订单 (D.order)" in text
    assert "按单履约价值流" in text


def test_old_explain_chains_hold() -> None:
    assert "不会改订单日期" in explain("C.give_earliest_keep_due", _CTX_E2, "销售")
    assert "归一到版" in explain("C.normalize_to_board", set())
    assert "禁止再乘人数" in explain("C.crew_no_double_count", set())


def test_who_can_change_due_points_to_sales() -> None:
    result = ask("谁能改订单交期")
    assert result.verdict == "成立"
    assert "D.order.due_date" in result.chain
    assert "F.l2.sales_owns_promise" in result.chain
    assert "F.l3.due_change_via_approval" in result.chain
    assert "客户约定日" in result.text
    assert "计划完工" in result.text
    assert "销售" in result.text
    assert "客户" in result.text
    assert "【回答】" in result.text
    assert "从交付模式上看" in result.text
    assert "因此，从权责上看" in result.text
    assert "所以，" in result.text
    assert result.text.index("【回答】") < result.text.index("从交付模式上看")
    assert result.text.index("从交付模式上看") < result.text.index("所以，")
    assert "只有人能改" not in result.text


def test_new_cards_are_hypotheses_and_clean() -> None:
    kb = load()
    new_ids = (
        *_STAGES,
        "F.l2.cap_plan",
        "F.l2.cap_dept1",
        "F.l2.cap_dept2",
        "F.l3.attendance_cap",
        "F.l3.unfinished_to_pool",
        "F.l3.sup.sample",
        "F.l3.sup.payment",
    )
    for fid in new_ids:
        fact = kb.facts[fid]
        assert fact.status == "假设", fid
        blob = yaml_blob(fact)
        for word in _FORBIDDEN:
            assert word not in blob, f"{fid} 含禁词 {word}"


def test_many_claims_can_own_many_streams(tmp_path) -> None:
    (tmp_path / "ops.yaml").write_text(
        """
卡片:
  - 编号: O.l1.a
    名称: 甲主张
    套: 运营
    层: 主张
    状态: 已封印
  - 编号: O.l1.b
    名称: 乙主张
    套: 运营
    层: 主张
    状态: 已封印
  - 编号: O.vsm.a
    名称: 甲流
    套: 运营
    层: 价值流
    状态: 假设
    撑住谁: [O.l1.a]
    其下: [O.stg.a]
  - 编号: O.vsm.a2
    名称: 甲的第二条流
    套: 运营
    层: 价值流
    状态: 假设
    撑住谁: [O.l1.a]
    其下: [O.stg.a2]
  - 编号: O.vsm.b
    名称: 乙流
    套: 运营
    层: 价值流
    状态: 假设
    撑住谁: [O.l1.b]
    其下: [O.stg.b]
  - 编号: O.stg.a
    名称: 甲环节
    套: 运营
    层: 环节
    属于: O.vsm.a
    其下: [O.p.a]
  - 编号: O.stg.a2
    名称: 甲二环节
    套: 运营
    层: 环节
    属于: O.vsm.a2
    其下: [O.p.a2]
  - 编号: O.stg.b
    名称: 乙环节
    套: 运营
    层: 环节
    属于: O.vsm.b
    其下: [O.p.b]
  - 编号: O.p.a
    名称: 甲许可
    套: 运营
    层: 节点
    属于: O.stg.a
  - 编号: O.p.a2
    名称: 甲二许可
    套: 运营
    层: 节点
    属于: O.stg.a2
  - 编号: O.p.b
    名称: 乙许可
    套: 运营
    层: 节点
    属于: O.stg.b
""",
        encoding="utf-8",
    )
    kb = load(tmp_path)
    text = format_ops_tree(kb)
    assert text.index("甲主张") < text.index("甲流")
    assert "甲的第二条流" in text
    assert "乙流" in text
    a_block = text[text.index("甲主张") : text.index("乙主张")]
    assert "乙流" not in a_block
    b_leaf = harvest_complete("O.p.b", confirmed=True, kb=kb)
    assert b_leaf.ok
    assert b_leaf.path[0] == "O.l1.b"
    assert "O.vsm.b" in b_leaf.path


def test_harvest_complete_walks_belongs() -> None:
    result = harvest_complete("F.l3.attendance_cap", confirmed=True)
    assert result.ok
    assert result.path[0] in {"F.l1.due_is_shared_reality", "F.l1.mto_no_fg_stock"}


def yaml_blob(fact) -> str:
    return " ".join(str(v) for v in fact.raw.values())
