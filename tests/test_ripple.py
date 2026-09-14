"""§11 T7 涟漪与锁定（BR-25/26）。"""

from datetime import date

from engine.models import SortMode, WoStatus
from engine.schedule import schedule
from tests.helpers import due_of, plan_start_of, tasks_of


def test_br25_pin_first_ripple_forward_push(run_ripple, ripple_wos):
    wos = ripple_wos()
    base = run_ripple(wos, sort_mode=SortMode.PIN_FIRST, pinned=["A"])
    wos_a600 = ripple_wos(qty_a=600)
    new = run_ripple(
        wos_a600,
        sort_mode=SortMode.PIN_FIRST,
        pinned=["A"],
    )
    assert tasks_of(new, "A") == [
        (date(2026, 9, 22), 300),
        (date(2026, 9, 23), 300),
    ]
    assert plan_start_of(new, "C") == date(2026, 9, 21)
    assert plan_start_of(new, "E") == date(2026, 9, 18)
    assert due_of(new, "C") == due_of(base, "C")


def test_br26_locked_wo_not_moved(run_ripple, ripple_wos, ripple_input):
    wos300 = ripple_wos()
    base300 = run_ripple(wos300)
    c_wo = next(w for w in base300.wos if w.item_code == "C").model_copy(update={"is_locked": True})
    locked_tasks = [t for t in base300.tasks if t.wo_no == c_wo.wo_no]
    wos600 = ripple_wos(qty_a=600)
    wos_locked = [c_wo if w.item_code == "C" else w for w in wos600]
    result = schedule(
        ripple_input.model_copy(
            update={
                "finished_override": wos_locked,
                "locked_tasks": locked_tasks,
            }
        )
    )
    assert plan_start_of(result, "C") == date(2026, 9, 22)
    assert c_wo.status == WoStatus.PLANNED
