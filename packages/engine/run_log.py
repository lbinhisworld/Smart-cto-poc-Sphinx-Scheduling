"""排程运行日志（纯函数）：算法说明 + 当次输入/trace/结果，供验收或送大模型。"""

from __future__ import annotations

from engine.models import ConflictLv, ScheduleInput, ScheduleResult, WoType

ALGORITHM_CARD: dict = {
    "name": "斯芬克斯 JIT 倒排",
    "version": "2026-09-15-v1",
    "summary": (
        "从交期当天往回填组×天空位；默认晚交期工单先占格；"
        "先排成品再展开半成品；冲突只提示不改客户交期。"
    ),
    "rules": [
        "BR-20：倒排起点 cursor = due_date，交期当天可排产",
        "BR-21：早于 earliest_start 仍有余量 → 未安置 E1",
        "BR-22：非工作日跳过，再往前一天",
        "BR-23/24：当日剩余产能>0 才落位，一次吃 min(余量, 剩余)",
        "BR-25：默认 sort_mode=DUE_DESC（交期降序）；插单/改单用 PIN_FIRST",
        "BR-27：禁止写回 so_order.due_date，交期只有人能改",
        "BR-32：半成品净需求 = 毛需求 − 库存；净=0 不生成半成品工单",
        "BR-33：半成品 due = 成品 plan_start − lead_time_days（自然日）",
        "BR-34：必须先排成品、再排半成品；成品一动半成品重建",
        "BR-40：禁止默认全量重排；插单走时间栅栏 + 涟漪抑制",
        "BR-47：物理不可行时给出最快可交期，禁止硬排做不到的计划",
        "BR-50：E1–E10 全部软约束，只提示不 raise 终止排产",
    ],
    "not_this": [
        "正排 / 双向排",
        "有限产能 APS 求解或优化库",
        "机台 / 工序 / 小时级排程",
        "系统自动改客户交期",
    ],
}

SCHEMA = "sphinx.schedule_run_log.v1"


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def render_llm_brief(log: dict) -> str:
    """把结构化日志压成可粘贴给大模型的 Markdown。"""
    run = log["run"]
    algo = log["algorithm"]
    lines = [
        f"# 排程运行 {run['run_id']}",
        "",
        f"用途：{log.get('purpose', '')}",
        f"记录时间：{run.get('recorded_at', '')}",
        f"触发：{run['trigger']} · 落库={run.get('persist')} · 计划版本={run.get('plan_version')}",
        f"基准日：{run['today']} · 策略：{run['sort_mode']} · 钉住：{run.get('pinned_wo_nos') or '无'}",
        "",
        f"## 算法（{algo['name']} {algo['version']}）",
        algo["summary"],
        "",
        "规则：",
    ]
    lines.extend(f"- {r}" for r in algo["rules"])
    lines.append("")
    lines.append("## 订单输入")
    for o in log["input"]["orders"]:
        lines.append(
            f"- {o['order_no']} 销售 {o.get('sales_name') or '未填'} · "
            f"{o['item_code']} {o['qty_order']}{o['unit']} · 交期 {o['due_date']} · "
            f"客户 {o.get('customer', '')}"
        )
    stock = log["input"].get("stock") or {}
    if stock:
        lines.append("")
        lines.append("## 库存快照（版）")
        lines.append(", ".join(f"{k}={v}" for k, v in stock.items()))
    lines.append("")
    lines.append("## 处理顺序（成品）")
    for e in log["trace"].get("events", []):
        if e.get("kind") == "queue_rank" and e.get("wo_type") == "FINISHED":
            lines.append(f"- {e.get('message')}")
    lines.append("")
    lines.append("## 落位 / 半成品（摘录）")
    for e in log["trace"].get("events", []):
        if e.get("kind") in {"place", "expand_semi", "semi_from_stock", "unplaced"}:
            lines.append(f"- [{e.get('act')}] {e.get('message')}")
    lines.append("")
    out = log["outcome"]
    lines.append("## 结果摘要")
    lines.append(
        f"成品工单 {out['finished_wo']} · 半成品工单 {out['semi_wo']} · "
        f"任务 {out['task_count']} · 未安置 {out['unplaced_count']}"
    )
    if out["conflicts"]:
        lines.append("")
        lines.append("## 冲突")
        for c in out["conflicts"]:
            lines.append(
                f"- {c['level']} {c['code']} {c.get('order_no') or ''}：{c['message']}"
            )
    else:
        lines.append("冲突：无")
    lines.append("")
    lines.append("## 请大模型")
    lines.append(log.get("llm_ask", ""))
    return "\n".join(lines) + "\n"


