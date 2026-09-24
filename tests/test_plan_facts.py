"""计划侧纯计算：分摊与未排口径。"""

from db.plan_facts import (
    EXPORT_NOT_PLACED,
    EXPORT_PARTIAL,
    EXPORT_WIP,
    classify_order,
    counts_as_pending_load,
    export_label,
    issue_progress,
    split_gross,
)


def test_split_gross_last_day_takes_remainder():
    parts = split_gross(10, [3, 3, 4], 10)
    assert parts == [3, 3, 4]
    assert sum(parts) == 10


def test_split_gross_unplaced_remainder_stays_on_last_scheduled_day():
    parts = split_gross(10, [3, 3], 10)
    assert parts[0] == 3
    assert sum(parts) == 10


def test_split_gross_single_day_gets_whole_gross():
    assert split_gross(7, [2], 5) == [7]


def test_classify_pending_never_in_plan():
    bucket = classify_order(
        phase="PENDING",
        has_tasks=False,
        has_unplaced=False,
        has_completion=False,
        has_pending_roll=False,
    )
    assert bucket == "NOT_PLACED"
    assert export_label(bucket, has_tasks=False) == EXPORT_NOT_PLACED
    assert counts_as_pending_load(bucket)


def test_classify_partial_and_wip_and_pool():
    partial = classify_order(
        phase="IN_PRODUCTION",
        has_tasks=True,
        has_unplaced=True,
        has_completion=True,
        has_pending_roll=False,
    )
    assert partial == "PARTIAL"
    assert export_label(partial, has_tasks=True) == EXPORT_PARTIAL

    wip = classify_order(
        phase="IN_PRODUCTION",
        has_tasks=False,
        has_unplaced=False,
        has_completion=True,
        has_pending_roll=False,
    )
    assert wip == "WIP_UNPLANNED"
    assert export_label(wip, has_tasks=False) == EXPORT_WIP

    pool = classify_order(
        phase="IN_SCHEDULING",
        has_tasks=False,
        has_unplaced=False,
        has_completion=False,
        has_pending_roll=False,
    )
    assert pool == "POOL_OPEN"
    assert export_label(pool, has_tasks=False) == EXPORT_NOT_PLACED
    assert not counts_as_pending_load(pool)

    placed = classify_order(
        phase="IN_PRODUCTION",
        has_tasks=True,
        has_unplaced=False,
        has_completion=False,
        has_pending_roll=False,
    )
    assert placed == "PLACED"
    assert export_label(placed, has_tasks=True) is None


def test_issue_progress_empty_without_records():
    blank = issue_progress(gross=10, issued=None, today_issued=None)
    assert blank == {"issued": None, "pending": None, "this_time": None}


def test_issue_progress_fills_when_recorded():
    filled = issue_progress(gross=10, issued=4, today_issued=2)
    assert filled == {"issued": 4, "pending": 6, "this_time": 2}
