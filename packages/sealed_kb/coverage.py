"""闭集扫描 + 台账对账。不改封印状态。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sealed_kb.store import default_kb_root, load

_SKIP_ENGINE = {"__init__.py"}
_SKIP_MODELS = {"_Model"}
_NO_SKIP_KINDS = {"业务规则", "引擎模块"}


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    source: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _spec_text() -> str:
    return (repo_root() / "斯芬克斯-排程服务POC-开发需求规格.md").read_text(encoding="utf-8")


def scan_brs() -> list[Asset]:
    found = re.findall(r"\*\*BR-([0-9]+[a-z]?)\*\*", _spec_text())
    ids = [f"BR-{x}" for x in found]
    # 稳定去重且保持规格出现顺序
    ordered = list(dict.fromkeys(ids))
    return [Asset(i, "业务规则", "斯芬克斯-排程服务POC-开发需求规格.md") for i in ordered]


def scan_conflicts() -> list[Asset]:
    spec = set(re.findall(r"\bE([1-9]|10)\b", _spec_text()))
    conflicts = (repo_root() / "packages/engine/conflicts.py").read_text(encoding="utf-8")
    code = set(re.findall(r"\bE([1-9]|10)\b", conflicts))
    nums = sorted({int(x) for x in spec | code})
    return [Asset(f"E{n}", "冲突码", "conflicts.py") for n in nums]


def scan_model_classes() -> list[Asset]:
    text = (repo_root() / "packages/engine/models.py").read_text(encoding="utf-8")
    names = [m for m in re.findall(r"^class (\w+)", text, re.M) if m not in _SKIP_MODELS]
    return [Asset(n, "行业对象", "packages/engine/models.py") for n in names]


def scan_engine_modules() -> list[Asset]:
    rows = []
    for path in sorted((repo_root() / "packages/engine").glob("*.py")):
        if path.name in _SKIP_ENGINE:
            continue
        rel = f"packages/engine/{path.name}"
        rows.append(Asset(rel, "引擎模块", rel))
    return rows


def scan_config_keys() -> list[Asset]:
    rows = []
    for path in sorted((repo_root() / "config").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        for key in data:
            aid = f"config/{path.name}#{key}"
            rows.append(Asset(aid, "可调参数", str(path.relative_to(repo_root()))))
    return rows


def scan_roles() -> list[Asset]:
    text = (repo_root() / "packages/shared/auth.py").read_text(encoding="utf-8")
    m = re.search(r"RoleCode = Literal\[([^\]]+)\]", text)
    roles: list[str] = []
    if m:
        roles = re.findall(r'"(\w+)"', m.group(1))
    return [Asset(r, "演示权责", "packages/shared/auth.py") for r in roles]


def scan_menu_keys() -> list[Asset]:
    text = (repo_root() / "packages/shared/auth.py").read_text(encoding="utf-8")
    keys = re.findall(r'MenuItem\("([^"]+)"', text)
    return [Asset(k, "演示权责", "packages/shared/auth.py") for k in keys]


def scan_modules() -> list[Asset]:
    text = (repo_root() / "packages/shared/auth.py").read_text(encoding="utf-8")
    mods = list(dict.fromkeys(re.findall(r', "(M\d+[a-z]?)"\)', text)))
    return [Asset(m, "产品模块", "packages/shared/auth.py") for m in mods]


def scan_redline_tests() -> list[Asset]:
    tests = repo_root() / "tests"
    rows = []
    for path in sorted(tests.glob("test_*br*.py")):
        rel = f"tests/{path.name}"
        rows.append(Asset(rel, "锁链测试", rel))
    red = tests / "test_db_redline.py"
    if red.exists():
        rows.append(Asset("tests/test_db_redline.py", "锁链测试", "tests/test_db_redline.py"))
    return rows


def scan_closed_set() -> list[Asset]:
    return (
        scan_brs()
        + scan_conflicts()
        + scan_model_classes()
        + scan_engine_modules()
        + scan_config_keys()
        + scan_roles()
        + scan_menu_keys()
        + scan_modules()
        + scan_redline_tests()
    )


def load_ledger(root: Path | None = None) -> list[dict[str, Any]]:
    path = (root or default_kb_root()) / "coverage.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("台账") or [])


@dataclass
class CoverageGap:
    missing_in_ledger: list[str]
    extra_in_ledger: list[str]
    unhung: list[str]
    bad_hangs: list[str]
    status_mismatch: list[str]
    illegal_skip: list[str]
    skip_no_reason: list[str]


def validate_coverage(root: Path | None = None) -> CoverageGap:
    kb = load(root)
    ledger = load_ledger(root)
    scanned = {a.id: a for a in scan_closed_set()}
    led_ids = {str(row["资产"]): row for row in ledger}
    missing = sorted(set(scanned) - set(led_ids))
    extra = sorted(set(led_ids) - set(scanned) - _intentional_only(ledger))
    unhung: list[str] = []
    bad_hangs: list[str] = []
    status_mismatch: list[str] = []
    illegal_skip: list[str] = []
    skip_no_reason: list[str] = []
    for row in ledger:
        aid = str(row["资产"])
        status = str(row.get("状态", ""))
        hangs = [str(x) for x in (row.get("挂到") or [])]
        kind = str(row.get("类") or (scanned[aid].kind if aid in scanned else ""))
        if status == "刻意不收":
            if not str(row.get("理由") or "").strip():
                skip_no_reason.append(aid)
            if kind in _NO_SKIP_KINDS or aid.startswith("BR-") or aid.startswith("packages/engine/"):
                illegal_skip.append(aid)
            continue
        if not hangs:
            unhung.append(aid)
        for hid in hangs:
            if hid not in kb.facts:
                bad_hangs.append(f"{aid}->{hid}")
            elif status == "已封印" and kb.facts[hid].status != "已封印":
                status_mismatch.append(f"{aid}->{hid}")
    return CoverageGap(missing, extra, unhung, bad_hangs, status_mismatch, illegal_skip, skip_no_reason)


def _intentional_only(ledger: list[dict[str, Any]]) -> set[str]:
    return {str(r["资产"]) for r in ledger if r.get("状态") == "刻意不收"}


# 闭集资产 → 卡片（生成台账用）
_BR_NODE = {
    "BR-01": "F.l3.normalize_to_board",
    "BR-02": "F.l3.normalize_to_board",
    "BR-03": "F.l3.normalize_to_board",
    "BR-04": "F.l3.normalize_to_board",
    "BR-05": "F.l3.normalize_to_board",
    "BR-10": "F.l3.sph_and_hours",
    "BR-11": "F.l3.sph_and_hours",
    "BR-12": "F.l3.sph_and_hours",
    "BR-13": "F.l3.sph_and_hours",
    "BR-14": "F.l3.sph_and_hours",
    "BR-20": "F.l3.backward_place",
    "BR-21": "F.l3.backward_place",
    "BR-22": "F.l3.backward_place",
    "BR-23": "F.l3.backward_place",
    "BR-24": "F.l3.backward_place",
    "BR-25": "F.l3.backward_place",
    "BR-26": "F.l3.backward_place",
    "BR-27": "F.l3.due_change_via_approval",
    "BR-30": "F.l3.finished_then_semi",
    "BR-31": "F.l3.finished_then_semi",
    "BR-32": "F.l3.finished_then_semi",
    "BR-32b": "F.l3.kitting",
    "BR-33": "F.l3.finished_then_semi",
    "BR-34": "F.l3.finished_then_semi",
    "BR-35": "F.l3.finished_then_semi",
    "BR-36": "F.l3.finished_then_semi",
    "BR-37": "F.l3.finished_then_semi",
    "BR-38": "F.l3.kitting",
    "BR-39": "F.l3.kitting",
    "BR-39b": "F.l3.kitting",
    "BR-40": "F.l3.fence_ripple",
    "BR-41": "F.l3.fence_ripple",
    "BR-42": "F.l3.fence_ripple",
    "BR-43": "F.l3.fence_ripple",
    "BR-44": "F.l3.fence_ripple",
    "BR-45": "F.l3.fence_ripple",
    "BR-46": "F.l3.fence_ripple",
    "BR-47": "F.l3.soft_conflicts",
    "BR-50": "F.l3.soft_conflicts",
}

_MODEL_OBJ = {
    "Dept": "D.dept",
    "GroupCode": "D.group",
    "WoType": "D.wo",
    "WoStatus": "D.wo",
    "Uom": "D.uom",
    "SphBasis": "D.sph",
    "Confidence": "D.sph",
    "ConflictLv": "D.conflict",
    "ChangeType": "D.diff",
    "SortMode": "D.schedule_io",
    "TraceAct": "D.trace",
    "InsertReason": "D.insert",
    "InsertStrategy": "D.insert",
    "PlanTrigger": "D.plan_version",
    "TraceEvent": "D.trace",
    "ScheduleTrace": "D.trace",
    "Item": "D.item",
    "UomConvert": "D.uom_convert",
    "ItemRoute": "D.item_route",
    "ComponentRole": "D.bom",
    "BomLine": "D.bom",
    "KitMode": "D.kit",
    "KitAllocation": "D.kit",
    "KitLineResult": "D.kit",
    "KitCheckResult": "D.kit",
    "Sph": "D.sph",
    "CalendarDay": "D.calendar",
    "Group": "D.group",
    "Order": "D.order",
    "Wo": "D.wo",
    "WoTask": "D.wo_task",
    "WoDependency": "D.wo_dep",
    "WoInsertLog": "D.insert",
    "PlanVersion": "D.plan_version",
    "Conflict": "D.conflict",
    "Unplaced": "D.unplaced",
    "ColineGroup": "D.coline",
    "ColineSummary": "D.coline",
    "LotSummary": "D.coline",
    "PriorityWeights": "D.schedule_io",
    "ScheduleConfig": "D.schedule_io",
    "CapacityOverride": "D.schedule_io",
    "ScheduleInput": "D.schedule_io",
    "ScheduleResult": "D.schedule_io",
    "HeadcountGap": "D.headcount_gap",
    "HeadcountTrial": "D.headcount_gap",
    "DiffEntry": "D.diff",
    "DiffResult": "D.diff",
    "FeasibilityStatus": "D.feasibility",
    "FeasibilityResult": "D.feasibility",
    "InsertStrategyOutcome": "D.insert",
    "InsertCompareResult": "D.insert",
}

_SEALED_CARDS = {
    "F.l1.due_is_shared_reality",
    "F.l1.board_is_meter",
    "F.l1.crew_in_sph",
    "F.l2.sales_owns_promise",
    "F.l3.due_change_via_approval",
    "F.l3.normalize_to_board",
    "F.l3.sph_and_hours",
    "F.l4.br27_no_write_due",
    "F.l4.group_code_drift",
    "C.give_earliest_keep_due",
    "C.normalize_to_board",
    "C.crew_no_double_count",
    "D.order",
    "D.order.due_date",
    "D.board",
    "D.group",
    "D.sph",
    "D.wo",
}

_INTENTIONAL = [
    {
        "资产": "seed/",
        "类": "刻意不收",
        "出处": "seed/",
        "挂到": [],
        "状态": "刻意不收",
        "理由": "演示数字实例，不是对象定义",
    },
    {
        "资产": "web/vite.config.ts",
        "类": "刻意不收",
        "出处": "web/vite.config.ts",
        "挂到": [],
        "状态": "刻意不收",
        "理由": "构建配置，不是业务本体",
    },
    {
        "资产": ".vscode/settings.json",
        "类": "刻意不收",
        "出处": ".vscode/settings.json",
        "挂到": [],
        "状态": "刻意不收",
        "理由": "编辑器主题，不是业务本体",
    },
]


def hangs_for(asset: Asset) -> list[str]:
    if asset.kind == "业务规则":
        node = _BR_NODE[asset.id]
        extra = ["F.l4.br27_no_write_due"] if asset.id == "BR-27" else []
        return [node, *extra]
    if asset.kind == "冲突码":
        return ["F.l3.soft_conflicts", "F.l4.mod_conflicts"]
    if asset.kind == "行业对象":
        return [_MODEL_OBJ[asset.id]]
    if asset.kind == "引擎模块":
        stem = Path(asset.id).stem
        return [f"F.l4.mod_{stem}"]
    if asset.kind == "可调参数":
        if asset.id.startswith("config/schedule.yaml") or asset.id.startswith("config/weights.yaml"):
            return ["F.l3.fence_ripple", "D.schedule_io"]
        if asset.id.startswith("config/qc_limits.yaml"):
            return ["F.l3.mod_M9"]
        if asset.id.startswith("config/demo.yaml"):
            return ["F.l3.mod_M0"]
        if asset.id.startswith("config/integrations.yaml"):
            return ["F.l3.mod_M3"]
        return ["D.schedule_io"]
    if asset.kind == "演示权责" and asset.id.isupper():
        return [f"F.l2.role_{asset.id}"]
    if asset.kind == "演示权责":
        return [f"F.l3.menu_{asset.id}"]
    if asset.kind == "产品模块":
        return [f"F.l3.mod_{asset.id}"]
    if asset.kind == "锁链测试":
        return ["F.l4.br27_no_write_due"]
    raise KeyError(asset)


def row_status(hangs: list[str]) -> str:
    if hangs and all(h in _SEALED_CARDS for h in hangs):
        return "已封印"
    return "假设"


def build_ledger_rows() -> list[dict[str, Any]]:
    rows = []
    for asset in scan_closed_set():
        hangs = hangs_for(asset)
        rows.append(
            {
                "资产": asset.id,
                "类": asset.kind,
                "出处": asset.source,
                "挂到": hangs,
                "状态": row_status(hangs),
            }
        )
    rows.extend(_INTENTIONAL)
    return rows
