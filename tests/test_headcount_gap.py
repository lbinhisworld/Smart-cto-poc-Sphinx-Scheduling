"""组在编折产能，以及加人缺口（单人口径人·时 / 多人配合不按比例放大）。"""

from datetime import date, timedelta
from decimal import Decimal

from engine.capacity import day_capacity, detect_e8
from engine.headcount_gap import (
    TRIAL_CAP,
    estimate_gaps,
    trial_extra_crew,
    trial_recalibrate,
    trial_roster,
)
from engine.models import (
    Confidence,
    Dept,
    GroupCode,
    Item,
    Order,
    ScheduleConfig,
    ScheduleInput,
    Sph,
    SphBasis,
    Uom,
    UomConvert,
    Wo,
    WoStatus,
    WoTask,
    WoType,
)
from engine.schedule import schedule

DAY = date(2026, 9, 21)
EPS = Decimal("0.0001")


def _item(code: str, *, group: GroupCode = GroupCode.MANUAL) -> Item:
    return Item(
        item_code=code,
        item_name=code,
        dept=Dept.FINISHED_DEPT,
        group_code=group,
        unit_sale=Uom.BOARD,
        pcs_per_board=1,
        board_per_box=Decimal("1"),
        loss_rate=Decimal("0"),
        color="",
        is_semi=False,
        computable=True,
    )


def _sph(
    code: str,
    value: int,
    basis: SphBasis,
    *,
    group: GroupCode = GroupCode.MANUAL,
    crew: int = 1,
) -> Sph:
    return Sph(
        item_code=code,
        group_code=group,
        sph_value=Decimal(value),
        sph_basis=basis,
        sph_crew=crew if basis == SphBasis.CREW else None,
        sph_uom=Uom.BOARD,
        crew_std=crew,
        confidence=Confidence.HIGH,
        effective_date=date(2026, 1, 1),
        source="test",
    )


def _calendar(headcounts: dict[date, int], *, group: GroupCode = GroupCode.MANUAL) -> list:
    days = []
    cursor = DAY - timedelta(days=10)
    end = DAY + timedelta(days=10)
    while cursor <= end:
        days.append(
            dict(
                dept=Dept.FINISHED_DEPT,
                group_code=group,
                work_date=cursor,
                is_workday=cursor.isoweekday() <= 5,
                hours_per_day=Decimal("8"),
                headcount=headcounts.get(cursor, 4),
                reserved_ratio=Decimal("0"),
            )
        )
        cursor += timedelta(days=1)
    from engine.models import CalendarDay

    return [CalendarDay(**row) for row in days]


def _wo(code: str, qty: int, *, due: date = DAY, crew: int = 1) -> Wo:
    return Wo(
        wo_no=f"WO-{code}",
        wo_type=WoType.FINISHED,
        source_order_no=code,
        item_code=code,
        group_code=GroupCode.MANUAL,
        dept=Dept.FINISHED_DEPT,
        qty_order=Decimal(qty),
        qty_board_plan=qty,
        due_date=due,
        earliest_start=DAY - timedelta(days=10),
        crew_plan=crew,
        status=WoStatus.DRAFT,
    )


def _order(code: str, *, due: date = DAY) -> Order:
    return Order(
        order_no=code,
        customer="c",
        item_code=code,
        qty_order=Decimal("1"),
        unit=Uom.BOARD,
        due_date=due,
        customer_level=1,
    )


def _input(wos: list[Wo], calendar, sph: dict, *, orders: list[Order] | None = None) -> ScheduleInput:
    items = {wo.item_code: _item(wo.item_code, group=wo.group_code) for wo in wos}
    converts = {
        code: [UomConvert(item_code=code, from_uom=Uom.BOARD, to_uom=Uom.BOARD, factor=Decimal("1"))]
        for code in items
    }
    return ScheduleInput(
        today=DAY - timedelta(days=5),
        orders=orders if orders is not None else [_order(wo.source_order_no, due=wo.due_date) for wo in wos],
        items=items,
        uom=converts,
        routes={},
        sph=sph,
        calendar=calendar,
        stock={},
        config=ScheduleConfig(reserved_ratio=Decimal("0"), attendance_scale_day_hours=False),
        finished_override=wos,
    )