def build_schedule_run_log(
    inp: ScheduleInput,
    result: ScheduleResult,
    *,
    trigger: str,
    run_id: str,
    recorded_at: str,
    persist: bool,
    plan_version: int,
) -> dict:
    wo_by_no = {w.wo_no: w for w in result.wos}
    orders = [
        {
            "order_no": o.order_no,
            "customer": o.customer,
            "sales_name": o.sales_name,
            "item_code": o.item_code,
            "qty_order": str(o.qty_order),
            "unit": o.unit.value if hasattr(o.unit, "value") else str(o.unit),
            "due_date": _iso(o.due_date),
            "ready_date": _iso(o.ready_date),
            "customer_level": o.customer_level,
            "is_urgent": o.is_urgent,
            "schedule_phase": o.schedule_phase,
        }
        for o in inp.orders
    ]
    conflicts = []
    for c in result.conflicts:
        wo = wo_by_no.get(c.wo_no or "")
        conflicts.append(
            {
                "code": c.code,
                "level": c.level.value if isinstance(c.level, ConflictLv) else str(c.level),
                "message": c.message,
                "suggest": c.suggest,
                "wo_no": c.wo_no,
                "order_no": wo.source_order_no if wo else None,
                "sales_name": next(
                    (o.sales_name for o in inp.orders if wo and o.order_no == wo.source_order_no),
                    "",
                ),
            }
        )
    trace = (
        result.trace.model_dump(mode="json")
        if result.trace is not None
        else {"sort_mode": inp.config.sort_mode.value, "events": []}
    )
    log = {
        "schema": SCHEMA,
        "purpose": "供人审阅或送大模型诊断排产问题 / 做过程验收；不是二次排产输入。",
        "algorithm": ALGORITHM_CARD,
        "run": {
            "run_id": run_id,
            "recorded_at": recorded_at,
            "trigger": trigger,
            "persist": persist,
            "plan_version": plan_version,
            "today": _iso(inp.today),
            "sort_mode": inp.config.sort_mode.value,
            "pinned_wo_nos": list(inp.config.pinned_wo_nos),
            "fence_days": inp.config.fence_days,
            "reserved_ratio": str(inp.config.reserved_ratio),
            "kit_mode": inp.config.kit_mode.value
            if hasattr(inp.config.kit_mode, "value")
            else str(inp.config.kit_mode),
        },
        "input": {
            "orders": orders,
            "stock": {k: str(v) for k, v in inp.stock.items()},
        },
        "trace": trace,
        "outcome": {
            "finished_wo": sum(1 for w in result.wos if w.wo_type == WoType.FINISHED),
            "semi_wo": sum(1 for w in result.wos if w.wo_type == WoType.SEMI),
            "task_count": len(result.tasks),
            "unplaced_count": len(result.unplaced),
            "skipped": list(result.skipped),
            "wos": [
                {
                    "wo_no": w.wo_no,
                    "wo_type": w.wo_type.value,
                    "source_order_no": w.source_order_no,
                    "item_code": w.item_code,
                    "qty_board_plan": w.qty_board_plan,
                    "due_date": _iso(w.due_date),
                    "plan_start": _iso(w.plan_start),
                    "plan_end": _iso(w.plan_end),
                }
                for w in result.wos
            ],
            "unplaced": [
                {
                    "wo_no": u.wo_no,
                    "code": u.code,
                    "remaining": u.remaining,
                    "reason": u.reason,
                    "earliest_finish": _iso(u.earliest_finish),
                }
                for u in result.unplaced
            ],
            "conflicts": conflicts,
        },
        "llm_ask": (
            "请根据算法规则核对：1) 处理顺序是否符合 sort_mode；"
            "2) 落位是否从交期往回、有无硬排不可行计划；"
            "3) 半成品是否在成品之后、净需求是否扣库存；"
            "4) 红冲突是否只提示且给出最快可交期；"
            "5) 指出可疑步骤与建议给人看的验收结论（通过/有条件通过/不通过）。"
        ),
    }
    log["llm_brief"] = render_llm_brief(log)
    return log
