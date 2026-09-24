"""组在编折成产能之后的加人缺口。试排只在内存里，不写交期。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from engine.capacity import hours_man, hours_wall, is_workday, person_day_hours
from engine.models import (
    Dept,
    GroupCode,
    HeadcountGap,
    HeadcountTrial,
    ScheduleInput,
    ScheduleResult,
    SphBasis,
    Wo,
)

TRIAL_CAP = 30
_Q = Decimal("0.0001")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_Q)


def _ceil_people(man: Decimal, one_day: Decimal) -> int:
    if man <= 0:
        return 0
    if one_day <= 0:
        return TRIAL_CAP + 1
    return int((man / one_day).to_integral_value(rounding=ROUND_CEILING))


def _roster_key(dept: Dept, group: GroupCode) -> str:
    return f"{dept.value}|{group.value}"


def _group_wos(result: ScheduleResult) -> dict[tuple[str, str], list[Wo]]:
    grouped: dict[tuple[str, str], list[Wo]] = defaultdict(list)
    for wo in result.wos:
        grouped[(wo.dept.value, wo.group_code.value)].append(wo)
    return grouped


def _bases(inp: ScheduleInput, wos: list[Wo]) -> set[SphBasis]:
    found: set[SphBasis] = set()
    for wo in wos:
        try:
            found.add(inp.sph_of(wo.item_code, wo.group_code).sph_basis)
        except KeyError:
            continue
    return found


def _workdays(inp: ScheduleInput, dept: Dept, group: GroupCode, start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if is_workday(inp.calendar, dept, group, cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _headcount_on(inp: ScheduleInput, dept: Dept, group: GroupCode, day: date) -> int:
    from engine.attendance import effective_headcount
    from engine.capacity import calendar_day

    row = calendar_day(inp.calendar, dept, group, day)
    if row is None:
        return 0
    return effective_headcount(row)


def _unplaced_man(inp: ScheduleInput, wo: Wo, remaining: int) -> Decimal:
    try:
        sph = inp.sph_of(wo.item_code, wo.group_code)
    except KeyError:
        return Decimal(0)
    converts = inp.converts_for(wo.item_code)
    wall = hours_wall(remaining, sph, wo.crew_plan, converts)
    return hours_man(wall, wo.crew_plan)


def _late_wo_nos(inp: ScheduleInput, result: ScheduleResult, dept: Dept, group: GroupCode) -> list[str]:
    wo_by = {wo.wo_no: wo for wo in result.wos}
    late: list[str] = []
    for miss in result.unplaced:
        wo = wo_by.get(miss.wo_no)
        if wo is None or wo.dept != dept or wo.group_code != group:
            continue
        if miss.remaining > 0:
            late.append(wo.wo_no)
    for wo in result.wos:
        if wo.dept != dept or wo.group_code != group:
            continue
        if wo.plan_start is not None and wo.plan_start < wo.earliest_start:
            late.append(wo.wo_no)
        elif any(
            t.task_date < wo.earliest_start
            for t in result.tasks
            if t.wo_no == wo.wo_no
        ):
            late.append(wo.wo_no)
    return list(dict.fromkeys(late))


def _earliest_by_wo(result: ScheduleResult, wo_nos: list[str]) -> dict[str, date]:
    out: dict[str, date] = {}
    for miss in result.unplaced:
        if miss.wo_no in wo_nos and miss.earliest_finish is not None:
            out[miss.wo_no] = miss.earliest_finish
    return out


def estimate_gaps(inp: ScheduleInput, result: ScheduleResult) -> list[HeadcountGap]:
    """按部×组估算高峰日要加的人数。未安置人·时摊到交期往前的工作日。"""
    grouped = _group_wos(result)
    gaps: list[HeadcountGap] = []
    for (dept_val, group_val), wos in sorted(grouped.items()):
        dept = Dept(dept_val)
        group = GroupCode(group_val)
        bases = _bases(inp, wos)
        if not bases:
            continue
        end = max(wo.due_date for wo in wos)
        start = inp.today
        if end < start:
            end = start
        days = _workdays(inp, dept, group, start, end)
        heads = [_headcount_on(inp, dept, group, day) for day in days]
        headcount = min(heads) if heads else 0
        have = Decimal(0)
        day_need: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
        for day in days:
            one = person_day_hours(
                inp.calendar,
                dept,
                group,
                day,
                inp.config.reserved_ratio,
                inp.capacity_overrides,
            )
            have += _q(one * Decimal(_headcount_on(inp, dept, group, day)))
        for task in result.tasks:
            if task.dept != dept or task.group_code != group:
                continue
            if task.task_date in day_need or task.task_date in days:
                day_need[task.task_date] += task.hours_man
        unplaced_man = Decimal(0)
        wo_by = {wo.wo_no: wo for wo in wos}
        for miss in result.unplaced:
            wo = wo_by.get(miss.wo_no)
            if wo is None or miss.remaining <= 0:
                continue
            man = _unplaced_man(inp, wo, miss.remaining)
            unplaced_man += man
            window = _workdays(inp, dept, group, max(inp.today, wo.earliest_start), wo.due_date)
            if not window:
                window = days or [wo.due_date]
            share = man / Decimal(len(window))
            for day in window:
                day_need[day] += share
        need = _q(sum(day_need.values(), Decimal(0)))
        have = _q(have)
        basis_code, basis_label, note, sph_crew, matches = _basis_fields(inp, wos, bases, headcount)
        estimate: int | None = None
        if basis_code == "SINGLE" and days:
            adds: list[int] = []
            for day in days:
                one = person_day_hours(
                    inp.calendar,
                    dept,
                    group,
                    day,
                    inp.config.reserved_ratio,
                    inp.capacity_overrides,
                )
                required = _ceil_people(day_need.get(day, Decimal(0)), one)
                adds.append(max(0, required - _headcount_on(inp, dept, group, day)))
            estimate = max(adds) if adds else 0
        elif basis_code == "CREW":
            note = (note + " 产量未随人数变化。").strip()
        gaps.append(
            HeadcountGap(
                dept=dept_val,
                group_code=group_val,
                basis_code=basis_code,
                basis_label=basis_label,
                headcount=headcount,
                sph_crew=sph_crew,
                crew_matches=matches,
                hours_man_need=need,
                hours_man_have=have,
                add_people_estimate=estimate,
                includes_unplaced=unplaced_man > 0,
                note=note,
            )
        )
    return gaps


def _basis_fields(
    inp: ScheduleInput,
    wos: list[Wo],
    bases: set[SphBasis],
    headcount: int,
) -> tuple[str, str, str, int | None, bool | None]:
    if bases == {SphBasis.SINGLE}:
        return "SINGLE", "单人", "", None, None
    if bases == {SphBasis.CREW}:
        crews = []
        for wo in wos:
            try:
                sph = inp.sph_of(wo.item_code, wo.group_code)
            except KeyError:
                continue
            if sph.sph_crew is not None:
                crews.append(sph.sph_crew)
        unique = set(crews)
        sph_crew = crews[0] if len(unique) == 1 else None
        matches = sph_crew == headcount if sph_crew is not None else None
        note = "多人配合的产量按标定人数，不按在编比例放大。"
        if sph_crew is None and unique:
            note += " 这一组标定人数不一致。"
        elif sph_crew is not None and not matches:
            note += f" 标定 {sph_crew} 人，日历在编 {headcount} 人。"
        return "CREW", "多人配合", note, sph_crew, matches
    return "MIXED", "口径不一致", "这一组单人与多人配合混在一起，加几个人这个数不出。", None, None


def _with_roster(inp: ScheduleInput, dept: Dept, group: GroupCode, roster: int) -> ScheduleInput:
    days = []
    for row in inp.calendar:
        if row.dept == dept and row.group_code == group:
            days.append(row.model_copy(update={"headcount": roster, "headcount_present": None}))
        else:
            days.append(row)
    return inp.model_copy(deep=True, update={"calendar": days, "baseline": None})


def _clears(inp: ScheduleInput, result: ScheduleResult, dept: Dept, group: GroupCode) -> bool:
    return not _late_wo_nos(inp, result, dept, group)


def attach_headcount_gaps(
    inp: ScheduleInput,
    result: ScheduleResult,
    *,
    with_exact: bool,
) -> None:
    from engine.schedule import schedule

    gaps = estimate_gaps(inp, result)
    if with_exact:
        for gap in gaps:
            if gap.basis_code != "SINGLE":
                continue
            dept = Dept(gap.dept)
            group = GroupCode(gap.group_code)
            if _clears(inp, result, dept, group):
                gap.add_people_exact = 0
                continue
            found = _smallest_roster_add(inp, result, dept, group, schedule)
            if found is None:
                gap.exact_infeasible = True
                gap.note = (gap.note + " 加人仍做不到。").strip()
            else:
                gap.add_people_exact = found
    result.headcount_gaps = gaps


def _smallest_roster_add(inp, result, dept, group, schedule) -> int | None:
    base = min(
        (
            _headcount_on(inp, dept, group, day)
            for day in _window_days(inp, result, dept, group)
        ),
        default=gap_head(inp, dept, group),
    )

    def clears_add(extra: int) -> bool:
        if extra == 0:
            return False
        trial_inp = _with_roster(inp, dept, group, base + extra)
        trial = schedule(trial_inp, with_headcount_exact=False)
        return _clears(trial_inp, trial, dept, group)

    if not clears_add(TRIAL_CAP):
        return None
    lo, hi = 1, TRIAL_CAP
    best = TRIAL_CAP
    while lo <= hi:
        mid = (lo + hi) // 2
        if clears_add(mid):
            best = mid
            hi = mid - 1
        else:
            lo = mid + 1
    return best


def gap_head(inp: ScheduleInput, dept: Dept, group: GroupCode) -> int:
    heads = [
        _headcount_on(inp, dept, group, row.work_date)
        for row in inp.calendar
        if row.dept == dept and row.group_code == group and row.is_workday
    ]
    return min(heads) if heads else 0


def _window_days(inp, result, dept, group) -> list[date]:
    wos = [wo for wo in result.wos if wo.dept == dept and wo.group_code == group]
    if not wos:
        return []
    end = max(wo.due_date for wo in wos)
    start = inp.today
    if end < start:
        end = start
    return _workdays(inp, dept, group, start, end)


def _compare(
    before: ScheduleResult,
    after: ScheduleResult,
    inp: ScheduleInput,
    dept: Dept,
    group: GroupCode,
) -> tuple[list[str], list[str], dict[str, date]]:
    late_before = set(_late_wo_nos(inp, before, dept, group))
    late_after = _late_wo_nos(inp, after, dept, group)
    cleared = sorted(late_before - set(late_after))
    return cleared, late_after, _earliest_by_wo(after, late_after)


def trial_roster(
    inp: ScheduleInput,
    dept: Dept,
    group: GroupCode,
    *,
    add_people: int,
) -> HeadcountTrial:
    from engine.schedule import schedule

    before = schedule(inp, with_headcount_exact=False)
    wos = [wo for wo in before.wos if wo.dept == dept and wo.group_code == group]
    bases = _bases(inp, wos)
    base = gap_head(inp, dept, group)
    if bases != {SphBasis.SINGLE}:
        return HeadcountTrial(
            dept=dept.value,
            group_code=group.value,
            mode="add_people",
            headcount=base,
            added_people=None,
            still_late=_late_wo_nos(inp, before, dept, group),
            earliest_finish=_earliest_by_wo(before, _late_wo_nos(inp, before, dept, group)),
            infeasible=True,
            note="多人配合不按人数比例加 1 人。请重新标定标准小时产能，或再开一整组。",
        )
    if add_people < 0:
        add_people = 0
    if add_people > TRIAL_CAP:
        add_people = TRIAL_CAP
    trial_inp = _with_roster(inp, dept, group, base + add_people)
    after = schedule(trial_inp, with_headcount_exact=False)
    cleared, still, earliest = _compare(before, after, trial_inp, dept, group)
    infeasible = bool(still)
    note = ""
    if infeasible and add_people >= TRIAL_CAP:
        note = "加人仍做不到。"
    return HeadcountTrial(
        dept=dept.value,
        group_code=group.value,
        mode="add_people",
        headcount=base + add_people,
        added_people=add_people,
        cleared_wo_nos=cleared,
        still_late=still,
        earliest_finish=earliest,
        infeasible=infeasible,
        note=note,
    )


def trial_recalibrate(
    inp: ScheduleInput,
    item_code: str,
    group: GroupCode,
    sph_value: Decimal,
) -> HeadcountTrial:
    from engine.schedule import schedule

    before = schedule(inp, with_headcount_exact=False)
    key = (item_code, group.value)
    if key not in inp.sph:
        return HeadcountTrial(
            dept="",
            group_code=group.value,
            mode="recalibrate",
            headcount=0,
            infeasible=True,
            note="没有这条标准小时产能，不能重标。",
        )
    copied = dict(inp.sph)
    copied[key] = inp.sph[key].model_copy(update={"sph_value": sph_value})
    dept = before.wos[0].dept if before.wos else Dept.FINISHED_DEPT
    for wo in before.wos:
        if wo.item_code == item_code and wo.group_code == group:
            dept = wo.dept
            break
    trial_inp = inp.model_copy(deep=True, update={"sph": copied, "baseline": None})
    after = schedule(trial_inp, with_headcount_exact=False)
    cleared, still, earliest = _compare(before, after, trial_inp, dept, group)
    return HeadcountTrial(
        dept=dept.value,
        group_code=group.value,
        mode="recalibrate",
        headcount=gap_head(inp, dept, group),
        added_people=None,
        cleared_wo_nos=cleared,
        still_late=still,
        earliest_finish=earliest,
        infeasible=bool(still),
        note="已按填写的标准小时产能试排，没有按人数比例推产值。",
    )


def trial_extra_crew(inp: ScheduleInput, dept: Dept, group: GroupCode) -> HeadcountTrial:
    from engine.schedule import schedule

    before = schedule(inp, with_headcount_exact=False)
    wos = [wo for wo in before.wos if wo.dept == dept and wo.group_code == group]
    crews = []
    for wo in wos:
        try:
            sph = inp.sph_of(wo.item_code, wo.group_code)
        except KeyError:
            continue
        if sph.sph_basis == SphBasis.CREW and sph.sph_crew is not None:
            crews.append(sph.sph_crew)
    unique = set(crews)
    added = crews[0] if len(unique) == 1 else None
    sets = dict(inp.crew_sets)
    key = _roster_key(dept, group)
    sets[key] = sets.get(key, 1) + 1
    trial_inp = inp.model_copy(deep=True, update={"crew_sets": sets, "baseline": None})
    after = schedule(trial_inp, with_headcount_exact=False)
    cleared, still, earliest = _compare(before, after, trial_inp, dept, group)
    note = "再开一整组，产量加上同样的一日产量。"
    if added is None:
        note += " 标定人数不一致，人数步长没有合成一个数。"
    else:
        note += f" 需要再投入标定的 {added} 人，不是在编加 1。"
    return HeadcountTrial(
        dept=dept.value,
        group_code=group.value,
        mode="extra_crew",
        headcount=gap_head(inp, dept, group),
        added_people=added,
        cleared_wo_nos=cleared,
        still_late=still,
        earliest_finish=earliest,
        infeasible=bool(still),
        note=note,
    )
