"""组×日 / 单任务详情指标（墙钟、产能利用率、人·时利用率）。"""

from datetime import date
from decimal import Decimal

from engine.cell_detail import build_cell_detail
from engine.models import Dept, GroupCode
from tests.helpers import tasks_of


def test_cell_detail_orders_and_cell_metrics(input_builder, schedule_input):
    result = __import__("engine.schedule", fromlist=["schedule"]).schedule(
        input_builder(None)
    )
    p1_tasks = tasks_of(result, "P1")
    assert p1_tasks
    task_date, qty = p1_tasks[0]
    detail = build_cell_detail(
        schedule_input,
        result,
        dept=Dept.FINISHED_DEPT,
        group_code=GroupCode.MANUAL,
        task_date=task_date,
        orders_by_no={o.order_no: o for o in schedule_input.orders},
        focus_task_id=None,
    )
    assert detail["dept"] == "FINISHED_DEPT"
    assert detail["group_code"] == "MANUAL"
    assert detail["task_date"] == task_date.isoformat()
    assert len(detail["tasks"]) >= 1
    assert Decimal(detail["cell_metrics"]["wall_clock_hours"]) > 0
    assert "capacity_utilization" in detail["cell_metrics"]
    assert "labor_utilization" in detail["cell_metrics"]
    assert Decimal(detail["cell_metrics"]["available_wall_hours"]) == Decimal("8")


def test_cell_detail_focus_task(input_builder, schedule_input):
    from engine.schedule import schedule

    result = schedule(input_builder(None))
    task = next(
        t
        for t in result.tasks
        if t.group_code == GroupCode.MANUAL and t.dept == Dept.FINISHED_DEPT
    )
    detail = build_cell_detail(
        schedule_input,
        result,
        dept=task.dept,
        group_code=GroupCode.MANUAL,
        task_date=task.task_date,
        orders_by_no={o.order_no: o for o in schedule_input.orders},
        focus_task_id=task.task_id,
    )
    assert detail["focus_task_id"] == task.task_id
    assert detail["task_metrics"] is not None
    assert detail["task_metrics"]["wall_clock_hours"] == str(task.hours_wall)
    assert len(detail["orders"]) >= 1
    assert detail["orders"][0]["order_no"]
