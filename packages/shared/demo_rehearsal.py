"""九幕演示剧本（Phase 8 · 联调）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RehearsalAct:
    act: int
    title: str
    module: str
    role: str
    path: str
    steps: tuple[str, ...]
    note: str = ""


REHEARSAL_ACTS: tuple[RehearsalAct, ...] = (
    RehearsalAct(
        1,
        "现状对照 · 为什么上系统",
        "M0",
        "GM",
        "/cockpit",
        (
            "打开管理驾驶舱，说明 Excel 一表三用 20 Sheet 痛点",
            "点 M1–M7 摘要，强调不是配置平台而是流程分工对齐",
        ),
        "断网可演示；真企微/迁移不在本期",
    ),
    RehearsalAct(
        2,
        "工艺主数据 · BOM 与 SPH",
        "M4",
        "PMC",
        "/bom",
        ("选 P2，看扇入工艺与数量展开", "说明版/盒换算与半成品依赖"),
    ),
    RehearsalAct(
        3,
        "金蝶 Push 进单",
        "M3",
        "PMC",
        "/kingdee",
        ("模拟推送 demo_p2", "到订单中心确认齐套率、来源 KINGDEE"),
    ),
    RehearsalAct(
        4,
        "齐套 · 库存 · 待排产池",
        "M4",
        "PMC",
        "/orders",
        ("勾选订单批量加入排产池", "库存中心可看占库与 ERP 模拟同步"),
    ),
    RehearsalAct(
        5,
        "销售 CTP · CRM 漏斗",
        "M2",
        "SALES",
        "/crm/ctp",
        ("任选品项/数量试算 feasible/冲突", "漏斗报表证明种子非 0"),
    ),
    RehearsalAct(
        6,
        "一键倒排 · 看板 · 导出派工",
        "M8",
        "PMC",
        "/schedule",
        (
            "（可选）先打开 /demo/story/schedule 讲倒排与冲突",
            "整池一键倒排",
            "拖拽/试排 Sandbox",
            "导出派工单 Excel",
        ),
    ),
    RehearsalAct(
        7,
        "订单变更 · 影响清单 · 企微模拟",
        "M3",
        "SALES→PMC",
        "/changes",
        ("销售提交 SO-002 改交期", "PMC 看影响清单后批准", "顶栏企微铃铛 S1/S3"),
    ),
    RehearsalAct(
        8,
        "插单 · 四策略 diff",
        "M8",
        "PMC",
        "/schedule",
        ("订单池 SO-004/SO-005 紧急单", "插单试排对比策略后应用"),
    ),
    RehearsalAct(
        9,
        "管理闭环 · 验收口径",
        "M0",
        "GM",
        "/cockpit",
        ("回顾 G1–G5 与 BR-27 交期锚", "POC 范围说明：五类明确不交付"),
    ),
    RehearsalAct(
        10,
        "班组长报工 · 人事生产成本",
        "M1b",
        "TEAM_LEADER→HR",
        "/modules/production/time-report",
        (
            "（可选）先打开 /demo/story/cost 讲人·时与 ¥1152 算例",
            "班组长王强确认本组昨日实际人·时",
            "人事打开生产成本页看部门-组计划 vs 实际差异",
        ),
        "非薪酬发薪；组×日粒度",
    ),
)


def acts_for_api() -> list[dict]:
    return [
        {
            "act": a.act,
            "title": a.title,
            "module": a.module,
            "role": a.role,
            "path": a.path,
            "steps": list(a.steps),
            "note": a.note,
        }
        for a in REHEARSAL_ACTS
    ]
