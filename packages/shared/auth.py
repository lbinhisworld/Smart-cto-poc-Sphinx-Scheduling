"""演示登录与角色（非生产 SSO）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoleCode = Literal[
    "GM",
    "SALES_MGR",
    "SALES",
    "SALES_ASSIST",
    "RD",
    "PMC",
    "WH",
    "FIN",
    "HR",
    "TEAM_LEADER",
    "QC",
]


@dataclass(frozen=True)
class DemoUser:
    code: RoleCode
    label: str
    name: str
    home_path: str


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser("GM", "总经理", "张总", "/portal"),
    DemoUser("SALES_MGR", "销售总监", "王经理", "/portal"),
    DemoUser("SALES", "业务员", "李业务", "/crm/visit"),
    DemoUser("SALES_ASSIST", "业务助理", "周助理", "/crm/visit"),
    DemoUser("RD", "研发", "周研发", "/crm/opportunities"),
    DemoUser("PMC", "生管/PMC", "陈生管", "/schedule"),
    DemoUser("WH", "仓库", "刘仓库", "/orders"),
    DemoUser("FIN", "财务总监", "李财务", "/portal"),
    DemoUser("HR", "人事", "周人事", "/portal"),
    DemoUser("TEAM_LEADER", "班组长", "王强", "/modules/production/time-report"),
    DemoUser("QC", "品控专员", "赵品控", "/qc/receipts"),
)

_ALL_PORTAL = frozenset(
    {"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "RD", "PMC", "WH", "FIN", "HR", "QC"}
)


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    path: str
    roles: frozenset[RoleCode]
    module: str


MENU: tuple[MenuItem, ...] = (
    MenuItem("portal", "首页", "/portal", _ALL_PORTAL, "M0"),
    MenuItem("todos", "待办中心", "/todos", _ALL_PORTAL, "M0"),
    MenuItem("demo", "演示控制台", "/demo", frozenset({"GM", "SALES_MGR", "PMC"}), "M0"),
    MenuItem("kb", "封印本体", "/kb", frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN", "HR", "TEAM_LEADER", "QC"}), "M0"),
    MenuItem("cockpit", "管理驾驶舱", "/cockpit", frozenset({"GM", "FIN"}), "M0"),
    MenuItem("settings", "系统配置", "/settings", frozenset({"GM"}), "M0"),
    MenuItem(
        "crm_visit",
        "销售移动端",
        "/crm/visit",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem("crm_goals", "目标管理", "/crm/goals", frozenset({"GM", "SALES_MGR"}), "M2"),
    MenuItem(
        "crm_my_leads",
        "我的线索",
        "/crm/leads/mine",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem("crm_lead_pool", "线索池", "/crm/leads/pool", frozenset({"GM", "SALES_MGR"}), "M2"),
    MenuItem("crm_lead_rules", "线索池规则", "/crm/leads/rules", frozenset({"GM", "SALES_MGR"}), "M2"),
    MenuItem(
        "crm_lead_report",
        "销售线索报表",
        "/crm/leads/report",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem("crm_sea", "公海池", "/crm/sea", frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}), "M2"),
    MenuItem(
        "crm_customers",
        "我的客户",
        "/crm/customers",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem(
        "crm_opps_list",
        "商机",
        "/crm/opportunities-list",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem(
        "crm_follows",
        "跟进记录",
        "/crm/follows",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem(
        "crm_checkin",
        "拜访签到",
        "/crm/checkin",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem(
        "crm_contacts",
        "联系人",
        "/crm/contacts",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST"}),
        "M2",
    ),
    MenuItem(
        "crm_opportunities",
        "商机大盘",
        "/crm/opportunities",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "FIN", "RD"}),
        "M2",
    ),
    MenuItem(
        "crm_samples",
        "打样",
        "/crm/samples",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "RD", "FIN"}),
        "M2",
    ),
    MenuItem("crm_reports", "销售报表", "/crm/reports", frozenset({"GM", "SALES_MGR"}), "M2"),
    MenuItem("ctp", "交期试算 CTP", "/crm/ctp", frozenset({"GM", "SALES_MGR", "SALES"}), "M2"),
    MenuItem("changes", "订单变更", "/changes", frozenset({"GM", "SALES_MGR", "SALES", "PMC"}), "M3"),
    MenuItem("orders", "销售订单", "/orders", frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN"}), "M3"),
    MenuItem(
        "crm_payments",
        "回款计划",
        "/crm/payments",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "FIN"}),
        "M3",
    ),
    MenuItem(
        "crm_progress",
        "签约产品生产进度",
        "/crm/progress",
        frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "FIN"}),
        "M3",
    ),
    MenuItem("crm_returns", "销售退货", "/crm/returns", frozenset({"GM", "SALES_MGR"}), "M3"),
    MenuItem("crm_ship", "销售出库", "/crm/shipments", frozenset({"GM", "SALES_MGR"}), "M3"),
    MenuItem("crm_recon", "销售对账", "/crm/reconcile", frozenset({"GM", "SALES_MGR", "FIN"}), "M3"),
    MenuItem("quotes", "报价", "/orders/quotes", frozenset({"GM", "SALES_MGR", "SALES", "SALES_ASSIST", "FIN"}), "M3"),
    MenuItem("kingdee", "金蝶同步", "/kingdee", frozenset({"GM", "PMC", "WH"}), "M3"),
    MenuItem("schedule", "生产排程", "/schedule", frozenset({"GM", "PMC"}), "M8"),
    MenuItem("stock", "库存中心", "/stock", frozenset({"GM", "PMC", "WH"}), "M4"),
    MenuItem("bom", "BOM 工艺", "/bom", frozenset({"GM", "PMC"}), "M4"),
    MenuItem("hr_roster", "花名册", "/modules/hr/roster", frozenset({"GM", "HR"}), "M1"),
    MenuItem("hr_attendance", "考勤管理", "/modules/hr/attendance", frozenset({"GM", "HR"}), "M1"),
    MenuItem("hr_labor_cost", "生产成本", "/modules/hr/labor-cost", frozenset({"GM", "HR", "FIN", "PMC"}), "M1"),
    MenuItem("labor_time_report", "组×日报工", "/modules/production/time-report", frozenset({"GM", "PMC", "TEAM_LEADER"}), "M5"),
    MenuItem("dept1_stats", "一部产能统计", "/modules/production/stats/dept1", frozenset({"GM", "PMC", "TEAM_LEADER", "FIN", "HR", "WH"}), "M5"),
    MenuItem("production", "生产运营", "/modules/production", frozenset({"GM", "PMC"}), "M5"),
    MenuItem("finance", "财务摘要", "/modules/finance", frozenset({"GM", "FIN"}), "M6"),
    MenuItem("project", "项目交付", "/modules/project", frozenset({"GM"}), "M7"),
    MenuItem("qc_receipts", "原辅料来料", "/qc/receipts", frozenset({"GM", "QC", "WH"}), "M9"),
    MenuItem("qc_exceptions", "原辅料异常", "/qc/exceptions", frozenset({"GM", "QC", "WH"}), "M9"),
    MenuItem("qc_daily_defects", "每日异常", "/qc/daily-defects", frozenset({"GM", "QC", "PMC"}), "M9"),
    MenuItem("qc_complaints", "客诉登记", "/qc/complaints", frozenset({"GM", "QC", "SALES", "SALES_MGR"}), "M9"),
    MenuItem("qc_audits", "二方三方审核", "/qc/audits", frozenset({"GM", "QC"}), "M9"),
    MenuItem("qc_lab_external", "外来测试", "/qc/lab-external", frozenset({"GM", "QC"}), "M9"),
    MenuItem("qc_swab_tests", "涂抹检测", "/qc/swab-tests", frozenset({"GM", "QC"}), "M9"),
    MenuItem("qc_product_tests", "产品检测", "/qc/product-tests", frozenset({"GM", "QC"}), "M9"),
    MenuItem("qc_master", "品控主数据", "/qc/master", frozenset({"GM", "QC", "WH"}), "M9"),
)


def menu_for_role(role: RoleCode) -> list[dict]:
    return [
        {"key": m.key, "label": m.label, "path": m.path, "module": m.module}
        for m in MENU
        if role in m.roles
    ]


def user_for_role(role: str) -> DemoUser | None:
    for u in DEMO_USERS:
        if u.code == role:
            return u
    return None


def decode_demo_user_header(value: str | None) -> str | None:
    """X-Demo-User：纯 ASCII 或 ``b64:`` + UTF-8（浏览器 fetch 头限制）。"""
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if v.startswith("b64:"):
        import base64

        return base64.b64decode(v[4:], validate=True).decode("utf-8")
    return v


def resolve_demo_actor(role: str, x_demo_user: str | None) -> str:
    decoded = decode_demo_user_header(x_demo_user)
    if decoded:
        return decoded
    user = user_for_role(role)
    return user.name if user else ""
