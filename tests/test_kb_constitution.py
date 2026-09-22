"""行业对象构成：属于 → 其下由加载器反查；关联 / 是一种不进其下。"""

from __future__ import annotations

from sealed_kb.store import format_tree, load

_INDEPENDENT_DOMAIN_NAMES = {
    "销售订单",
    "版",
    "组",
    "工单",
    "装饰件品项",
    "装饰件计量单位",
    "一部成品与二部半成品",
    "成品工单",
    "半成品工单",
}

_RUNTIME_ROOT_NAMES = {
    "一次倒排运行",
}


def test_load_derives_children_from_belongs(tmp_path) -> None:
    (tmp_path / "d.yaml").write_text(
        """
卡片:
  - 编号: D.a
    名称: 甲
    套: 行业
    层: 对象
  - 编号: D.a.b
    名称: 甲的乙
    套: 行业
    层: 槽
    属于: D.a
""",
        encoding="utf-8",
    )
    kb = load(tmp_path)
    assert kb.facts["D.a.b"].belongs_to == "D.a"
    assert kb.children_of("D.a") == ["D.a.b"]
    assert kb.facts["D.a"].children == ["D.a.b"]


def test_order_due_date_is_under_order() -> None:
    kb = load()
    due = kb.facts["D.order.due_date"]
    assert due.belongs_to == "D.order"
    assert due.layer == "槽"
    assert "D.order.due_date" in kb.children_of("D.order")


def test_slot_id_mirrors_parent() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.pack != "行业" or fact.layer != "槽":
            continue
        if not fact.belongs_to:
            bad.append(f"{fact.id}:槽未写属于")
            continue
        if not fact.id.startswith(f"{fact.belongs_to}."):
            bad.append(f"{fact.id}:编号未镜像{fact.belongs_to}")
    assert bad == [], bad


def test_belongs_parent_exists_and_name_is_a_of_b() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.pack != "行业":
            continue
        if fact.layer == "槽" and not fact.belongs_to:
            bad.append(f"{fact.id}:槽未写属于")
        if fact.belongs_to:
            if fact.belongs_to not in kb.facts:
                bad.append(f"{fact.id}:属于{fact.belongs_to}不存在")
            if "的" not in fact.name:
                bad.append(f"{fact.id}:{fact.name}:有属于但名称不是A的B")
        elif fact.layer == "对象" and fact.name not in _INDEPENDENT_DOMAIN_NAMES:
            if "的" not in fact.name:
                bad.append(f"{fact.id}:{fact.name}:无属于的对象未进独立名单")
        elif fact.layer == "运行结果" and not fact.belongs_to:
            if fact.name not in _RUNTIME_ROOT_NAMES:
                bad.append(f"{fact.id}:{fact.name}:运行结果根未登记")
    assert bad == [], bad


def test_declared_under_matches_derived_children() -> None:
    kb = load()
    bad = []
    for fact in kb.facts.values():
        if fact.pack != "行业":
            continue
        derived = set(fact.children)
        declared = set(kb.declared_under(fact.id))
        if derived and not declared:
            bad.append(f"{fact.id}:有孩子但未写其下")
        if declared != derived:
            bad.append(f"{fact.id}:其下{sorted(declared)}≠反查{sorted(derived)}")
    assert bad == [], bad


def test_format_tree_shows_order_slot() -> None:
    text = format_tree(load())
    assert "销售订单 (D.order)" in text
    assert "销售订单的客户约定日 (D.order.due_date)" in text


def test_relates_do_not_enter_children() -> None:
    kb = load()
    assert "D.item" not in kb.children_of("D.sph")
    assert "D.group" not in kb.children_of("D.sph")
    assert "D.wo.finished" not in kb.children_of("D.wo")