def test_single_day_cap_scales_with_roster():
    sph = _sph("A", 10, SphBasis.SINGLE)
    converts = [UomConvert(item_code="A", from_uom=Uom.BOARD, to_uom=Uom.BOARD, factor=Decimal("1"))]
    cal4 = _calendar({DAY: 4})
    cal5 = _calendar({DAY: 5})
    cap4 = day_capacity(
        cal4, Dept.FINISHED_DEPT, GroupCode.MANUAL, DAY, sph, 1, converts, Decimal("0")
    )
    cap5 = day_capacity(
        cal5, Dept.FINISHED_DEPT, GroupCode.MANUAL, DAY, sph, 99, converts, Decimal("0")
    )
    assert cap4 == 320
    assert cap5 == 400


def test_single_mixed_sph_shares_person_hours_not_boards():
    sph = {
        ("A", "MANUAL"): _sph("A", 10, SphBasis.SINGLE),
        ("B", "MANUAL"): _sph("B", 5, SphBasis.SINGLE),
    }
    # 4 人 × 8 小时 = 32 人·时。A 用 10 人·时（100 版），B 还能落 22×5=110 版。
    # 若按版去减 B 自己的 160 版上限，B 只会剩 60 版。
    inp = _input(
        [_wo("A", 100), _wo("B", 200, due=DAY)],
        _calendar({DAY: 4}),
        sph,
    )
    inp.today = DAY
    for wo in inp.finished_override or []:
        wo.earliest_start = DAY
    result = schedule(inp, with_headcount_exact=False)
    placed = {t.wo_no: t.qty_board for t in result.tasks}
    assert placed.get("WO-A") == 100
    assert placed.get("WO-B") == 110
    man = sum((t.hours_man for t in result.tasks), Decimal("0"))
    assert abs(man - Decimal("32")) < EPS


def test_crew_cap_ignores_roster_and_flags_mismatch():
    sph = _sph("S", 40, SphBasis.CREW, crew=4)
    converts = [UomConvert(item_code="S", from_uom=Uom.BOARD, to_uom=Uom.BOARD, factor=Decimal("1"))]
    low = day_capacity(
        _calendar({DAY: 3}),
        Dept.FINISHED_DEPT,
        GroupCode.MANUAL,
        DAY,
        sph,
        4,
        converts,
        Decimal("0"),
    )
    high = day_capacity(
        _calendar({DAY: 5}),
        Dept.FINISHED_DEPT,
        GroupCode.MANUAL,
        DAY,
        sph,
        4,
        converts,
        Decimal("0"),
    )
    assert low == high == 320
    assert high != int(320 * 5 / 4)
    mismatch = detect_e8(sph, crew_plan=5)
    assert mismatch is not None and mismatch.code == "E8"


def test_gap_uses_peak_day_not_average():
    sph = {("A", "MANUAL"): _sph("A", 10, SphBasis.SINGLE)}
    d1 = DAY
    d2 = DAY + timedelta(days=1)
    inp = _input([_wo("A", 1, due=d2)], _calendar({d1: 1, d2: 1}), sph)
    tasks = [
        WoTask(
            task_id=1,
            wo_no="WO-A",
            dept=Dept.FINISHED_DEPT,
            group_code=GroupCode.MANUAL,
            task_date=d1,
            qty_board=240,
            hours_wall=Decimal("24"),
            hours_man=Decimal("24"),
            crew_plan=1,
        ),
        WoTask(
            task_id=2,
            wo_no="WO-A",
            dept=Dept.FINISHED_DEPT,
            group_code=GroupCode.MANUAL,
            task_date=d2,
            qty_board=80,
            hours_wall=Decimal("8"),
            hours_man=Decimal("8"),
            crew_plan=1,
        ),
    ]
    from engine.models import ScheduleResult

    result = ScheduleResult(
        wos=list(inp.finished_override or []),
        tasks=tasks,
    )
    gap = estimate_gaps(inp, result)[0]
    assert gap.add_people_estimate == 2
    assert gap.add_people_estimate != 1


