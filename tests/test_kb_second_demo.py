"""二演后履约叶子：先写断言。新叶子须能 grounding 到已有 L1；不收项不入库。"""

from __future__ import annotations

from sealed_kb.roles import grounding_path, harvest_complete
from sealed_kb.store import load
from sealed_kb.workbench import list_themes, load_batches

_STREAM = "F.l3.vsm.order_to_delivery"
_SEALED_L1 = {
    "F.l1.due_is_shared_reality",
    "F.l1.mto_no_fg_stock",
    "F.l1.board_is_meter",
    "F.l1.crew_in_sph",
}

# 路径 A：复用已有主张与环节，只新增假设叶子
_LEAVES = {
    "F.l3.earliest_whatif": "F.l3.stg.fulfill",
    "F.l3.dispatch_daily_kit": "F.l3.stg.make",
    "F.l3.unplaced_three_kinds": "F.l3.stg.fulfill",
    "F.l3.semi_progress_on_order": "F.l3.stg.make",
    "F.l3.headcount_to_capacity": "F.l3.stg.schedule",
    "F.l3.sup.visit": "F.l3.stg.demand",
    "F.l3.sup.a_to_project": "F.l3.stg.demand",
    "F.l3.sup.finance_slice": "F.l3.stg.fulfill",
    "F.l3.sup.qc_on_board": "F.l3.stg.make",
}

_BINDS = {
    "F.l3.earliest_whatif": {"D.feasibility"},
    "F.l3.dispatch_daily_kit": {"D.wo_task", "D.bom"},
    "F.l3.unplaced_three_kinds": {"D.unplaced"},
    "F.l3.semi_progress_on_order": {"D.wo"},
    "F.l3.headcount_to_capacity": {"D.headcount_gap", "D.sph"},
    "F.l3.sup.visit": {"D.visit"},
    "F.l3.sup.a_to_project": {"D.project"},
}

_FORBIDDEN_WORDS = (
    "冷链",
    "过敏原",
    "机台 APS",
    "Wave 3",
    "Wave 4",
    "Wave X",
    "自动改约定日",
    "不受 BR-27",
)

_FORBIDDEN_IDS = (
    "F.l3.vsm.sample",
    "F.l3.vsm.sales_mobile",
    "F.l3.vsm.finance",
    "F.l3.quote_rule",
    "F.l3.person_roster",
    "F.l3.kingdee_live",
    "F.l1.sales_mobile",
    "F.l1.finance_cockpit",
)


def _blob(fact) -> str:
    return " ".join(str(v) for v in fact.raw.values())


def test_second_demo_leaves_are_hypotheses_under_existing_stages() -> None:
    kb = load()
    for fid, stage in _LEAVES.items():
        fact = kb.facts[fid]
        assert fact.status == "假设", fid
        assert fact.pack == "运营", fid
        assert fact.layer == "节点", fid
        assert fact.belongs_to == stage, fid
        assert fid in kb.children_of(stage), fid
        assert "命题" in fact.raw and "定义" not in fact.raw, fid
        for word in _FORBIDDEN_WORDS:
            assert word not in _blob(fact), f"{fid} 含禁词 {word}"


def test_second_demo_leaves_ground_to_sealed_l1() -> None:
    kb = load()
    for fid in _LEAVES:
        path = grounding_path(fid, kb)
        assert path, fid
        assert path[0] in _SEALED_L1, (fid, path)
        assert path[-1] == fid
        assert _STREAM in path or path[0] in _SEALED_L1
        done = harvest_complete(fid, confirmed=True, kb=kb)
        assert done.ok, (fid, done.reason)
        assert done.path[0] in _SEALED_L1


def test_second_demo_does_not_open_l1_or_stream() -> None:
    kb = load()
    claims = [f for f in kb.facts.values() if f.layer == "主张"]
    streams = [f for f in kb.facts.values() if f.layer == "价值流"]
    assert {f.id for f in claims} == _SEALED_L1
    assert [f.id for f in streams] == [_STREAM]
    assert kb.facts["F.l3.sup.sample"].belongs_to == "F.l3.stg.demand"
    assert kb.facts["F.l3.sup.sample"].status == "假设"
    assert kb.facts["D.insert"].status == "假设"


