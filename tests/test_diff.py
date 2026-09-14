"""§6.7 diff 算法。"""

from datetime import date

from engine.diff import diff
from engine.models import ChangeType, SortMode
from tests.helpers import plan_start_of


def test_diff_add_move_summary(run_ripple, ripple_wos):
    wos = ripple_wos()
    base = run_ripple(wos, sort_mode=SortMode.DUE_DESC)
    wos_a600 = ripple_wos(qty_a=600)
    new = run_ripple(wos_a600, sort_mode=SortMode.PIN_FIRST, pinned=["A"])
    d = diff(base, new, date(2026, 9, 15))
    assert any(e.change_type == ChangeType.MOVE for e in d.entries)
    assert "移动" in d.summary_text


def test_diff_detects_new_wo(run_ripple, ripple_wos, ripple_input):
    wos = ripple_wos()
    base = run_ripple(wos)
    inp = ripple_input.model_copy(
        update={
            "items": {
                **ripple_input.items,
                "N": ripple_input.items["A"].model_copy(update={"item_code": "N"}),
            },
            "uom": {**ripple_input.uom, "N": ripple_input.uom["A"]},
            "sph": {**ripple_input.sph, ("N", "MANUAL"): ripple_input.sph[("A", "MANUAL")]},
        }
    )
    extra = wos + [
        wos[0].model_copy(
            update={
                "wo_no": "N",
                "item_code": "N",
                "source_order_no": "N",
                "due_date": date(2026, 9, 24),
                "qty_board_plan": 300,
            }
        )
    ]
    cfg = inp.config.model_copy(update={"sort_mode": SortMode.PIN_FIRST, "pinned_wo_nos": ["N"]})
    from engine.schedule import schedule

    new = schedule(inp.model_copy(update={"finished_override": extra, "config": cfg}))
    d = diff(base, new, date(2026, 9, 15))
    assert any(e.change_type == ChangeType.ADD for e in d.entries)