def test_trial_roster_does_not_write_due_or_replace_plan():
    sph = {("A", "MANUAL"): _sph("A", 10, SphBasis.SINGLE, crew=1)}
    wo = _wo("A", 160)
    wo.earliest_start = DAY
    order = _order("A", due=DAY)
    inp = _input([wo], _calendar({DAY: 1}), sph, orders=[order])
    inp.today = DAY
    before = schedule(inp, with_headcount_exact=False)
    due_before = order.due_date
    tasks_before = [(t.task_date, t.qty_board) for t in before.tasks]
    unplaced_before = [(u.wo_no, u.remaining) for u in before.unplaced]
    trial = trial_roster(inp, Dept.FINISHED_DEPT, GroupCode.MANUAL, add_people=1)
    assert order.due_date == due_before
    assert [(t.task_date, t.qty_board) for t in before.tasks] == tasks_before
    assert [(u.wo_no, u.remaining) for u in before.unplaced] == unplaced_before
    assert "WO-A" in trial.cleared_wo_nos
    assert trial.infeasible is False


def test_trial_stops_at_cap_without_forcing_plan():
    sph = {("A", "MANUAL"): _sph("A", 1, SphBasis.SINGLE)}
    wo = _wo("A", 8 * (1 + TRIAL_CAP) + 50)
    wo.earliest_start = DAY
    order = _order("A", due=DAY)
    inp = _input([wo], _calendar({DAY: 1}), sph, orders=[order])
    inp.today = DAY
    before = schedule(inp, with_headcount_exact=False)
    due_before = order.due_date
    tasks_before = [(t.task_date, t.qty_board) for t in before.tasks]
    trial = trial_roster(inp, Dept.FINISHED_DEPT, GroupCode.MANUAL, add_people=TRIAL_CAP)
    assert trial.infeasible is True
    assert order.due_date == due_before
    assert [(t.task_date, t.qty_board) for t in before.tasks] == tasks_before
    assert before.unplaced[0].earliest_finish is not None


def test_estimate_includes_unplaced_man_hours():
    sph = {("A", "MANUAL"): _sph("A", 10, SphBasis.SINGLE)}
    wo = _wo("A", 160)
    wo.earliest_start = DAY
    inp = _input([wo], _calendar({DAY: 1}), sph)
    inp.today = DAY
    result = schedule(inp)
    gap = next(g for g in result.headcount_gaps if g.group_code == "MANUAL")
    assert gap.includes_unplaced is True
    assert gap.hours_man_need == Decimal("16.0000")
    assert gap.add_people_estimate == 1
    assert gap.add_people_exact == 1


def test_crew_recalibrate_and_extra_crew_do_not_use_plus_one():
    sph = {("S", "MANUAL"): _sph("S", 40, SphBasis.CREW, crew=4)}
    wo = _wo("S", 400, crew=4)
    wo.earliest_start = DAY
    inp = _input([wo], _calendar({DAY: 4}), sph)
    inp.today = DAY
    base = schedule(inp, with_headcount_exact=False)
    plus = trial_roster(inp, Dept.FINISHED_DEPT, GroupCode.MANUAL, add_people=1)
    assert plus.note
    assert "不按人数比例" in plus.note
    assert sum(t.qty_board for t in base.tasks) == sum(t.qty_board for t in schedule(
        inp.model_copy(update={"calendar": _calendar({DAY: 5})}),
        with_headcount_exact=False,
    ).tasks)
    extra = trial_extra_crew(inp, Dept.FINISHED_DEPT, GroupCode.MANUAL)
    assert extra.added_people == 4
    assert extra.infeasible is False
    recalc = trial_recalibrate(
        inp, "S", GroupCode.MANUAL, Decimal("80")
    )
    assert recalc.infeasible is False
    assert "WO-S" in recalc.cleared_wo_nos or recalc.still_late == []
