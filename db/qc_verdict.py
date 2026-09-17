"""检测合格线判定（BR-QC-05 / BR-QC-06）。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from db.qc_limits_loader import load_qc_limits

Verdict = str  # PASS | FAIL | MANUAL


def _parse_decimal(raw: str) -> Decimal | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _qualitative_verdict(raw: str, qual: dict[str, Any]) -> Verdict | None:
    s = (raw or "").strip()
    if not s:
        return None
    for tok in qual.get("fail_tokens") or []:
        if s == tok or tok in s:
            return "FAIL"
    for tok in qual.get("pass_tokens") or []:
        if s == tok or tok in s:
            return "PASS"
    return None


def _check_max(value_raw: str, max_str: str, label: str) -> tuple[Verdict | None, str]:
    qual = load_qc_limits().get("qualitative") or {}
    qv = _qualitative_verdict(value_raw, qual)
    if qv == "PASS":
        return "PASS", ""
    if qv == "FAIL":
        return "FAIL", f"{label} 定性不合格"

    val = _parse_decimal(value_raw)
    cap = _parse_decimal(max_str)
    if val is None or cap is None:
        return None, ""
    if val > cap:
        return "FAIL", f"{label} {val} > 上限 {cap}"
    return "PASS", ""


def compute_swab_verdict(*, tpc_cfu_ml: str, coliform_cfu_ml: str) -> tuple[Verdict, str]:
    cfg = load_qc_limits().get("swab_test") or {}
    logic = cfg.get("logic", "any")
    checks: list[tuple[Verdict | None, str]] = []
    checks.append(
        _check_max(
            tpc_cfu_ml,
            str((cfg.get("total_plate_count_cfu_ml") or {}).get("max", "")),
            "菌落总数 cfu/ml",
        )
    )
    checks.append(
        _check_max(
            coliform_cfu_ml,
            str((cfg.get("coliform_cfu_ml") or {}).get("max", "")),
            "大肠菌群 cfu/ml",
        )
    )
    return _merge_checks(checks, logic)


def compute_product_verdict(
    *,
    moisture_pct: str,
    coliform_cfu_g: str,
    tpc_cfu_g: str,
) -> tuple[Verdict, str]:
    cfg = load_qc_limits().get("product_test") or {}
    logic = cfg.get("logic", "any")
    checks: list[tuple[Verdict | None, str]] = []
    checks.append(
        _check_max(
            moisture_pct,
            str((cfg.get("moisture_pct") or {}).get("max", "")),
            "水分",
        )
    )
    checks.append(
        _check_max(
            coliform_cfu_g,
            str((cfg.get("coliform_cfu_g") or {}).get("max", "")),
            "大肠菌群 cfu/g",
        )
    )
    checks.append(
        _check_max(
            tpc_cfu_g,
            str((cfg.get("total_plate_count_cfu_g") or {}).get("max", "")),
            "菌落总数 cfu/g",
        )
    )
    return _merge_checks(checks, logic)


def _merge_checks(checks: list[tuple[Verdict | None, str]], logic: str) -> tuple[Verdict, str]:
    reasons: list[str] = []
    any_fail = False
    any_pass = False
    any_manual = False
    for v, reason in checks:
        if v == "FAIL":
            any_fail = True
            if reason:
                reasons.append(reason)
        elif v == "PASS":
            any_pass = True
        elif v is None:
            any_manual = True

    if logic == "any" and any_fail:
        return "FAIL", "；".join(reasons)
    if any_manual and not any_fail and not any_pass:
        return "MANUAL", ""
    if any_manual and not any_fail:
        return "MANUAL", ""
    return "PASS", ""


def effective_verdict(*, computed: str, final: str | None) -> str:
    return final if final else computed


def validate_override(*, computed: str, final: str | None, override_reason: str) -> None:
    if final and final != computed and not (override_reason or "").strip():
        raise ValueError("人工覆写判定须填写 override_reason（BR-QC-06）")
