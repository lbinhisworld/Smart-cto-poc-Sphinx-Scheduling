"""§11 T8 变动死区（BR-42）。"""

from datetime import date

from tests.helpers import plan_start_of


def test_br42_deadband_suppresses_small_change(run_ripple, ripple_wos):
    wos = ripple_wos()
    baseline = run_ripple(wos)
    wos301 = ripple_wos(qty_a=301)
    result = run_ripple(
        wos301,
        baseline=baseline,
        deadband_trigger=["A"],
    )
    assert plan_start_of(result, "C") == date(2026, 9, 22)
