"""演示登录与角色（非生产 SSO）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoleCode = Literal["GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN", "HR"]


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
)


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    path: str
    roles: frozenset[RoleCode]
    module: str


MENU: tuple[MenuItem, ...] = (
    MenuItem("portal", "首页", "/portal", frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN", "HR"}), "M0"),
    MenuItem("orders", "销售订单", "/orders", frozenset({"GM", "SALES_MGR", "SALES", "PMC", "WH", "FIN"}), "M3"),
    MenuItem("kingdee", "金蝶同步", "/kingdee", frozenset({"GM", "PMC", "WH"}), "M3"),
    MenuItem("schedule", "生产排程", "/schedule", frozenset({"GM", "PMC"}), "M8"),
    MenuItem("stock", "库存中心", "/stock", frozenset({"GM", "PMC", "WH"}), "M4"),
    MenuItem("bom", "BOM 工艺", "/bom", frozenset({"GM", "PMC"}), "M4"),
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
