"""主题工作台：待确认认链 + 探针问栏。台账不是卡片。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from sealed_kb.roles import grounding_path, harvest_complete
from sealed_kb.store import KnowledgeBase, default_kb_root, load

DEFAULT_THEME = "履约四环节"
FORBIDDEN_PROBE_WORDS = ("冷链", "冷库", "保质期", "过敏原", "茶饮", "机台 APS")
MAIN_FOREST_ROOTS = frozenset({"D.order", "D.board", "D.group", "D.wo", "D.item", "D.uom", "D.sph"})
EXCLUDE_LAYERS = frozenset({"投影"})
NOD_ROLES = frozenset({"PMC", "SALES", "SALES_MGR", "GM"})
SEAL_ROLES = frozenset({"GM"})
LEDGER_FILES = frozenset({"pending_batches.yaml", "nods.yaml", "probe_journal.yaml"})

_LAYER_LEAD = {
    "主张": "从交付模式上看，",
    "权责": "因此，从权责上看，",
    "价值流": "因此，从履约过程上看，",
    "环节": "因此，从这一步上看，",
    "节点": "所以，",
    "投影": "落到系统上，",
    "结论": "所以结论是，",
}
_TEMPLATES = {
    "何时成立": "「{name}」是不是所有订单都这样？什么情况下才算？",
    "何时不算": "「{name}」有没有例外？内部返工、无约定或别的口径还算不算？",
    "失败长什么样": "如果不守「{name}」，厂里坏的是约定、计量还是产能口径？",
    "谁有权": "「{name}」打架时谁说了算？系统能不能代做这一步？",
    "撑住谁": "不做「{name}」，坏的是哪条已有主张？请指到编号。",
    "绑哪个对象": "「{name}」落在哪个最小槽？不要只指到父对象。",
    "属于": "「{name}」属于哪一站或哪条流？还是不该挂在这里？",
    "其下或缺口": "「{name}」规格不够的部分是记缺口，还是另开一条流？",
    "何时触发或禁止": "「{name}」什么时候必须触发？什么时候绝对不能做？",
    "持有": "「{name}」持有的是承诺、计划还是库存？",
    "可以": "「{name}」可以做哪些事？",
    "禁止": "「{name}」明确不能做什么？",
    "定义": "离开本厂编制，「{name}」还能不能被指认？它是独立事物还是谁的格子？",
    "别名": "「{name}」现场还叫什么？有没有缩写要写进别名？",
}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _kb_root() -> Path:
    return default_kb_root()


def _ledger_root() -> Path:
    return _kb_root() / "ops"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def load_batches(root: Path | None = None) -> list[dict[str, Any]]:
    path = (root or _kb_root()) / "ops" / "pending_batches.yaml"
    return list(_load_yaml(path).get("批次") or [])


def list_themes(root: Path | None = None) -> list[dict[str, Any]]:
    rows = []
    for batch in load_batches(root):
        rows.append(
            {
                "主题": batch["主题"],
                "轨": batch.get("轨", "运营"),
                "默认打开": bool(batch.get("默认打开")),
                "说明": batch.get("说明") or "",
            }
        )
    rows.sort(key=lambda row: (not row["默认打开"], row["主题"]))
    return rows


def _batch(theme: str, root: Path | None = None) -> dict[str, Any]:
    for batch in load_batches(root):
        if batch.get("主题") == theme:
            return batch
    raise KeyError(f"没有这个主题：{theme}")


def _excluded(fact) -> bool:
    if fact is None:
        return True
    if fact.layer in EXCLUDE_LAYERS:
        return True
    if fact.id.startswith("F.l3.menu_"):
        return True
    if fact.id.startswith("F.l4."):
        return True
    return False


def _who(fact) -> list[str]:
    return _as_list(fact.raw.get("谁有权"))


def _ancestors(kb: KnowledgeBase, seed_ids: list[str]) -> list[str]:
    seen: list[str] = []
    queue = list(seed_ids)
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        fact = kb.facts.get(current)
        if fact is None or _excluded(fact):
            continue
        seen.append(current)
        for parent in (*fact.supports, *([fact.belongs_to] if fact.belongs_to else []), *_who(fact)):
            if parent and parent not in seen:
                queue.append(parent)
    return seen


def _descendants(kb: KnowledgeBase, seed_id: str) -> list[str]:
    found: list[str] = []
    queue = [seed_id]
    seen: set[str] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        fact = kb.facts.get(current)
        if fact is None:
            continue
        found.append(current)
        for child in (*fact.children, *_as_list(fact.raw.get("其下"))):
            if child not in seen:
                queue.append(child)
    return found


def domain_path(leaf_id: str, kb: KnowledgeBase) -> list[str]:
    chain: list[str] = []
    current: str | None = leaf_id
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        fact = kb.facts.get(current)
        if fact is None:
            break
        chain.append(current)
        current = fact.belongs_to
    chain.reverse()
    return chain


def _ops_path(leaf_id: str, kb: KnowledgeBase) -> list[str]:
    path = grounding_path(leaf_id, kb)
    if path:
        return path
    return _ancestors(kb, [leaf_id])


def _track_path(leaf_id: str, track: str, kb: KnowledgeBase) -> list[str]:
    if track == "行业主林":
        path = domain_path(leaf_id, kb)
        if not path:
            return []
        root = kb.facts.get(path[0])
        if root is None or root.layer == "运行结果":
            return []
        if path[0] not in MAIN_FOREST_ROOTS and root.belongs_to:
            return []
        return path
    if track == "运行结果":
        path = domain_path(leaf_id, kb)
        if not path:
            return []
        root = kb.facts.get(path[0])
        if root is None or root.layer != "运行结果":
            return []
        return path
    return _ops_path(leaf_id, kb)


def _shallowest_unsealed(path: list[str], kb: KnowledgeBase) -> str | None:
    for fid in path:
        fact = kb.facts.get(fid)
        if fact is not None and fact.status != "已封印" and not _excluded(fact):
            return fid
    return None


@dataclass
class ThemeClosure:
    theme: str
    track: str
    named: list[str]
    permits: list[str]
    path_ids: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)


def theme_closure(theme: str, kb: KnowledgeBase | None = None, root: Path | None = None) -> ThemeClosure:
    store = kb if kb is not None else load()
    batch = _batch(theme, root)
    track = str(batch.get("轨") or "运营")
    named = [str(item) for item in batch.get("叶子") or []]
    permits = [str(item) for item in batch.get("挂上许可") or []]
    groups: dict[str, list[str]] = {}
    path_ids: list[str] = []
    for leaf in named:
        fact = store.facts.get(leaf)
        if fact is None or _excluded(fact):
            continue
        path = _track_path(leaf, track, store)
        if track == "运营" and not path:
            continue
        if track == "行业主林" and not path:
            continue
        if track == "运行结果" and (not path or not permits):
            continue
        extra: list[str] = []
        for fid in path:
            node = store.facts.get(fid)
            if node is None or _excluded(node):
                continue
            if fid not in path_ids:
                path_ids.append(fid)
            extra.extend(node.supports)
        for fid in extra:
            node = store.facts.get(fid)
            if node is not None and not _excluded(node) and fid not in path_ids:
                path_ids.append(fid)
        if track == "运行结果":
            if fact.status == "已封印":
                continue
            groups.setdefault(leaf, []).append(leaf)
            continue
        shallow = _shallowest_unsealed(path, store)
        if shallow is None:
            continue
        groups.setdefault(shallow, []).append(leaf)
    supported: list[str] = []
    for leaf in named:
        for node_id in _descendants(store, leaf):
            kid = store.facts.get(node_id)
            if kid is None:
                continue
            for claim_id in kid.supports:
                claim = store.facts.get(claim_id)
                if claim is not None and not _excluded(claim) and claim_id not in path_ids:
                    supported.append(claim_id)
    for fid in supported:
        if fid not in path_ids:
            path_ids.append(fid)
    for permit in permits:
        if permit not in path_ids and permit in store.facts and not _excluded(store.facts[permit]):
            path_ids.append(permit)
    return ThemeClosure(
        theme=theme,
        track=track,
        named=named,
        permits=permits,
        path_ids=path_ids,
        groups=groups,
    )


@dataclass
class PendingItem:
    theme: str
    track: str
    shallow_id: str
    name: str
    status: str
    layer: str
    chain: list[str]
    captured: list[str]
    permits: list[str]
    speech: str


def _line(fact, track: str) -> str:
    body = (fact.say.get("默认") or fact.claim or fact.name).strip()
    if track == "行业主林":
        return body
    if track == "运行结果":
        return body
    return f"{_LAYER_LEAD.get(fact.layer, '')}{body}"


def _speech(kb: KnowledgeBase, chain: list[str], track: str) -> str:
    parts: list[str] = []
    if track == "行业主林":
        parts.append("从对象上看，")
    seen: set[str] = set()
    for fid in chain:
        fact = kb.facts.get(fid)
        if fact is None:
            continue
        line = _line(fact, track)
        if line and line not in seen:
            parts.append(line)
            seen.add(line)
    return "".join(parts) if track == "行业主林" else "\n".join(parts)


def pending_items(theme: str, kb: KnowledgeBase | None = None, root: Path | None = None) -> list[PendingItem]:
    store = kb if kb is not None else load()
    closed = theme_closure(theme, store, root)
    items: list[PendingItem] = []
    for shallow_id, captured in closed.groups.items():
        fact = store.facts[shallow_id]
        chain = _track_path(shallow_id, closed.track, store)
        kids = {cid for cid in captured if cid != shallow_id}
        kids.update(cid for cid in _descendants(store, shallow_id) if cid != shallow_id)
        items.append(
            PendingItem(
                theme=theme,
                track=closed.track,
                shallow_id=shallow_id,
                name=fact.name,
                status=fact.status,
                layer=fact.layer,
                chain=chain,
                captured=sorted(kids),
                permits=list(closed.permits),
                speech=_speech(store, chain, closed.track),
            )
        )
    items.sort(key=lambda item: item.shallow_id)
    return items


def _field_empty(fact, field: str) -> bool:
    raw = fact.raw
    if field == "何时成立":
        return not fact.true_when
    if field == "何时不算":
        return not fact.false_when
    if field == "失败长什么样":
        return not str(raw.get("失败长什么样") or "").strip()
    if field == "撑住谁":
        return not fact.supports
    if field == "绑哪个对象":
        return not fact.binds
    if field == "属于":
        return not fact.belongs_to
    if field == "谁有权":
        return not _who(fact)
    if field == "其下或缺口":
        if fact.children or _as_list(raw.get("其下")):
            return False
        return "缺口" not in str(raw.get("说明") or "")
    if field == "何时触发或禁止":
        return not str(raw.get("何时触发") or "").strip() and not _as_list(raw.get("这一步禁止")) and not _as_list(
            raw.get("禁止")
        )
    if field == "持有":
        return not str(raw.get("持有") or "").strip()
    if field == "可以":
        return not _as_list(raw.get("可以"))
    if field == "禁止":
        return not _as_list(raw.get("禁止"))
    if field == "定义":
        return not str(raw.get("定义") or fact.claim or "").strip()
    if field == "别名":
        return False
    return False


def _probe_fields(fact) -> list[str]:
    layer = fact.layer
    if layer == "主张":
        return ["何时成立", "何时不算", "失败长什么样"]
    if layer == "权责":
        return ["撑住谁", "持有", "可以", "禁止", "绑哪个对象"]
    if layer == "价值流":
        return ["撑住谁", "其下或缺口"]
    if layer == "环节":
        return ["属于", "谁有权", "其下或缺口", "何时成立", "何时不算"]
    if layer == "节点":
        return ["属于", "撑住谁", "绑哪个对象", "何时触发或禁止", "何时成立", "何时不算"]
    if layer in {"对象", "槽", "运行结果"}:
        return ["定义"]
    return []


def _template(fact, field: str) -> str:
    name = fact.name or fact.id
    return _TEMPLATES[field].format(name=name)


@dataclass
class ProbeItem:
    theme: str
    anchor: str
    name: str
    field: str
    question: str
    status: str
    layer: str


def _busy_anchors() -> set[str]:
    busy: set[str] = set()
    for row in journal_entries():
        if row.get("状态") in {"已问", "已答"}:
            busy.add(str(row.get("锚点") or ""))
    return busy


def probe_queue(theme: str, kb: KnowledgeBase | None = None, root: Path | None = None) -> list[ProbeItem]:
    store = kb if kb is not None else load()
    closed = theme_closure(theme, store, root)
    pending = pending_items(theme, store, root)
    shallow_ids = {item.shallow_id for item in pending}
    blocked_children: set[str] = set()
    for item in pending:
        blocked_children.update(item.captured)
    busy = _busy_anchors()
    anchors: list[str] = []
    for fid in (*shallow_ids, *closed.path_ids):
        if fid in anchors:
            continue
        fact = store.facts.get(fid)
        if fact is None or _excluded(fact):
            continue
        if fid in blocked_children:
            continue
        if fact.status == "已封印" or fid in shallow_ids:
            anchors.append(fid)
    items: list[ProbeItem] = []
    for fid in anchors:
        if fid in busy:
            continue
        fact = store.facts[fid]
        for field in _probe_fields(fact):
            if not _field_empty(fact, field):
                continue
            question = _template(fact, field)
            if any(word in question for word in FORBIDDEN_PROBE_WORDS):
                continue
            items.append(
                ProbeItem(
                    theme=theme,
                    anchor=fid,
                    name=fact.name,
                    field=field,
                    question=question,
                    status=fact.status,
                    layer=fact.layer,
                )
            )
    items.sort(key=lambda row: (0 if row.anchor.startswith("F.l3.stg.") else 1, row.anchor, row.field))
    return items


def pending_as_dict(theme: str) -> dict[str, Any]:
    items = pending_items(theme)
    return {
        "theme": theme,
        "readonly": True,
        "items": [
            {
                "shallow_id": item.shallow_id,
                "name": item.name,
                "status": item.status,
                "layer": item.layer,
                "track": item.track,
                "chain": item.chain,
                "captured": item.captured,
                "permits": item.permits,
                "speech": item.speech,
            }
            for item in items
        ],
    }


def probe_as_dict(theme: str) -> dict[str, Any]:
    return {
        "theme": theme,
        "readonly": True,
        "items": [
            {
                "anchor": row.anchor,
                "name": row.name,
                "field": row.field,
                "question": row.question,
                "status": row.status,
                "layer": row.layer,
            }
            for row in probe_queue(theme)
        ],
    }


def format_pending(theme: str) -> str:
    items = pending_items(theme)
    if not items:
        return f"【待确认 {theme}】无条目"
    lines = [f"【待确认 {theme}】"]
    for item in items:
        lines.append(f"{item.shallow_id} {item.name} ({item.status})")
        lines.append("链: " + " → ".join(item.chain))
        lines.append(item.speech)
        lines.append("")
    return "\n".join(lines).rstrip()


def format_probe(theme: str) -> str:
    items = probe_queue(theme)
    if not items:
        return f"【探针 {theme}】这次没有可补的栏"
    lines = [f"【探针 {theme}】"]
    for item in items:
        lines.append(f"{item.anchor} · {item.field}")
        lines.append(item.question)
        lines.append("")
    return "\n".join(lines).rstrip()


def journal_entries() -> list[dict[str, Any]]:
    data = _load_yaml(_ledger_root() / "probe_journal.yaml")
    return list(data.get("记录") or [])


def nod_entries() -> list[dict[str, Any]]:
    data = _load_yaml(_ledger_root() / "nods.yaml")
    return list(data.get("记录") or [])


def format_journal() -> str:
    rows = journal_entries()
    if not rows:
        return "【探针日志】暂无记录"
    lines = ["【探针日志】"]
    for row in rows:
        delta = row.get("增量") or {}
        patches = delta.get("改栏") or []
        patch_txt = "、".join(f"{p.get('编号')} {p.get('栏')}" for p in patches) or "无改栏"
        lines.append(f"{row.get('编号')} {row.get('小白问') or ''} → {patch_txt} ({row.get('状态')})")
    return "\n".join(lines)


def validate_journal_row(row: dict[str, Any], kb: KnowledgeBase | None = None) -> str:
    store = kb if kb is not None else load()
    status = str(row.get("状态") or "")
    delta = row.get("增量") or {}
    new_cards = _as_list(delta.get("新卡"))
    patches = list(delta.get("改栏") or [])
    edges = list(delta.get("新边") or [])
    if status == "拒收" and (new_cards or patches or edges):
        return "拒收时增量必须空"
    if status == "已问" and patches:
        return "已问不得出现改栏"
    for fid in new_cards:
        if fid not in store.facts:
            return fid
    for patch in patches:
        pid = str(patch.get("编号") or "")
        if pid and pid not in store.facts:
            return pid
    return ""


def append_journal(row: dict[str, Any]) -> None:
    reason = validate_journal_row(row)
    if reason:
        raise ValueError(reason)
    path = _ledger_root() / "probe_journal.yaml"
    data = _load_yaml(path)
    records = list(data.get("记录") or [])
    records.append(row)
    data["记录"] = records
    _dump_yaml(path, data)


def append_nod(row: dict[str, Any]) -> None:
    path = _ledger_root() / "nods.yaml"
    data = _load_yaml(path)
    records = list(data.get("记录") or [])
    payload = dict(row)
    payload.setdefault("何时", date.today().isoformat())
    records.append(payload)
    data["记录"] = records
    _dump_yaml(path, data)


def latest_nod(leaf_id: str) -> dict[str, Any] | None:
    found = None
    for row in nod_entries():
        if row.get("叶子") == leaf_id:
            found = row
    return found


def can_nod_role(role: str | None) -> bool:
    return (role or "") in NOD_ROLES


def can_seal_role(role: str | None) -> bool:
    return (role or "") in SEAL_ROLES


def record_nod(
    *,
    leaf: str,
    theme: str,
    result: str,
    role: str,
    break_layer: str = "",
    field: str = "",
    probes: list[str] | None = None,
    kb: KnowledgeBase | None = None,
) -> dict[str, Any]:
    store = kb if kb is not None else load()
    if leaf not in store.facts:
        raise KeyError(leaf)
    if result not in {"认", "张力", "认栏"}:
        raise ValueError("结果只能是认、张力或认栏")
    if result == "张力" and not break_layer:
        raise ValueError("张力须指出断在哪一层")
    if result == "认栏" and not field:
        raise ValueError("认栏须写栏名")
    closed = theme_closure(theme, store)
    chain = _track_path(leaf, closed.track, store)
    if result == "认":
        if closed.track == "运营":
            checked = harvest_complete(leaf, confirmed=True, kb=store)
            if not checked.ok:
                raise ValueError(checked.reason)
            chain = checked.path or chain
        elif not chain:
            raise ValueError("没有可认的路径")
    row = {
        "叶子": leaf,
        "链": chain,
        "主题": theme,
        "结果": result,
        "断在": break_layer,
        "栏": field,
        "探针": list(probes or []),
        "谁": role,
        "何时": date.today().isoformat(),
    }
    append_nod(row)
    if probes:
        _mark_journal(probes, "已点头" if result in {"认", "认栏"} else "已答")
    return row


def _mark_journal(ids: list[str], status: str) -> None:
    path = _ledger_root() / "probe_journal.yaml"
    data = _load_yaml(path)
    records = list(data.get("记录") or [])
    wanted = set(ids)
    changed = False
    for row in records:
        if row.get("编号") in wanted:
            row["状态"] = status
            changed = True
    if changed:
        data["记录"] = records
        _dump_yaml(path, data)


def can_seal(leaf: str, result: str | None = None) -> tuple[bool, str]:
    nod = latest_nod(leaf)
    if nod is None:
        return False, "无台账"
    verdict = result or str(nod.get("结果") or "")
    if verdict != "认":
        return False, "仅认栏不够"
    store = load()
    theme = str(nod.get("主题") or DEFAULT_THEME)
    closed = theme_closure(theme, store)
    current = _track_path(leaf, closed.track, store)
    recorded = _as_list(nod.get("链"))
    if recorded and current != recorded:
        return False, "链已变，须重新认"
    return True, ""


def _set_status_in_text(text: str, card_id: str, status: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    in_card = False
    changed = False
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("- 编号:"):
            in_card = card_id == stripped.split(":", 1)[1].strip()
        if in_card and stripped.startswith("状态:"):
            prefix = line[: line.find("状态:")]
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{prefix}状态: {status}{newline}"
            changed = True
            break
    return "".join(lines), changed


def seal_path(card_ids: list[str], kb_root: Path | None = None) -> list[str]:
    root = kb_root or _kb_root()
    store = load(root)
    changed: list[str] = []
    for path in sorted(root.rglob("*.yaml")):
        if path.name in LEDGER_FILES | {"schema.yaml", "coverage.yaml", "inventory.yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        file_changed = False
        for card_id in card_ids:
            fact = store.facts.get(card_id)
            if fact is None or fact.layer == "投影" or fact.status == "已封印":
                continue
            updated, did = _set_status_in_text(updated, card_id, "已封印")
            if did:
                file_changed = True
                if card_id not in changed:
                    changed.append(card_id)
        if file_changed:
            path.write_text(updated, encoding="utf-8")
    return changed


def seal_leaf(leaf: str, theme: str, role: str) -> list[str]:
    if not can_seal_role(role):
        raise PermissionError("无权封印")
    ok, reason = can_seal(leaf)
    if not ok:
        raise PermissionError(reason)
    nod = latest_nod(leaf)
    assert nod is not None
    store = load()
    path_ids = _as_list(nod.get("链")) or _track_path(leaf, theme_closure(theme, store).track, store)
    to_seal = [
        fid
        for fid in path_ids
        if (fact := store.facts.get(fid)) is not None and fact.status != "已封印" and fact.layer != "投影"
    ]
    changed = seal_path(to_seal)
    probes = _as_list(nod.get("探针"))
    if probes:
        _mark_journal(probes, "已封印")
    return changed


def workbench_hint_for(ids: list[str], theme: str = DEFAULT_THEME) -> dict[str, str]:
    pending = pending_items(theme)
    for item in pending:
        if item.shallow_id in ids:
            return {
                "kind": "pending",
                "theme": theme,
                "id": item.shallow_id,
                "text": f"去待确认认这条链（{theme} / {item.name}）。",
            }
    for row in probe_queue(theme):
        if row.anchor in ids:
            return {
                "kind": "probe",
                "theme": theme,
                "id": row.anchor,
                "text": f"去探针问这句：{row.question}",
            }
    return {}
