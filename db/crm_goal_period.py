"""销售目标 · 年 / 月 / 周。完成数按发生日归期，不写在目标行上。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.tables import (
    CrmContractRow,
    CrmFieldVisitRow,
    CrmPaymentReceiptRow,
    CrmSalesGoalPeriodRow,
    CrmVisitRow,
)

DEMO_TODAY = date(2026, 9, 15)
GOAL_PERIOD_METRICS = ("新增客户数", "拜访量", "签约金额", "回款金额")
QTY_METRICS = frozenset({"新增客户数", "拜访量"})
AMOUNT_METRICS = frozenset({"签约金额", "回款金额"})
PERIOD_PACK_KEY = "crm_goal_period_pack"
PERIOD_PACK_VERSION = "2026-09-23-goal-v2"


def week_index(day: int) -> int:
    if day <= 7:
        return 1
    if day <= 14:
        return 2
    if day <= 21:
        return 3
    if day <= 28:
        return 4
    return 5


def weeks_in_month(year: int, month: int) -> list[int]:
    import calendar

    last = calendar.monthrange(year, month)[1]
    indices = [1, 2, 3, 4]
    if last >= 29:
        indices.append(5)
    return indices


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def year_key(year: int) -> str:
    return f"{year:04d}"


def week_key(year: int, month: int, w: int) -> str:
    return f"{month_key(year, month)}-W{w}"


def period_label(kind: str, key: str) -> str:
    if kind == "YEAR":
        return key
    if kind == "MONTH":
        return key
    if kind == "WEEK" and "-W" in key:
        base, wpart = key.rsplit("-W", 1)
        return f"{base} 第{wpart}周"
    return key


def week_date_range(year: int, month: int, w: int) -> tuple[date, date]:
    import calendar

    last = calendar.monthrange(year, month)[1]
    starts = {1: 1, 2: 8, 3: 15, 4: 22, 5: 29}
    start_day = starts[w]
    if w == 5:
        end_day = last
    elif w == 4:
        end_day = min(28, last)
    else:
        end_day = start_day + 6
    return date(year, month, start_day), date(year, month, end_day)


def date_in_period(kind: str, key: str, d: date) -> bool:
    if kind == "YEAR":
        return d.year == int(key)
    if kind == "MONTH":
        y, m = key.split("-")
        return d.year == int(y) and d.month == int(m)
    if kind == "WEEK":
        y = int(key[:4])
        m = int(key[5:7])
        w = int(key.split("-W")[1])
        start, end = week_date_range(y, m, w)
        return start <= d <= end
    return False


def split_int(total: int, parts: int) -> list[int]:
    if parts <= 0:
        return []
    base = total // parts
    rem = total % parts
    return [base + (1 if i < rem else 0) for i in range(parts)]


def split_amount(total: Decimal, parts: int) -> list[Decimal]:
    if parts <= 0:
        return []
    cents = int((total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    base = cents // parts
    rem = cents % parts
    out: list[Decimal] = []
    for i in range(parts):
        c = base + (1 if i < rem else 0)
        out.append(Decimal(c) / Decimal(100))
    return out


def _now() -> datetime:
    return datetime(2026, 9, 15, 12, 0, 0)


def _row_target(row: CrmSalesGoalPeriodRow) -> Decimal | int:
    if row.metric in QTY_METRICS:
        return int(row.target_qty)
    return Decimal(str(row.target_amount or 0))


def _set_row_target(row: CrmSalesGoalPeriodRow, value: int | Decimal) -> None:
    if row.metric in QTY_METRICS:
        row.target_qty = int(value)
        row.target_amount = Decimal("0")
    else:
        row.target_amount = Decimal(str(value))
        row.target_qty = 0


def _get_rows(
    session: Session,
    *,
    owner: str,
    kind: str,
    key: str,
) -> dict[str, CrmSalesGoalPeriodRow]:
    rows = session.scalars(
        select(CrmSalesGoalPeriodRow).where(
            CrmSalesGoalPeriodRow.owner_sales == owner,
            CrmSalesGoalPeriodRow.period_kind == kind,
            CrmSalesGoalPeriodRow.period_key == key,
        )
    ).all()
    return {r.metric: r for r in rows}


def _upsert_metric_rows(
    session: Session,
    *,
    owner: str,
    dept: str,
    kind: str,
    key: str,
    targets: dict[str, int | Decimal | str],
    actor: str,
) -> None:
    existing = _get_rows(session, owner=owner, kind=kind, key=key)
    now = _now()
    for metric in GOAL_PERIOD_METRICS:
        raw = targets.get(metric, 0)
        row = existing.get(metric)
        if row is None:
            row = CrmSalesGoalPeriodRow(
                owner_sales=owner,
                owner_dept=dept,
                period_kind=kind,
                period_key=key,
                metric=metric,
                created_by=actor,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        if metric in QTY_METRICS:
            _set_row_target(row, int(raw))
        else:
            _set_row_target(row, Decimal(str(raw)))
        row.owner_dept = dept
        row.updated_at = now
        if not row.created_by:
            row.created_by = actor
    session.flush()


def done_for_owner(session: Session, owner: str, *, start: date, end: date) -> dict[str, Decimal | int]:
    visits = session.scalars(
        select(CrmVisitRow).where(
            CrmVisitRow.owner_sales == owner,
            CrmVisitRow.status == "CONFIRMED",
            CrmVisitRow.is_valid.is_(True),
        )
    ).all()
    new_cust = 0
    visit_n = 0
    for v in visits:
        if v.confirmed_at is None:
            continue
        d = v.confirmed_at.date()
        if not (start <= d <= end):
            continue
        visit_n += 1
        if v.created_customer:
            new_cust += 1
    for fv in session.scalars(
        select(CrmFieldVisitRow).where(
            CrmFieldVisitRow.owner_sales == owner,
            CrmFieldVisitRow.status == "已确认",
        )
    ).all():
        if fv.check_out_at is None:
            continue
        d = fv.check_out_at.date()
        if start <= d <= end:
            visit_n += 1

    contracts = session.scalars(
        select(CrmContractRow).where(
            CrmContractRow.owner_sales == owner,
            CrmContractRow.status == "ACTIVE",
            CrmContractRow.signed_date.is_not(None),
        )
    ).all()
    signed = Decimal("0")
    contract_nos: set[str] = set()
    for c in contracts:
        assert c.signed_date is not None
        if start <= c.signed_date <= end:
            signed += Decimal(str(c.contract_amount))
            contract_nos.add(c.contract_no)

    receipts = session.scalars(select(CrmPaymentReceiptRow)).all()
    paid = Decimal("0")
    for r in receipts:
        if r.receipt_date < start or r.receipt_date > end:
            continue
        contract = session.get(CrmContractRow, r.contract_no)
        if contract is None or contract.owner_sales != owner:
            continue
        paid += Decimal(str(r.amount))

    return {
        "新增客户数": new_cust,
        "拜访量": visit_n,
        "签约金额": signed,
        "回款金额": paid,
    }


def _period_range(kind: str, key: str) -> tuple[date, date]:
    if kind == "YEAR":
        y = int(key)
        return date(y, 1, 1), date(y, 12, 31)
    if kind == "MONTH":
        y, m = map(int, key.split("-"))
        import calendar

        last = calendar.monthrange(y, m)[1]
        return date(y, m, 1), date(y, m, last)
    if kind == "WEEK":
        y = int(key[:4])
        m = int(key[5:7])
        w = int(key.split("-W")[1])
        return week_date_range(y, m, w)
    raise ValueError(f"unknown period {kind}/{key}")


def metrics_payload(
    session: Session,
    owner: str,
    *,
    kind: str,
    key: str,
) -> dict[str, dict]:
    rows = _get_rows(session, owner=owner, kind=kind, key=key)
    start, end = _period_range(kind, key)
    done = done_for_owner(session, owner, start=start, end=end)
    out: dict[str, dict] = {}
    for metric in GOAL_PERIOD_METRICS:
        row = rows.get(metric)
        if metric in QTY_METRICS:
            target = int(row.target_qty) if row else 0
            finished = int(done[metric])
            out[metric] = {
                "target": target,
                "done": finished,
                "gap": target - finished,
                "kind": "qty",
            }
        else:
            target = Decimal(str(row.target_amount)) if row else Decimal("0")
            finished = Decimal(str(done[metric]))
            out[metric] = {
                "target": str(target.quantize(Decimal("0.01"))),
                "done": str(finished.quantize(Decimal("0.01"))),
                "gap": str((target - finished).quantize(Decimal("0.01"))),
                "kind": "amount",
            }
    return out


def goal_lines_for_period(
    session: Session,
    owner: str,
    *,
    kind: str,
    key: str,
) -> list[dict]:
    payload = metrics_payload(session, owner, kind=kind, key=key)
    lines = []
    for metric in GOAL_PERIOD_METRICS:
        m = payload[metric]
        if m["kind"] == "qty":
            lines.append(
                {
                    "metric": metric,
                    "target": m["target"],
                    "done": m["done"],
                    "gap": m["gap"],
                }
            )
        else:
            target = float(m["target"])
            done = float(m["done"])
            lines.append(
                {
                    "metric": metric,
                    "target": target,
                    "done": done,
                    "gap": target - done,
                    "display_target": m["target"],
                    "display_done": m["done"],
                    "is_amount": True,
                }
            )
    return lines


def mobile_goal_blocks(session: Session, owner: str, today: date) -> dict:
    y = year_key(today.year)
    m = month_key(today.year, today.month)
    w = week_key(today.year, today.month, week_index(today.day))
    return {
        "year": {"period_key": y, "label": period_label("YEAR", y), "lines": goal_lines_for_period(session, owner, kind="YEAR", key=y)},
        "month": {"period_key": m, "label": period_label("MONTH", m), "lines": goal_lines_for_period(session, owner, kind="MONTH", key=m)},
        "week": {"period_key": w, "label": period_label("WEEK", w), "lines": goal_lines_for_period(session, owner, kind="WEEK", key=w)},
    }


def _sum_children(
    session: Session,
    owner: str,
    *,
    parent_kind: str,
    parent_key: str,
    child_kind: str,
    child_keys: Iterable[str],
) -> dict[str, int | Decimal]:
    totals: dict[str, int | Decimal] = {}
    for metric in GOAL_PERIOD_METRICS:
        totals[metric] = 0 if metric in QTY_METRICS else Decimal("0")
    for ck in child_keys:
        rows = _get_rows(session, owner=owner, kind=child_kind, key=ck)
        for metric in GOAL_PERIOD_METRICS:
            row = rows.get(metric)
            if row is None:
                continue
            if metric in QTY_METRICS:
                totals[metric] = int(totals[metric]) + int(row.target_qty)  # type: ignore[arg-type]
            else:
                totals[metric] = Decimal(totals[metric]) + Decimal(str(row.target_amount))  # type: ignore[arg-type]
    return totals


def validate_children_sum(
    session: Session,
    owner: str,
    *,
    parent_kind: str,
    parent_key: str,
    child_kind: str,
    child_keys: list[str],
) -> list[str]:
    parent_rows = _get_rows(session, owner=owner, kind=parent_kind, key=parent_key)
    if not parent_rows:
        return []
    totals = _sum_children(session, owner, parent_kind=parent_kind, parent_key=parent_key, child_kind=child_kind, child_keys=child_keys)
    errors: list[str] = []
    for metric in GOAL_PERIOD_METRICS:
        row = parent_rows.get(metric)
        if row is None:
            continue
        if metric in QTY_METRICS:
            if int(row.target_qty) != int(totals[metric]):
                errors.append(f"{metric} 下级合计 {totals[metric]} ≠ 上级 {row.target_qty}")
        else:
            p = Decimal(str(row.target_amount)).quantize(Decimal("0.01"))
            c = Decimal(str(totals[metric])).quantize(Decimal("0.01"))
            if p != c:
                errors.append(f"{metric} 下级合计 {c} ≠ 上级 {p}")
    return errors


def split_year_to_months(session: Session, *, owner: str, year: int, actor: str) -> None:
    yk = year_key(year)
    parent = _get_rows(session, owner=owner, kind="YEAR", key=yk)
    if not parent:
        raise ValueError("请先保存年目标")
    dept = next(iter(parent.values())).owner_dept if parent else "销售部"
    for month in range(1, 13):
        mk = month_key(year, month)
        targets: dict[str, int | Decimal] = {}
        for metric in GOAL_PERIOD_METRICS:
            row = parent.get(metric)
            total = _row_target(row) if row else (0 if metric in QTY_METRICS else Decimal("0"))
            parts = split_int(int(total), 12) if metric in QTY_METRICS else split_amount(Decimal(str(total)), 12)
            targets[metric] = parts[month - 1]
        _upsert_metric_rows(session, owner=owner, dept=dept, kind="MONTH", key=mk, targets=targets, actor=actor)
        split_month_to_weeks(session, owner=owner, year=year, month=month, actor=actor, from_year_split=True)


def split_month_to_weeks(
    session: Session,
    *,
    owner: str,
    year: int,
    month: int,
    actor: str,
    from_year_split: bool = False,
) -> None:
    mk = month_key(year, month)
    parent = _get_rows(session, owner=owner, kind="MONTH", key=mk)
    if not parent:
        if from_year_split:
            return
        raise ValueError("请先保存月目标")
    dept = next(iter(parent.values())).owner_dept
    week_ids = weeks_in_month(year, month)
    for wi, w in enumerate(week_ids):
        wk = week_key(year, month, w)
        targets: dict[str, int | Decimal] = {}
        for metric in GOAL_PERIOD_METRICS:
            row = parent.get(metric)
            total = _row_target(row) if row else (0 if metric in QTY_METRICS else Decimal("0"))
            parts = split_int(int(total), len(week_ids)) if metric in QTY_METRICS else split_amount(Decimal(str(total)), len(week_ids))
            targets[metric] = parts[wi]
        _upsert_metric_rows(session, owner=owner, dept=dept, kind="WEEK", key=wk, targets=targets, actor=actor)


def save_period_targets(
    session: Session,
    *,
    owner: str,
    dept: str,
    kind: str,
    key: str,
    targets: dict[str, int | Decimal | str],
    actor: str,
) -> None:
    _upsert_metric_rows(session, owner=owner, dept=dept, kind=kind, key=key, targets=targets, actor=actor)

    def _any_child(child_kind: str, keys: list[str]) -> bool:
        return any(_get_rows(session, owner=owner, kind=child_kind, key=ck) for ck in keys)

    if kind == "MONTH":
        y, m = map(int, key.split("-"))
        child_keys = [week_key(y, m, w) for w in weeks_in_month(y, m)]
        if _any_child("WEEK", child_keys):
            errs = validate_children_sum(
                session, owner, parent_kind="MONTH", parent_key=key, child_kind="WEEK", child_keys=child_keys
            )
            if errs:
                raise ValueError("；".join(errs))
    if kind == "YEAR":
        child_keys = [month_key(int(key), m) for m in range(1, 13)]
        if _any_child("MONTH", child_keys):
            errs = validate_children_sum(
                session, owner, parent_kind="YEAR", parent_key=key, child_kind="MONTH", child_keys=child_keys
            )
            if errs:
                raise ValueError("；".join(errs))


def list_goal_owner_candidates(session: Session) -> list[str]:
    owners: set[str] = set(
        session.scalars(select(CrmSalesGoalPeriodRow.owner_sales).distinct()).all()
    )
    visit_owners = session.scalars(select(CrmVisitRow.owner_sales).distinct()).all()
    owners.update(visit_owners)
    owners.add("李业务")
    return sorted(o for o in owners if o)


def save_year_and_split(
    session: Session,
    *,
    owner: str,
    dept: str,
    year: int,
    targets: dict[str, int | Decimal | str],
    actor: str,
    auto_split: bool = True,
) -> None:
    yk = year_key(year)
    save_period_targets(session, owner=owner, dept=dept, kind="YEAR", key=yk, targets=targets, actor=actor)
    if auto_split:
        split_year_to_months(session, owner=owner, year=year, actor=actor)
        reapply_demo_week_bump(session, owner=owner, year=year)


def delete_year_goal(session: Session, *, owner: str, year: int) -> None:
    yk = year_key(year)
    session.execute(
        delete(CrmSalesGoalPeriodRow).where(
            CrmSalesGoalPeriodRow.owner_sales == owner,
            CrmSalesGoalPeriodRow.period_key.like(f"{yk}%"),
        )
    )
    session.execute(
        delete(CrmSalesGoalPeriodRow).where(
            CrmSalesGoalPeriodRow.owner_sales == owner,
            CrmSalesGoalPeriodRow.period_kind == "YEAR",
            CrmSalesGoalPeriodRow.period_key == yk,
        )
    )


def list_goal_tree(
    session: Session,
    *,
    year: int,
    month_from: int | None,
    month_to: int | None,
    owner_sales: str | None,
    owner_dept: str | None,
    role: str,
    actor: str,
) -> list[dict]:
    q = select(CrmSalesGoalPeriodRow.period_kind, CrmSalesGoalPeriodRow.period_key, CrmSalesGoalPeriodRow.owner_sales).where(
        CrmSalesGoalPeriodRow.period_kind == "YEAR",
        CrmSalesGoalPeriodRow.period_key == year_key(year),
    )
    if owner_sales:
        q = q.where(CrmSalesGoalPeriodRow.owner_sales == owner_sales)
    if owner_dept:
        q = q.where(CrmSalesGoalPeriodRow.owner_dept == owner_dept)
    pairs = session.execute(q.distinct()).all()
    trees: list[dict] = []
    yk = year_key(year)
    mf = month_from or 1
    mt = month_to or 12
    for kind, key, owner in pairs:
        if role == "SALES" and owner != actor:
            continue
        if role not in ("GM", "SALES_MGR", "FIN") and owner != actor:
            continue
        sample = _get_rows(session, owner=owner, kind="YEAR", key=yk)
        dept = next(iter(sample.values())).owner_dept if sample else "销售部"
        year_node = {
            "owner_sales": owner,
            "owner_dept": dept,
            "period_kind": "YEAR",
            "period_key": yk,
            "period_label": period_label("YEAR", yk),
            "metrics": metrics_payload(session, owner, kind="YEAR", key=yk),
            "months": [],
        }
        for month in range(1, 13):
            if month < mf or month > mt:
                continue
            mk = month_key(year, month)
            month_node = {
                "period_kind": "MONTH",
                "period_key": mk,
                "period_label": period_label("MONTH", mk),
                "metrics": metrics_payload(session, owner, kind="MONTH", key=mk),
                "weeks": [],
            }
            for w in weeks_in_month(year, month):
                wk = week_key(year, month, w)
                month_node["weeks"].append(
                    {
                        "period_kind": "WEEK",
                        "period_key": wk,
                        "period_label": period_label("WEEK", wk),
                        "metrics": metrics_payload(session, owner, kind="WEEK", key=wk),
                    }
                )
            year_node["months"].append(month_node)
        trees.append(year_node)
    return trees


def reapply_demo_week_bump(session: Session, *, owner: str, year: int) -> None:
    """演示：9 月第 3 周拜访量略高于完成数，便于移动端展示「还差」。"""
    if owner != "李业务" or year != 2026:
        return
    wk = week_key(2026, 9, 3)
    bump = _get_rows(session, owner=owner, kind="WEEK", key=wk)
    if bump.get("拜访量"):
        bump["拜访量"].target_qty = 20
    session.flush()


def ensure_demo_goal_period(session: Session) -> None:
    from db.tables import AppSettingRow

    row = session.get(AppSettingRow, PERIOD_PACK_KEY)
    if row is not None and row.value == PERIOD_PACK_VERSION:
        return
    delete_year_goal(session, owner="李业务", year=2026)
    targets = {
        "新增客户数": 48,
        "拜访量": 144,
        "签约金额": Decimal("360000.00"),
        "回款金额": Decimal("240000.00"),
    }
    _upsert_metric_rows(
        session,
        owner="李业务",
        dept="销售部",
        kind="YEAR",
        key="2026",
        targets=targets,
        actor="销管",
    )
    session.flush()
    split_year_to_months(session, owner="李业务", year=2026, actor="销管")
    wk = week_key(2026, 9, 3)
    bump = _get_rows(session, owner="李业务", kind="WEEK", key=wk)
    if bump.get("拜访量"):
        # 演示日落在第 3 周；完成数含历史测试写入的拜访，目标略高于当周完成数以展示「还差」
        bump["拜访量"].target_qty = 20
    if row is None:
        session.add(AppSettingRow(key=PERIOD_PACK_KEY, value=PERIOD_PACK_VERSION))
    else:
        row.value = PERIOD_PACK_VERSION
    session.flush()
