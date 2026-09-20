"""闭集台账对账：有缺口即失败。"""

from __future__ import annotations

from sealed_kb.coverage import validate_coverage


def test_closed_set_fully_ledgered() -> None:
    gap = validate_coverage()
    assert gap.missing_in_ledger == [], gap.missing_in_ledger
    assert gap.extra_in_ledger == [], gap.extra_in_ledger
    assert gap.unhung == [], gap.unhung
    assert gap.bad_hangs == [], gap.bad_hangs
    assert gap.status_mismatch == [], gap.status_mismatch
    assert gap.illegal_skip == [], gap.illegal_skip
    assert gap.skip_no_reason == [], gap.skip_no_reason