def test_second_demo_binds_minimal_slots() -> None:
    kb = load()
    for fid, slots in _BINDS.items():
        assert slots <= set(kb.facts[fid].binds), (fid, kb.facts[fid].binds)


def test_earliest_whatif_forbids_publish_and_due_write() -> None:
    fact = load().facts["F.l3.earliest_whatif"]
    blob = _blob(fact)
    assert "发布" in blob
    assert "约定日" in blob
    assert "C.give_earliest_keep_due" in fact.supports
    assert "F.l3.soft_conflicts" in fact.supports
    assert "D.feasibility" in fact.binds


def test_dispatch_daily_kit_normalizes_and_skips_roster_permit() -> None:
    kb = load()
    fact = kb.facts["F.l3.dispatch_daily_kit"]
    blob = _blob(fact)
    assert "毛需求" in blob
    assert "版" in blob
    assert "F.l3.person_roster" not in kb.facts
    assert "人员级排班" not in fact.name


def test_sample_column_rights_without_quote_rule() -> None:
    kb = load()
    fact = kb.facts["F.l3.sup.sample"]
    blob = _blob(fact)
    assert "打样成本" in blob
    assert "对客报价" in blob
    assert "研发" in blob
    assert "销管" in blob
    assert "F.l3.quote_rule" not in kb.facts
    assert fact.status == "假设"


def test_visit_and_project_relate_order_not_child() -> None:
    kb = load()
    for fid in ("D.visit", "D.opportunity", "D.project"):
        fact = kb.facts[fid]
        assert fact.status == "假设"
        assert fact.pack == "行业"
        assert fact.layer == "对象"
        assert "定义" in fact.raw and "命题" not in fact.raw
        assert "D.order" in fact.relates_to
        assert fact.belongs_to is None
        assert fid not in kb.children_of("D.order")
    assert "D.visit" not in kb.children_of("D.order")
    assert "D.project" not in kb.children_of("D.order")


def test_menus_and_roles_are_projections_not_l3_roots() -> None:
    kb = load()
    for fid in (
        "F.l3.menu_crm_visit",
        "F.l3.menu_settings",
        "F.l2.role_SALES_ASSIST",
        "F.l2.role_RD",
    ):
        assert kb.facts[fid].layer == "投影"
        assert kb.facts[fid].status == "假设"
        assert kb.facts[fid].belongs_to is None


def test_rejected_topics_have_no_cards() -> None:
    kb = load()
    for fid in _FORBIDDEN_IDS:
        assert fid not in kb.facts
    blob = " ".join(_blob(f) for f in kb.facts.values() if f.id in _LEAVES or f.id in {
        "F.l3.sup.sample",
        "D.visit",
        "D.opportunity",
        "D.project",
    })
    for word in _FORBIDDEN_WORDS:
        assert word not in blob


def test_finance_and_qc_are_gaps_not_new_permits() -> None:
    kb = load()
    finance = kb.facts["F.l3.sup.finance_slice"]
    qc = kb.facts["F.l3.sup.qc_on_board"]
    assert "缺口" in str(finance.raw.get("说明") or "")
    assert "缺口" in str(qc.raw.get("说明") or "")
    assert "工序树" not in finance.name
    assert "折旧" not in finance.name
    assert "真集成" not in qc.name


def test_second_demo_theme_names_new_leaves() -> None:
    names = [row["主题"] for row in list_themes()]
    assert "二演后履约叶子" in names
    theme = next(row for row in load_batches() if row["主题"] == "二演后履约叶子")
    assert theme.get("轨") == "运营"
    named = set(theme.get("叶子") or [])
    assert _LEAVES.keys() <= named
    assert "F.l3.sup.sample" in named
    assert "F.l3.menu_crm_visit" not in named
    assert "D.insert" not in named


def test_headcount_leaf_reuses_crew_claim() -> None:
    fact = load().facts["F.l3.headcount_to_capacity"]
    assert "F.l1.crew_in_sph" in fact.supports
    assert "F.l3.sph_and_hours" in fact.supports
    blob = _blob(fact)
    assert "再乘" in blob or "CREW" in blob
    assert "点名" in blob
