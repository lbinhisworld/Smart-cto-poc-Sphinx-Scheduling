"""演示登录与角色（非生产 SSO）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoleCode = Literal["GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN", "HR", "TEAM_LEADER", "QC"]


@dataclass(frozen=True)
class DemoUser:
    code: RoleCode
    label: str
    name: str
    home_path: str


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser("GM", "总经理", "张总", "/portal"),
    DemoUser("SALES_MGR", "销售总监", "王经理", "/portal"),
    DemoUser("SALES", "业务员", "李业务", "/portal"),
    DemoUser("PMC", "生管/PMC", "陈生管", "/schedule"),
    DemoUser("WH", "仓库", "刘仓库", "/orders"),
    DemoUser("FIN", "财务总监", "李财务", "/portal"),
    DemoUser("HR", "人事", "周人事", "/portal"),
    DemoUser("TEAM_LEADER", "班组长", "王强", "/modules/production/time-report"),
    DemoUser("QC", "品控专员", "赵品控", "/qc/receipts"),
)

_ALL_PORTAL = frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN", "HR", "QC"})


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
    MenuItem("cockpit", "管理驾驶舱", "/cockpit", frozenset({"GM", "FIN"}), "M0"),
    MenuItem("crm_customers", "客户档案", "/crm/customers", frozenset({"GM", "SALES_MGR", "SALES"}), "M2"),
    MenuItem("crm_opportunities", "商机列表", "/crm/opportunities", frozenset({"GM", "SALES_MGR", "SALES"}), "M2"),
    MenuItem("crm_samples", "样品流程", "/crm/samples", frozenset({"GM", "SALES_MGR", "SALES"}), "M2"),
    MenuItem("crm_reports", "销售报表", "/crm/reports", frozenset({"GM", "SALES_MGR"}), "M2"),
    MenuItem("ctp", "交期试算 CTP", "/crm/ctp", frozenset({"GM", "SALES_MGR", "SALES"}), "M2"),
    MenuItem("changes", "订单变更", "/changes", frozenset({"GM", "SALES_MGR", "SALES", "PMC"}), "M3"),
    MenuItem("orders", "销售订单", "/orders", frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN"}), "M3"),
    MenuItem("kingdee", "金蝶同步", "/kingdee", frozenset({"GM", "PMC", "WH"}), "M3"),
    MenuItem("schedule", "生产排程", "/schedule", frozenset({"GM", "PMC"}), "M8"),
    MenuItem("stock", "库存中心", "/stock", frozenset({"GM", "PMC", "WH"}), "M4"),
    MenuItem("bom", "BOM 工艺", "/bom", frozenset({"GM", "PMC"}), "M4"),
    MenuItem("hr_roster", "花名册", "/modules/hr/roster", frozenset({"GM", "HR"}), "M1"),
    MenuItem("hr_attendance", "考勤管理", "/modules/hr/attendance", frozenset({"GM", "HR"}), "M1"),
    MenuItem("hr_labor_cost", "生产成本", "/modules/hr/labor-cost", frozenset({"GM", "HR", "FIN", "PMC"}), "M1"),
    MenuItem("labor_time_report", "组×日报工", "/modules/production/time-report", frozenset({"GM", "PMC", "TEAM_LEADER"}), "M5"),
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
